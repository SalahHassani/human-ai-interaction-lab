from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import Assignment, ExperimentVersion, Participant
from app.schemas.participant import (
    AssignmentResponse,
    ChatExchangeResponse,
    ConsentRequest,
    MessageCreateRequest,
    MessageItemResponse,
    ParticipantFlowResponse,
    ParticipantSessionRequest,
    ParticipantSessionResponse,
    ResponseBatchSubmitRequest,
    ResponseSavedItem,
)
from app.services import participant_service

router = APIRouter(prefix="/participant", tags=["participant"])


def get_current_participant(
    x_participant_token: str | None = Header(default=None, alias="X-Participant-Token"),
    db: Session = Depends(get_db),
) -> Participant:
    if not x_participant_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Participant-Token header is required",
        )
    return participant_service.resolve_participant_from_token(db, x_participant_token)


@router.post("/session", response_model=ParticipantSessionResponse)
def start_or_resume_session(
    payload: ParticipantSessionRequest, db: Session = Depends(get_db)
) -> ParticipantSessionResponse:
    participant, experiment, session_token = participant_service.init_or_resume_session(
        db, payload.invite_token, payload.existing_session_token
    )
    version = db.get(ExperimentVersion, participant.version_id)
    cfg = version.config_json if version else {}
    assignment = db.scalar(
        select(Assignment).where(
            Assignment.participant_id == participant.id,
            Assignment.version_id == participant.version_id,
        )
    )
    return ParticipantSessionResponse(
        session_token=session_token,
        participant_id=participant.id,
        pseudonymous_code=participant.pseudonymous_code,
        experiment_id=experiment.id,
        version_id=participant.version_id,
        experiment_title=cfg.get("title", experiment.title),
        experiment_description=cfg.get("description", experiment.description),
        participant_information=cfg.get("participant_information", experiment.participant_information),
        consent_statement=cfg.get("consent_statement", experiment.consent_statement),
        consented=participant.consented_at is not None,
        declined=participant.declined_at is not None,
        completed=participant.completed_at is not None,
        assigned_condition_id=assignment.condition_id if assignment else None,
    )


@router.post("/consent", response_model=ParticipantFlowResponse)
def submit_consent(
    payload: ConsentRequest,
    participant: Participant = Depends(get_current_participant),
    db: Session = Depends(get_db),
) -> ParticipantFlowResponse:
    updated = participant_service.record_consent(db, participant, payload.consented)
    return participant_service.get_participant_flow(db, updated)


@router.post("/assign", response_model=AssignmentResponse)
def assign_condition(
    participant: Participant = Depends(get_current_participant),
    db: Session = Depends(get_db),
) -> AssignmentResponse:
    return participant_service.assign_or_get_condition(db, participant)


@router.get("/flow", response_model=ParticipantFlowResponse)
def get_flow(
    participant: Participant = Depends(get_current_participant),
    db: Session = Depends(get_db),
) -> ParticipantFlowResponse:
    return participant_service.get_participant_flow(db, participant)


@router.post("/messages", response_model=ChatExchangeResponse, status_code=status.HTTP_201_CREATED)
def post_message(
    payload: MessageCreateRequest,
    participant: Participant = Depends(get_current_participant),
    db: Session = Depends(get_db),
) -> ChatExchangeResponse:
    user_msg, assistant_msg = participant_service.send_participant_message(db, participant, payload)
    return ChatExchangeResponse(
        user_message=MessageItemResponse.model_validate(user_msg),
        assistant_message=MessageItemResponse.model_validate(assistant_msg),
    )


@router.post("/responses", response_model=list[ResponseSavedItem], status_code=status.HTTP_201_CREATED)
def submit_responses(
    payload: ResponseBatchSubmitRequest,
    participant: Participant = Depends(get_current_participant),
    db: Session = Depends(get_db),
) -> list[ResponseSavedItem]:
    saved = participant_service.submit_task_responses(db, participant, payload)
    return [ResponseSavedItem.model_validate(r) for r in saved]


@router.post("/complete", response_model=ParticipantFlowResponse)
def complete_study(
    participant: Participant = Depends(get_current_participant),
    db: Session = Depends(get_db),
) -> ParticipantFlowResponse:
    updated = participant_service.complete_participant_study(db, participant)
    return participant_service.get_participant_flow(db, updated)