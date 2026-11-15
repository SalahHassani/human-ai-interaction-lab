import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from app.models.enums import ExperimentStatus, TaskType


class QuestionItemSchema(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=500)
    type: str = Field(pattern="^(likert|text|choice)$")
    min: int | None = 1
    max: int | None = 7
    options: list[str] | None = None
    required: bool = True


class TaskCreate(BaseModel):
    condition_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    instructions: str = ""
    scenario_prompt: str = ""
    task_order: int = Field(default=1, ge=1)
    task_type: TaskType = TaskType.AI_INTERACTION
    questions_json: list[QuestionItemSchema] = Field(default_factory=list)


class TaskResponse(BaseModel):
    id: uuid.UUID
    condition_id: uuid.UUID
    title: str
    instructions: str
    scenario_prompt: str
    task_order: int
    task_type: TaskType
    questions_json: list[dict[str, Any]]

    model_config = {"from_attributes": True}


class ConditionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    ai_answer_template: str = Field(min_length=1)
    ai_explanation_template: str | None = None
    condition_order: int = Field(default=1, ge=1)


class ConditionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    ai_answer_template: str | None = None
    ai_explanation_template: str | None = None
    condition_order: int | None = Field(default=None, ge=1)


class ConditionResponse(BaseModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    version_id: uuid.UUID | None
    name: str
    description: str
    ai_answer_template: str
    ai_explanation_template: str | None
    condition_order: int
    tasks: list[TaskResponse] = []

    model_config = {"from_attributes": True}


class ExperimentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = ""
    participant_information: str = ""
    consent_statement: str = (
        "I have read the study information and voluntarily consent to participate."
    )


class ExperimentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = None
    participant_information: str | None = None
    consent_statement: str | None = None


class ExperimentVersionResponse(BaseModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    version_number: int
    config_json: dict[str, Any]
    published_at: datetime

    model_config = {"from_attributes": True}


class ExperimentSummaryResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    title: str
    description: str
    status: ExperimentStatus
    current_version_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ExperimentDetailResponse(ExperimentSummaryResponse):
    participant_information: str
    consent_statement: str
    draft_conditions: list[ConditionResponse] = []
    versions: list[ExperimentVersionResponse] = []


class InvitationCreate(BaseModel):
    label: str = Field(default="Participant Invitation", min_length=1, max_length=255)
    expires_in_hours: int = Field(default=168, ge=1, le=8760)
    max_uses: int | None = Field(default=None, ge=1)


class InvitationCreatedResponse(BaseModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    version_id: uuid.UUID
    label: str
    raw_token: str
    invite_url: str
    expires_at: datetime
    max_uses: int | None
    use_count: int
    created_at: datetime


class InvitationListItem(BaseModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    version_id: uuid.UUID
    label: str
    expires_at: datetime
    revoked_at: datetime | None
    max_uses: int | None
    use_count: int
    created_at: datetime

    model_config = {"from_attributes": True}