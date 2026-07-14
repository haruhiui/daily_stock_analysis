"""ExternalTool operations wrapped by DSA's existing task lifecycle."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from src.services.task_queue import TaskInfo, get_task_queue

from .errors import ExternalToolExtensionError, sanitize_adapter_payload
from .service import ExternalToolService

REPORT_TYPE_PREFIX = "external_tool:"


class ExternalToolTaskHandlers:
    def __init__(self, config: Any, *, service: Optional[ExternalToolService] = None) -> None:
        self.service = service or ExternalToolService(config)
        self.adapter_module = str(getattr(config, "external_tool_adapter_module", "") or "")

    def submit(
        self,
        capability: str,
        payload: Dict[str, Any],
        *,
        method_id: Optional[str] = None,
    ) -> TaskInfo:
        task_id = uuid.uuid4().hex
        queue = get_task_queue()

        def run() -> Dict[str, Any]:
            queue.update_task_progress(task_id, 25, "正在调用 ExternalTool 研究引擎")
            try:
                if method_id is not None:
                    def report_progress(completed: int, total: int, message: str) -> None:
                        safe_total = max(1, int(total))
                        safe_completed = max(0, min(safe_total, int(completed)))
                        percent = 25 + round((safe_completed / safe_total) * 60)
                        safe_message = sanitize_adapter_payload(
                            str(message or "正在执行研究方法"),
                            adapter_module=self.adapter_module,
                        )
                        queue.update_task_progress(
                            task_id,
                            percent,
                            f"{safe_completed}/{safe_total} {safe_message}",
                        )

                    result = self.service.run_method(
                        method_id,
                        payload,
                        progress_callback=report_progress,
                    )
                else:
                    result = self.service.run_capability(capability, payload)
            except ExternalToolExtensionError as exc:
                safe_message = sanitize_adapter_payload(exc.message, adapter_module=self.adapter_module)
                safe_detail = sanitize_adapter_payload(exc.detail, adapter_module=self.adapter_module)
                raise ExternalToolExtensionError(
                    exc.code,
                    str(safe_message),
                    status_code=exc.status_code,
                    detail=safe_detail if isinstance(safe_detail, dict) else None,
                ) from exc
            except Exception as exc:
                safe_message = sanitize_adapter_payload(str(exc), adapter_module=self.adapter_module)
                raise RuntimeError(str(safe_message)) from exc
            queue.update_task_progress(task_id, 90, "研究结果已生成，正在整理")
            safe_result = sanitize_adapter_payload(result, adapter_module=self.adapter_module)
            return safe_result if isinstance(safe_result, dict) else {"result": safe_result}

        label = method_id or capability
        return queue.submit_background_task(
            run,
            stock_code="external_tool",
            stock_name=label,
            report_type=f"{REPORT_TYPE_PREFIX}{capability}",
            message="ExternalTool 研究任务已提交",
            task_id=task_id,
            trace_id=task_id,
        )
