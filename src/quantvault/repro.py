"""Data fingerprinting and reproducibility helpers (stdlib only)."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any, Iterable


def fingerprint_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint_text(text: str) -> str:
    return fingerprint_bytes(text.encode("utf-8"))


def fingerprint_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return fingerprint_text(payload)


def fingerprint_file(path: Path | str, *, chunk_size: int = 1024 * 1024) -> str:
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint_path(path: Path | str) -> str:
    """Fingerprint a file, or a directory via sorted relative paths + file hashes."""
    path = Path(path)
    if path.is_file():
        return fingerprint_file(path)
    if not path.is_dir():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    for file_path in sorted(p for p in path.rglob("*") if p.is_file()):
        rel = file_path.relative_to(path).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(fingerprint_file(file_path).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def snapshot_config(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "config": config,
        "fingerprint": fingerprint_json(config),
    }


def capture_environment(packages: Iterable[str] | None = None) -> dict[str, Any]:
    """Capture non-sensitive runtime metadata for reproducibility.

    Omits working directory and absolute executable paths (those can leak
    usernames/local layout if a ledger is ever shared).
    """
    env: dict[str, Any] = {
        "python_version": platform.python_version(),
        "platform": platform.system() + " " + platform.release(),
        "python_implementation": platform.python_implementation(),
    }
    if packages:
        versions: dict[str, str] = {}
        for name in packages:
            try:
                mod = __import__(name)
                versions[name] = getattr(mod, "__version__", "unknown")
            except Exception as exc:  # noqa: BLE001 — best-effort inventory
                versions[name] = f"unavailable: {type(exc).__name__}"
        env["packages"] = versions
    return env


def reproducibility_record(
    *,
    config: dict[str, Any] | None = None,
    dataset_fingerprint: str | None = None,
    seed: int | None = None,
    environment: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "config": config or {},
        "config_fingerprint": fingerprint_json(config or {}),
        "dataset_fingerprint": dataset_fingerprint,
        "seed": seed,
        "environment": environment or capture_environment(),
        "extra": extra or {},
    }
    record["repro_fingerprint"] = fingerprint_json(
        {
            "config_fingerprint": record["config_fingerprint"],
            "dataset_fingerprint": dataset_fingerprint,
            "seed": seed,
            "environment": {
                "python_version": record["environment"].get("python_version"),
                "platform": record["environment"].get("platform"),
                "packages": record["environment"].get("packages"),
            },
            "extra": record["extra"],
        }
    )
    return record
