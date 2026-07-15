from __future__ import annotations

import base64
import hashlib
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.deps import get_config_dep
from api.v1.endpoints import external_tool
from src.services.task_queue import TaskInfo, TaskStatus


def _config(enabled: bool = True, adapter_module: str = "external_tool.adapter"):
    return SimpleNamespace(
        external_tool_enabled=enabled,
        external_tool_adapter_module=adapter_module,
        external_tool_contract_min=1,
        external_tool_contract_max=1,
    )


def _adapter():
    descriptor = {
        "method_id": "example",
        "method_version": 1,
        "title": "示例方法",
        "input_schema": {"type": "object"},
        "output_views": ["summary"],
    }
    return SimpleNamespace(
        get_status=lambda: {
            "available": True,
            "contract_version": 1,
            "engine_version": "test",
            "capabilities": ["research_methods", "formula_canvas", "hosted_surfaces"],
        },
        list_research_methods=lambda: [descriptor],
        get_research_method_schema=lambda method_id: descriptor,
        get_formula_catalog=lambda: {
            "presets": [{"id": "sample"}],
            "functions": [{"name": "plot", "category": "绘图函数"}],
            "syntax_notes": ["script"],
        },
        get_watchlists=lambda: {
            "contract_version": 1,
            "watchlist_count": 1,
            "item_count": 1,
            "default_watchlist_id": 7,
            "watchlists": [{
                "id": 7,
                "name": "关注标的",
                "item_count": 1,
                "items": [{"id": 11, "symbol": "000001", "name": "上证指数", "latest_date": "2026-07-14"}],
            }],
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
        run_research_method=lambda method_id, request, progress_callback=None: {"method_id": method_id},
        run_formula=lambda request: {"capability": "formula"},
        run_market_indicators=lambda request: {"capability": "market"},
        run_grid_optimization=lambda request: {"capability": "grid"},
        run_strategy_backtest=lambda request: {"capability": "backtest"},
        generate_daily_report=lambda request: {"status": "success", "sections": []},
    )


def _client(config=None) -> TestClient:
    app = FastAPI()
    app.include_router(external_tool.router, prefix="/api/v1/external-tool")
    app.dependency_overrides[get_config_dep] = lambda: config or _config()
    return TestClient(app)


def test_status_and_generic_method_endpoints() -> None:
    with patch("src.extensions.external_tool.loader.importlib.import_module", return_value=_adapter()):
        client = _client()
        status = client.get("/api/v1/external-tool/status")
        methods = client.get("/api/v1/external-tool/methods")
        schema = client.get("/api/v1/external-tool/methods/example/schema")
        formula_catalog = client.get("/api/v1/external-tool/formulas/catalog")
    assert status.status_code == 200
    assert status.json()["state"] == "available"
    assert methods.json()["methods"][0]["method_id"] == "example"
    assert schema.json()["method_id"] == "example"
    assert formula_catalog.json()["functions"][0]["name"] == "plot"


def test_watchlists_endpoint_uses_optional_adapter_capability() -> None:
    adapter = _adapter()
    original_status = adapter.get_status
    adapter.get_status = lambda: {**original_status(), "capabilities": ["research_methods", "watchlists"]}
    with patch("src.extensions.external_tool.loader.importlib.import_module", return_value=adapter):
        response = _client().get("/api/v1/external-tool/watchlists")

    assert response.status_code == 200
    assert response.json()["default_watchlist_id"] == 7
    assert response.json()["watchlists"][0]["items"][0]["latest_date"] == "2026-07-14"


def test_hosted_surface_manifest_exposes_same_origin_asset_urls() -> None:
    with patch("src.extensions.external_tool.loader.importlib.import_module", return_value=_adapter()):
        response = _client().get("/api/v1/external-tool/surfaces/research")

    assert response.status_code == 200
    assert response.json() == {
        "surface_contract_version": 1,
        "surface_id": "research",
        "entry_url": "/api/v1/external-tool/surfaces/research/assets/research-surface.js",
        "stylesheet_urls": [
            "/api/v1/external-tool/surfaces/research/assets/research-surface.css"
        ],
    }


def test_hosted_surface_asset_is_verified_and_served() -> None:
    with patch("src.extensions.external_tool.loader.importlib.import_module", return_value=_adapter()):
        response = _client().get(
            "/api/v1/external-tool/surfaces/research/assets/research-surface.js"
        )

    assert response.status_code == 200
    assert response.content == b"export const ready = true"
    assert response.headers["content-type"].startswith("text/javascript")
    assert response.headers["etag"]


def test_disabled_capability_returns_stable_error() -> None:
    response = _client(_config(enabled=False)).get("/api/v1/external-tool/capabilities")
    assert response.status_code == 424
    assert response.json()["detail"]["error"] == "external_tool_unavailable"


def test_task_submission_returns_202() -> None:
    task = TaskInfo(
        task_id="task-1",
        trace_id="task-1",
        stock_code="external_tool",
        report_type="external_tool:formula",
        message="已提交",
    )
    with (
        patch("src.extensions.external_tool.loader.importlib.import_module", return_value=_adapter()),
        patch.object(external_tool.ExternalToolTaskHandlers, "submit", return_value=task),
    ):
        response = _client().post(
            "/api/v1/external-tool/formulas/run/tasks",
            json={"payload": {"code": "CLOSE"}},
        )
    assert response.status_code == 202
    assert response.json()["task_id"] == "task-1"


def test_task_polling_only_exposes_external_tool_tasks() -> None:
    local_path = "C:" + "\\private\\status.yaml"
    email = "person" + "@example.test"
    token = "github" + "_pat_example_secret"
    task = TaskInfo(
        task_id="task-2",
        trace_id="task-2",
        stock_code="external_tool",
        report_type="external_tool:method",
        status=TaskStatus.COMPLETED,
        progress=100,
        message=f"PrivateEngine 读取 {local_path}",
        error=f"{email} token={token}",
        result={"method_id": "example", "source": "private_engine", "markdown": "PrivateEngine 结果"},
    )
    queue = SimpleNamespace(get_task=lambda task_id: task)
    with patch("api.v1.endpoints.external_tool.get_task_queue", return_value=queue):
        response = _client(_config(adapter_module="private_engine.adapter")).get("/api/v1/external-tool/tasks/task-2")
    assert response.status_code == 200
    assert response.json()["result"]["method_id"] == "example"
    rendered = response.text.lower()
    assert "privateengine" not in rendered
    assert "private_engine" not in rendered
    assert local_path.lower().replace("\\", "\\\\") not in rendered
    assert email not in rendered
    assert token not in rendered
