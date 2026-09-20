from __future__ import annotations

from pathlib import Path

from quantvault.ledger import Ledger
from quantvault.plugins import adapt_framework, compute_custom_metrics, list_frameworks, register_framework_adapter
from quantvault.validation import lookahead_bias_checks, leakage_detection, survivorship_bias_checks, validate_experiment_bundle


def test_validate_portfolio_live(tmp_path: Path) -> None:
    with Ledger.open(tmp_path) as ledger:
        a = ledger.record("mean_reversion", parameters={"lookback": 20}, tags=["t"])
        b = ledger.record("momentum", parameters={"lookback": 60})
        ledger.analyze(a.id, equity=[100, 101, 102, 103, 104])
        ledger.analyze(b.id, equity=[100, 100.5, 101, 102, 103])
        report = ledger.validate(a.id)
        assert report["experiment_id"] == a.id
        assert "quality_warnings" in report

        port = ledger.create_portfolio(
            "mix",
            [
                {"experiment_id": a.id, "weight": 0.6},
                {"experiment_id": b.id, "weight": 0.4},
            ],
        )
        assert port["allocation"]["n_strategies"] == 2
        assert len(ledger.list_portfolios()) == 1

        live = ledger.track_live(
            "paper-1",
            kind="paper",
            backtest_id=a.id,
            fills=[{"pnl": 1.0}, {"pnl": -0.5}],
            equity=[1.0, 1.01, 1.02, 1.015, 1.03],
        )
        assert live["metrics"]["summary"]["n"] == 2
        assert ledger.list_live(kind="paper")

        wf = ledger.record_walk_forward(
            a.id,
            [
                {"train_metric": 1.2, "test_metric": 1.0},
                {"train_metric": 1.1, "test_metric": 0.9},
            ],
        )
        assert wf["n_windows"] == 2
        over = ledger.record_overfitting(a.id, in_sample=1.5, out_of_sample=0.8, n_trials=25)
        assert over["overfit_flag"] is True
        chart = ledger.store_custom_chart(
            a.id,
            {"type": "line", "labels": [1, 2, 3], "datasets": [{"label": "x", "data": [1, 2, 3]}]},
            name="demo",
        )
        assert chart["name"] == "custom_charts.json"


def test_plugins_and_bundle() -> None:
    register_framework_adapter("dummy", lambda **kw: {"strategy": kw.get("strategy", "x"), "parameters": {}})
    metrics = compute_custom_metrics({"trades": [{"pnl": 1}, {"pnl": -1}]})
    assert "custom_hit_rate" in metrics
    bundle = validate_experiment_bundle(experiment={"id": "1", "params": {}, "metrics": {}})
    assert bundle["reproducibility"]["ok"] is False
    assert "generic" in list_frameworks()
    adapted = adapt_framework(
        "vectorbt",
        {"strategy": "mr", "value": [100, 101, 102], "stats": {"sharpe_ratio": 1.2}},
    )
    assert adapted["strategy"] == "mr"
    assert adapted["metrics"]["sharpe"] == 1.2
    assert lookahead_bias_checks(meta={"signal_timing": "close_same_bar"})
    assert survivorship_bias_checks({"index_membership": "current_only"})
    assert leakage_detection(meta={"target_in_features": True})
