from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Sequence

from sqlalchemy import and_, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import HealthMetric


class MetricRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_metric(self, metric: HealthMetric) -> HealthMetric:
        self.session.add(metric)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            existing = self.session.execute(
                select(HealthMetric).where(
                    and_(
                        HealthMetric.user_id == metric.user_id,
                        HealthMetric.dedup_hash == metric.dedup_hash,
                        HealthMetric.deleted.is_(False),
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                return existing
            raise
        return metric

    def bulk_create(self, metrics: Sequence[HealthMetric]) -> List[HealthMetric]:
        created: List[HealthMetric] = []
        for metric in metrics:
            created.append(self.create_metric(metric))
        return created

    def query_metrics(
        self,
        user_id: str,
        type_code: Optional[str] = None,
        limit: int = 20,
        order: str = "desc",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        source: Optional[str] = None,
    ) -> List[HealthMetric]:
        stmt = select(HealthMetric).where(
            and_(HealthMetric.user_id == user_id, HealthMetric.deleted.is_(False))
        )
        if type_code:
            stmt = stmt.where(HealthMetric.type_code == type_code)
        if start_time:
            stmt = stmt.where(HealthMetric.recorded_at >= start_time)
        if end_time:
            stmt = stmt.where(HealthMetric.recorded_at <= end_time)
        if source:
            stmt = stmt.where(HealthMetric.source == source)
        stmt = stmt.order_by(
            HealthMetric.recorded_at.asc() if order == "asc" else HealthMetric.recorded_at.desc()
        )
        if limit:
            stmt = stmt.limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def delete_metric(self, user_id: str, record_id: str) -> bool:
        stmt = (
            update(HealthMetric)
            .where(
                and_(
                    HealthMetric.id == record_id,
                    HealthMetric.user_id == user_id,
                    HealthMetric.deleted.is_(False),
                )
            )
            .values(deleted=True, updated_at=func.now())
        )
        result = self.session.execute(stmt)
        return result.rowcount > 0

    def list_for_trend(
        self,
        user_id: str,
        type_code: str,
        metric_field: Optional[str],
        start_time: Optional[datetime],
    ) -> List[HealthMetric]:
        stmt = select(HealthMetric).where(
            and_(
                HealthMetric.user_id == user_id,
                HealthMetric.type_code == type_code,
                HealthMetric.deleted.is_(False),
            )
        )
        if start_time:
            stmt = stmt.where(HealthMetric.recorded_at >= start_time)
        stmt = stmt.order_by(HealthMetric.recorded_at.asc())
        return list(self.session.execute(stmt).scalars().all())


def group_by_timepoints(
    metrics: Sequence[HealthMetric],
    group_by: str,
    metric_field: Optional[str] = None,
) -> Dict[str, Dict[str, float]]:
    buckets: Dict[str, Dict[str, float]] = {}
    for metric in metrics:
        ts = metric.recorded_at
        if group_by == "day":
            key = ts.strftime("%Y-%m-%d")
        elif group_by == "week":
            key = f"{ts.strftime('%Y')}-W{ts.isocalendar().week:02d}"
        elif group_by == "month":
            key = ts.strftime("%Y-%m")
        else:
            raise ValueError(f"Unsupported group_by: {group_by}")

        value = _extract_value(metric, metric_field)
        bucket = buckets.setdefault(key, {"total": 0.0, "count": 0})
        bucket["total"] += value
        bucket["count"] += 1
    return buckets


def _extract_value(metric: HealthMetric, metric_field: Optional[str]) -> float:
    if metric.value_number is not None:
        return float(metric.value_number)
    if metric_field and metric.value_json:
        field_value = metric.value_json.get(metric_field)
        if field_value is None:
            raise ValueError(f"Metric field '{metric_field}' not present in record {metric.id}")
        return float(field_value)
    if metric.value_text:
        try:
            return float(metric.value_text)
        except ValueError:
            pass
    raise ValueError(f"Cannot extract numeric value for record {metric.id}")
