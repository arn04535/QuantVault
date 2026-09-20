"""Portfolio and multi-strategy research analytics."""

from __future__ import annotations

import math
import statistics
from typing import Any, Sequence

from quantvault.analytics import drawdown_analysis, equity_curve_analysis, risk_adjusted_metrics, returns_from_equity


def portfolio_from_strategies(
    legs: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Combine strategy equity legs with weights into a portfolio equity curve.

    Each leg: {name, equity: [...], weight: float}
    """
    if not legs:
        return {"equity": [], "weights": {}, "names": []}
    length = min(len(leg["equity"]) for leg in legs)
    weights = {leg["name"]: float(leg.get("weight", 1.0)) for leg in legs}
    total_w = sum(weights.values()) or 1.0
    norm = {k: v / total_w for k, v in weights.items()}
    # normalize each leg to 1.0 start, then weight
    series = []
    for i in range(length):
        value = 0.0
        for leg in legs:
            eq = leg["equity"]
            base = eq[0] or 1.0
            value += norm[leg["name"]] * (eq[i] / base)
        series.append(value)
    return {"equity": series, "weights": norm, "names": [leg["name"] for leg in legs]}


def portfolio_risk_analytics(equity: Sequence[float], *, periods_per_year: float = 252.0) -> dict[str, Any]:
    rets = returns_from_equity(equity)
    return {
        "equity_curve": equity_curve_analysis(equity),
        "drawdown": drawdown_analysis(equity),
        "risk_adjusted": risk_adjusted_metrics(rets, periods_per_year=periods_per_year, equity=equity),
    }


def allocation_analysis(weights: dict[str, float]) -> dict[str, Any]:
    total = sum(abs(v) for v in weights.values()) or 1.0
    parts = {k: v / total for k, v in weights.items()}
    long_exposure = sum(v for v in parts.values() if v > 0)
    short_exposure = sum(v for v in parts.values() if v < 0)
    return {
        "weights": parts,
        "long_exposure": long_exposure,
        "short_exposure": short_exposure,
        "gross_exposure": long_exposure + abs(short_exposure),
        "net_exposure": long_exposure + short_exposure,
        "n_strategies": len(parts),
        "hhi": sum(v * v for v in parts.values()),
    }


def strategy_correlation(series_map: dict[str, Sequence[float]]) -> dict[str, Any]:
    """Correlate return series across strategies."""
    names = sorted(series_map)
    rets = {n: returns_from_equity(series_map[n]) if _looks_like_equity(series_map[n]) else list(series_map[n]) for n in names}
    length = min((len(rets[n]) for n in names), default=0)
    matrix: dict[str, dict[str, float]] = {a: {} for a in names}
    for a in names:
        for b in names:
            matrix[a][b] = _corr(rets[a][:length], rets[b][:length]) if length else 0.0
    return {"names": names, "matrix": matrix, "n": length}


def portfolio_drawdown(equity: Sequence[float]) -> dict[str, Any]:
    return drawdown_analysis(equity)


def _looks_like_equity(values: Sequence[float]) -> bool:
    if len(values) < 2:
        return True
    # heuristic: equity usually near 1..1e6 and cumulative; treat as equity by default
    return True


def _corr(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) < 2 or len(b) < 2:
        return 0.0
    n = min(len(a), len(b))
    a, b = list(a[:n]), list(b[:n])
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)
