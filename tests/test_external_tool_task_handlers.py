from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from src.extensions.external_tool.task_handlers import ExternalToolTaskHandlers
from src.services.task_queue import TaskInfo


_TEST_PATH = "C:" + "\\private\\input.yaml"
_TEST_EMAIL = "person" + "@example.test"
_TEST_TOKEN = "github" + "_pat_example_secret"


class FakeQueue:
    def __init__(self) -> None:
        self.progress = []
        self.run_task = None

    def update_task_progress(self, task_id, progress, message):
        self.progress.append((task_id, progress, message))

    def submit_background_task(self, run_task, **kwargs):
        self.run_task = run_task
        return TaskInfo(
            task_id=kwargs["task_id"],
            trace_id=kwargs["trace_id"],
            stock_code=kwargs["stock_code"],
            report_type=kwargs["report_type"],
            message=kwargs["message"],
        )


class FakeService:
    def run_method(self, method_id, payload, *, progress_callback=None):
        progress_callback(1, 2, "第一项")
        progress_callback(2, 2, "第二项")
        return {"method_id": method_id, "failed_items": [], "result": payload}

    def run_capability(self, capability, payload):
        return {"capability": capability, "result": payload}


class PrivateIdentityService(FakeService):
    def run_method(self, method_id, payload, *, progress_callback=None):
        progress_callback(1, 1, f"PrivateEngine 读取 {_TEST_PATH} {_TEST_EMAIL}")
        return {
            "source": "private_engine",
            "markdown": f"PrivateEngine token={_TEST_TOKEN}",
        }


def test_method_task_uses_existing_queue_and_reports_real_fraction() -> None:
    queue = FakeQueue()
    handlers = ExternalToolTaskHandlers(SimpleNamespace(), service=FakeService())
    with patch("src.extensions.external_tool.task_handlers.get_task_queue", return_value=queue):
        task = handlers.submit("method", {"symbols": ["TEST"]}, method_id="example")
        result = queue.run_task()
    assert task.report_type == "external_tool:method"
    assert result["method_id"] == "example"
    assert any("1/2" in message for _, _, message in queue.progress)
    assert any("2/2" in message for _, _, message in queue.progress)


def test_capability_task_returns_adapter_result() -> None:
    queue = FakeQueue()
    handlers = ExternalToolTaskHandlers(SimpleNamespace(), service=FakeService())
    with patch("src.extensions.external_tool.task_handlers.get_task_queue", return_value=queue):
        handlers.submit("formula", {"code": "CLOSE"})
        result = queue.run_task()
    assert result["capability"] == "formula"


def test_task_progress_and_results_hide_private_adapter_identity_and_secrets() -> None:
    queue = FakeQueue()
    config = SimpleNamespace(external_tool_adapter_module="private_engine.adapter")
    handlers = ExternalToolTaskHandlers(config, service=PrivateIdentityService())
    with patch("src.extensions.external_tool.task_handlers.get_task_queue", return_value=queue):
        handlers.submit("method", {}, method_id="example")
        result = queue.run_task()

    rendered = f"{queue.progress} {result}".lower()
    assert "privateengine" not in rendered
    assert "private_engine" not in rendered
    assert _TEST_PATH.lower() not in rendered
    assert _TEST_EMAIL not in rendered
    assert _TEST_TOKEN not in rendered
