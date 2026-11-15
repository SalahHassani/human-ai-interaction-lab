import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import get_current_researcher
from app.core.database import get_db
from app.models import Experiment, ExperimentStatus, Invitation, User
from app.schemas.experiment import (
    ConditionCreate,
    ConditionResponse,
    ConditionUpdate,
    ExperimentCreate,
    ExperimentDetailResponse,
    ExperimentSummaryResponse,
    ExperimentUpdate,
    ExperimentVersionResponse,
    InvitationCreate,
    InvitationCreatedResponse,
    InvitationListItem,
    TaskCreate,
    TaskResponse,
)
from app.services import experiment_service

router = APIRouter(prefix="/experiments", tags=["experiments"])


def _serialize_experiment_detail(exp: Experiment) -> ExperimentDetailResponse:
    draft_only = [c for c in exp.draft_conditions if c.version_id is None]
    return ExperimentDetailResponse(
        id=exp.id,
        owner_id=exp.owner_id,
        title=exp.title,
        description=exp.description,
        participant_information=exp.participant_information,
        consent_statement=exp.consent_statement,
        status=exp.status,
        current_version_id=exp.current_version_id,
        created_at=exp.created_at,
        updated_at=exp.updated_at,
        draft_conditions=[ConditionResponse.model_validate(c) for c in draft_only],
        versions=[ExperimentVersionResponse.model_validate(v) for v in exp.versions],
    )


@router.get("", response_model=list[ExperimentSummaryResponse])
def list_experiments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_researcher),
) -> list[Experiment]:
    return experiment_service.list_experiments_for_owner(db, current_user)


@router.post("", response_model=ExperimentDetailResponse, status_code=status.HTTP_201_CREATED)
def create_experiment(
    payload: ExperimentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_researcher),
) -> ExperimentDetailResponse:
    exp = experiment_service.create_experiment(db, current_user, payload)
    return _serialize_experiment_detail(exp)


@router.get("/{experiment_id}", response_model=ExperimentDetailResponse)
def get_experiment(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_researcher),
) -> ExperimentDetailResponse:
    exp = experiment_service.get_experiment_for_owner(db, experiment_id, current_user)
    return _serialize_experiment_detail(exp)


@router.patch("/{experiment_id}", response_model=ExperimentDetailResponse)
def update_experiment(
    experiment_id: uuid.UUID,
    payload: ExperimentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_researcher),
) -> ExperimentDetailResponse:
    exp = experiment_service.get_experiment_for_owner(db, experiment_id, current_user)
    experiment_service.update_experiment(db, exp, payload)
    refreshed = experiment_service.get_experiment_for_owner(db, experiment_id, current_user)
    return _serialize_experiment_detail(refreshed)


@router.get("/{experiment_id}/conditions", response_model=list[ConditionResponse])
def list_conditions(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_researcher),
) -> list[ConditionResponse]:
    exp = experiment_service.get_experiment_for_owner(db, experiment_id, current_user)
    conditions = experiment_service.get_draft_conditions(db, exp.id)
    return [ConditionResponse.model_validate(c) for c in conditions]


@router.post(
    "/{experiment_id}/conditions",
    response_model=ConditionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_condition(
    experiment_id: uuid.UUID,
    payload: ConditionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_researcher),
) -> ConditionResponse:
    exp = experiment_service.get_experiment_for_owner(db, experiment_id, current_user)
    cond = experiment_service.create_condition(db, exp, payload)
    return ConditionResponse.model_validate(cond)


@router.patch("/{experiment_id}/conditions/{condition_id}", response_model=ConditionResponse)
def update_condition(
    experiment_id: uuid.UUID,
    condition_id: uuid.UUID,
    payload: ConditionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_researcher),
) -> ConditionResponse:
    exp = experiment_service.get_experiment_for_owner(db, experiment_id, current_user)
    cond = experiment_service.update_condition(db, exp, condition_id, payload)
    return ConditionResponse.model_validate(cond)


@router.post(
    "/{experiment_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    experiment_id: uuid.UUID,
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_researcher),
) -> TaskResponse:
    exp = experiment_service.get_experiment_for_owner(db, experiment_id, current_user)
    task = experiment_service.create_task(db, exp, payload)
    return TaskResponse.model_validate(task)


@router.post(
    "/{experiment_id}/publish",
    response_model=ExperimentVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def publish_experiment(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_researcher),
) -> ExperimentVersionResponse:
    exp = experiment_service.get_experiment_for_owner(db, experiment_id, current_user)
    version = experiment_service.publish_experiment(db, exp)
    return ExperimentVersionResponse.model_validate(version)


@router.post("/{experiment_id}/pause", response_model=ExperimentSummaryResponse)
def pause_experiment(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_researcher),
) -> Experiment:
    exp = experiment_service.get_experiment_for_owner(db, experiment_id, current_user)
    return experiment_service.transition_experiment_status(db, exp, ExperimentStatus.PAUSED)


@router.post("/{experiment_id}/close", response_model=ExperimentSummaryResponse)
def close_experiment(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_researcher),
) -> Experiment:
    exp = experiment_service.get_experiment_for_owner(db, experiment_id, current_user)
    return experiment_service.transition_experiment_status(db, exp, ExperimentStatus.CLOSED)


@router.post("/{experiment_id}/archive", response_model=ExperimentSummaryResponse)
def archive_experiment(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_researcher),
) -> Experiment:
    exp = experiment_service.get_experiment_for_owner(db, experiment_id, current_user)
    return experiment_service.transition_experiment_status(db, exp, ExperimentStatus.ARCHIVED)


@router.get("/{experiment_id}/invitations", response_model=list[InvitationListItem])
def list_invitations(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_researcher),
) -> list[Invitation]:
    exp = experiment_service.get_experiment_for_owner(db, experiment_id, current_user)
    stmt = (
        select(Invitation)
        .where(Invitation.experiment_id == exp.id)
        .order_by(Invitation.created_at.desc())
    )
    return list(db.scalars(stmt).all())


@router.post(
    "/{experiment_id}/invitations",
    response_model=InvitationCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    experiment_id: uuid.UUID,
    payload: InvitationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_researcher),
) -> InvitationCreatedResponse:
    exp = experiment_service.get_experiment_for_owner(db, experiment_id, current_user)
    invitation, invite_url = experiment_service.create_invitation(db, exp, payload)
    return InvitationCreatedResponse(
        id=invitation.id,
        experiment_id=invitation.experiment_id,
        version_id=invitation.version_id,
        label=invitation.label,
        raw_token=invite_url.rsplit("/", 1)[-1],
        invite_url=invite_url,
        expires_at=invitation.expires_at,
        max_uses=invitation.max_uses,
        use_count=invitation.use_count,
        created_at=invitation.created_at,
    )