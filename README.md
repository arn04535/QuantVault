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

## Install (development)

```bash
pip install -e ".[dev]"
```

## Planned features

### 1. Experiment Management

- **Experiment Ledger / Registry** — catalog every run with identity, status, and metadata
- **Experiment Search & Filtering** — find runs by strategy, tags, metrics, date, status
- **Experiment Tagging** — label runs for grouping and review
- **Experiment Notes & Annotations** — attach research context to individual runs
- **Experiment Comparison** — side-by-side metrics, configs, and outcomes
- **What Changed?** — diff parameters, code/data fingerprints, and results between runs
- **Experiment Lineage** — parent/child links across sweeps, forks, and follow-ups
- **Research Checkpoints** — freeze a coherent research state you can return to
- **Research Journal** — chronological notes across the research process
- **Strategy Profiles** — reusable strategy definitions and default configs

More feature areas (robustness, bias checks, paper/live vs backtest, export, CLI) will land as the package grows.

## Local-first

QuantLedger does not require a cloud account. Your experiment history stays on your machine unless you choose to export or sync it yourself.

## License

MIT
