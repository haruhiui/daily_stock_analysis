"""Stable error boundary for the optional ExternalTool extension."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

_PATH_PATTERN = re.compile(r"(?:[A-Za-z]:[\\/]|/home/|/Users/)[^\s,;]+")
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"\b([A-Z0-9_-]*(?:token|password|secret|authorization|api[_-]?key)[A-Z0-9_-]*)"
    r"(\s*[:=]\s*)[^\s,;]+",
    re.IGNORECASE,
)
_KNOWN_TOKEN_PATTERN = re.compile(
    r"\b(?:github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{12,})\b"
)


class ExternalToolExtensionError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 424,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.code = code
        self.message = sanitize_message(message)
        self.status_code = status_code
        sanitized_detail = sanitize_payload(detail or {})
        self.detail = sanitized_detail if isinstance(sanitized_detail, dict) else {}
        super().__init__(self.message)


def translate_adapter_error(exc: Exception) -> ExternalToolExtensionError:
    code = _normalize_adapter_error_code(getattr(exc, "code", None))
    message = str(getattr(exc, "message", str(exc) or "ExternalTool 执行失败"))
    status_code = 400 if code in {
        "external_tool_invalid_request",
        "external_tool_method_not_found",
    } else 424
    if code == "external_tool_method_not_found":
        status_code = 404
    raw_detail = getattr(exc, "details", {})
    detail = raw_detail if isinstance(raw_detail, dict) else {}
    return ExternalToolExtensionError(code, message, status_code=status_code, detail=detail)


def _normalize_adapter_error_code(value: Any) -> str:
    """Map private adapter codes to stable public host codes without exposing its namespace."""

    candidate = str(value or "").strip().lower()
    if candidate.endswith("_invalid_request"):
        return "external_tool_invalid_request"
    if candidate.endswith("_method_not_found"):
        return "external_tool_method_not_found"
    return "external_tool_execution_failed"


def sanitize_message(message: str) -> str:
    sanitized = _PATH_PATTERN.sub("<path>", str(message or ""))
    sanitized = _EMAIL_PATTERN.sub("<email>", sanitized)
    sanitized = _SECRET_ASSIGNMENT_PATTERN.sub(r"\1\2<redacted>", sanitized)
    sanitized = _KNOWN_TOKEN_PATTERN.sub("<redacted>", sanitized)
    return sanitized[:1000]


def sanitize_payload(value: Any) -> Any:
    """Recursively sanitize diagnostic data before API, email, or artifact output."""

    if isinstance(value, str):
        return sanitize_message(value)
    if isinstance(value, dict):
        return {key: sanitize_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_payload(item) for item in value)
    return value


def sanitize_adapter_payload(value: Any, *, adapter_module: str = "") -> Any:
    """Sanitize diagnostics and replace private producer identity in public payload values."""

    module_root = str(adapter_module or "").partition(".")[0].strip()
    identity_variants = _identity_variants(module_root)

    def visit(item: Any) -> Any:
        if isinstance(item, str):
            sanitized = sanitize_message(item)
            for variant in identity_variants:
                sanitized = re.sub(re.escape(variant), "external tool", sanitized, flags=re.IGNORECASE)
            return sanitized
        if isinstance(item, dict):
            normalized = {key: visit(child) for key, child in item.items()}
            if "source" in normalized:
                source = str(normalized.get("source") or "").strip()
                if source not in {"external_tool", "user_config"}:
                    normalized["source"] = "external_tool"
            return normalized
        if isinstance(item, list):
            return [visit(child) for child in item]
        if isinstance(item, tuple):
            return tuple(visit(child) for child in item)
        return item

    return visit(value)


def _identity_variants(module_root: str) -> list[str]:
    if not module_root:
        return []
    words = [part for part in re.split(r"[_-]+", module_root) if part]
    variants = {
        module_root,
        "_".join(words),
        "-".join(words),
        " ".join(words),
        "".join(words),
        "".join(word.capitalize() for word in words),
    }
    return sorted((item for item in variants if item), key=len, reverse=True)
