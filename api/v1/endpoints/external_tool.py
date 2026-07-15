# -*- coding: utf-8 -*-
"""Optional ExternalTool research APIs."""

from __future__ import annotations

import base64
import binascii
import hashlib
from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from api.deps import get_config_dep
from api.v1.errors import api_error
from src.config import Config
from src.extensions.external_tool.errors import ExternalToolExtensionError, sanitize_adapter_payload
from src.extensions.external_tool.service import ExternalToolService
from src.extensions.external_tool.task_handlers import REPORT_TYPE_PREFIX, ExternalToolTaskHandlers
from src.services.task_queue import TaskStatus as QueueTaskStatus
from src.services.task_queue import get_task_queue

router = APIRouter()


class ExternalToolTaskRequest(BaseModel):
    payload: Dict[str, Any] = Field(default_factory=dict)


class ExternalToolTaskAccepted(BaseModel):
    task_id: str
    trace_id: str
    status: str
    progress: int = 0
    message: Optional[str] = None


class ExternalToolTaskStatus(BaseModel):
    task_id: str
    trace_id: str
    status: str
    progress: int = 0
    message: Optional[str] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


def _service(config: Config) -> ExternalToolService:
    return ExternalToolService(config)


def _raise_extension_error(exc: ExternalToolExtensionError):
    raise api_error(
        exc.status_code,
        exc.code,
        exc.message,
        detail=exc.detail or None,
    ) from exc


@router.get("/status")
def external_tool_status(config: Config = Depends(get_config_dep)) -> Dict[str, Any]:
    return _service(config).status()


@router.get("/capabilities")
def external_tool_capabilities(config: Config = Depends(get_config_dep)) -> Dict[str, Any]:
    try:
        return _service(config).capabilities()
    except ExternalToolExtensionError as exc:
        _raise_extension_error(exc)


@router.get("/methods")
def external_tool_methods(config: Config = Depends(get_config_dep)) -> Dict[str, Any]:
    try:
        return _service(config).methods()
    except ExternalToolExtensionError as exc:
        _raise_extension_error(exc)


@router.get("/watchlists")
def external_tool_watchlists(config: Config = Depends(get_config_dep)) -> Dict[str, Any]:
    try:
        return _service(config).watchlists()
    except ExternalToolExtensionError as exc:
        _raise_extension_error(exc)


@router.get("/formulas/catalog")
def external_tool_formula_catalog(config: Config = Depends(get_config_dep)) -> Dict[str, Any]:
    try:
        return _service(config).formula_catalog()
    except ExternalToolExtensionError as exc:
        _raise_extension_error(exc)


@router.get("/surfaces/{surface_id}")
def external_tool_surface_manifest(
    surface_id: str,
    config: Config = Depends(get_config_dep),
) -> Dict[str, Any]:
    try:
        manifest = _service(config).surface_manifest(surface_id)
    except ExternalToolExtensionError as exc:
        _raise_extension_error(exc)
    encoded_surface = quote(surface_id, safe="")
    asset_prefix = f"/api/v1/external-tool/surfaces/{encoded_surface}/assets"
    return {
        "surface_contract_version": manifest["surface_contract_version"],
        "surface_id": manifest["surface_id"],
        "entry_url": f"{asset_prefix}/{quote(manifest['entry_asset'], safe='')}",
        "stylesheet_urls": [
            f"{asset_prefix}/{quote(asset, safe='')}"
            for asset in manifest["stylesheet_assets"]
        ],
    }


@router.get("/surfaces/{surface_id}/assets/{asset_path:path}")
def external_tool_surface_asset(
    surface_id: str,
    asset_path: str,
    config: Config = Depends(get_config_dep),
) -> Response:
    try:
        payload = _service(config).surface_asset(surface_id, asset_path)
        content = base64.b64decode(payload["content_base64"], validate=True)
    except (binascii.Error, ValueError, KeyError) as exc:
        _raise_extension_error(
            ExternalToolExtensionError(
                "external_tool_invalid_response",
                "ExternalTool 托管页面资源编码无效",
            )
        )
    except ExternalToolExtensionError as exc:
        _raise_extension_error(exc)
    digest = hashlib.sha256(content).hexdigest()
    if digest != payload["sha256"]:
        _raise_extension_error(
            ExternalToolExtensionError(
                "external_tool_invalid_response",
                "ExternalTool 托管页面资源校验失败",
            )
        )
    return Response(
        content=content,
        media_type=payload["media_type"],
        headers={"Cache-Control": "no-cache", "ETag": f'"{digest}"'},
    )


@router.get("/methods/{method_id}/schema")
def external_tool_method_schema(
    method_id: str,
    config: Config = Depends(get_config_dep),
) -> Dict[str, Any]:
    try:
        return _service(config).method_schema(method_id)
    except ExternalToolExtensionError as exc:
        _raise_extension_error(exc)


@router.post("/methods/{method_id}/tasks", status_code=202, response_model=ExternalToolTaskAccepted)
def external_tool_method_task(
    method_id: str,
    request: ExternalToolTaskRequest,
    config: Config = Depends(get_config_dep),
) -> ExternalToolTaskAccepted:
    return _submit_task(config, "method", request.payload, method_id=method_id)


@router.post("/formulas/run/tasks", status_code=202, response_model=ExternalToolTaskAccepted)
def external_tool_formula_task(
    request: ExternalToolTaskRequest,
    config: Config = Depends(get_config_dep),
) -> ExternalToolTaskAccepted:
    return _submit_task(config, "formula", request.payload)


@router.post("/market-indicators/tasks", status_code=202, response_model=ExternalToolTaskAccepted)
def external_tool_market_indicator_task(
    request: ExternalToolTaskRequest,
    config: Config = Depends(get_config_dep),
) -> ExternalToolTaskAccepted:
    return _submit_task(config, "market_indicators", request.payload)


@router.post("/grid/tasks", status_code=202, response_model=ExternalToolTaskAccepted)
def external_tool_grid_task(
    request: ExternalToolTaskRequest,
    config: Config = Depends(get_config_dep),
) -> ExternalToolTaskAccepted:
    return _submit_task(config, "grid", request.payload)


@router.post("/backtests/tasks", status_code=202, response_model=ExternalToolTaskAccepted)
def external_tool_backtest_task(
    request: ExternalToolTaskRequest,
    config: Config = Depends(get_config_dep),
) -> ExternalToolTaskAccepted:
    return _submit_task(config, "backtest", request.payload)


@router.post("/daily-report/tasks", status_code=202, response_model=ExternalToolTaskAccepted)
def external_tool_daily_report_task(
    request: ExternalToolTaskRequest,
    config: Config = Depends(get_config_dep),
) -> ExternalToolTaskAccepted:
    return _submit_task(config, "daily_report", request.payload)


@router.get("/tasks/{task_id}", response_model=ExternalToolTaskStatus)
def external_tool_task_status(
    task_id: str,
    config: Config = Depends(get_config_dep),
) -> ExternalToolTaskStatus:
    task = get_task_queue().get_task(task_id)
    if task is None or not task.report_type.startswith(REPORT_TYPE_PREFIX):
        raise api_error(
            404,
            "external_tool_task_not_found",
            f"ExternalTool 任务 {task_id} 不存在或已过期",
        )
    adapter_module = str(getattr(config, "external_tool_adapter_module", "") or "")
    safe_task = sanitize_adapter_payload(
        {
            "message": task.message,
            "error": task.error,
            "result": task.result if task.status == QueueTaskStatus.COMPLETED else None,
        },
        adapter_module=adapter_module,
    )
    result = safe_task["result"] if isinstance(safe_task.get("result"), dict) else None
    return ExternalToolTaskStatus(
        task_id=task.task_id,
        trace_id=task.trace_id or task.task_id,
        status=task.status.value if isinstance(task.status, QueueTaskStatus) else str(task.status),
        progress=task.progress,
        message=safe_task.get("message"),
        error=safe_task.get("error"),
        result=result,
    )


def _submit_task(
    config: Config,
    capability: str,
    payload: Dict[str, Any],
    *,
    method_id: Optional[str] = None,
) -> ExternalToolTaskAccepted:
    try:
        service = _service(config)
        service.capabilities()
        task = ExternalToolTaskHandlers(config, service=service).submit(
            capability,
            payload,
            method_id=method_id,
        )
    except ExternalToolExtensionError as exc:
        _raise_extension_error(exc)
    return ExternalToolTaskAccepted(
        task_id=task.task_id,
        trace_id=task.trace_id or task.task_id,
        status=task.status.value if isinstance(task.status, QueueTaskStatus) else str(task.status),
        progress=task.progress,
        message=task.message,
    )
