import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Optional, Union


def compute_dedup_hash(
    user_id: str,
    type_code: str,
    recorded_at: datetime,
    value: Union[float, str, Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    payload = {
        "user_id": user_id,
        "type": type_code,
        "recorded_at": recorded_at.isoformat(),
        "value": value,
        "metadata": metadata or {},
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def ensure_datetime(value: Optional[Union[str, datetime]]) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return datetime.utcnow()
