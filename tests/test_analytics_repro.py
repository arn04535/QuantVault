from __future__ import annotations

from pathlib import Path

from quantvault.analytics import (
    expand_param_grid,
    overfitting_analysis,
    performance_report,
    walk_forward_analysis,
)
from quantvault.ledger import Ledger
from quantvault.repro import fingerprint_file, reproducibility_record


def test_performance_report_and_overfit() -> None:
    equity = [100, 101, 102, 101, 103, 104, 103, 105]
    trades = [{"pnl": 1.0, "notional": 100}, {"pnl": -0.5, "notional": 100}]
    report = performance_report(
        equity=equity,
        trades=trades,
        benchmark_returns=[0.0, 0.01, -0.01, 0.01, 0.0, -0.005, 0.01],
        cost_bps=5,
        slippage_bps=2,
    )
    assert report["equity_curve"]["n"] == 8
    assert report["drawdown"]["max_drawdown"] <= 0
    assert "sharpe" in report["risk_adjusted"]
    assert report["trades"]["n"] == 2
    assert report["transaction_costs"]["total_cost"] > 0
    assert report["benchmark"]["n"] > 0
    assert 0 <= report["srsi"]["srsi"] <= 1

    overfit = overfitting_analysis(1.5, 0.4, n_trials=30)
    assert overfit["overfit_flag"] is True

    wf = walk_forward_analysis(
        [
            {"train_metric": 1.2, "test_metric": 0.8},
            {"train_metric": 1.1, "test_metric": 0.9},
        ]
    )
    assert wf["n_windows"] == 2


def test_param_grid() -> None:
    combos = expand_param_grid({"x": 1}, {"a": [1, 2], "b": [10]})
    assert len(combos) == 2
    assert {"x": 1, "a": 1, "b": 10} in combos


def test_dataset_artifact_repro_sweep(tmp_path: Path) -> None:
    data = tmp_path / "prices.csv"
    data.write_text("date,close\n2020-01-01,100\n", encoding="utf-8")
    with Ledger.open(tmp_path / "ql") as ledger:
        ds = ledger.register_dataset("prices", path=data, version="1")
        assert ds["fingerprint"] == fingerprint_file(data)
        v2 = ledger.register_dataset(
            "prices", path=data, version="2", parent_id=ds["id"]
        )
        assert [d["id"] for d in ledger.dataset_lineage(v2["id"])] == [ds["id"], v2["id"]]

        exp = ledger.create("run", strategy="mr", params={"lookback": 20})
        repro = ledger.attach_repro(exp.id, dataset_id=ds["id"], seed=42)
        assert repro["seed"] == 42
        assert ledger.get_repro(exp.id)["repro_fingerprint"]

        art = ledger.store_artifact(exp.id, "note.txt", data="hello")
        assert Path(art["path"]).read_text(encoding="utf-8") == "hello"

        equity = [1.0, 1.01, 1.02, 1.015, 1.03]
        report = ledger.analyze(exp.id, equity=equity)
        assert "sharpe" in ledger.require(exp.id).metrics
        assert report["equity_curve"]["end"] == 1.03

        returns = [0.01, -0.005, 0.002, 0.01]
        mc = ledger.run_monte_carlo(exp.id, returns, n_sims=50, seed=1)
        assert mc["n_sims"] == 50

        sweep = ledger.create_sweep(
            "lb",
            strategy="mr",
            base_params={"threshold": 1.5},
            grid={"lookback": [10, 20]},
        )
        assert len(sweep["experiment_ids"]) == 2
        for eid in sweep["experiment_ids"]:
            ledger.update(eid, metrics={"sharpe": 1.0 if eid == sweep["experiment_ids"][0] else 0.8})
        rob = ledger.robustness_of(sweep["experiment_ids"])
        assert rob["n"] == 2

        batch = ledger.create_batch(
            "batch1",
            [{"name": "a", "params": {"x": 1}}, {"name": "b", "params": {"x": 2}}],
        )
        assert len(batch["experiment_ids"]) == 2


def test_repro_record_stable() -> None:
    a = reproducibility_record(config={"a": 1}, seed=1, dataset_fingerprint="abc")
    b = reproducibility_record(config={"a": 1}, seed=1, dataset_fingerprint="abc")
    assert a["config_fingerprint"] == b["config_fingerprint"]
