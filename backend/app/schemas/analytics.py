import uuid
from datetime import datetime
from pydantic import BaseModel


class FunnelMetrics(BaseModel):
    total_opened: int
    consented_count: int
    declined_count: int
    assigned_count: int
    completed_count: int
    incomplete_count: int
    completion_rate: float


class ConditionBalanceItem(BaseModel):
    condition_id: uuid.UUID
    condition_name: str
    version_number: int
    assigned_count: int
    completed_count: int


class QuestionSummaryStats(BaseModel):
    condition_id: uuid.UUID
    condition_name: str
    question_id: str
    n: int
    mean: float | None
    median: float | None
    sd: float | None
    min: float | None
    max: float | None


class DataQualityItem(BaseModel):
    participant_code: str | None
    flag_code: str
    severity: str
    details: str
    created_at: datetime | None = None


class ExperimentAnalyticsResponse(BaseModel):
    experiment_id: uuid.UUID
    experiment_title: str
    funnel: FunnelMetrics
    condition_balance: list[ConditionBalanceItem]
    rating_summaries: list[QuestionSummaryStats]
    median_completion_seconds: float | None
    data_quality_flags: list[DataQualityItem]