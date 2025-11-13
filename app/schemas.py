from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, root_validator, validator


class MetadataModel(BaseModel):
    file_hash: Optional[str]
    raw_text: Optional[str]
    extra: Dict[str, Any] = Field(default_factory=dict)

    @root_validator(pre=True)
    def allow_arbitrary_keys(cls, values):
        known_keys = {"file_hash", "raw_text"}
        extra = {k: v for k, v in values.items() if k not in known_keys}
        base = {k: v for k, v in values.items() if k in known_keys}
        base.setdefault("extra", {}).update(extra)
        return base


class HealthStoreMetricInput(BaseModel):
    user_id: str
    type: str
    value: Union[float, int, str, Dict[str, Any]]
    unit: Optional[str] = None
    recorded_at: Optional[datetime]
    source: str
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[Dict[str, Any]] = None

class HealthStoreMetricOutput(BaseModel):
    record_id: str
    deduplicated: bool = False


class HealthBatchStoreMetricsInput(BaseModel):
    records: List[HealthStoreMetricInput]


class HealthBatchStoreMetricsOutput(BaseModel):
    records: List[HealthStoreMetricOutput]


class QueryFilters(BaseModel):
    user_id: str
    type: Optional[str] = None
    limit: int = 20
    order: str = "desc"
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    source: Optional[str]

    @validator("order")
    def validate_order(cls, value: str) -> str:
        if value not in {"asc", "desc"}:
            raise ValueError("order must be 'asc' or 'desc'")
        return value


class HealthQueryMetricsOutput(BaseModel):
    records: List[Dict[str, Any]]


class TrendSummaryInput(BaseModel):
    user_id: str
    type: str
    metric_field: Optional[str]
    group_by: str = "week"
    lookback_days: Optional[int] = None

    @validator("group_by")
    def validate_group_by(cls, value: str) -> str:
        if value not in {"day", "week", "month"}:
            raise ValueError("group_by must be day/week/month")
        return value


class TrendSummaryOutput(BaseModel):
    points: List[Dict[str, Any]]
    stats: Dict[str, Any]


class HealthDeleteRecordInput(BaseModel):
    user_id: str
    record_id: str


class HealthDeleteRecordOutput(BaseModel):
    success: bool
    message: Optional[str]


class HealthListMetricTypesOutput(BaseModel):
    types: List[Dict[str, Any]]


class MCPRequest(BaseModel):
    jsonrpc: str
    method: str
    id: Optional[Union[str, int]]
    params: Dict[str, Any]


class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]]
    result: Any = None
    error: Optional[Dict[str, Any]] = None
