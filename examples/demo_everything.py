"""End-to-end demo: exercise QuantLedger features and open the local dashboard.

Run from the repo root:

    python examples/demo_everything.py

Then open http://127.0.0.1:8787

Build data only:

    python examples/demo_everything.py --no-serve
"""

from __future__ import annotations

import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quantledger.analytics import returns_from_equity
from quantledger.dashboard import start_dashboard
from quantledger.exporters import backup_ledger, export_experiment, export_experiments
from quantledger.ledger import Ledger


def _synthetic_equity(n: int = 120, seed: int = 7, drift: float = 0.0008) -> list[float]:
    rng = random.Random(seed)
    equity = [100.0]
    for _ in range(n - 1):
        shock = rng.gauss(drift, 0.01)
        equity.append(max(1.0, equity[-1] * (1.0 + shock)))
    return equity


def _trades_from_equity(equity: list[float], every: int = 8) -> list[dict]:
    trades = []
    for i in range(every, len(equity), every):
        pnl = equity[i] - equity[i - every]
        trades.append({"pnl": round(pnl, 4), "notional": 10_000.0})
    return trades


def build_demo(root: Path) -> Ledger:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    ledger = Ledger.open(root)

    data_dir = root / "sample_data"
    data_dir.mkdir()
    prices = data_dir / "prices.csv"
    prices.write_text(
        "date,close\n"
        + "\n".join(f"2024-01-{i:02d},{100 + i * 0.2:.2f}" for i in range(1, 21)),
        encoding="utf-8",
    )
    ds_v1 = ledger.register_dataset("demo-prices", path=prices, version="1")
    ds_v2 = ledger.register_dataset(
        "demo-prices",
        path=prices,
        version="2",
        parent_id=ds_v1["id"],
        meta={"note": "same file, bumped version for lineage demo"},
    )

    ledger.set_profile(
        "mean_reversion",
        default_params={"lookback": 20, "threshold": 1.5},
        description="Demo mean-reversion profile",
    )

    baseline = ledger.create(
        "baseline",
        strategy="mean_reversion",
        profile="mean_reversion",
        tags=["demo", "pilot"],
        notes="First clean run",
    )
    equity_a = _synthetic_equity(seed=7, drift=0.0009)
    trades_a = _trades_from_equity(equity_a)
    rets_a = returns_from_equity(equity_a)
    bench = [r * 0.4 + 0.0001 for r in rets_a]
    ledger.analyze(
        baseline.id,
        equity=equity_a,
        trades=trades_a,
        benchmark_returns=bench,
        cost_bps=5,
        slippage_bps=2,
    )
    ledger.attach_repro(
        baseline.id,
        dataset_id=ds_v2["id"],
        seed=7,
        packages=["quantledger"],
        config={"lookback": 20, "threshold": 1.5, "universe": "demo"},
    )
    ledger.run_monte_carlo(baseline.id, rets_a, n_sims=200, seed=7)
    ledger.record_walk_forward(
        baseline.id,
        [
            {"train_metric": 1.4, "test_metric": 1.1, "start": "2023-01", "end": "2023-06"},
            {"train_metric": 1.3, "test_metric": 0.9, "start": "2023-07", "end": "2023-12"},
            {"train_metric": 1.5, "test_metric": 1.0, "start": "2024-01", "end": "2024-06"},
        ],
    )
    ledger.annotate(baseline.id, "Looks stable on this synthetic sample.")
    ledger.add_journal("Demo ledger seeded for dashboard review.", experiment_id=baseline.id)

    variant = ledger.create(
        "wider-threshold",
        strategy="mean_reversion",
        params={"lookback": 20, "threshold": 2.0},
        parent_id=baseline.id,
        tags=["demo", "candidate"],
    )
    equity_b = _synthetic_equity(seed=11, drift=0.0012)
    trades_b = _trades_from_equity(equity_b)
    rets_b = returns_from_equity(equity_b)
    ledger.analyze(
        variant.id,
        equity=equity_b,
        trades=trades_b,
        benchmark_returns=[r * 0.35 for r in rets_b],
        cost_bps=5,
        slippage_bps=2,
    )
    ledger.attach_repro(variant.id, dataset_id=ds_v2["id"], seed=11)
    ledger.store_artifact(
        variant.id,
        "notes.md",
        data="# Variant\nHigher threshold, slightly stronger drift in demo data.\n",
        kind="note",
    )

    weak = ledger.create(
        "overfit-suspect",
        strategy="mean_reversion",
        params={"lookback": 5, "threshold": 0.8},
        parent_id=baseline.id,
        tags=["demo", "caution"],
    )
    equity_c = _synthetic_equity(seed=99, drift=-0.0002)
    ledger.analyze(weak.id, equity=equity_c, trades=_trades_from_equity(equity_c))
    ledger.update(
        weak.id,
        metrics={
            **ledger.require(weak.id).metrics,
            "in_sample_sharpe": 2.4,
            "oos_sharpe": 0.3,
        },
    )

    mom = ledger.create(
        "momentum-60",
        strategy="momentum",
        params={"lookback": 60},
        tags=["demo", "momentum"],
    )
    equity_d = _synthetic_equity(seed=21, drift=0.0006)
    ledger.analyze(mom.id, equity=equity_d, trades=_trades_from_equity(equity_d))

    sweep = ledger.create_sweep(
        "lookback-sweep",
        strategy="mean_reversion",
        base_params={"threshold": 1.5},
        grid={"lookback": [10, 20, 40]},
        parent_id=baseline.id,
        tags=["demo"],
    )
    for i, eid in enumerate(sweep["experiment_ids"]):
        eq = _synthetic_equity(seed=30 + i, drift=0.0005 + i * 0.0002)
        ledger.analyze(eid, equity=eq)

    rob = ledger.robustness_of(sweep["experiment_ids"], metric="sharpe")
    ledger.store_artifact(baseline.id, "robustness.json", data=rob, kind="analysis")

    ledger.create_batch(
        "evening-batch",
        [
            {"name": "batch-a", "strategy": "momentum", "params": {"lookback": 30}},
            {"name": "batch-b", "strategy": "momentum", "params": {"lookback": 90}},
        ],
        meta={"demo": True},
    )

    ledger.sensitivity_sweep(
        "threshold-sensitivity",
        {"lookback": 20, "threshold": 1.5},
        {"threshold": [1.0, 1.5, 2.0, 2.5]},
        strategy="mean_reversion",
        parent_id=baseline.id,
    )

    ledger.checkpoint(
        "demo-freeze",
        [baseline.id, variant.id, mom.id],
        note="Dashboard demo checkpoint",
    )
    diff = ledger.compare(baseline.id, variant.id)
    ledger.store_artifact(baseline.id, "compare_vs_variant.json", data=diff, kind="analysis")

    export_dir = root / "exports"
    export_experiment(ledger, baseline.id, export_dir, fmt="json")
    export_experiment(ledger, baseline.id, export_dir, fmt="csv")
    export_experiment(ledger, baseline.id, export_dir, fmt="html")
    export_experiments(ledger, export_dir, fmt="html")
    backup_ledger(ledger, root / "demo-backup.zip")

    summary = {
        "baseline": baseline.id,
        "variant": variant.id,
        "weak": weak.id,
        "momentum": mom.id,
        "sweep": sweep["id"],
        "dataset": ds_v2["id"],
        "experiments": len(ledger.list()),
        "dashboard": "http://127.0.0.1:8787/",
        "experiment_pages": {
            "baseline": f"http://127.0.0.1:8787/experiment/{baseline.id}",
            "variant": f"http://127.0.0.1:8787/experiment/{variant.id}",
        },
    }
    (root / "DEMO_INDEX.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return ledger


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    serve = "--no-serve" not in args
    root = ROOT / ".quantledger-demo"
    print(f"Building demo ledger at {root} ...", flush=True)
    ledger = build_demo(root)
    if not serve:
        ledger.close()
        print("Demo data ready (no server).", flush=True)
        return 0

    server = start_dashboard(ledger, host="127.0.0.1", port=8787)
    print(flush=True)
    print("Dashboard ready:", flush=True)
    print("  http://127.0.0.1:8787/", flush=True)
    print(f"  ledger: {ledger.path}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
    finally:
        server.server_close()
        ledger.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
