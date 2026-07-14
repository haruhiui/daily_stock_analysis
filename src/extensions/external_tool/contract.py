"""External-tool adapter contract supported by this DSA extension."""

from __future__ import annotations

from typing import Any, Dict, Iterable

MIN_CONTRACT_VERSION = 1
MAX_CONTRACT_VERSION = 1
REQUIRED_FUNCTIONS = (
    "get_status",
    "list_research_methods",
    "get_research_method_schema",
    "run_research_method",
    "run_formula",
    "run_market_indicators",
    "run_grid_optimization",
    "run_strategy_backtest",
    "generate_daily_report",
)

CAPABILITY_FUNCTIONS = {
    "formula": "run_formula",
    "market_indicators": "run_market_indicators",
    "grid": "run_grid_optimization",
    "backtest": "run_strategy_backtest",
    "daily_report": "generate_daily_report",
}


def validate_adapter(adapter: Any) -> None:
    """Validate the stable adapter surface before exposing it to DSA."""

    missing = [name for name in REQUIRED_FUNCTIONS if not callable(getattr(adapter, name, None))]
    if missing:
        raise TypeError(f"ExternalTool 适配器缺少必要函数: {', '.join(missing)}")


def validate_status(
    status: Any,
    *,
    minimum: int = MIN_CONTRACT_VERSION,
    maximum: int = MAX_CONTRACT_VERSION,
) -> Dict[str, Any]:
    """Validate and normalize adapter compatibility metadata."""

    if not isinstance(status, dict):
        raise TypeError("ExternalTool 状态必须是对象")
    try:
        version = int(status.get("contract_version"))
    except (TypeError, ValueError) as exc:
        raise TypeError("ExternalTool 合同版本无效") from exc
    if minimum > maximum:
        raise ValueError(f"DSA ExternalTool 合同范围无效: {minimum}..{maximum}")
    if not minimum <= version <= maximum:
        raise ValueError(
            f"ExternalTool 合同版本 {version} 不受支持，"
            f"DSA 支持 {minimum}..{maximum}"
        )
    normalized = dict(status)
    normalized["contract_version"] = version
    normalized["capabilities"] = _string_list(status.get("capabilities"))
    return normalized


def _string_list(value: Any) -> list[str]:
    values: Iterable[Any] = value if isinstance(value, (list, tuple, set)) else ()
    return [str(item) for item in values if str(item).strip()]
