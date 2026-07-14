"""DSA service facade for the ExternalTool adapter contract."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .contract import CAPABILITY_FUNCTIONS, MAX_CONTRACT_VERSION, MIN_CONTRACT_VERSION
from .errors import ExternalToolExtensionError, translate_adapter_error
from .loader import ExternalToolLoader


class ExternalToolService:
    def __init__(self, config: Any, *, loader: Optional[ExternalToolLoader] = None) -> None:
        self.config = config
        self.loader = loader or ExternalToolLoader(
            enabled=bool(getattr(config, "external_tool_enabled", False)),
            adapter_module=str(getattr(config, "external_tool_adapter_module", "") or ""),
            contract_min=int(getattr(config, "external_tool_contract_min", MIN_CONTRACT_VERSION)),
            contract_max=int(getattr(config, "external_tool_contract_max", MAX_CONTRACT_VERSION)),
        )

    def status(self) -> Dict[str, Any]:
        payload = self.loader.status()
        payload["supported_contract"] = {
            "min": int(getattr(self.config, "external_tool_contract_min", MIN_CONTRACT_VERSION)),
            "max": int(getattr(self.config, "external_tool_contract_max", MAX_CONTRACT_VERSION)),
        }
        return payload

    def capabilities(self) -> Dict[str, Any]:
        status = self._require_available_status()
        return {
            "contract_version": status["contract_version"],
            "engine_version": status.get("engine_version"),
            "capabilities": list(status.get("capabilities") or []),
        }

    def methods(self) -> Dict[str, Any]:
        result = self._call("list_research_methods")
        if not isinstance(result, list):
            raise ExternalToolExtensionError(
                "external_tool_invalid_response",
                "ExternalTool 方法列表格式无效",
            )
        return {"methods": result, "method_count": len(result)}

    def method_schema(self, method_id: str) -> Dict[str, Any]:
        result = self._call("get_research_method_schema", method_id)
        if not isinstance(result, dict):
            raise ExternalToolExtensionError(
                "external_tool_invalid_response",
                "ExternalTool 方法 Schema 格式无效",
            )
        return result

    def run_method(
        self,
        method_id: str,
        payload: Dict[str, Any],
        *,
        progress_callback=None,
    ) -> Dict[str, Any]:
        return self._dict_result(
            self._call(
                "run_research_method",
                method_id,
                dict(payload or {}),
                progress_callback=progress_callback,
            )
        )

    def run_capability(self, capability: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        function_name = CAPABILITY_FUNCTIONS.get(capability)
        if function_name is None:
            raise ExternalToolExtensionError(
                "external_tool_capability_not_found",
                f"未知 ExternalTool 能力: {capability}",
                status_code=404,
            )
        return self._dict_result(self._call(function_name, dict(payload or {})))

    def _require_available_status(self) -> Dict[str, Any]:
        status = self.loader.status()
        if not status.get("available"):
            diagnostics = status.get("diagnostics") if isinstance(status.get("diagnostics"), dict) else {}
            raise ExternalToolExtensionError(
                str(diagnostics.get("reason") or "external_tool_unavailable"),
                str(status.get("message") or "ExternalTool 当前不可用"),
                status_code=409 if status.get("state") == "incompatible" else 424,
            )
        return status

    def _call(self, function_name: str, *args, **kwargs):
        try:
            adapter = self.loader.load()
            return getattr(adapter, function_name)(*args, **kwargs)
        except ExternalToolExtensionError:
            raise
        except Exception as exc:
            raise translate_adapter_error(exc) from exc

    @staticmethod
    def _dict_result(result: Any) -> Dict[str, Any]:
        if not isinstance(result, dict):
            raise ExternalToolExtensionError(
                "external_tool_invalid_response",
                "ExternalTool 执行结果格式无效",
            )
        return result
