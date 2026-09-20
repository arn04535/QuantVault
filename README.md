# QuantVault

**Local quant-research operating system** — one local core, three interfaces:

**Python API · true CLI · optional local dashboard**

Record backtests, sweeps, portfolios, and paper/live runs; analyze, validate, compare, and reproduce — all offline.

[Documentation](https://arn04535.github.io/QuantVault/) · [GitHub](https://github.com/arn04535/QuantVault)

Research data stays on your machine. This repo ships the package only.

## Install

```bash
pip install QuantVault
```

```bash
pip install -e ".[dev]"
pip install "QuantVault[export]"   # optional Parquet
```

## Quick start

```bash
quant-vault init
quant-vault record mean_reversion --param lookback=20 --tag pilot
quant-vault analyze <id> --file run.json
quant-vault validate <id>
quant-vault montecarlo <id> --file run.json
quant-vault dashboard
```

```python
from quantvault import Ledger

with Ledger.open() as ledger:
    exp = ledger.record("RSI", parameters={"period": 14}, tags=["pilot"])
    ledger.analyze(exp.id, equity=[100, 101, 102])
    ledger.validate(exp.id)
    ledger.compare(exp.id, other_id)
```

## Capabilities

| Area | Status |
|------|--------|
| Experiment management | done |
| Backtest & performance analysis | done |
| Data & reproducibility | done |
| Research quality & validation | done |
| Portfolio & multi-strategy research | done |
| Local visualization & export | done |
| Professional CLI | done |
| Integrations / plugins / custom metrics | done |
| Paper / live vs backtest tracking | done |
| Privacy, tests, CI, docs | done |

Full command reference and guides: **https://arn04535.github.io/QuantVault/**

## Demo

```bash
python examples/demo_everything.py
```

## License

MIT · Pre-alpha
