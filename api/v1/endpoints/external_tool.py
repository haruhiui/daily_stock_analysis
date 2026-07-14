# -*- coding: utf-8 -*-
"""Optional ExternalTool research APIs."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
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
