import secrets
import uuid
from datetime import datetime, timezone
import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.core.security import create_access_token, decode_access_token, hash_token
from app.models import (
    Assignment,
    Condition,
    Event,
    Experiment,
    ExperimentStatus,
    ExperimentVersion,
    Invitation,
    Message,
    MessageRole,
    Participant,
    Response,
    Task,
)
from app.schemas.participant import (
    AssignmentResponse,
    ConditionPublicResponse,
    MessageCreateRequest,
    MessageItemResponse,
    ParticipantFlowResponse,
    ResponseBatchSubmitRequest,
    ResponseSavedItem,
    TaskPublicResponse,
)
from app.services.ai_provider import get_ai_provider


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_pseudonymous_code(db: Session) -> str:
    for _ in range(10):
        code = f"P-{secrets.token_hex(4).upper()}"
        exists = db.scalar(select(Participant.id).where(Participant.pseudonymous_code == code))
        if exists is None:
            return code
    raise RuntimeError("Unable to generate unique pseudonymous participant code")


def create_participant_token(participant: Participant) -> str:
    return create_access_token(subject=str(participant.id), role="participant")


def resolve_participant_from_token(db: Session, token: str) -> Participant:
    try:
        payload = decode_access_token(token)
        if payload.get("role") != "participant":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid participant session scope",
            )
        participant_id = uuid.UUID(str(payload.get("sub")))
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired participant session",
        ) from exc

    participant = db.get(Participant, participant_id)
    if participant is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Participant session not found",
        )
    return participant


def init_or_resume_session(
    db: Session, raw_invite_token: str, existing_session_token: str | None = None
) -> tuple[Participant, Experiment, str]:
    token_hash = hash_token(raw_invite_token.strip())
    invitation = db.scalar(select(Invitation).where(Invitation.token_hash == token_hash))
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation link is invalid",
        )
    now = _utc_now()
    if invitation.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This invitation link has been revoked",
        )
    if invitation.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This invitation link has expired",
        )

    experiment = db.get(Experiment, invitation.experiment_id)
    if experiment is None or experiment.status != ExperimentStatus.PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This study is not currently accepting participants",
        )

    # Resume existing participant session if valid and tied to this invitation
    if existing_session_token:
        try:
            existing_p = resolve_participant_from_token(db, existing_session_token)
            if existing_p.invitation_id == invitation.id:
                return existing_p, experiment, existing_session_token
        except HTTPException:
            pass

    if invitation.max_uses is not None and invitation.use_count >= invitation.max_uses:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This invitation link has reached its maximum participant limit",
        )

    participant = Participant(
        experiment_id=experiment.id,
        version_id=invitation.version_id,
        invitation_id=invitation.id,
        pseudonymous_code=_generate_pseudonymous_code(db),
    )
    invitation.use_count += 1
    db.add(participant)
    db.flush()
    db.add(
        Event(
            experiment_id=experiment.id,
            version_id=invitation.version_id,
            participant_id=participant.id,
            event_type="experiment_opened",
            event_data_json={"invitation_id": str(invitation.id)},
        )
    )
    db.commit()
    db.refresh(participant)
    session_token = create_participant_token(participant)
    return participant, experiment, session_token


def record_consent(db: Session, participant: Participant, consented: bool) -> Participant:
    if participant.completed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Study already completed",
        )
    now = _utc_now()
    if consented:
        if participant.consented_at is None:
            participant.consented_at = now
            participant.declined_at = None
    else:
        if participant.consented_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Consent was already granted for this session",
            )
        participant.declined_at = now

    db.add(
        Event(
            experiment_id=participant.experiment_id,
            version_id=participant.version_id,
            participant_id=participant.id,
            event_type="consent_submitted",
            event_data_json={"consented": consented},
        )
    )
    db.commit()
    db.refresh(participant)
    return participant


def _require_consent(participant: Participant) -> None:
    if participant.consented_at is None or participant.declined_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Informed consent is required before accessing study tasks or conditions",
        )


def _load_condition_with_tasks(db: Session, condition_id: uuid.UUID) -> Condition:
    cond = db.scalar(
        select(Condition)
        .where(Condition.id == condition_id)
        .options(selectinload(Condition.tasks))
    )
    if cond is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assigned condition not found")
    return cond


def _serialize_assignment(db: Session, assignment: Assignment) -> AssignmentResponse:
    cond = _load_condition_with_tasks(db, assignment.condition_id)
    sorted_tasks = sorted(cond.tasks, key=lambda t: t.task_order)
    return AssignmentResponse(
        id=assignment.id,
        participant_id=assignment.participant_id,
        version_id=assignment.version_id,
        condition_id=assignment.condition_id,
        method=assignment.method,
        assigned_at=assignment.assigned_at,
        condition=ConditionPublicResponse(
            id=cond.id,
            name=cond.name,
            description=cond.description,
            condition_order=cond.condition_order,
            tasks=[TaskPublicResponse.model_validate(t) for t in sorted_tasks],
        ),
    )


def assign_or_get_condition(db: Session, participant: Participant) -> AssignmentResponse:
    _require_consent(participant)

    existing = db.scalar(
        select(Assignment).where(
            Assignment.participant_id == participant.id,
            Assignment.version_id == participant.version_id,
        )
    )
    if existing is not None:
        return _serialize_assignment(db, existing)

    version_conditions = list(
        db.scalars(
            select(Condition)
            .where(Condition.version_id == participant.version_id)
            .order_by(Condition.condition_order.asc())
        ).all()
    )
    if not version_conditions:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No conditions configured for published study version",
        )

    chosen_condition = secrets.choice(version_conditions)
    assignment = Assignment(
        participant_id=participant.id,
        version_id=participant.version_id,
        condition_id=chosen_condition.id,
        method="secrets_uniform_random",
    )
    db.add(assignment)
    try:
        db.flush()
        db.add(
            Event(
                experiment_id=participant.experiment_id,
                version_id=participant.version_id,
                participant_id=participant.id,
                event_type="condition_assigned",
                event_data_json={
                    "condition_id": str(chosen_condition.id),
                    "condition_name": chosen_condition.name,
                    "method": "secrets_uniform_random",
                },
            )
        )
        db.commit()
        db.refresh(assignment)
    except IntegrityError:
        db.rollback()
        assignment = db.scalar(
            select(Assignment).where(
                Assignment.participant_id == participant.id,
                Assignment.version_id == participant.version_id,
            )
        )
        assert assignment is not None

    return _serialize_assignment(db, assignment)


def _get_assigned_task(db: Session, participant: Participant, task_id: uuid.UUID) -> tuple[Condition, Task]:
    _require_consent(participant)
    assignment = db.scalar(
        select(Assignment).where(
            Assignment.participant_id == participant.id,
            Assignment.version_id == participant.version_id,
        )
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Condition assignment must occur before interacting with tasks",
        )
    task = db.scalar(
        select(Task).where(Task.id == task_id, Task.condition_id == assignment.condition_id)
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found in your assigned condition",
        )
    condition = db.get(Condition, assignment.condition_id)
    assert condition is not None
    return condition, task


def send_participant_message(
    db: Session, participant: Participant, payload: MessageCreateRequest
) -> tuple[Message, Message]:
    if participant.completed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Study is already completed",
        )
    condition, task = _get_assigned_task(db, participant, payload.task_id)

    # Log task_started on first interaction with this task
    prior_events = db.scalar(
        select(Event.id).where(
            Event.participant_id == participant.id,
            Event.task_id == task.id,
            Event.event_type == "task_started",
        )
    )
    if prior_events is None:
        db.add(
            Event(
                experiment_id=participant.experiment_id,
                version_id=participant.version_id,
                participant_id=participant.id,
                task_id=task.id,
                event_type="task_started",
                event_data_json={"task_title": task.title},
            )
        )

    user_msg = Message(
        participant_id=participant.id,
        task_id=task.id,
        role=MessageRole.PARTICIPANT,
        content=payload.content.strip(),
    )
    db.add(user_msg)
    db.flush()

    provider = get_ai_provider()
    ai_reply_text = provider.generate_response(condition, task, user_msg.content)

    assistant_msg = Message(
        participant_id=participant.id,
        task_id=task.id,
        role=MessageRole.ASSISTANT,
        content=ai_reply_text,
    )
    db.add(assistant_msg)
    db.flush()

    db.add(
        Event(
            experiment_id=participant.experiment_id,
            version_id=participant.version_id,
            participant_id=participant.id,
            task_id=task.id,
            event_type="message_sent",
            event_data_json={"message_id": str(user_msg.id), "char_length": len(user_msg.content)},
        )
    )
    db.add(
        Event(
            experiment_id=participant.experiment_id,
            version_id=participant.version_id,
            participant_id=participant.id,
            task_id=task.id,
            event_type="response_received",
            event_data_json={
                "message_id": str(assistant_msg.id),
                "condition_id": str(condition.id),
                "has_explanation": bool(condition.ai_explanation_template),
            },
        )
    )
    db.commit()
    db.refresh(user_msg)
    db.refresh(assistant_msg)
    return user_msg, assistant_msg


def submit_task_responses(
    db: Session, participant: Participant, payload: ResponseBatchSubmitRequest
) -> list[Response]:
    if participant.completed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Study is already completed",
        )
    _, task = _get_assigned_task(db, participant, payload.task_id)

    question_map = {q["id"]: q for q in task.questions_json}
    submitted_map = {a.question_id: a.value for a in payload.answers}

    # Check required questions and validate types/ranges
    for q_id, q_spec in question_map.items():
        val = submitted_map.get(q_id)
        if q_spec.get("required", True) and (val is None or (isinstance(val, str) and not val.strip())):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Required question '{q_id}' is missing",
            )
        if val is not None and q_spec.get("type") == "likert":
            if isinstance(val, bool) or not isinstance(val, int):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Question '{q_id}' requires an integer Likert rating",
                )
            min_v = q_spec.get("min", 1)
            max_v = q_spec.get("max", 7)
            if val < min_v or val > max_v:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Question '{q_id}' must be between {min_v} and {max_v}",
                )

    for ans_qid in submitted_map:
        if ans_qid not in question_map:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown question_id '{ans_qid}' for this task",
            )

    saved_records: list[Response] = []
    for ans in payload.answers:
        existing_resp = db.scalar(
            select(Response).where(
                Response.participant_id == participant.id,
                Response.task_id == task.id,
                Response.question_id == ans.question_id,
            )
        )
        if existing_resp is not None:
            existing_resp.value_json = {"value": ans.value}
            existing_resp.submitted_at = _utc_now()
            saved_records.append(existing_resp)
        else:
            rec = Response(
                participant_id=participant.id,
                task_id=task.id,
                question_id=ans.question_id,
                value_json={"value": ans.value},
            )
            db.add(rec)
            saved_records.append(rec)

        db.add(
            Event(
                experiment_id=participant.experiment_id,
                version_id=participant.version_id,
                participant_id=participant.id,
                task_id=task.id,
                event_type="rating_submitted",
                event_data_json={"question_id": ans.question_id},
            )
        )

    db.add(
        Event(
            experiment_id=participant.experiment_id,
            version_id=participant.version_id,
            participant_id=participant.id,
            task_id=task.id,
            event_type="task_completed",
            event_data_json={"task_title": task.title, "answer_count": len(payload.answers)},
        )
    )
    db.commit()
    for r in saved_records:
        db.refresh(r)
    return saved_records


def complete_participant_study(db: Session, participant: Participant) -> Participant:
    _require_consent(participant)
    if participant.completed_at is None:
        participant.completed_at = _utc_now()
        db.add(
            Event(
                experiment_id=participant.experiment_id,
                version_id=participant.version_id,
                participant_id=participant.id,
                event_type="experiment_completed",
                event_data_json={"pseudonymous_code": participant.pseudonymous_code},
            )
        )
        db.commit()
        db.refresh(participant)
    return participant


def get_participant_flow(db: Session, participant: Participant) -> ParticipantFlowResponse:
    version = db.get(ExperimentVersion, participant.version_id)
    assert version is not None
    cfg = version.config_json

    consented = participant.consented_at is not None
    declined = participant.declined_at is not None
    completed = participant.completed_at is not None

    assignment_row = db.scalar(
        select(Assignment).where(
            Assignment.participant_id == participant.id,
            Assignment.version_id == participant.version_id,
        )
    )

    if declined:
        step = "declined"
    elif not consented:
        step = "consent"
    elif assignment_row is None:
        step = "assign"
    elif completed:
        step = "completed"
    else:
        step = "tasks"

    assignment_dto = _serialize_assignment(db, assignment_row) if assignment_row else None
    msgs = list(
        db.scalars(
            select(Message)
            .where(Message.participant_id == participant.id)
            .order_by(Message.created_at.asc())
        ).all()
    )
    resps = list(
        db.scalars(
            select(Response)
            .where(Response.participant_id == participant.id)
            .order_by(Response.submitted_at.asc())
        ).all()
    )

    return ParticipantFlowResponse(
        step=step,
        pseudonymous_code=participant.pseudonymous_code,
        experiment_title=cfg.get("title", ""),
        participant_information=cfg.get("participant_information", ""),
        consent_statement=cfg.get("consent_statement", ""),
        consented=consented,
        declined=declined,
        completed=completed,
        assignment=assignment_dto,
        messages=[MessageItemResponse.model_validate(m) for m in msgs],
        submitted_responses=[ResponseSavedItem.model_validate(r) for r in resps],
    )