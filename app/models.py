import uuid
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import JSON

Base = declarative_base()


class HealthMetric(Base):
    __tablename__ = "health_metrics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), nullable=False, index=True)
    type_code = Column(String(128), nullable=False, index=True)
    value_number = Column(Float, nullable=True)
    value_text = Column(Text, nullable=True)
    value_json = Column(MySQLJSON().with_variant(JSON, "sqlite"), nullable=True)
    recorded_at = Column(DateTime, nullable=False, index=True)
    source = Column(String(32), nullable=False, index=True)
    unit = Column(String(32), nullable=True)
    metadata_json = Column(MySQLJSON().with_variant(JSON, "sqlite"), nullable=True)
    tags_json = Column(MySQLJSON().with_variant(JSON, "sqlite"), nullable=True)
    dedup_hash = Column(String(64), nullable=False, index=True)
    deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "dedup_hash", name="uq_user_dedup"),
        Index("idx_user_type_recorded", "user_id", "type_code", "recorded_at"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.id,
            "user_id": self.user_id,
            "type": self.type_code,
            "value_number": self.value_number,
            "value_text": self.value_text,
            "value": self.value_json,
            "recorded_at": self.recorded_at.isoformat(),
            "source": self.source,
            "unit": self.unit,
            "metadata": self.metadata_json,
            "tags": self.tags_json,
            "deleted": self.deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
