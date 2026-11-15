import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from app.models.enums import MessageRole, TaskType


class ParticipantSessionRequest(BaseModel):
    invite_token: str = Field(min_length=10, max_length=255)
    existing_session_token: str | None = None


class ParticipantSessionResponse(BaseModel):
    session_token: str
    participant_id: uuid.UUID
    pseudonymous_code: str
    experiment_id: uuid.UUID
    version_id: uuid.UUID
    experiment_title: str
    experiment_description: str
    participant_information: str
    consent_statement: str
    consented: bool
    declined: bool
    completed: bool
    assigned_condition_id: uuid.UUID | None = None


class ConsentRequest(BaseModel):
    consented: bool


class TaskPublicResponse(BaseModel):
    id: uuid.UUID
    title: str
    instructions: str
    scenario_prompt: str
    task_order: int
    task_type: TaskType
    questions_json: list[dict[str, Any]]

    model_config = {"from_attributes": True}


class ConditionPublicResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    condition_order: int
    tasks: list[TaskPublicResponse] = []

    model_config = {"from_attributes": True}


class AssignmentResponse(BaseModel):
    id: uuid.UUID
    participant_id: uuid.UUID
    version_id: uuid.UUID
    condition_id: uuid.UUID
    method: str
    assigned_at: datetime
    condition: ConditionPublicResponse


class MessageCreateRequest(BaseModel):
    task_id: uuid.UUID
    content: str = Field(min_length=1, max_length=4000)


class MessageItemResponse(BaseModel):
    id: uuid.UUID
    participant_id: uuid.UUID
    task_id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatExchangeResponse(BaseModel):
    user_message: MessageItemResponse
    assistant_message: MessageItemResponse


class SingleAnswerInput(BaseModel):
    question_id: str = Field(min_length=1, max_length=128)
    value: int | float | str | bool


class ResponseBatchSubmitRequest(BaseModel):
    task_id: uuid.UUID
    answers: list[SingleAnswerInput] = Field(min_length=1)


class ResponseSavedItem(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    question_id: str
    value_json: dict[str, Any]
    submitted_at: datetime

    model_config = {"from_attributes": True}


class ParticipantFlowResponse(BaseModel):
    step: str  # "consent" | "declined" | "assign" | "tasks" | "completed"
    pseudonymous_code: str
    experiment_title: str
    participant_information: str
    consent_statement: str
    consented: bool
    declined: bool
    completed: bool
    assignment: AssignmentResponse | None = None
    messages: list[MessageItemResponse] = []
    submitted_responses: list[ResponseSavedItem] = []