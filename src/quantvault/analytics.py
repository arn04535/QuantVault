"""Backtest and performance analysis (stdlib only)."""

from __future__ import annotations

import math
import random
import statistics
from itertools import product
from typing import Any, Iterable, Sequence


def returns_from_equity(equity: Sequence[float]) -> list[float]:
    if len(equity) < 2:
        return []
    out: list[float] = []
    for prev, cur in zip(equity, equity[1:]):
        if prev == 0:
            out.append(0.0)
        else:
            out.append((cur - prev) / prev)
    return out


def equity_curve_analysis(equity: Sequence[float]) -> dict[str, Any]:
    if not equity:
        return {"n": 0}
    rets = returns_from_equity(equity)
    total_return = (equity[-1] / equity[0] - 1.0) if equity[0] else 0.0
    return {
        "n": len(equity),
        "start": equity[0],
        "end": equity[-1],
        "total_return": total_return,
        "mean_return": statistics.fmean(rets) if rets else 0.0,
        "volatility": statistics.pstdev(rets) if len(rets) > 1 else 0.0,
        "positive_periods": sum(1 for r in rets if r > 0),
        "negative_periods": sum(1 for r in rets if r < 0),
    }


def drawdown_analysis(equity: Sequence[float]) -> dict[str, Any]:
    if not equity:
        return {"max_drawdown": 0.0, "underwater_periods": 0, "path": []}
    peak = equity[0]
    max_dd = 0.0
    path: list[float] = []
    underwater = 0
    for value in equity:
        peak = max(peak, value)
        dd = 0.0 if peak == 0 else (value - peak) / peak
        path.append(dd)
        max_dd = min(max_dd, dd)
        if dd < 0:
            underwater += 1
    return {
        "max_drawdown": max_dd,
        "underwater_periods": underwater,
        "path": path,
    }


def risk_adjusted_metrics(
    returns: Sequence[float],
    *,
    periods_per_year: float = 252.0,
    risk_free: float = 0.0,
    equity: Sequence[float] | None = None,
) -> dict[str, Any]:
    if not returns:
        return {"sharpe": 0.0, "sortino": 0.0, "calmar": 0.0}
    mean = statistics.fmean(returns)
    excess = [r - risk_free / periods_per_year for r in returns]
    vol = statistics.pstdev(excess) if len(excess) > 1 else 0.0
    downside = [min(0.0, r) for r in excess]
    down_vol = statistics.pstdev(downside) if len(downside) > 1 else 0.0
    sharpe = 0.0 if vol == 0 else (statistics.fmean(excess) / vol) * math.sqrt(periods_per_year)
    sortino = (
        0.0
        if down_vol == 0
        else (statistics.fmean(excess) / down_vol) * math.sqrt(periods_per_year)
    )
    eq = list(equity) if equity is not None else _equity_from_returns(returns)
    dd = drawdown_analysis(eq)
    ann_return = mean * periods_per_year
    calmar = 0.0 if dd["max_drawdown"] == 0 else ann_return / abs(dd["max_drawdown"])
    return {
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "ann_return": ann_return,
        "ann_vol": vol * math.sqrt(periods_per_year),
        "max_drawdown": dd["max_drawdown"],
    }


def trade_level_analysis(trades: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {"n": 0}
    pnls = [float(t.get("pnl", 0.0)) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "n": len(pnls),
        "total_pnl": sum(pnls),
        "avg_pnl": statistics.fmean(pnls),
        "win_rate": len(wins) / len(pnls),
        "avg_win": statistics.fmean(wins) if wins else 0.0,
        "avg_loss": statistics.fmean(losses) if losses else 0.0,
        "profit_factor": (gross_win / gross_loss) if gross_loss else None,
        "best": max(pnls),
        "worst": min(pnls),
    }


def transaction_cost_analysis(
    trades: Sequence[dict[str, Any]],
    *,
    cost_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> dict[str, Any]:
    """Estimate cost drag. Uses notional if present, else abs(pnl) as proxy."""
    total_cost = 0.0
    net_pnls: list[float] = []
    bps = (cost_bps + slippage_bps) / 10_000.0
    for trade in trades:
        pnl = float(trade.get("pnl", 0.0))
        notional = float(trade.get("notional", abs(pnl)))
        cost = abs(notional) * bps
        total_cost += cost
        net_pnls.append(pnl - cost)
    gross = trade_level_analysis(trades)
    net = trade_level_analysis([{"pnl": p} for p in net_pnls])
    return {
        "cost_bps": cost_bps,
        "slippage_bps": slippage_bps,
        "total_cost": total_cost,
        "gross": gross,
        "net": net,
        "pnl_drag": gross.get("total_pnl", 0.0) - net.get("total_pnl", 0.0),
    }


def benchmark_comparison(
    strategy_returns: Sequence[float],
    benchmark_returns: Sequence[float],
) -> dict[str, Any]:
    n = min(len(strategy_returns), len(benchmark_returns))
    if n == 0:
        return {"n": 0}
    s = list(strategy_returns[:n])
    b = list(benchmark_returns[:n])
    excess = [a - c for a, c in zip(s, b)]
    # ponytail: OLS beta via closed form; upgrade to statsmodels if needed
    mean_s, mean_b = statistics.fmean(s), statistics.fmean(b)
    var_b = statistics.pvariance(b) if n > 1 else 0.0
    cov = statistics.fmean([(x - mean_s) * (y - mean_b) for x, y in zip(s, b)])
    beta = 0.0 if var_b == 0 else cov / var_b
    alpha = mean_s - beta * mean_b
    tracking = statistics.pstdev(excess) if n > 1 else 0.0
    info_ratio = 0.0 if tracking == 0 else statistics.fmean(excess) / tracking
    return {
        "n": n,
        "alpha": alpha,
        "beta": beta,
        "excess_mean": statistics.fmean(excess),
        "tracking_error": tracking,
        "information_ratio": info_ratio,
        "corr": _corr(s, b),
    }


def srsi_analysis(
    returns: Sequence[float],
    *,
    window: int = 20,
    periods_per_year: float = 252.0,
) -> dict[str, Any]:
    """Sharpe Ratio Stability Index: lower rolling-Sharpe CV ⇒ higher SRSI."""
    if len(returns) < window or window < 2:
        return {"srsi": 0.0, "rolling_sharpes": [], "cv": None}
    sharpes: list[float] = []
    for i in range(window, len(returns) + 1):
        chunk = returns[i - window : i]
        vol = statistics.pstdev(chunk)
        sharpes.append(
            0.0 if vol == 0 else (statistics.fmean(chunk) / vol) * math.sqrt(periods_per_year)
        )
    mean_s = statistics.fmean(sharpes)
    cv = 0.0 if mean_s == 0 else statistics.pstdev(sharpes) / abs(mean_s)
    srsi = 1.0 / (1.0 + cv)
    return {
        "srsi": srsi,
        "cv": cv,
        "window": window,
        "rolling_sharpes": sharpes,
        "mean_rolling_sharpe": mean_s,
    }


def monte_carlo_analysis(
    returns: Sequence[float],
    *,
    n_sims: int = 500,
    horizon: int | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    if not returns:
        return {"n_sims": 0}
    rng = random.Random(seed)
    h = horizon or len(returns)
    finals: list[float] = []
    max_dds: list[float] = []
    # store paths for percentile fan chart
    paths: list[list[float]] = []
    for _ in range(n_sims):
        path = [1.0]
        for _t in range(h):
            path.append(path[-1] * (1.0 + rng.choice(list(returns))))
        paths.append(path)
        finals.append(path[-1] - 1.0)
        max_dds.append(drawdown_analysis(path)["max_drawdown"])

    fan = {"p05": [], "p25": [], "p50": [], "p75": [], "p95": []}
    for t in range(h + 1):
        col = sorted(p[t] - 1.0 for p in paths)
        fan["p05"].append(_percentile(col, 0.05))
        fan["p25"].append(_percentile(col, 0.25))
        fan["p50"].append(_percentile(col, 0.50))
        fan["p75"].append(_percentile(col, 0.75))
        fan["p95"].append(_percentile(col, 0.95))

    finals_sorted = sorted(finals)
    hist = _histogram(finals_sorted, bins=25)
    prob_pos = sum(1 for x in finals if x > 0) / len(finals)
    return {
        "n_sims": n_sims,
        "horizon": h,
        "seed": seed,
        "final_return": {
            "mean": statistics.fmean(finals),
            "p05": _percentile(finals_sorted, 0.05),
            "p25": _percentile(finals_sorted, 0.25),
            "p50": _percentile(finals_sorted, 0.50),
            "p75": _percentile(finals_sorted, 0.75),
            "p95": _percentile(finals_sorted, 0.95),
        },
        "max_drawdown": {
            "mean": statistics.fmean(max_dds),
            "p05": _percentile(sorted(max_dds), 0.05),
            "p50": _percentile(sorted(max_dds), 0.50),
            "p95": _percentile(sorted(max_dds), 0.95),
        },
        "fan": fan,
        "distribution": hist,
        "edge": {
            "prob_positive": prob_pos,
            "median_final": _percentile(finals_sorted, 0.50),
            "mean_final": statistics.fmean(finals),
            "tail_p05": _percentile(finals_sorted, 0.05),
            "edge_score": (prob_pos - 0.5) * 2.0,
            "has_edge": prob_pos > 0.55 and _percentile(finals_sorted, 0.50) > 0,
        },
    }


def _histogram(sorted_vals: Sequence[float], bins: int = 20) -> dict[str, Any]:
    if not sorted_vals:
        return {"bins": [], "counts": []}
    lo, hi = sorted_vals[0], sorted_vals[-1]
    if lo == hi:
        return {"bins": [lo], "counts": [len(sorted_vals)]}
    width = (hi - lo) / bins
    counts = [0] * bins
    centers = []
    for i in range(bins):
        centers.append(lo + (i + 0.5) * width)
    for value in sorted_vals:
        idx = min(bins - 1, int((value - lo) / width))
        counts[idx] += 1
    return {"bins": centers, "counts": counts, "min": lo, "max": hi}


def sensitivity_analysis(
    base_params: dict[str, Any],
    perturbations: dict[str, Sequence[Any]],
) -> list[dict[str, Any]]:
    """Return param sets for one-at-a-time sensitivity (not full cartesian)."""
    rows: list[dict[str, Any]] = [{"params": dict(base_params), "kind": "base"}]
    for key, values in perturbations.items():
        for value in values:
            params = dict(base_params)
            params[key] = value
            rows.append({"params": params, "kind": "sensitivity", "varied": key})
    return rows


def parameter_robustness(
    results: Sequence[dict[str, Any]],
    *,
    metric: str = "sharpe",
) -> dict[str, Any]:
    """Summarize metric stability across a neighborhood of runs."""
    values = [float(r["metrics"][metric]) for r in results if metric in r.get("metrics", {})]
    if not values:
        return {"metric": metric, "n": 0}
    mean = statistics.fmean(values)
    stdev = statistics.pstdev(values) if len(values) > 1 else 0.0
    return {
        "metric": metric,
        "n": len(values),
        "mean": mean,
        "stdev": stdev,
        "min": min(values),
        "max": max(values),
        "cv": 0.0 if mean == 0 else stdev / abs(mean),
        "robustness_score": 1.0 / (1.0 + (stdev / abs(mean) if mean else stdev)),
    }


def overfitting_analysis(
    in_sample_metric: float,
    out_of_sample_metric: float,
    *,
    n_trials: int = 1,
) -> dict[str, Any]:
    """Simple IS/OOS degradation + trial-count warning."""
    gap = in_sample_metric - out_of_sample_metric
    rel = 0.0 if in_sample_metric == 0 else gap / abs(in_sample_metric)
    return {
        "in_sample": in_sample_metric,
        "out_of_sample": out_of_sample_metric,
        "gap": gap,
        "relative_gap": rel,
        "n_trials": n_trials,
        "overfit_flag": rel > 0.25 or (n_trials >= 20 and out_of_sample_metric < in_sample_metric),
    }


def walk_forward_analysis(
    windows: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate walk-forward window results.

    Each window: {train_metric, test_metric, start?, end?, params?}
    """
    if not windows:
        return {"n_windows": 0}
    trains = [float(w["train_metric"]) for w in windows]
    tests = [float(w["test_metric"]) for w in windows]
    gaps = [a - b for a, b in zip(trains, tests)]
    return {
        "n_windows": len(windows),
        "train_mean": statistics.fmean(trains),
        "test_mean": statistics.fmean(tests),
        "gap_mean": statistics.fmean(gaps),
        "test_stdev": statistics.pstdev(tests) if len(tests) > 1 else 0.0,
        "windows": list(windows),
        "overfitting": overfitting_analysis(
            statistics.fmean(trains),
            statistics.fmean(tests),
            n_trials=len(windows),
        ),
    }


def expand_param_grid(
    base_params: dict[str, Any],
    grid: dict[str, Sequence[Any]],
) -> list[dict[str, Any]]:
    if not grid:
        return [dict(base_params)]
    keys = sorted(grid)
    combos: list[dict[str, Any]] = []
    for values in product(*(grid[k] for k in keys)):
        params = dict(base_params)
        params.update(dict(zip(keys, values)))
        combos.append(params)
    return combos


def performance_report(
    *,
    equity: Sequence[float] | None = None,
    returns: Sequence[float] | None = None,
    trades: Sequence[dict[str, Any]] | None = None,
    benchmark_returns: Sequence[float] | None = None,
    cost_bps: float = 0.0,
    slippage_bps: float = 0.0,
    periods_per_year: float = 252.0,
) -> dict[str, Any]:
    """One-shot performance analytics bundle."""
    eq = list(equity) if equity is not None else None
    rets = list(returns) if returns is not None else (returns_from_equity(eq) if eq else [])
    if eq is None and rets:
        eq = _equity_from_returns(rets)
    report: dict[str, Any] = {
        "equity_curve": equity_curve_analysis(eq or []),
        "drawdown": drawdown_analysis(eq or []),
        "risk_adjusted": risk_adjusted_metrics(
            rets, periods_per_year=periods_per_year, equity=eq
        ),
        "srsi": srsi_analysis(rets, periods_per_year=periods_per_year),
    }
    if trades is not None:
        report["trades"] = trade_level_analysis(trades)
        report["transaction_costs"] = transaction_cost_analysis(
            trades, cost_bps=cost_bps, slippage_bps=slippage_bps
        )
    if benchmark_returns is not None:
        report["benchmark"] = benchmark_comparison(rets, benchmark_returns)
    report["series"] = {
        "equity": list(eq or []),
        "drawdown": (report["drawdown"].get("path") or []),
        "returns": rets,
    }
    return report


def _equity_from_returns(returns: Sequence[float], start: float = 1.0) -> list[float]:
    equity = [start]
    for r in returns:
        equity.append(equity[-1] * (1.0 + float(r)))
    return equity


def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    pos = q * (len(sorted_vals) - 1)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(sorted_vals[lo])
    return float(sorted_vals[lo]) * (hi - pos) + float(sorted_vals[hi]) * (pos - lo)


def _corr(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) < 2:
        return 0.0
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den_a = math.sqrt(sum((x - ma) ** 2 for x in a))
    den_b = math.sqrt(sum((y - mb) ** 2 for y in b))
    if den_a == 0 or den_b == 0:
        return 0.0
    return num / (den_a * den_b)
