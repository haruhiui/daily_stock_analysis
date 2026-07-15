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

    def formula_catalog(self) -> Dict[str, Any]:
        self._require_capability("formula_canvas", "当前 ExternalTool 版本不支持公式画布")
        result = self._dict_result(self._call("get_formula_catalog"))
        if not isinstance(result.get("functions"), list) or not isinstance(result.get("presets"), list):
            raise ExternalToolExtensionError(
                "external_tool_invalid_response",
                "ExternalTool 公式目录格式无效",
            )
        return result

    def watchlists(self) -> Dict[str, Any]:
        status = self._require_available_status()
        if "watchlists" not in set(status.get("capabilities") or []):
            raise ExternalToolExtensionError(
                "external_tool_capability_not_found",
                "当前 ExternalTool 版本不支持自选列表",
                status_code=404,
            )
        result = self._dict_result(self._call("get_watchlists"))
        if not isinstance(result.get("watchlists"), list):
            raise ExternalToolExtensionError(
                "external_tool_invalid_response",
                "ExternalTool 自选列表格式无效",
            )
        return result

    def surface_manifest(self, surface_id: str) -> Dict[str, Any]:
        self._require_capability("hosted_surfaces", "当前 ExternalTool 版本不支持托管页面")
        result = self._dict_result(self._call("get_hosted_surface_manifest", surface_id))
        entry_asset = result.get("entry_asset")
        stylesheets = result.get("stylesheet_assets")
        if (
            result.get("surface_id") != surface_id
            or not self._is_asset_name(entry_asset)
            or not isinstance(stylesheets, list)
            or any(not self._is_asset_name(item) for item in stylesheets)
        ):
            raise ExternalToolExtensionError(
                "external_tool_invalid_response",
                "ExternalTool 托管页面清单格式无效",
            )
        return result

    def surface_asset(self, surface_id: str, asset_path: str) -> Dict[str, Any]:
        self._require_capability("hosted_surfaces", "当前 ExternalTool 版本不支持托管页面")
        result = self._dict_result(self._call("get_hosted_surface_asset", surface_id, asset_path))
        if (
            result.get("surface_id") != surface_id
            or result.get("asset_path") != asset_path
            or not isinstance(result.get("content_base64"), str)
            or not isinstance(result.get("media_type"), str)
            or not isinstance(result.get("sha256"), str)
        ):
            raise ExternalToolExtensionError(
                "external_tool_invalid_response",
                "ExternalTool 托管页面资源格式无效",
            )
        return result

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

    def _require_capability(self, capability: str, message: str) -> Dict[str, Any]:
        status = self._require_available_status()
        if capability not in set(status.get("capabilities") or []):
            raise ExternalToolExtensionError(
                "external_tool_capability_not_found",
                message,
                status_code=404,
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

    @staticmethod
    def _is_asset_name(value: Any) -> bool:
        return (
            isinstance(value, str)
            and bool(value)
            and "/" not in value
            and "\\" not in value
            and value not in {".", ".."}
        )
