# QuantVault

**Local quant-research operating system** - one local core, three interfaces:

**Python API · true CLI · optional local dashboard**

Record backtests, sweeps, portfolios, and paper/live runs. Analyze, validate, compare, and reproduce - all offline.

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

- **CLI:** `quant-vault` (alias: `quantvault`)
- **Import:** `from quantvault import Ledger`
- **Storage:** `./.quantvault/` (override with `--root` / `Ledger.open(path)` / `QUANTVAULT_ROOT`)
- **Requires:** Python 3.10+

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
    ledger.compare(exp.id, other_id)
```

Experiment IDs accept unambiguous prefixes (`quant-vault show a1b2`).

## Architecture

```text
                 QUANTVAULT
                      |
                +-----+-----+
                | Local Core |  experiments · analytics · validation
                |            |  reproducibility · storage · research
                +-----+-----+
          +-----------+-----------+
          |           |           |
     Python API      CLI    Local Dashboard
          +-----------+-----------+
                      |
               Local Storage
            SQLite · files · artifacts
```

Every substantive feature works locally and is available from both the Python API and the CLI. The dashboard is a read-only visualization layer on the same ledger.

## What it covers

| Area | Highlights |
|------|------------|
| Experiment management | Registry, search, tags, notes, compare, lineage, checkpoints, journal, strategy profiles |
| Performance analysis | Equity, drawdown, risk metrics, trades, costs, benchmark, SRSI, Monte Carlo, sensitivity, robustness, walk-forward, sweeps |
| Data and reproducibility | Dataset fingerprints, config + env snapshots, seeds, artifacts |
| Research quality | Warnings, integrity checks, lookahead / survivorship / leakage heuristics, repro validation |
| Portfolio research | Multi-strategy tracking, allocation, correlation, portfolio risk and drawdown |
| Visualization and export | Local dashboard, HTML reports, custom charts, CSV / JSON / Parquet, import/export, backup/restore |
| Integrations | Custom metrics, custom metadata, plugins, framework adapters (`generic`, `vectorbt`, `backtesting.py`, `zipline`) |
| Paper / live | Paper fills, live-vs-backtest comparison |

## CLI reference

Global options:

```bash
quant-vault --help
quant-vault --version
quant-vault --root PATH <command> ...
```

### Experiment management

| Command | What it does |
|---------|--------------|
| `quant-vault init` | Create local ledger at `./.quantvault/` |
| `quant-vault record STRATEGY [--name N] [--param k=v] [--metric k=v] [--tag T] [--parent ID] [--profile P] [--notes TEXT] [--status S]` | Record a research run |
| `quant-vault create NAME [--strategy S] [--param k=v] [--metric k=v] [--tag T] [--parent ID] [--profile P] [--notes TEXT] [--status S]` | Register a named experiment |
| `quant-vault list [--strategy S] [--status S] [--tag T] [-q QUERY] [--json]` | Search / filter experiments |
| `quant-vault show ID` | Print one experiment |
| `quant-vault set ID [--name N] [--strategy S] [--status S] [--param k=v] [--metric k=v]` | Update fields |
| `quant-vault tag ID TAG [TAG...]` | Add tags |
| `quant-vault note ID TEXT` | Append a note |
| `quant-vault compare LEFT RIGHT` | Diff params / metrics / tags |
| `quant-vault lineage ID [--json]` | Ancestors and children |
| `quant-vault journal [TEXT] [--experiment ID] [--json]` | Research journal (list or append) |
| `quant-vault checkpoint [NAME ID...] [--note TEXT] [--json]` | Freeze a set of runs |
| `quant-vault profile [NAME] [--set] [--param k=v] [--description TEXT] [--json]` | Strategy profiles |

### Analysis and validation

| Command | What it does |
|---------|--------------|
| `quant-vault analyze ID [--file run.json] [--cost-bps N] [--slippage-bps N]` | Performance report (or show stored) |
| `quant-vault validate ID` | Quality / integrity / bias / repro checks |
| `quant-vault risk ID` | Risk snapshot |
| `quant-vault srsi ID [--file run.json] [--window N]` | Sharpe Ratio Stability Index |
| `quant-vault montecarlo ID --file run.json [--sims N] [--seed N]` | Monte Carlo fan + distribution |
| `quant-vault robustness ID [ID...] [--metric sharpe]` | Neighborhood stability |
| `quant-vault walkforward ID [--file windows.json]` | Walk-forward windows analysis |
| `quant-vault overfit ID [--in-sample N] [--out-of-sample N] [--trials N]` | IS/OOS overfitting gap |
| `quant-vault sensitivity NAME --grid '{"p":[1,2]}' [--strategy S] [--param k=v] [--parent ID]` | One-at-a-time sensitivity batch |
| `quant-vault sweep [NAME] [--strategy S] [--param k=v] [--grid '{...}'] [--parent ID]` | Parameter sweep -> child experiments |
| `quant-vault batch [--name N] [--file specs.json]` | Create / list experiment batches |
| `quant-vault chart ID --file chart.json [--name NAME]` | Store a custom Chart.js chart |
| `quant-vault adapt FRAMEWORK --file result.json [--dry-run]` | Import via adapter (`generic`, `vectorbt`, `backtesting.py`, `zipline`) |

### Data and reproducibility

| Command | What it does |
|---------|--------------|
| `quant-vault dataset --register NAME --path FILE [--version V] [--parent ID]` | Fingerprint and register a dataset |
| `quant-vault dataset [--name N] [--lineage ID] [--json]` | List datasets / show lineage |
| `quant-vault artifact EXP [--file PATH] [--name NAME] [--json]` | Store or list artifacts |
| `quant-vault repro --attach ID [--config cfg.json] [--dataset ID] [--seed N] [--package PKG]` | Attach reproducibility metadata |
| `quant-vault repro --show ID` | Show repro record |
| `quant-vault reproduce ID` | Bundle needed to re-run |

### Portfolio and paper / live

| Command | What it does |
|---------|--------------|
| `quant-vault portfolio --name N --file legs.json` | Multi-strategy portfolio (`[{experiment_id, weight}]`) |
| `quant-vault portfolio` | List portfolios |
| `quant-vault live --name N --backtest ID [--kind paper\|live] [--fills fills.json] [--equity equity.json]` | Track paper/live vs backtest |
| `quant-vault live [--kind paper\|live]` | List live/paper runs |

### Reports, export, dashboard

| Command | What it does |
|---------|--------------|
| `quant-vault report [ID] [--format json\|html\|csv\|parquet] [--out PATH]` | Research report |
| `quant-vault export [ID] [--format json\|csv\|html\|parquet] [--out DIR]` | Export experiment(s) |
| `quant-vault import FILE.json` | Import an experiment JSON pack |
| `quant-vault backup [--out backup.zip]` | Zip DB + artifacts |
| `quant-vault restore ARCHIVE.zip` | Restore into ledger root |
| `quant-vault dashboard [--host 127.0.0.1] [--port 8787]` | Local visualization UI |
| `quant-vault config [--set k=v]` | Local configuration |
| `quant-vault plugins` | List plugins, custom metrics, framework adapters |

### Analyze / Monte Carlo input file

`run.json` example:

```json
{
  "equity": [100, 101.2, 100.8, 102.5],
  "returns": [0.012, -0.004, 0.017],
  "trades": [{"pnl": 15.0, "notional": 10000}],
  "benchmark_returns": [0.001, 0.0, 0.002]
}
```

```bash
quant-vault analyze <id> --file run.json --cost-bps 5 --slippage-bps 2
quant-vault montecarlo <id> --file run.json --sims 500 --seed 7
```

## Python API

Same core as the CLI:

```python
from quantvault import Ledger

with Ledger.open() as ledger:
    exp = ledger.record(
        "mean_reversion",
        parameters={"lookback": 20, "threshold": 1.5},
        tags=["pilot"],
    )

    ledger.analyze(
        exp.id,
        equity=equity_curve,
        trades=[{"pnl": 12.5, "notional": 10_000}],
        benchmark_returns=bench,
        cost_bps=5,
        slippage_bps=2,
    )
    ledger.validate(exp.id)
    ledger.run_monte_carlo(exp.id, returns, n_sims=500, seed=7)
    ledger.attach_repro(exp.id, seed=7, packages=["numpy"])

    ledger.compare(exp.id, other_id)
    ledger.list(strategy="mean_reversion", tag="pilot")
    ledger.create_portfolio("book", [{"experiment_id": exp.id, "weight": 1.0}])
    ledger.track_live("paper-1", kind="paper", backtest_id=exp.id, equity=paper_eq)
```

## Local dashboard

```bash
quant-vault dashboard
# http://127.0.0.1:8787/
# /experiment/<id>
# /strategy/<name>
```

Shows experiment blotter, strategy books, portfolios, paper/live runs, and full experiment pages (equity, drawdown, Monte Carlo, validation, walk-forward, trades, costs, repro). Charts only - no strategy verdicts.

## Demo

```bash
python examples/demo_everything.py
```

Synthetic data only. Seeds a local demo ledger and opens the dashboard.

## Privacy

Kept **out of git** by default (see `.gitignore`):

- `.quantvault/` databases and artifacts
- exports, backups, parquet/zip dumps
- `.env`, credentials, keys, `.pypirc`

Reproducibility metadata stores Python/platform/package versions - not home-directory paths or absolute executable paths.

## License

MIT · Pre-alpha · v0.1.1
