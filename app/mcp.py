from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .schemas import MCPRequest, MCPResponse
from .services import MetricService

router = APIRouter(prefix="/mcp", tags=["mcp"])


TOOLS = {
    "health_store_metric": "Store a single health metric record",
    "health_batch_store_metrics": "Store multiple health metric records in batch",
    "health_query_metrics": "Query stored metrics",
    "health_trend_summary": "Return aggregated trend information",
    "health_delete_record": "Delete a metric record",
    "health_list_metric_types": "List supported metric types",
}


@router.post("/tools", response_model=MCPResponse)
def handle_json_rpc(request: MCPRequest, session: Session = Depends(get_db)) -> Dict[str, Any]:
    if request.jsonrpc != "2.0":
        raise HTTPException(status_code=400, detail="Unsupported JSON-RPC version")

    service = MetricService(session)

    if request.method == "tools.list":
        return MCPResponse(
            id=request.id,
            result={
                "tools": [
                    {"name": name, "description": description}
                    for name, description in TOOLS.items()
                ]
            },
        )
    if request.method == "tools.call":
        params = request.params or {}
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name not in TOOLS:
            raise HTTPException(status_code=404, detail=f"Unknown tool: {name}")
        result = _invoke_tool(name, arguments, service)
        return MCPResponse(id=request.id, result=result)

    raise HTTPException(status_code=404, detail=f"Unknown method: {request.method}")


def _invoke_tool(name: str, arguments: Dict[str, Any], service: MetricService) -> Dict[str, Any]:
    if name == "health_store_metric":
        metric, dedup = _safe_store_metric(arguments, service)
        return {"record_id": metric.id, "deduplicated": dedup}
    if name == "health_batch_store_metrics":
        records = []
        for record in arguments.get("records", []):
            metric, dedup = _safe_store_metric(record, service)
            records.append({"record_id": metric.id, "deduplicated": dedup})
        return {"records": records}
    if name == "health_query_metrics":
        metrics = service.query_metrics(
            user_id=arguments["user_id"],
            type_code=arguments.get("type"),
            limit=arguments.get("limit", 20),
            order=arguments.get("order", "desc"),
            start_time=arguments.get("start_time"),
            end_time=arguments.get("end_time"),
            source=arguments.get("source"),
        )
        return {"records": [metric.to_dict() for metric in metrics]}
    if name == "health_trend_summary":
        try:
            summary = service.trend_summary(
                user_id=arguments["user_id"],
                type_code=arguments["type"],
                metric_field=arguments.get("metric_field"),
                group_by=arguments.get("group_by", "week"),
                lookback_days=arguments.get("lookback_days"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return summary
    if name == "health_delete_record":
        deleted = service.delete_metric(arguments["user_id"], arguments["record_id"])
        return {"success": deleted, "message": None if deleted else "record not found"}
    if name == "health_list_metric_types":
        return {"types": service.list_metric_types()}
    raise HTTPException(status_code=404, detail=f"Unsupported tool: {name}")


def _safe_store_metric(arguments: Dict[str, Any], service: MetricService):
    try:
        return service.store_metric(
            user_id=arguments["user_id"],
            type_code=arguments["type"],
            value=arguments.get("value"),
            unit=arguments.get("unit"),
            recorded_at=arguments.get("recorded_at"),
            source=arguments.get("source", "unknown"),
            metadata=arguments.get("metadata"),
            tags=arguments.get("tags"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
