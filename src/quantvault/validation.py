"""Research quality warnings and validation checks (local, non-judgmental flags)."""

from __future__ import annotations

from typing import Any


def research_quality_warnings(
    *,
    experiment: dict[str, Any],
    repro: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    trades: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return structured warnings. Severity is informational — not a verdict."""
    warnings: list[dict[str, Any]] = []
    params = experiment.get("params") or {}
    metrics = experiment.get("metrics") or {}

    if not repro:
        warnings.append(
            {
                "code": "missing_repro",
                "category": "reproducibility",
                "message": "No reproducibility record attached",
            }
        )
    else:
        if repro.get("seed") is None:
            warnings.append(
                {
                    "code": "missing_seed",
                    "category": "reproducibility",
                    "message": "Random seed not recorded",
                }
            )
        if not repro.get("dataset_fingerprint") and not repro.get("dataset_id"):
            warnings.append(
                {
                    "code": "missing_dataset",
                    "category": "reproducibility",
                    "message": "Dataset fingerprint/id not recorded",
                }
            )

    if not params:
        warnings.append(
            {
                "code": "empty_params",
                "category": "integrity",
                "message": "Experiment has empty parameters",
            }
        )

    if not metrics:
        warnings.append(
            {
                "code": "empty_metrics",
                "category": "integrity",
                "message": "Experiment has no metrics yet",
            }
        )

    if analysis is None:
        warnings.append(
            {
                "code": "missing_analysis",
                "category": "integrity",
                "message": "No stored performance analysis artifact",
            }
        )

    # IS/OOS gap signal (data only)
    is_s = metrics.get("in_sample_sharpe")
    oos = metrics.get("oos_sharpe")
    if is_s is not None and oos is not None:
        gap = float(is_s) - float(oos)
        warnings.append(
            {
                "code": "is_oos_gap",
                "category": "overfitting",
                "message": "In-sample vs out-of-sample metric gap recorded",
                "data": {"in_sample": is_s, "out_of_sample": oos, "gap": gap},
            }
        )

    if trades is not None and len(trades) < 5:
        warnings.append(
            {
                "code": "few_trades",
                "category": "integrity",
                "message": "Very few trades in sample",
                "data": {"n": len(trades)},
            }
        )

    n_trials = metrics.get("n_trials") or (repro or {}).get("n_trials")
    if n_trials is not None and int(n_trials) >= 50:
        warnings.append(
            {
                "code": "many_trials",
                "category": "overfitting",
                "message": "Large trial count recorded - multiple-testing risk",
                "data": {"n_trials": int(n_trials)},
            }
        )

    rel_gap = metrics.get("overfit_relative_gap")
    if rel_gap is not None and float(rel_gap) > 0.25:
        warnings.append(
            {
                "code": "large_relative_is_oos_gap",
                "category": "overfitting",
                "message": "Relative IS/OOS gap exceeds 25%",
                "data": {"relative_gap": rel_gap},
            }
        )

    return warnings


def backtest_integrity_checks(
    *,
    equity: list[float] | None = None,
    trades: list[dict[str, Any]] | None = None,
    params: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if equity is not None:
        if len(equity) < 2:
            findings.append({"code": "short_equity", "message": "Equity series too short", "data": {"n": len(equity)}})
        if any(v <= 0 for v in equity):
            findings.append({"code": "non_positive_equity", "message": "Non-positive equity values present"})
        if len(equity) >= 2 and equity[0] == equity[-1] and len(set(equity)) == 1:
            findings.append({"code": "flat_equity", "message": "Equity curve is completely flat"})

    if trades is not None:
        missing_pnl = sum(1 for t in trades if "pnl" not in t)
        if missing_pnl:
            findings.append(
                {
                    "code": "trades_missing_pnl",
                    "message": "Some trades missing pnl field",
                    "data": {"count": missing_pnl},
                }
            )

    params = params or {}
    for key in ("train_end", "test_start", "fit_end", "signal_end"):
        if key in params:
            findings.append(
                {
                    "code": "split_boundary_present",
                    "message": f"Parameter {key} present — verify no boundary leakage",
                    "data": {"key": key, "value": params[key]},
                }
            )
    return findings


def data_quality_checks(
    *,
    rows: list[dict[str, Any]] | None = None,
    columns: list[str] | None = None,
    null_counts: dict[str, int] | None = None,
    duplicate_timestamps: int = 0,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if rows is not None and len(rows) == 0:
        findings.append({"code": "empty_dataset", "message": "Dataset has zero rows"})
    if null_counts:
        bad = {k: v for k, v in null_counts.items() if v}
        if bad:
            findings.append({"code": "nulls_present", "message": "Null values present", "data": bad})
    if duplicate_timestamps:
        findings.append(
            {
                "code": "duplicate_timestamps",
                "message": "Duplicate timestamps detected",
                "data": {"count": duplicate_timestamps},
            }
        )
    if columns is not None:
        required = {"timestamp", "close"}
        missing = sorted(required - set(columns))
        if missing:
            findings.append(
                {
                    "code": "missing_columns",
                    "message": "Common research columns missing",
                    "data": {"missing": missing},
                }
            )
    return findings


def lookahead_bias_checks(params: dict[str, Any] | None = None, meta: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Heuristic flags only - cannot prove lookahead without the research code."""
    findings: list[dict[str, Any]] = []
    blob = {**(params or {}), **(meta or {})}
    text = " ".join(str(v).lower() for v in blob.values()) + " " + " ".join(str(k).lower() for k in blob)
    suspects = (
        "future",
        "next_close",
        "next_open",
        "t+1",
        "shift(-",
        "forward_fill_signal",
        "peek",
        "lookahead",
        "use_future",
        "leak_future",
        ".shift(-1)",
    )
    hits = [s for s in suspects if s in text]
    if hits:
        findings.append(
            {
                "code": "lookahead_keyword",
                "message": "Configuration text mentions possible lookahead-related tokens",
                "data": {"tokens": hits},
            }
        )
    if blob.get("uses_same_bar_close") is True:
        findings.append(
            {
                "code": "same_bar_close",
                "message": "uses_same_bar_close=True - verify execution assumptions",
            }
        )
    if blob.get("signal_timing") in {"close_same_bar", "intrabar_future"}:
        findings.append(
            {
                "code": "signal_timing",
                "message": f"signal_timing={blob.get('signal_timing')} may allow same-bar lookahead",
            }
        )
    if blob.get("execution_price") == "close" and blob.get("signal_on") == "close":
        findings.append(
            {
                "code": "signal_and_fill_on_close",
                "message": "Signal and fill both on close - confirm no same-bar lookahead",
            }
        )
    return findings


def survivorship_bias_checks(meta: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    meta = meta or {}
    if meta.get("universe_includes_delisted") is False:
        findings.append(
            {
                "code": "delisted_excluded",
                "message": "Universe excludes delisted names - survivorship risk possible",
            }
        )
    if meta.get("point_in_time") is False:
        findings.append(
            {
                "code": "not_point_in_time",
                "message": "Dataset marked as not point-in-time",
            }
        )
    if "survivorship_free" in meta and meta.get("survivorship_free") is False:
        findings.append(
            {
                "code": "not_survivorship_free",
                "message": "Dataset explicitly not survivorship-free",
            }
        )
    if meta.get("index_membership") == "current_only":
        findings.append(
            {
                "code": "current_index_membership",
                "message": "Universe uses current index membership only - classic survivorship pattern",
            }
        )
    if meta.get("rebalance_uses_future_constituents") is True:
        findings.append(
            {
                "code": "future_constituents",
                "message": "Rebalance uses future constituents",
            }
        )
    return findings


def leakage_detection(params: dict[str, Any] | None = None, meta: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    blob = {**(params or {}), **(meta or {})}
    if blob.get("label_uses_future_returns") is True:
        findings.append(
            {
                "code": "label_future_returns",
                "message": "Labels use future returns - check for target leakage",
            }
        )
    if blob.get("scaler_fit_on") == "full_sample":
        findings.append(
            {
                "code": "scaler_full_sample",
                "message": "Scaler fit on full sample - possible leakage across splits",
            }
        )
    if blob.get("feature_selection_on") == "full_sample":
        findings.append(
            {
                "code": "feature_selection_full_sample",
                "message": "Feature selection on full sample - possible selection leakage",
            }
        )
    overlap = blob.get("train_test_overlap")
    if overlap:
        findings.append(
            {
                "code": "train_test_overlap",
                "message": "Train/test overlap reported",
                "data": {"overlap": overlap},
            }
        )
    embargo = blob.get("embargo_bars")
    if embargo is not None and int(embargo) <= 0 and blob.get("purged_cv") is True:
        findings.append(
            {
                "code": "purged_cv_no_embargo",
                "message": "Purged CV enabled but embargo_bars <= 0",
            }
        )
    if blob.get("target_in_features") is True:
        findings.append(
            {
                "code": "target_in_features",
                "message": "Target reported present in feature set",
            }
        )
    return findings


def reproducibility_validation(repro: dict[str, Any] | None) -> dict[str, Any]:
    required = ["config_fingerprint", "repro_fingerprint"]
    present = []
    missing = []
    if not repro:
        return {
            "ok": False,
            "present": [],
            "missing": required + ["seed", "dataset_fingerprint", "environment"],
        }
    for key in required + ["seed", "dataset_fingerprint", "environment"]:
        if repro.get(key) in (None, "", {}):
            missing.append(key)
        else:
            present.append(key)
    return {"ok": len(missing) == 0, "present": present, "missing": missing}


def validate_experiment_bundle(
    *,
    experiment: dict[str, Any],
    repro: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    trades: list[dict[str, Any]] | None = None,
    equity: list[float] | None = None,
    data_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate all validation layers into one local report."""
    params = experiment.get("params") or {}
    series = (analysis or {}).get("series") or {}
    eq = equity if equity is not None else series.get("equity")
    return {
        "experiment_id": experiment.get("id"),
        "quality_warnings": research_quality_warnings(
            experiment=experiment, repro=repro, analysis=analysis, trades=trades
        ),
        "integrity": backtest_integrity_checks(equity=eq, trades=trades, params=params),
        "data_quality": data_quality_checks(
            columns=(data_meta or {}).get("columns"),
            null_counts=(data_meta or {}).get("null_counts"),
            duplicate_timestamps=int((data_meta or {}).get("duplicate_timestamps") or 0),
            rows=(data_meta or {}).get("rows"),
        ),
        "lookahead": lookahead_bias_checks(params=params, meta=data_meta),
        "survivorship": survivorship_bias_checks(data_meta),
        "leakage": leakage_detection(params=params, meta=data_meta),
        "reproducibility": reproducibility_validation(repro),
    }
