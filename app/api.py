from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .schemas import (
    HealthBatchStoreMetricsInput,
    HealthBatchStoreMetricsOutput,
    HealthDeleteRecordOutput,
    HealthQueryMetricsOutput,
    HealthStoreMetricInput,
    HealthStoreMetricOutput,
    TrendSummaryInput,
    TrendSummaryOutput,
    QueryFilters,
    HealthListMetricTypesOutput,
)
from .services import MetricService

router = APIRouter(prefix="/api", tags=["health"])


def _service(session: Session) -> MetricService:
    return MetricService(session)


@router.get("/metric-types", response_model=HealthListMetricTypesOutput)
def list_metric_types(session: Session = Depends(get_db)):
    service = _service(session)
    return HealthListMetricTypesOutput(types=service.list_metric_types())


@router.post("/metrics", response_model=HealthStoreMetricOutput)
def store_metric(payload: HealthStoreMetricInput, session: Session = Depends(get_db)):
    service = _service(session)
    try:
        metric, deduplicated = service.store_metric(
            user_id=payload.user_id,
            type_code=payload.type,
            value=payload.value,
            unit=payload.unit,
            recorded_at=payload.recorded_at,
            source=payload.source,
            metadata=payload.metadata,
            tags=payload.tags,
        )
    except ValueError as exc:  # pragma: no cover - FastAPI handles error response
        raise HTTPException(status_code=400, detail=str(exc))
    return HealthStoreMetricOutput(record_id=metric.id, deduplicated=deduplicated)


@router.post("/metrics/batch", response_model=HealthBatchStoreMetricsOutput)
def batch_store_metrics(
    payload: HealthBatchStoreMetricsInput, session: Session = Depends(get_db)
):
    service = _service(session)
    created = []
    for record in payload.records:
        try:
            metric, deduplicated = service.store_metric(
                user_id=record.user_id,
                type_code=record.type,
                value=record.value,
                unit=record.unit,
                recorded_at=record.recorded_at,
                source=record.source,
                metadata=record.metadata,
                tags=record.tags,
            )
        except ValueError as exc:  # pragma: no cover
            raise HTTPException(status_code=400, detail=str(exc))
        created.append(
            HealthStoreMetricOutput(record_id=metric.id, deduplicated=deduplicated)
        )
    return HealthBatchStoreMetricsOutput(records=created)


@router.get("/metrics", response_model=HealthQueryMetricsOutput)
def query_metrics(filters: QueryFilters = Depends(), session: Session = Depends(get_db)):
    service = _service(session)
    metrics = service.query_metrics(
        user_id=filters.user_id,
        type_code=filters.type,
        limit=filters.limit,
        order=filters.order,
        start_time=filters.start_time,
        end_time=filters.end_time,
        source=filters.source,
    )
    return HealthQueryMetricsOutput(records=[metric.to_dict() for metric in metrics])


@router.post("/metrics/trend", response_model=TrendSummaryOutput)
def trend_summary(payload: TrendSummaryInput, session: Session = Depends(get_db)):
    service = _service(session)
    try:
        summary = service.trend_summary(
            user_id=payload.user_id,
            type_code=payload.type,
            metric_field=payload.metric_field,
            group_by=payload.group_by,
            lookback_days=payload.lookback_days,
        )
    except ValueError as exc:  # pragma: no cover
        raise HTTPException(status_code=400, detail=str(exc))
    return TrendSummaryOutput(**summary)


@router.delete("/metrics/{record_id}", response_model=HealthDeleteRecordOutput)
def delete_metric(record_id: str, user_id: str, session: Session = Depends(get_db)):
    service = _service(session)
    deleted = service.delete_metric(user_id, record_id)
    if not deleted:
        return HealthDeleteRecordOutput(success=False, message="record not found")
    return HealthDeleteRecordOutput(success=True, message=None)
