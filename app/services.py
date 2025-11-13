from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from .catalog import get_metric_type, list_metric_types
from .models import HealthMetric
from .repositories import MetricRepository, group_by_timepoints
from .utils import compute_dedup_hash, ensure_datetime


class MetricService:
    def __init__(self, session: Session):
        self.repo = MetricRepository(session)

    def store_metric(
        self,
        *,
        user_id: str,
        type_code: str,
        value,
        unit: Optional[str],
        recorded_at: Optional[datetime],
        source: str,
        metadata: Optional[Dict],
        tags: Optional[Dict],
    ) -> tuple[HealthMetric, bool]:
        metric_type = get_metric_type(type_code)
        recorded_at = ensure_datetime(recorded_at)
        dedup_hash = compute_dedup_hash(user_id, type_code, recorded_at, value, metadata)
        value_number = None
        value_json = None
        value_text = None
        if isinstance(value, (int, float)):
            value_number = float(value)
        elif isinstance(value, dict):
            value_json = value
        elif isinstance(value, str):
            value_text = value
        elif value is not None:
            raise ValueError("Unsupported value type")

        metric = HealthMetric(
            user_id=user_id,
            type_code=type_code,
            value_number=value_number,
            value_text=value_text,
            value_json=value_json,
            recorded_at=recorded_at,
            source=source,
            unit=unit or (metric_type.unit if metric_type else None),
            metadata_json=metadata,
            tags_json=tags,
            dedup_hash=dedup_hash,
        )
        created = self.repo.create_metric(metric)
        deduplicated = created is not metric
        return created, deduplicated

    def batch_store_metrics(
        self, metrics: Iterable[Dict]
    ) -> List[tuple[HealthMetric, bool]]:
        created: List[tuple[HealthMetric, bool]] = []
        for payload in metrics:
            created_metric, dedup = self.store_metric(**payload)
            created.append((created_metric, dedup))
        return created

    def query_metrics(
        self,
        *,
        user_id: str,
        type_code: Optional[str],
        limit: int,
        order: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        source: Optional[str],
    ) -> List[HealthMetric]:
        return self.repo.query_metrics(
            user_id=user_id,
            type_code=type_code,
            limit=limit,
            order=order,
            start_time=start_time,
            end_time=end_time,
            source=source,
        )

    def delete_metric(self, user_id: str, record_id: str) -> bool:
        return self.repo.delete_metric(user_id, record_id)

    def trend_summary(
        self,
        *,
        user_id: str,
        type_code: str,
        metric_field: Optional[str],
        group_by: str,
        lookback_days: Optional[int] = None,
    ) -> Dict:
        start_time = None
        if lookback_days:
            start_time = datetime.utcnow() - timedelta(days=lookback_days)
        metrics = self.repo.list_for_trend(user_id, type_code, metric_field, start_time)
        if not metrics:
            return {"points": [], "stats": {"slope": 0, "count": 0}}
        buckets = group_by_timepoints(metrics, group_by, metric_field)
        points = []
        for key in sorted(buckets.keys()):
            bucket = buckets[key]
            points.append({
                "time_bucket": key,
                "average": bucket["total"] / bucket["count"],
                "count": bucket["count"],
            })
        slope = _compute_slope(points)
        return {
            "points": points,
            "stats": {"slope": slope, "count": len(metrics)},
        }

    def list_metric_types(self) -> List[Dict]:
        return [asdict(item) for item in list_metric_types()]


def _compute_slope(points: List[Dict[str, float]]) -> float:
    if len(points) < 2:
        return 0.0
    xs = list(range(len(points)))
    ys = [point["average"] for point in points]
    n = len(points)
    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_x2 = sum(x * x for x in xs)
    denominator = n * sum_x2 - sum_x ** 2
    if denominator == 0:
        return 0.0
    slope = (n * sum_xy - sum_x * sum_y) / denominator
    return slope
