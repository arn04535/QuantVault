"""Integrations, custom metrics/metadata, and a tiny plugin registry."""

from __future__ import annotations

from typing import Any, Callable

MetricFn = Callable[[dict[str, Any]], dict[str, float]]
HookFn = Callable[..., Any]

_CUSTOM_METRICS: dict[str, MetricFn] = {}
_PLUGINS: dict[str, dict[str, Any]] = {}
_FRAMEWORK_ADAPTERS: dict[str, Callable[..., dict[str, Any]]] = {}


def register_metric(name: str, fn: MetricFn) -> None:
    _CUSTOM_METRICS[name] = fn


def list_metrics() -> list[str]:
    return sorted(_CUSTOM_METRICS)


def compute_custom_metrics(context: dict[str, Any], names: list[str] | None = None) -> dict[str, float]:
    selected = names or list(_CUSTOM_METRICS)
    out: dict[str, float] = {}
    for name in selected:
        fn = _CUSTOM_METRICS.get(name)
        if fn is None:
            continue
        out.update(fn(context))
    return out


def merge_metadata(base: dict[str, Any] | None, extra: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(base or {})
    merged.update(dict(extra or {}))
    return merged


def register_plugin(name: str, *, hooks: dict[str, HookFn] | None = None, meta: dict[str, Any] | None = None) -> None:
    _PLUGINS[name] = {"hooks": dict(hooks or {}), "meta": dict(meta or {})}


def list_plugins() -> list[dict[str, Any]]:
    return [{"name": k, **v} for k, v in sorted(_PLUGINS.items())]


def call_plugin_hook(plugin: str, hook: str, *args: Any, **kwargs: Any) -> Any:
    entry = _PLUGINS.get(plugin)
    if entry is None:
        raise KeyError(f"unknown plugin: {plugin}")
    fn = entry["hooks"].get(hook)
    if fn is None:
        raise KeyError(f"plugin {plugin!r} has no hook {hook!r}")
    return fn(*args, **kwargs)


def register_framework_adapter(name: str, adapter: Callable[..., dict[str, Any]]) -> None:
    """Adapter should return a dict suitable for Ledger.record / analyze."""
    _FRAMEWORK_ADAPTERS[name] = adapter


def list_frameworks() -> list[str]:
    return sorted(_FRAMEWORK_ADAPTERS)


def adapt_framework(name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    adapter = _FRAMEWORK_ADAPTERS.get(name)
    if adapter is None:
        raise KeyError(f"unknown framework adapter: {name}")
    return adapter(*args, **kwargs)


def _example_hit_rate(context: dict[str, Any]) -> dict[str, float]:
    trades = context.get("trades") or []
    if not trades:
        return {}
    wins = sum(1 for t in trades if float(t.get("pnl", 0)) > 0)
    return {"custom_hit_rate": wins / len(trades)}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if hasattr(value, "tolist"):
        try:
            return list(value.tolist())
        except Exception:  # noqa: BLE001
            pass
    try:
        return list(value)
    except TypeError:
        return [value]


def _adapter_generic(payload: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    """Normalize a generic research result dict into QuantVault record+analyze fields."""
    data = {**(payload or {}), **kwargs}
    strategy = str(data.get("strategy") or data.get("name") or "strategy")
    parameters = dict(data.get("parameters") or data.get("params") or {})
    metrics = dict(data.get("metrics") or {})
    tags = list(data.get("tags") or [])
    equity = _as_list(data.get("equity") or data.get("equity_curve") or data.get("portfolio_value"))
    returns = _as_list(data.get("returns") or data.get("rets"))
    trades = list(data.get("trades") or data.get("trade_list") or [])
    return {
        "strategy": strategy,
        "name": data.get("run_name") or data.get("experiment_name"),
        "parameters": parameters,
        "metrics": metrics,
        "tags": tags,
        "notes": str(data.get("notes") or ""),
        "equity": equity,
        "returns": returns,
        "trades": trades,
        "benchmark_returns": _as_list(data.get("benchmark_returns")),
        "meta": dict(data.get("meta") or {"adapter": "generic"}),
    }


def _adapter_vectorbt(payload: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    """Accept common vectorbt-style keys (portfolio value / returns / stats)."""
    data = {**(payload or {}), **kwargs}
    stats = dict(data.get("stats") or {})
    metrics = dict(data.get("metrics") or {})
    for key in ("sharpe_ratio", "Sharpe Ratio", "sharpe"):
        if key in stats and "sharpe" not in metrics:
            metrics["sharpe"] = float(stats[key])
    for key in ("max_drawdown", "Max Drawdown"):
        if key in stats and "max_drawdown" not in metrics:
            metrics["max_drawdown"] = float(stats[key])
    out = _adapter_generic(
        {
            "strategy": data.get("strategy") or "vectorbt",
            "parameters": data.get("parameters") or data.get("params") or {},
            "metrics": metrics,
            "tags": list(data.get("tags") or ["vectorbt"]),
            "equity": data.get("equity") or data.get("value") or data.get("portfolio_value"),
            "returns": data.get("returns"),
            "trades": data.get("trades") or [],
            "notes": data.get("notes") or "adapted from vectorbt-style payload",
            "meta": {"adapter": "vectorbt", **dict(data.get("meta") or {})},
        }
    )
    return out


def _adapter_backtesting_py(payload: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    """Accept backtesting.py stats/_equity_curve style payloads."""
    data = {**(payload or {}), **kwargs}
    stats = dict(data.get("stats") or data.get("results") or {})
    equity = data.get("equity") or data.get("_equity_curve") or data.get("equity_curve")
    if hasattr(equity, "tolist"):
        equity = list(equity.tolist()) if not hasattr(equity, "columns") else None
    if equity is None and hasattr(data.get("_equity_curve"), "Equity"):
        try:
            equity = list(data["_equity_curve"]["Equity"].tolist())
        except Exception:  # noqa: BLE001
            equity = []
    metrics: dict[str, Any] = {}
    mapping = {
        "Sharpe Ratio": "sharpe",
        "Return [%]": "total_return_pct",
        "Max. Drawdown [%]": "max_drawdown_pct",
        "# Trades": "n_trades",
        "Win Rate [%]": "win_rate_pct",
    }
    for src, dst in mapping.items():
        if src in stats:
            try:
                metrics[dst] = float(stats[src])
            except (TypeError, ValueError):
                metrics[dst] = stats[src]
    return _adapter_generic(
        {
            "strategy": data.get("strategy") or stats.get("strategy") or "backtesting.py",
            "parameters": data.get("parameters") or data.get("params") or {},
            "metrics": metrics,
            "tags": list(data.get("tags") or ["backtesting.py"]),
            "equity": equity or [],
            "trades": data.get("trades") or [],
            "notes": data.get("notes") or "adapted from backtesting.py-style payload",
            "meta": {"adapter": "backtesting.py", **dict(data.get("meta") or {})},
        }
    )


def _adapter_zipline(payload: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    """Accept zipline/pyfolio-like perf dicts with returns / positions keys."""
    data = {**(payload or {}), **kwargs}
    returns = data.get("returns") or data.get("daily_returns")
    equity = data.get("equity") or data.get("portfolio_value")
    metrics = dict(data.get("metrics") or {})
    if "sharpe" in data:
        metrics.setdefault("sharpe", float(data["sharpe"]))
    return _adapter_generic(
        {
            "strategy": data.get("strategy") or data.get("algo_name") or "zipline",
            "parameters": data.get("parameters") or data.get("params") or {},
            "metrics": metrics,
            "tags": list(data.get("tags") or ["zipline"]),
            "equity": equity or [],
            "returns": returns or [],
            "trades": data.get("trades") or data.get("transactions") or [],
            "notes": data.get("notes") or "adapted from zipline-style payload",
            "meta": {"adapter": "zipline", **dict(data.get("meta") or {})},
        }
    )


register_metric("hit_rate", _example_hit_rate)
register_framework_adapter("generic", _adapter_generic)
register_framework_adapter("vectorbt", _adapter_vectorbt)
register_framework_adapter("backtesting.py", _adapter_backtesting_py)
register_framework_adapter("zipline", _adapter_zipline)
