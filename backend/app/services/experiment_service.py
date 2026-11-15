import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from app.core.config import settings
from app.core.security import generate_invitation_token
from app.models import (
    Condition,
    Event,
    Experiment,
    ExperimentStatus,
    ExperimentVersion,
    Invitation,
    Task,
    User,
)
from app.schemas.experiment import (
    ConditionCreate,
    ConditionUpdate,
    ExperimentCreate,
    ExperimentUpdate,
    InvitationCreate,
    TaskCreate,
)


def get_experiment_for_owner(db: Session, experiment_id: uuid.UUID, owner: User) -> Experiment:
    stmt = (
        select(Experiment)
        .where(Experiment.id == experiment_id)
        .options(
            selectinload(Experiment.draft_conditions).selectinload(Condition.tasks),
            selectinload(Experiment.versions),
        )
    )
    experiment = db.scalar(stmt)
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment not found")
    if experiment.owner_id != owner.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this experiment",
        )
    return experiment


def list_experiments_for_owner(db: Session, owner: User) -> list[Experiment]:
    stmt = (
        select(Experiment)
        .where(Experiment.owner_id == owner.id)
        .order_by(Experiment.updated_at.desc())
    )
    return list(db.scalars(stmt).all())


def create_experiment(db: Session, owner: User, payload: ExperimentCreate) -> Experiment:
    experiment = Experiment(
        owner_id=owner.id,
        title=payload.title.strip(),
        description=payload.description.strip(),
        participant_information=payload.participant_information.strip(),
        consent_statement=payload.consent_statement.strip(),
        status=ExperimentStatus.DRAFT,
    )
    db.add(experiment)
    db.flush()
    db.add(
        Event(
            experiment_id=experiment.id,
            event_type="experiment_created",
            event_data_json={"title": experiment.title},
        )
    )
    db.commit()
    return get_experiment_for_owner(db, experiment.id, owner)


def update_experiment(
    db: Session, experiment: Experiment, payload: ExperimentUpdate
) -> Experiment:
    if experiment.status == ExperimentStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Archived experiments cannot be modified",
        )
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(experiment, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(experiment)
    return experiment


def get_draft_conditions(db: Session, experiment_id: uuid.UUID) -> list[Condition]:
    stmt = (
        select(Condition)
        .where(Condition.experiment_id == experiment_id, Condition.version_id.is_(None))
        .options(selectinload(Condition.tasks))
        .order_by(Condition.condition_order.asc())
    )
    return list(db.scalars(stmt).all())


def create_condition(
    db: Session, experiment: Experiment, payload: ConditionCreate
) -> Condition:
    if experiment.status == ExperimentStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot add conditions to an archived experiment",
        )
    condition = Condition(
        experiment_id=experiment.id,
        version_id=None,
        name=payload.name.strip(),
        description=payload.description.strip(),
        ai_answer_template=payload.ai_answer_template.strip(),
        ai_explanation_template=(
            payload.ai_explanation_template.strip()
            if payload.ai_explanation_template is not None
            else None
        ),
        condition_order=payload.condition_order,
    )
    db.add(condition)
    db.commit()
    db.refresh(condition)
    return condition


def update_condition(
    db: Session, experiment: Experiment, condition_id: uuid.UUID, payload: ConditionUpdate
) -> Condition:
    condition = db.scalar(
        select(Condition).where(
            Condition.id == condition_id,
            Condition.experiment_id == experiment.id,
            Condition.version_id.is_(None),
        )
    )
    if condition is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft condition not found")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(condition, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    db.refresh(condition)
    return condition


def create_task(db: Session, experiment: Experiment, payload: TaskCreate) -> Task:
    condition = db.scalar(
        select(Condition).where(
            Condition.id == payload.condition_id,
            Condition.experiment_id == experiment.id,
            Condition.version_id.is_(None),
        )
    )
    if condition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target draft condition not found in this experiment",
        )
    task = Task(
        condition_id=condition.id,
        title=payload.title.strip(),
        instructions=payload.instructions.strip(),
        scenario_prompt=payload.scenario_prompt.strip(),
        task_order=payload.task_order,
        task_type=payload.task_type,
        questions_json=[q.model_dump() for q in payload.questions_json],
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def publish_experiment(db: Session, experiment: Experiment) -> ExperimentVersion:
    if experiment.status not in (
        ExperimentStatus.DRAFT,
        ExperimentStatus.PUBLISHED,
        ExperimentStatus.PAUSED,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot publish an experiment in '{experiment.status.value}' state",
        )

    draft_conditions = get_draft_conditions(db, experiment.id)
    if len(draft_conditions) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least two experimental conditions are required before publishing",
        )
    for cond in draft_conditions:
        if len(cond.tasks) < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Condition '{cond.name}' must have at least one task before publishing",
            )

    max_ver = db.scalar(
        select(func.max(ExperimentVersion.version_number)).where(
            ExperimentVersion.experiment_id == experiment.id
        )
    )
    next_version_number = (max_ver or 0) + 1

    snapshot_payload = {
        "title": experiment.title,
        "description": experiment.description,
        "participant_information": experiment.participant_information,
        "consent_statement": experiment.consent_statement,
        "conditions": [
            {
                "name": cond.name,
                "description": cond.description,
                "ai_answer_template": cond.ai_answer_template,
                "ai_explanation_template": cond.ai_explanation_template,
                "condition_order": cond.condition_order,
                "tasks": [
                    {
                        "title": t.title,
                        "instructions": t.instructions,
                        "scenario_prompt": t.scenario_prompt,
                        "task_order": t.task_order,
                        "task_type": t.task_type.value,
                        "questions_json": t.questions_json,
                    }
                    for t in sorted(cond.tasks, key=lambda x: x.task_order)
                ],
            }
            for cond in sorted(draft_conditions, key=lambda x: x.condition_order)
        ],
    }

    version = ExperimentVersion(
        experiment_id=experiment.id,
        version_number=next_version_number,
        config_json=snapshot_payload,
    )
    db.add(version)
    db.flush()

    for cond in draft_conditions:
        frozen_cond = Condition(
            experiment_id=experiment.id,
            version_id=version.id,
            name=cond.name,
            description=cond.description,
            ai_answer_template=cond.ai_answer_template,
            ai_explanation_template=cond.ai_explanation_template,
            condition_order=cond.condition_order,
        )
        db.add(frozen_cond)
        db.flush()
        for t in cond.tasks:
            db.add(
                Task(
                    condition_id=frozen_cond.id,
                    title=t.title,
                    instructions=t.instructions,
                    scenario_prompt=t.scenario_prompt,
                    task_order=t.task_order,
                    task_type=t.task_type,
                    questions_json=list(t.questions_json),
                )
            )

    experiment.status = ExperimentStatus.PUBLISHED
    experiment.current_version_id = version.id
    db.add(
        Event(
            experiment_id=experiment.id,
            version_id=version.id,
            event_type="experiment_published",
            event_data_json={"version_number": next_version_number},
        )
    )
    db.commit()
    db.refresh(version)
    return version


def transition_experiment_status(
    db: Session, experiment: Experiment, target_status: ExperimentStatus
) -> Experiment:
    allowed_transitions: dict[ExperimentStatus, set[ExperimentStatus]] = {
        ExperimentStatus.DRAFT: {ExperimentStatus.ARCHIVED},
        ExperimentStatus.PUBLISHED: {ExperimentStatus.PAUSED, ExperimentStatus.CLOSED},
        ExperimentStatus.PAUSED: {ExperimentStatus.PUBLISHED, ExperimentStatus.CLOSED},
        ExperimentStatus.CLOSED: {ExperimentStatus.ARCHIVED},
        ExperimentStatus.ARCHIVED: set(),
    }
    if target_status not in allowed_transitions.get(experiment.status, set()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid lifecycle transition from '{experiment.status.value}' to '{target_status.value}'",
        )
    previous = experiment.status.value
    experiment.status = target_status
    db.add(
        Event(
            experiment_id=experiment.id,
            version_id=experiment.current_version_id,
            event_type=f"experiment_{target_status.value}",
            event_data_json={"from": previous, "to": target_status.value},
        )
    )
    db.commit()
    db.refresh(experiment)
    return experiment


def create_invitation(
    db: Session, experiment: Experiment, payload: InvitationCreate
) -> tuple[Invitation, str]:
    if experiment.status != ExperimentStatus.PUBLISHED or experiment.current_version_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Experiment must be published before creating participant invitations",
        )
    raw_token, token_hash = generate_invitation_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=payload.expires_in_hours)
    invitation = Invitation(
        experiment_id=experiment.id,
        version_id=experiment.current_version_id,
        token_hash=token_hash,
        label=payload.label.strip(),
        expires_at=expires_at,
        max_uses=payload.max_uses,
    )
    db.add(invitation)
    db.flush()
    db.add(
        Event(
            experiment_id=experiment.id,
            version_id=experiment.current_version_id,
            event_type="invitation_created",
            event_data_json={"invitation_id": str(invitation.id), "label": invitation.label},
        )
    )
    db.commit()
    db.refresh(invitation)
    invite_url = f"{settings.FRONTEND_ORIGIN}/study/{raw_token}"
    return invitation, invite_url