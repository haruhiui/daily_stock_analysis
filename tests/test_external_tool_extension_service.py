from __future__ import annotations

import base64
import hashlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.extensions.external_tool.errors import ExternalToolExtensionError
from src.extensions.external_tool.loader import ExternalToolLoader
from src.extensions.external_tool.service import ExternalToolService


def _config(*, enabled: bool = True, minimum: int = 1, maximum: int = 1):
    return SimpleNamespace(
        external_tool_enabled=enabled,
        external_tool_adapter_module="external_tool.adapter",
        external_tool_contract_min=minimum,
        external_tool_contract_max=maximum,
    )


def _adapter(*, contract_version: int = 1):
    methods = [
        {"method_id": "first", "method_version": 1, "input_schema": {}, "output_views": ["summary"]},
        {"method_id": "second", "method_version": 1, "input_schema": {}, "output_views": ["table"]},
    ]
    return SimpleNamespace(
        get_status=lambda: {
            "available": True,
            "contract_version": contract_version,
            "engine_version": "test",
            "capabilities": ["research_methods", "daily_report", "hosted_surfaces", "formula_canvas"],
        },
        list_research_methods=lambda: methods,
        get_research_method_schema=lambda method_id: next(
            item for item in methods if item["method_id"] == method_id
        ),
        get_formula_catalog=lambda: {
            "presets": [{"id": "sample"}],
            "functions": [{"name": "plot", "category": "绘图函数"}],
            "syntax_notes": ["script"],
        },
        get_watchlists=lambda: {
            "contract_version": contract_version,
            "watchlist_count": 1,
            "item_count": 1,
            "default_watchlist_id": 1,
            "watchlists": [{"id": 1, "name": "关注标的", "item_count": 1, "items": []}],
        },
        get_hosted_surface_manifest=lambda surface_id: {
            "surface_contract_version": 1,
            "surface_id": surface_id,
            "entry_asset": "research-surface.js",
            "stylesheet_assets": ["research-surface.css"],
        },
        get_hosted_surface_asset=lambda surface_id, asset_path: {
            "surface_id": surface_id,
            "asset_path": asset_path,
            "media_type": "text/javascript",
            "sha256": hashlib.sha256(b"export const ready = true").hexdigest(),
            "content_base64": base64.b64encode(b"export const ready = true").decode("ascii"),
        },
        run_research_method=lambda method_id, request, progress_callback=None: {
            "method_id": method_id,
            "result": request,
        },
        run_formula=lambda request: {"capability": "formula", "result": request},
        run_market_indicators=lambda request: {"capability": "market", "result": request},
        run_grid_optimization=lambda request: {"capability": "grid", "result": request},
        run_strategy_backtest=lambda request: {"capability": "backtest", "result": request},
        generate_daily_report=lambda request: {"status": "success", "sections": []},
    )


def test_disabled_extension_does_not_import_engine() -> None:
    loader = ExternalToolLoader(enabled=False, adapter_module="external_tool.adapter")
    with patch("src.extensions.external_tool.loader.importlib.import_module") as importer:
        status = loader.status()
    assert status["state"] == "disabled"
    assert status["available"] is False
    importer.assert_not_called()


def test_enabled_extension_requires_configured_adapter_module() -> None:
    status = ExternalToolLoader(enabled=True).status()

    assert status["state"] == "degraded"
    assert status["diagnostics"]["reason"] == "external_tool_configuration_missing"


def test_missing_package_is_reported_without_raising() -> None:
    missing = ModuleNotFoundError("No module named 'external_tool'", name="external_tool")
    with patch("src.extensions.external_tool.loader.importlib.import_module", side_effect=missing):
        status = ExternalToolLoader(enabled=True, adapter_module="external_tool.adapter").status()
    assert status["state"] == "missing"
    assert status["diagnostics"]["reason"] == "external_tool_not_installed"


@pytest.mark.parametrize("version", [0, 2])
def test_contract_versions_outside_supported_range_are_incompatible(version: int) -> None:
    with patch("src.extensions.external_tool.loader.importlib.import_module", return_value=_adapter(contract_version=version)):
        status = ExternalToolService(_config()).status()
    assert status["state"] == "incompatible"
    assert status["available"] is False


def test_generic_method_discovery_handles_second_method_without_router_changes() -> None:
    with patch("src.extensions.external_tool.loader.importlib.import_module", return_value=_adapter()):
        service = ExternalToolService(_config())
        result = service.methods()
        executed = service.run_method("second", {"symbols": ["TEST"]})
    assert [item["method_id"] for item in result["methods"]] == ["first", "second"]
    assert executed["method_id"] == "second"


def test_formula_catalog_is_loaded_from_adapter() -> None:
    with patch("src.extensions.external_tool.loader.importlib.import_module", return_value=_adapter()):
        result = ExternalToolService(_config()).formula_catalog()

    assert result["functions"][0]["name"] == "plot"


def test_watchlists_require_declared_optional_capability() -> None:
    adapter = _adapter()
    original_status = adapter.get_status
    adapter.get_status = lambda: {**original_status(), "capabilities": ["research_methods", "daily_report", "watchlists"]}
    with patch("src.extensions.external_tool.loader.importlib.import_module", return_value=adapter):
        result = ExternalToolService(_config()).watchlists()

    assert result["default_watchlist_id"] == 1


def test_watchlists_reject_adapter_without_declared_capability() -> None:
    with patch("src.extensions.external_tool.loader.importlib.import_module", return_value=_adapter()):
        with pytest.raises(ExternalToolExtensionError) as captured:
            ExternalToolService(_config()).watchlists()

    assert captured.value.code == "external_tool_capability_not_found"
    assert captured.value.status_code == 404


def test_hosted_surface_manifest_and_asset_are_validated() -> None:
    with patch("src.extensions.external_tool.loader.importlib.import_module", return_value=_adapter()):
        service = ExternalToolService(_config())
        manifest = service.surface_manifest("research")
        asset = service.surface_asset("research", manifest["entry_asset"])

    assert manifest["entry_asset"] == "research-surface.js"
    assert asset["media_type"] == "text/javascript"


def test_hosted_surface_rejects_nested_asset_names_in_manifest() -> None:
    adapter = _adapter()
    adapter.get_hosted_surface_manifest = lambda surface_id: {
        "surface_contract_version": 1,
        "surface_id": surface_id,
        "entry_asset": "../private.js",
        "stylesheet_assets": [],
    }
    with patch("src.extensions.external_tool.loader.importlib.import_module", return_value=adapter):
        with pytest.raises(ExternalToolExtensionError) as captured:
            ExternalToolService(_config()).surface_manifest("research")

    assert captured.value.code == "external_tool_invalid_response"


def test_capability_dispatch_rejects_unknown_capability() -> None:
    with patch("src.extensions.external_tool.loader.importlib.import_module", return_value=_adapter()):
        service = ExternalToolService(_config())
        with pytest.raises(ExternalToolExtensionError) as captured:
            service.run_capability("unknown", {})
    assert captured.value.code == "external_tool_capability_not_found"
    assert captured.value.status_code == 404
