from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class MetricType:
    type_code: str
    name: str
    unit: Optional[str]
    description: str
    value_schema: str


CATALOG: List[MetricType] = [
    MetricType(
        type_code="body/weight",
        name="体重",
        unit="kg",
        description="用户体重",
        value_schema="number",
    ),
    MetricType(
        type_code="body/body_fat_rate",
        name="体脂率",
        unit="%",
        description="体脂率",
        value_schema="number",
    ),
    MetricType(
        type_code="medical/blood_glucose",
        name="空腹血糖",
        unit="mmol/L",
        description="空腹血糖",
        value_schema="number",
    ),
    MetricType(
        type_code="medical/uric_acid",
        name="尿酸",
        unit="umol/L",
        description="尿酸",
        value_schema="number",
    ),
    MetricType(
        type_code="medical/creatinine",
        name="肌酐",
        unit="umol/L",
        description="肌酐",
        value_schema="number",
    ),
    MetricType(
        type_code="sport/running_session",
        name="跑步记录",
        unit=None,
        description="单次跑步训练记录",
        value_schema="object",
    ),
]


CATALOG_INDEX: Dict[str, MetricType] = {item.type_code: item for item in CATALOG}


def list_metric_types() -> List[MetricType]:
    return CATALOG


def get_metric_type(type_code: str) -> Optional[MetricType]:
    return CATALOG_INDEX.get(type_code)
