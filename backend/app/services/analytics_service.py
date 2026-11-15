import io
import uuid
from datetime import datetime, timezone
from typing import Any
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import (
    Assignment,
    Condition,
    DataQualityFlag,
    Event,
    Experiment,
    ExperimentVersion,
    Message,
    Participant,
    Response,
    Task,
)
from app.schemas.analytics import (
    ConditionBalanceItem,
    DataQualityItem,
    ExperimentAnalyticsResponse,
    FunnelMetrics,
    QuestionSummaryStats,
)

ALLOWED_DATASETS = {
    "participants",
    "assignments",
    "responses",
    "messages",
    "events",
    "experiment_summary",
}


def sanitize_csv_cell(value: Any) -> Any:
    """Prevent CSV spreadsheet formula injection while preserving missing values as None."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{value}"
    return value


def _sanitize_dataframe_for_csv(df: pd.DataFrame) -> str:
    if df.empty:
        return df.to_csv(index=False)
    safe_df = df.copy()
    for col in safe_df.columns:
        safe_df[col] = safe_df[col].map(sanitize_csv_cell)
    buf = io.StringIO()
    safe_df.to_csv(buf, index=False)
    return buf.getvalue()


def build_analytics(db: Session, experiment: Experiment) -> ExperimentAnalyticsResponse:
    participants = list(
        db.scalars(
            select(Participant)
            .where(Participant.experiment_id == experiment.id)
            .order_by(Participant.created_at.asc())
        ).all()
    )
    participant_ids = [p.id for p in participants]

    assignments = (
        list(db.scalars(select(Assignment).where(Assignment.participant_id.in_(participant_ids))).all())
        if participant_ids
        else []
    )
    responses = (
        list(db.scalars(select(Response).where(Response.participant_id.in_(participant_ids))).all())
        if participant_ids
        else []
    )
    conditions = list(
        db.scalars(select(Condition).where(Condition.experiment_id == experiment.id)).all()
    )
    versions = list(
        db.scalars(
            select(ExperimentVersion).where(ExperimentVersion.experiment_id == experiment.id)
        ).all()
    )

    cond_map = {c.id: c for c in conditions}
    ver_map = {v.id: v for v in versions}
    part_map = {p.id: p for p in participants}
    assign_by_participant = {a.participant_id: a for a in assignments}

    total_opened = len(participants)
    consented_count = sum(1 for p in participants if p.consented_at is not None)
    declined_count = sum(1 for p in participants if p.declined_at is not None)
    assigned_count = len(assignments)
    completed_count = sum(1 for p in participants if p.completed_at is not None)
    incomplete_count = max(0, consented_count - completed_count)
    completion_rate = round((completed_count / consented_count) * 100, 1) if consented_count > 0 else 0.0

    # Condition balance across published versions
    version_conditions = [c for c in conditions if c.version_id is not None]
    balance_items: list[ConditionBalanceItem] = []
    for cond in sorted(
        version_conditions,
        key=lambda c: (
            ver_map[c.version_id].version_number if c.version_id in ver_map else 0,
            c.condition_order,
        ),
    ):
        cond_assignments = [a for a in assignments if a.condition_id == cond.id]
        cond_completed = sum(
            1
            for a in cond_assignments
            if a.participant_id in part_map and part_map[a.participant_id].completed_at is not None
        )
        ver_num = ver_map[cond.version_id].version_number if cond.version_id in ver_map else 0
        balance_items.append(
            ConditionBalanceItem(
                condition_id=cond.id,
                condition_name=cond.name,
                version_number=ver_num,
                assigned_count=len(cond_assignments),
                completed_count=cond_completed,
            )
        )

    # Numeric Likert rating summaries via pandas
    rating_rows: list[dict[str, Any]] = []
    for resp in responses:
        val = resp.value_json.get("value") if isinstance(resp.value_json, dict) else None
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            assign = assign_by_participant.get(resp.participant_id)
            if assign and assign.condition_id in cond_map:
                cond = cond_map[assign.condition_id]
                rating_rows.append(
                    {
                        "condition_id": str(cond.id),
                        "condition_name": cond.name,
                        "question_id": resp.question_id,
                        "value": float(val),
                    }
                )

    rating_summaries: list[QuestionSummaryStats] = []
    if rating_rows:
        df = pd.DataFrame(rating_rows)
        grouped = df.groupby(["condition_id", "condition_name", "question_id"], sort=True)["value"]
        for (cid, cname, qid), series in grouped:
            clean = series.dropna()
            n_val = int(clean.count())
            rating_summaries.append(
                QuestionSummaryStats(
                    condition_id=uuid.UUID(str(cid)),
                    condition_name=str(cname),
                    question_id=str(qid),
                    n=n_val,
                    mean=round(float(clean.mean()), 2) if n_val > 0 else None,
                    median=round(float(clean.median()), 2) if n_val > 0 else None,
                    sd=round(float(clean.std(ddof=1)), 2) if n_val > 1 else None,
                    min=round(float(clean.min()), 2) if n_val > 0 else None,
                    max=round(float(clean.max()), 2) if n_val > 0 else None,
                )
            )

    # Completion durations
    durations: list[float] = []
    for p in participants:
        if p.consented_at is not None and p.completed_at is not None:
            delta = (p.completed_at - p.consented_at).total_seconds()
            if delta >= 0:
                durations.append(delta)
    median_duration = round(float(pd.Series(durations).median()), 1) if durations else None

    # Non-destructive data quality diagnostics
    quality_flags: list[DataQualityItem] = []
    stored_flags = list(
        db.scalars(
            select(DataQualityFlag)
            .where(DataQualityFlag.experiment_id == experiment.id, DataQualityFlag.resolved_at.is_(None))
            .order_by(DataQualityFlag.created_at.desc())
        ).all()
    )
    for sf in stored_flags:
        p_code = part_map[sf.participant_id].pseudonymous_code if sf.participant_id in part_map else None
        quality_flags.append(
            DataQualityItem(
                participant_code=p_code,
                flag_code=sf.flag_code,
                severity="warning",
                details=sf.details,
                created_at=sf.created_at,
            )
        )

    for p in participants:
        if p.consented_at is not None and p.completed_at is None:
            quality_flags.append(
                DataQualityItem(
                    participant_code=p.pseudonymous_code,
                    flag_code="INCOMPLETE_SESSION",
                    severity="info",
                    details="Participant consented but has not reached completion state.",
                    created_at=p.consented_at,
                )
            )
        if p.consented_at is not None and p.completed_at is not None:
            dur = (p.completed_at - p.consented_at).total_seconds()
            if dur < 10.0:
                quality_flags.append(
                    DataQualityItem(
                        participant_code=p.pseudonymous_code,
                        flag_code="SPEEDING_DURATION",
                        severity="warning",
                        details=f"Completed study in {dur:.1f}s (< 10s threshold).",
                        created_at=p.completed_at,
                    )
                )

    return ExperimentAnalyticsResponse(
        experiment_id=experiment.id,
        experiment_title=experiment.title,
        funnel=FunnelMetrics(
            total_opened=total_opened,
            consented_count=consented_count,
            declined_count=declined_count,
            assigned_count=assigned_count,
            completed_count=completed_count,
            incomplete_count=incomplete_count,
            completion_rate=completion_rate,
        ),
        condition_balance=balance_items,
        rating_summaries=rating_summaries,
        median_completion_seconds=median_duration,
        data_quality_flags=quality_flags,
    )


def export_experiment_csv(db: Session, experiment: Experiment, dataset: str) -> tuple[str, str]:
    if dataset not in ALLOWED_DATASETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown dataset '{dataset}'. Allowed: {sorted(ALLOWED_DATASETS)}",
        )

    participants = list(
        db.scalars(
            select(Participant)
            .where(Participant.experiment_id == experiment.id)
            .order_by(Participant.created_at.asc())
        ).all()
    )
    part_map = {p.id: p for p in participants}
    participant_ids = list(part_map.keys())

    conditions = list(
        db.scalars(select(Condition).where(Condition.experiment_id == experiment.id)).all()
    )
    cond_map = {c.id: c for c in conditions}

    versions = list(
        db.scalars(
            select(ExperimentVersion).where(ExperimentVersion.experiment_id == experiment.id)
        ).all()
    )
    ver_map = {v.id: v for v in versions}

    tasks = (
        list(db.scalars(select(Task).where(Task.condition_id.in_(list(cond_map.keys())))).all())
        if cond_map
        else []
    )
    task_map = {t.id: t for t in tasks}

    if dataset == "participants":
        rows = []
        for p in participants:
            if p.completed_at is not None:
                c_status = "completed"
            elif p.declined_at is not None:
                c_status = "declined"
            elif p.consented_at is not None:
                c_status = "in_progress"
            else:
                c_status = "opened_only"
            rows.append(
                {
                    "participant_code": p.pseudonymous_code,
                    "version_number": ver_map[p.version_id].version_number if p.version_id in ver_map else None,
                    "consented_at": p.consented_at.isoformat() if p.consented_at else None,
                    "completed_at": p.completed_at.isoformat() if p.completed_at else None,
                    "completion_status": c_status,
                }
            )
        df = pd.DataFrame(
            rows,
            columns=[
                "participant_code",
                "version_number",
                "consented_at",
                "completed_at",
                "completion_status",
            ],
        )

    elif dataset == "assignments":
        assigns = (
            list(
                db.scalars(
                    select(Assignment)
                    .where(Assignment.participant_id.in_(participant_ids))
                    .order_by(Assignment.assigned_at.asc())
                ).all()
            )
            if participant_ids
            else []
        )
        rows = [
            {
                "participant_code": part_map[a.participant_id].pseudonymous_code,
                "version_number": ver_map[a.version_id].version_number if a.version_id in ver_map else None,
                "condition_name": cond_map[a.condition_id].name if a.condition_id in cond_map else None,
                "assigned_at": a.assigned_at.isoformat(),
                "method": a.method,
            }
            for a in assigns
        ]
        df = pd.DataFrame(
            rows,
            columns=["participant_code", "version_number", "condition_name", "assigned_at", "method"],
        )

    elif dataset == "responses":
        resps = (
            list(
                db.scalars(
                    select(Response)
                    .where(Response.participant_id.in_(participant_ids))
                    .order_by(Response.submitted_at.asc())
                ).all()
            )
            if participant_ids
            else []
        )
        rows = [
            {
                "participant_code": part_map[r.participant_id].pseudonymous_code,
                "task_title": task_map[r.task_id].title if r.task_id in task_map else None,
                "question_id": r.question_id,
                "value": r.value_json.get("value") if isinstance(r.value_json, dict) else None,
                "submitted_at": r.submitted_at.isoformat(),
            }
            for r in resps
        ]
        df = pd.DataFrame(
            rows,
            columns=["participant_code", "task_title", "question_id", "value", "submitted_at"],
        )

    elif dataset == "messages":
        msgs = (
            list(
                db.scalars(
                    select(Message)
                    .where(Message.participant_id.in_(participant_ids))
                    .order_by(Message.created_at.asc())
                ).all()
            )
            if participant_ids
            else []
        )
        rows = [
            {
                "participant_code": part_map[m.participant_id].pseudonymous_code,
                "task_title": task_map[m.task_id].title if m.task_id in task_map else None,
                "role": m.role.value,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in msgs
        ]
        df = pd.DataFrame(
            rows,
            columns=["participant_code", "task_title", "role", "content", "created_at"],
        )

    elif dataset == "events":
        evts = list(
            db.scalars(
                select(Event)
                .where(Event.experiment_id == experiment.id)
                .order_by(Event.occurred_at.asc())
            ).all()
        )
        rows = [
            {
                "participant_code": part_map[e.participant_id].pseudonymous_code
                if e.participant_id and e.participant_id in part_map
                else None,
                "event_type": e.event_type,
                "occurred_at": e.occurred_at.isoformat(),
                "task_title": task_map[e.task_id].title if e.task_id and e.task_id in task_map else None,
                "metadata": str(e.event_data_json) if e.event_data_json else "",
            }
            for e in evts
        ]
        df = pd.DataFrame(
            rows,
            columns=["participant_code", "event_type", "occurred_at", "task_title", "metadata"],
        )

    else:  # experiment_summary
        analytics = build_analytics(db, experiment)
        rows = [
            {
                "condition_name": s.condition_name,
                "question_id": s.question_id,
                "n": s.n,
                "mean": s.mean,
                "median": s.median,
                "sd": s.sd,
                "min": s.min,
                "max": s.max,
            }
            for s in analytics.rating_summaries
        ]
        df = pd.DataFrame(
            rows,
            columns=["condition_name", "question_id", "n", "mean", "median", "sd", "min", "max"],
        )

    csv_text = _sanitize_dataframe_for_csv(df)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"hai_lab_{dataset}_{timestamp}.csv"
    return filename, csv_text