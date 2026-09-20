# QuantLedger

Local-first Python toolkit for quantitative research management.

Record backtests, parameter sweeps, portfolio experiments, and paper trades — then search, compare, analyze, and reproduce them from Python or the terminal. Optional local dashboard for visualization.

**Your research data never leaves your machine.** QuantLedger uses a local SQLite ledger and local artifact files. This repository contains only the open-source package — not anyone’s strategies, trades, or market data.

## Install

```bash
pip install QuantLedger
```

From source:

```bash
pip install -e ".[dev]"
```

Optional Parquet export:

```bash
pip install "QuantLedger[export]"
```

## Quick start

```bash
quant-ledger init
quant-ledger create "baseline" --strategy mean_reversion --param lookback=20 --tag pilot
quant-ledger list
quant-ledger compare <id1> <id2>
quant-ledger dashboard
```

```python
from quantledger import Ledger

with Ledger.open() as ledger:
    exp = ledger.create(
        "baseline",
        strategy="mean_reversion",
        params={"lookback": 20},
    )
    ledger.analyze(exp.id, equity=[100, 101, 102, 101, 103])
```

Default storage: `./.quantledger/` (override with `--root` / `Ledger.open(path)`).

## What it covers

| Area | Highlights |
|------|------------|
| Experiment management | Registry, search, tags, notes, compare, lineage, checkpoints, journal, strategy profiles |
| Performance analysis | Equity, drawdown, risk metrics, trades, costs, benchmark, SRSI, Monte Carlo, walk-forward, sweeps |
| Data & reproducibility | Dataset fingerprints/versions/lineage, config + env snapshots, seeds, artifacts |
| Visualization & export | Local dashboard, HTML reports, CSV/JSON/Parquet export, backup/restore |
| CLI | `quant-ledger` (alias: `quantledger`) |

## Local dashboard

```bash
quant-ledger dashboard
# http://127.0.0.1:8787
```

The dashboard is a **read-only visualization layer** on the same ledger used by the API and CLI. It shows metrics and charts; it does not judge strategy quality.

Demo (synthetic data only):

```bash
python examples/demo_everything.py
```

## Privacy

Kept **out of git** by default (see `.gitignore`):

- `.quantledger/` databases and artifacts
- exports, backups, parquet/zip dumps
- `.env`, credentials, keys

Reproducibility metadata stores Python/platform/package versions — not home-directory paths or absolute executable paths.

## Status

Pre-alpha. APIs and on-disk formats may change.

## License

MIT
