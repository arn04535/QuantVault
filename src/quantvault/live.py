"""Paper / live tracking and comparison against backtests."""

from __future__ import annotations

from typing import Any, Sequence

from quantvault.analytics import benchmark_comparison, returns_from_equity


def live_vs_backtest(
    *,
    backtest_equity: Sequence[float] | None = None,
    live_equity: Sequence[float] | None = None,
    backtest_returns: Sequence[float] | None = None,
    live_returns: Sequence[float] | None = None,
) -> dict[str, Any]:
    bt = list(backtest_returns) if backtest_returns is not None else returns_from_equity(backtest_equity or [])
    lv = list(live_returns) if live_returns is not None else returns_from_equity(live_equity or [])
    n = min(len(bt), len(lv))
    cmp_ = benchmark_comparison(lv[:n], bt[:n]) if n else {"n": 0}
    return {
        "n": n,
        "comparison": cmp_,
        "live_mean": (sum(lv[:n]) / n) if n else None,
        "backtest_mean": (sum(bt[:n]) / n) if n else None,
        "tracking_gap": ((sum(lv[:n]) / n) - (sum(bt[:n]) / n)) if n else None,
    }


def paper_summary(fills: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not fills:
        return {"n": 0, "realized_pnl": 0.0}
    pnls = [float(f.get("pnl", 0.0)) for f in fills]
    return {
        "n": len(pnls),
        "realized_pnl": sum(pnls),
        "avg_pnl": sum(pnls) / len(pnls),
        "win_rate": sum(1 for p in pnls if p > 0) / len(pnls),
    }
