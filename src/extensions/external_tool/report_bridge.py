"""Compose optional ExternalTool output into DSA's native daily report."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict

from .errors import ExternalToolExtensionError, sanitize_adapter_payload
from .service import ExternalToolService


_SECTION_SEPARATOR = "\n\n---\n\n"
_ERROR_CODE_PATTERN = re.compile(r"^external_tool_[a-z0-9_]+$")
logger = logging.getLogger(__name__)


def report_markdown(report: Dict[str, Any]) -> str:
    """Return fail-open Markdown suitable for DSA email/report composition."""

    sections = report.get("sections") if isinstance(report, dict) else None
    if not isinstance(sections, list):
        return "## 自定义研究\n\nExternalTool 未返回有效报告。"
    rendered = ["## 自定义研究"]
    universe = report.get("research_universe")
    if isinstance(universe, dict):
        count = universe.get("count")
        if isinstance(count, int):
            rendered.append(
                f"研究筛选池：{count} 个标的；候选结果不会自动触发 DSA 深度分析。"
            )
    for section in _ordered_sections(sections):
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or "").strip()
        markdown = str(section.get("markdown") or "").strip()
        if title:
            rendered.append(f"### {title}")
        if markdown:
            rendered.append(markdown)
    if len(rendered) == 1:
        rendered.append("暂无可展示的研究片段。")

    usage_markdown = _data_access_usage_markdown(report.get("data_access_usage"))
    if usage_markdown:
        rendered.append(usage_markdown)

    metadata = []
    trade_date = str(report.get("trade_date") or "").strip()
    if trade_date:
        metadata.append(f"数据截止日：{trade_date}")
    source = str(report.get("source") or "").strip()
    if source:
        metadata.append(f"数据来源：{source}")
    if metadata:
        rendered.append("；".join(metadata))

    limitations = report.get("limitations")
    if isinstance(limitations, list) and limitations:
        rendered.append("### 数据限制")
        rendered.append("\n".join(f"- {item}" for item in limitations if str(item).strip()))
    disclaimer = str(report.get("disclaimer") or "").strip()
    if disclaimer:
        rendered.append(f"> {disclaimer}")
    return "\n\n".join(rendered)


def compose_daily_email(
    native_sections: list[str],
    *,
    config: Any,
    service: ExternalToolService | None = None,
    output_dir: str | Path | None = None,
) -> str:
    """Append the optional daily research report without breaking native DSA output.

    The function is deliberately called only from DSA's existing merged-report
    path.  When the extension is disabled it is a byte-for-byte join of the
    native sections.  Any extension failure becomes a short, sanitized section
    and is also saved as an artifact for diagnosis.
    """

    sections = [str(item).strip() for item in native_sections if str(item).strip()]
    if not bool(getattr(config, "external_tool_enabled", False)):
        return _SECTION_SEPARATOR.join(sections)

    destination = Path(output_dir) if output_dir is not None else _default_output_dir()
    try:
        automation_config = str(
            getattr(config, "external_tool_automation_config", "") or ""
        ).strip()
        if not automation_config:
            raise ExternalToolExtensionError(
                "external_tool_automation_config_missing",
                "未配置 ExternalTool 自动化报告文件",
            )
        extension_service = service or ExternalToolService(config)
        report = extension_service.run_capability(
            "daily_report",
            {"config_path": automation_config},
        )
        safe_report = sanitize_adapter_payload(
            report,
            adapter_module=str(getattr(config, "external_tool_adapter_module", "") or ""),
        )
        if not isinstance(safe_report, dict):
            raise ExternalToolExtensionError(
                "external_tool_invalid_response",
                "ExternalTool 每日报告格式无效",
            )
        _write_artifacts_safely(safe_report, destination)
        sections.append(report_markdown(safe_report))
    except Exception as exc:  # fail-open boundary around an optional private package
        code = _stable_error_code(getattr(exc, "code", None))
        message = sanitize_adapter_payload(
            str(getattr(exc, "message", "ExternalTool 每日研究生成失败")),
            adapter_module=str(getattr(config, "external_tool_adapter_module", "") or ""),
        )
        message = str(message)
        failure = {
            "schema_version": 1,
            "source": "external_tool",
            "status": "failed",
            "sections": [],
            "error": {"code": code, "message": message},
            "disclaimer": "DSA 原生报告未受影响；仅供研究，不构成投资建议",
        }
        _write_artifacts_safely(failure, destination)
        sections.append(
            "## 自定义研究\n\n"
            f"ExternalTool 片段生成失败（`{code}`）：{message}\n\n"
            "> DSA 原生报告未受影响；仅供研究，不构成投资建议"
        )
    return _SECTION_SEPARATOR.join(sections)


def _write_artifacts(report: Dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "external-tool-daily.json"
    markdown_path = output_dir / "external-tool-daily.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    markdown = str(report.get("markdown") or report_markdown(report)).strip()
    markdown_path.write_text(f"{markdown}\n", encoding="utf-8")


def _ordered_sections(sections: list[Any]) -> list[Any]:
    """Keep source order within the method, other, and custom report groups."""

    def group(section: Any) -> int:
        if not isinstance(section, dict):
            return 1
        section_id = str(section.get("id") or "")
        if section_id.startswith("method:"):
            return 0
        if section_id.startswith("custom:"):
            return 2
        return 1

    return [item for _, item in sorted(enumerate(sections), key=lambda pair: (group(pair[1]), pair[0]))]


def _data_access_usage_markdown(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    providers = value.get("providers")
    if not isinstance(providers, list):
        return ""
    lines = [
        "### 行情访问用量",
        "",
        "| 渠道 | 本次用量 | 计量口径 | 今日累计 | 日上限 | 剩余 |",
        "| --- | ---: | --- | ---: | ---: | ---: |",
    ]
    labels = {
        "provider_request": "渠道请求",
        "client_call": "客户端调用",
        "unavailable": "未提供计数",
    }
    details: list[str] = []
    for item in providers:
        if not isinstance(item, dict):
            continue
        quota = item.get("daily_quota") if isinstance(item.get("daily_quota"), dict) else {}
        requests = item.get("requests")
        measurement = str(item.get("measurement") or "unavailable")
        lines.append(
            f"| {item.get('provider', '-')} | {requests if isinstance(requests, int) else '未计数'} | "
            f"{labels.get(measurement, measurement)} | {quota.get('used', '-')} | "
            f"{quota.get('limit', '-')} | {quota.get('remaining', '-')} |"
        )
        operations = item.get("operations")
        if isinstance(operations, dict) and operations:
            detail = "，".join(f"{name} {count}" for name, count in operations.items())
            details.append(f"- {item.get('provider', '-')} 本次明细：{detail}")
    if len(lines) == 4:
        return "### 行情访问用量\n\n本次没有可计数的外部行情访问。"
    if details:
        lines.extend(["", *details])
    return "\n".join(lines)


def _write_artifacts_safely(report: Dict[str, Any], output_dir: Path) -> bool:
    try:
        _write_artifacts(report, output_dir)
        return True
    except Exception as exc:
        logger.warning("ExternalTool 报告 artifact 写入失败: %s", type(exc).__name__)
        return False


def _stable_error_code(value: Any) -> str:
    candidate = str(value or "")
    if _ERROR_CODE_PATTERN.fullmatch(candidate):
        return candidate
    return "external_tool_report_failed"


def _default_output_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "reports" / "external-tool"
