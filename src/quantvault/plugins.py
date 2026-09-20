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
    """Adapter should return a dict suitable for Ledger.record(**kwargs)."""
    _FRAMEWORK_ADAPTERS[name] = adapter


def list_frameworks() -> list[str]:
    return sorted(_FRAMEWORK_ADAPTERS)


def adapt_framework(name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    adapter = _FRAMEWORK_ADAPTERS.get(name)
    if adapter is None:
        raise KeyError(f"unknown framework adapter: {name}")
    return adapter(*args, **kwargs)


# Built-in example metric (optional to use)
def _example_hit_rate(context: dict[str, Any]) -> dict[str, float]:
    trades = context.get("trades") or []
    if not trades:
        return {}
    wins = sum(1 for t in trades if float(t.get("pnl", 0)) > 0)
    return {"custom_hit_rate": wins / len(trades)}


register_metric("hit_rate", _example_hit_rate)
