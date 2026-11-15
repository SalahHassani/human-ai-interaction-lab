import uuid
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.orm import Session
from app.api.deps import get_current_researcher
from app.core.database import get_db
from app.models import User
from app.schemas.analytics import ExperimentAnalyticsResponse
from app.services import analytics_service, experiment_service

router = APIRouter(prefix="/experiments/{experiment_id}", tags=["analytics"])


@router.get("/analytics", response_model=ExperimentAnalyticsResponse)
def get_experiment_analytics(
    experiment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_researcher),
) -> ExperimentAnalyticsResponse:
    experiment = experiment_service.get_experiment_for_owner(db, experiment_id, current_user)
    return analytics_service.build_analytics(db, experiment)


@router.get("/export")
def export_experiment_dataset(
    experiment_id: uuid.UUID,
    dataset: str = Query(
        default="participants",
        description="One of: participants, assignments, responses, messages, events, experiment_summary",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_researcher),
) -> FastAPIResponse:
    experiment = experiment_service.get_experiment_for_owner(db, experiment_id, current_user)
    filename, csv_content = analytics_service.export_experiment_csv(db, experiment, dataset)
    return FastAPIResponse(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )