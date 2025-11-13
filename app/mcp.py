from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.responses import EventSourceResponse
from sqlalchemy.orm import Session

from .db import get_db
from .events import event_manager
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


HEARTBEAT_SECONDS = 15


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/tools", response_model=MCPResponse)
async def handle_json_rpc(
    request: MCPRequest, session: Session = Depends(get_db)
) -> Dict[str, Any]:
    if request.jsonrpc != "2.0":
        await event_manager.publish(
            "mcp.error",
            jsonable_encoder(
                {
                    "id": request.id,
                    "method": request.method,
                    "error": "Unsupported JSON-RPC version",
                    "timestamp": _now_iso(),
                }
            ),
        )
        raise HTTPException(status_code=400, detail="Unsupported JSON-RPC version")

    service = MetricService(session)

    if request.method == "tools.list":
        response = MCPResponse(
            id=request.id,
            result={
                "tools": [
                    {"name": name, "description": description}
                    for name, description in TOOLS.items()
                ]
            },
        )
        await event_manager.publish(
            "mcp.tools.list",
            jsonable_encoder(
                {
                    "id": request.id,
                    "tool_names": list(TOOLS.keys()),
                    "timestamp": _now_iso(),
                }
            ),
        )
        return response
    if request.method == "tools.call":
        params = request.params or {}
        name = params.get("name")
        arguments = params.get("arguments", {})
        if name not in TOOLS:
            await event_manager.publish(
                "mcp.tools.error",
                jsonable_encoder(
                    {
                        "id": request.id,
                        "method": request.method,
                        "tool": name,
                        "error": "Unknown tool",
                        "timestamp": _now_iso(),
                    }
                ),
            )
            raise HTTPException(status_code=404, detail=f"Unknown tool: {name}")
        try:
            result = await run_in_threadpool(_invoke_tool, name, arguments, service)
        except HTTPException as exc:
            await event_manager.publish(
                "mcp.tools.error",
                jsonable_encoder(
                    {
                        "id": request.id,
                        "method": request.method,
                        "tool": name,
                        "error": exc.detail,
                        "status": exc.status_code,
                        "timestamp": _now_iso(),
                    }
                ),
            )
            raise
        await event_manager.publish(
            "mcp.tools.call",
            jsonable_encoder(
                {
                    "id": request.id,
                    "tool": name,
                    "arguments": arguments,
                    "result": result,
                    "timestamp": _now_iso(),
                }
            ),
        )
        return MCPResponse(id=request.id, result=result)

    await event_manager.publish(
        "mcp.error",
        jsonable_encoder(
            {
                "id": request.id,
                "method": request.method,
                "error": "Unknown method",
                "timestamp": _now_iso(),
            }
        ),
    )
    raise HTTPException(status_code=404, detail=f"Unknown method: {request.method}")


@router.get("/stream")
async def stream_events(request: Request) -> EventSourceResponse:
    queue = event_manager.subscribe()

    async def event_generator():
        try:
            yield {
                "event": "ready",
                "data": json.dumps(
                    {
                        "timestamp": _now_iso(),
                        "message": "MCP SSE stream established",
                    },
                    ensure_ascii=False,
                ),
            }
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event, payload = await asyncio.wait_for(
                        queue.get(), timeout=HEARTBEAT_SECONDS
                    )
                except asyncio.TimeoutError:
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps(
                            {"timestamp": _now_iso()}, ensure_ascii=False
                        ),
                    }
                    continue
                yield {"event": event, "data": payload}
        finally:
            event_manager.unsubscribe(queue)

    return EventSourceResponse(event_generator())


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
