# QuantVault

**Local quant-research operating system** - record backtests, sweeps, portfolios, and paper/live runs; analyze, validate, compare, and reproduce from Python or the terminal.

[Documentation](https://arn04535.github.io/QuantVault/) · [PyPI](https://pypi.org/project/QuantVault/) · [GitHub](https://github.com/arn04535/QuantVault)

Your research data stays on your machine. This repo ships the open-source package only - not strategies, trades, or market data.

## Install

```bash
pip install QuantVault
```

```bash
pip install -e ".[dev]"                  # from source
pip install "QuantVault[export]"         # optional Parquet
```

## Quick start

```bash
quant-vault init
quant-vault record mean_reversion --param lookback=20 --tag pilot
quant-vault list
quant-vault analyze <id> --file run.json
quant-vault validate <id>
quant-vault montecarlo <id> --file run.json --sims 500
quant-vault compare <id1> <id2>
quant-vault dashboard                    # http://127.0.0.1:8787
```

```python
from quantvault import Ledger

with Ledger.open() as ledger:
    exp = ledger.record(
        "mean_reversion",
        parameters={"lookback": 20},
        tags=["pilot"],
    )
    ledger.analyze(exp.id, equity=[100, 101, 102, 101, 103])
    ledger.validate(exp.id)
```

Default storage: `./.quantvault/` (override with `--root` / `Ledger.open(path)`).

## What it covers

| Area | Highlights |
|------|------------|
| Experiment management | Registry, search, tags, notes, compare, lineage, checkpoints, journal, strategy profiles |
| Performance analysis | Equity, drawdown, risk metrics, trades, costs, benchmark, SRSI, Monte Carlo, sensitivity, robustness, walk-forward, sweeps |
| Data and reproducibility | Dataset fingerprints, config + env snapshots, seeds, artifacts |
| Research quality | Warnings, integrity checks, lookahead / survivorship / leakage heuristics, repro validation |
| Portfolio research | Multi-strategy tracking, allocation, correlation, portfolio risk and drawdown |
| Visualization and export | Local dashboard, HTML reports, CSV / JSON / Parquet, import/export, backup/restore |
| Integrations | Custom metrics, custom metadata, plugins, framework adapters |
| Paper / live | Paper fills, live-vs-backtest comparison |
| CLI | `quant-vault` (alias: `quantvault`) |

One local core · three interfaces: **Python API · CLI · optional local dashboard**.

## Docs

Full guide - how it works, Python API, complete CLI reference, features, dashboard, privacy:

**https://arn04535.github.io/QuantVault/**

## Demo

```bash
python examples/demo_everything.py
```

Synthetic data only. Opens the local dashboard.

## Privacy

Kept **out of git** by default (see `.gitignore`):

- `.quantvault/` databases and artifacts
- exports, backups, parquet/zip dumps
- `.env`, credentials, keys, `.pypirc`

Reproducibility metadata stores Python/platform/package versions - not home-directory paths or absolute executable paths.

## License

MIT · Pre-alpha · v0.1.0
