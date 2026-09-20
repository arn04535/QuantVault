# QuantLedger

**Local-first quantitative research ledger** — record backtests, sweeps, and paper trades; compare, analyze, reproduce, and explore from Python or the terminal.

[Documentation](https://arn04535.github.io/QuantLedger/) · [GitHub](https://github.com/arn04535/QuantLedger)

Your research data stays on your machine. This repo ships the open-source package only — not strategies, trades, or market data.

## Install

```bash
pip install QuantLedger
```

```bash
pip install -e ".[dev]"                  # from source
pip install "QuantLedger[export]"        # optional Parquet
```

## Quick start

```bash
quant-ledger init
quant-ledger create "baseline" --strategy mean_reversion --param lookback=20 --tag pilot
quant-ledger list
quant-ledger analyze <id> --file run.json
quant-ledger montecarlo <id> --file run.json --sims 500
quant-ledger dashboard                   # http://127.0.0.1:8787
```

```python
from quantledger import Ledger

with Ledger.open() as ledger:
    exp = ledger.create("baseline", strategy="mean_reversion", params={"lookback": 20})
    ledger.analyze(exp.id, equity=[100, 101, 102, 101, 103])
```

## Docs

Full guide — how it works, Python API, **complete CLI reference**, features, dashboard, privacy:

**https://arn04535.github.io/QuantLedger/**

## Demo

```bash
python examples/demo_everything.py
```

Synthetic data only. Opens the local dashboard.

## License

MIT · Pre-alpha
