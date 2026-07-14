"""Lazy loader for the optional ExternalTool Python package."""

from __future__ import annotations

import importlib
import logging
import re
from types import ModuleType
from typing import Any, Dict, Optional

from .contract import validate_adapter, validate_status
from .errors import ExternalToolExtensionError, sanitize_message

logger = logging.getLogger(__name__)
_MODULE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")


class ExternalToolLoader:
    """Load only the fixed adapter module and keep failures local to the extension."""

    def __init__(
        self,
        *,
        enabled: bool,
        adapter_module: str = "",
        contract_min: int = 1,
        contract_max: int = 1,
    ) -> None:
        self.enabled = bool(enabled)
        self.adapter_module = str(adapter_module or "").strip()
        self.contract_min = int(contract_min)
        self.contract_max = int(contract_max)
        self._adapter: Optional[ModuleType] = None
        self._status: Optional[Dict[str, Any]] = None

    def status(self) -> Dict[str, Any]:
        if not self.enabled:
            return self._base_status("disabled", "ExternalTool 扩展未启用")
        try:
            adapter = self.load()
            status = validate_status(
                adapter.get_status(),
                minimum=self.contract_min,
                maximum=self.contract_max,
            )
        except ExternalToolExtensionError as exc:
            states = {
                "external_tool_not_installed": "missing",
                "external_tool_incompatible": "incompatible",
                "external_tool_dependency_missing": "degraded",
            }
            return self._base_status(
                states.get(exc.code, "degraded"),
                exc.message,
                diagnostics={"reason": exc.code},
            )
        except Exception as exc:  # defensive boundary for third-party package import
            logger.warning("ExternalTool status check failed: %s", sanitize_message(str(exc)))
            return self._base_status(
                "unavailable",
                "ExternalTool 状态检查失败",
                diagnostics={"reason": "external_tool_status_failed", "error_type": type(exc).__name__},
            )
        payload = dict(status)
        available = bool(status.get("available", True))
        payload.update({
            "enabled": True,
            "available": available,
            "state": "available" if available else "degraded",
        })
        self._status = payload
        return payload

    def load(self) -> ModuleType:
        if not self.enabled:
            raise ExternalToolExtensionError(
                "external_tool_disabled",
                "ExternalTool 扩展未启用",
                status_code=404,
            )
        if self._adapter is not None:
            return self._adapter
        if not _MODULE_PATTERN.fullmatch(self.adapter_module):
            raise ExternalToolExtensionError(
                "external_tool_configuration_missing",
                "未配置有效的外部工具适配模块",
            )
        try:
            adapter = importlib.import_module(self.adapter_module)
        except ModuleNotFoundError as exc:
            module_root = self.adapter_module.partition(".")[0]
            if exc.name in {module_root, self.adapter_module}:
                raise ExternalToolExtensionError(
                    "external_tool_not_installed",
                    "未安装 ExternalTool，请按扩展文档安装固定版本",
                ) from exc
            raise ExternalToolExtensionError(
                "external_tool_dependency_missing",
                f"ExternalTool 缺少运行依赖: {exc.name or 'unknown'}",
            ) from exc
        except Exception as exc:
            raise ExternalToolExtensionError(
                "external_tool_import_failed",
                f"ExternalTool 导入失败: {type(exc).__name__}",
            ) from exc
        try:
            validate_adapter(adapter)
            validate_status(
                adapter.get_status(),
                minimum=self.contract_min,
                maximum=self.contract_max,
            )
        except ValueError as exc:
            raise ExternalToolExtensionError(
                "external_tool_incompatible",
                str(exc),
                status_code=409,
            ) from exc
        except (TypeError, RuntimeError) as exc:
            raise ExternalToolExtensionError(
                "external_tool_invalid_adapter",
                str(exc),
                status_code=409,
            ) from exc
        self._adapter = adapter
        return adapter

    def _base_status(
        self,
        state: str,
        message: str,
        *,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "enabled": self.enabled,
            "available": False,
            "state": state,
            "message": message,
            "capabilities": [],
        }
        if diagnostics:
            payload["diagnostics"] = diagnostics
        return payload
