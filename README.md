# QuantLedger

Free, open-source Python package for quantitative research management.

QuantLedger records what you run — backtests, parameter sweeps, portfolio experiments, paper trades — so you can answer:

- What did I run?
- What were the results?
- What data and parameters did I use?
- What changed between two experiments?
- Can I reproduce this experiment?
- Is the result robust?
- Is there evidence of overfitting or bias?
- How do different strategies compare?
- How does paper/live performance compare with the backtest?
- Can I export everything?
- Can I do all of this from Python or the terminal?

Everything is stored **locally** (local database + local files).

## Status

Pre-alpha. API and storage format may change.

## Install

```bash
pip install QuantLedger
```

From source (contributors):

```bash
pip install -e ".[dev]"
```

## Quick start

```bash
quantledger init
quantledger create "baseline" --strategy mean_reversion --param lookback=20 --tag pilot
quantledger list --strategy mean_reversion
quantledger compare <id1> <id2>
```

Python:

```python
from quantledger import Ledger

with Ledger.open() as ledger:
    exp = ledger.create("baseline", strategy="mean_reversion", params={"lookback": 20})
    print(exp.id)
```

Data lives in `./.quantledger/ledger.db` (override with `--root` / `Ledger.open(path)`).

## Experiment Management (v0.1)

| Feature | Status |
|---------|--------|
| Experiment Ledger / Registry | done |
| Experiment Search & Filtering | done |
| Experiment Tagging | done |
| Experiment Notes & Annotations | done |
| Experiment Comparison / What Changed? | done (params, metrics, tags) |
| Experiment Lineage | done |
| Research Checkpoints | done |
| Research Journal | done |
| Strategy Profiles | done |

Still deferred: code/data fingerprints, robustness/bias checks, paper vs backtest, export packs.

## Local-first

QuantLedger does not require a cloud account. Your experiment history stays on your machine unless you choose to export or sync it yourself.

## License

MIT
