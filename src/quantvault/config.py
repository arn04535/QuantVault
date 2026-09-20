"""Local configuration management for QuantVault."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULTS: dict[str, Any] = {
    "root": None,  # default: ./.quantvault
    "dashboard_host": "127.0.0.1",
    "dashboard_port": 8787,
    "periods_per_year": 252,
}


def config_path(root: Path | str | None = None) -> Path:
    if root is not None:
        return Path(root) / "config.json"
    env = os.environ.get("QUANTVAULT_ROOT") or os.environ.get("QUANTLEDGER_ROOT")
    if env:
        return Path(env) / "config.json"
    return Path.cwd() / ".quantvault" / "config.json"


def load_config(root: Path | str | None = None) -> dict[str, Any]:
    path = config_path(root)
    cfg = dict(DEFAULTS)
    if path.exists():
        cfg.update(json.loads(path.read_text(encoding="utf-8")))
    if os.environ.get("QUANTVAULT_ROOT"):
        cfg["root"] = os.environ["QUANTVAULT_ROOT"]
    return cfg


def save_config(data: dict[str, Any], root: Path | str | None = None) -> Path:
    path = config_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    merged = load_config(root)
    merged.update(data)
    path.write_text(json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8")
    return path
