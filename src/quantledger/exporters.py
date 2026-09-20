"""Export, import, backup, and restore for local ledgers."""

from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path
from typing import Any

from quantledger.ledger import Ledger


def export_experiment(
    ledger: Ledger,
    experiment_id: str,
    dest: Path | str,
    *,
    fmt: str = "json",
) -> Path:
    exp = ledger.require(experiment_id)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment": exp.to_dict(),
        "repro": ledger.get_repro(exp.id),
        "artifacts": ledger.list_artifacts(exp.id),
    }
    fmt = fmt.lower()
    if fmt == "json":
        path = dest / f"{exp.id}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return path
    if fmt == "csv":
        path = dest / f"{exp.id}.csv"
        _write_experiment_csv(path, exp.to_dict())
        return path
    if fmt == "html":
        from quantledger.reports import render_experiment_html

        path = dest / f"{exp.id}.html"
        path.write_text(render_experiment_html(ledger, exp.id), encoding="utf-8")
        return path
    if fmt == "parquet":
        path = dest / f"{exp.id}.parquet"
        _write_parquet(path, [exp.to_dict()])
        return path
    raise ValueError(f"unsupported format: {fmt}")


def export_experiments(
    ledger: Ledger,
    dest: Path | str,
    *,
    fmt: str = "json",
    experiment_ids: list[str] | None = None,
) -> Path:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    experiments = (
        [ledger.require(i).to_dict() for i in experiment_ids]
        if experiment_ids
        else [e.to_dict() for e in ledger.list()]
    )
    fmt = fmt.lower()
    if fmt == "json":
        path = dest / "experiments.json"
        path.write_text(json.dumps(experiments, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return path
    if fmt == "csv":
        path = dest / "experiments.csv"
        _write_experiments_table_csv(path, experiments)
        return path
    if fmt == "parquet":
        path = dest / "experiments.parquet"
        _write_parquet(path, experiments)
        return path
    if fmt == "html":
        from quantledger.reports import render_ledger_html

        path = dest / "report.html"
        path.write_text(render_ledger_html(ledger), encoding="utf-8")
        return path
    raise ValueError(f"unsupported format: {fmt}")


def import_experiment_json(ledger: Ledger, path: Path | str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "experiment" in data:
        exp_data = data["experiment"]
    else:
        exp_data = data
    created = ledger.create(
        exp_data.get("name", "imported"),
        strategy=exp_data.get("strategy", ""),
        params=exp_data.get("params"),
        metrics=exp_data.get("metrics"),
        tags=list(exp_data.get("tags") or []) + ["imported"],
        notes=exp_data.get("notes", ""),
        status=exp_data.get("status", "created"),
    )
    if data.get("repro"):
        repro = data["repro"]
        ledger.attach_repro(
            created.id,
            config=repro.get("config"),
            seed=repro.get("seed"),
            extra={"imported_from": str(path)},
        )
    return created.to_dict()


def backup_ledger(ledger: Ledger, dest: Path | str) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.suffix.lower() != ".zip":
        dest = dest.with_suffix(".zip")
    root = ledger.root
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        db = ledger.path
        if db.exists():
            zf.write(db, arcname="ledger.db")
        artifacts = root / "artifacts"
        if artifacts.exists():
            for file_path in artifacts.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, arcname=str(file_path.relative_to(root)))
    return dest


def restore_ledger(archive: Path | str, root: Path | str) -> Path:
    archive = Path(archive)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(root)
    return root / "ledger.db"


def _write_experiment_csv(path: Path, exp: dict[str, Any]) -> None:
    flat = {
        "id": exp.get("id"),
        "name": exp.get("name"),
        "strategy": exp.get("strategy"),
        "status": exp.get("status"),
        "parent_id": exp.get("parent_id"),
        "tags": ",".join(exp.get("tags") or []),
        "notes": exp.get("notes"),
        "created_at": exp.get("created_at"),
        "updated_at": exp.get("updated_at"),
        "params_json": json.dumps(exp.get("params") or {}, sort_keys=True),
        "metrics_json": json.dumps(exp.get("metrics") or {}, sort_keys=True),
    }
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(flat))
        writer.writeheader()
        writer.writerow(flat)


def _write_experiments_table_csv(path: Path, experiments: list[dict[str, Any]]) -> None:
    if not experiments:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = [
        "id",
        "name",
        "strategy",
        "status",
        "parent_id",
        "tags",
        "created_at",
        "updated_at",
        "params_json",
        "metrics_json",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for exp in experiments:
            writer.writerow(
                {
                    "id": exp.get("id"),
                    "name": exp.get("name"),
                    "strategy": exp.get("strategy"),
                    "status": exp.get("status"),
                    "parent_id": exp.get("parent_id"),
                    "tags": ",".join(exp.get("tags") or []),
                    "created_at": exp.get("created_at"),
                    "updated_at": exp.get("updated_at"),
                    "params_json": json.dumps(exp.get("params") or {}, sort_keys=True),
                    "metrics_json": json.dumps(exp.get("metrics") or {}, sort_keys=True),
                }
            )


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise SystemExit(
            "Parquet export requires pyarrow. Install with: pip install 'QuantLedger[export]'"
        ) from exc

    flat_rows = []
    for exp in rows:
        flat_rows.append(
            {
                "id": exp.get("id"),
                "name": exp.get("name"),
                "strategy": exp.get("strategy"),
                "status": exp.get("status"),
                "parent_id": exp.get("parent_id"),
                "tags": ",".join(exp.get("tags") or []),
                "created_at": exp.get("created_at"),
                "updated_at": exp.get("updated_at"),
                "params_json": json.dumps(exp.get("params") or {}, sort_keys=True),
                "metrics_json": json.dumps(exp.get("metrics") or {}, sort_keys=True),
            }
        )
    table = pa.Table.from_pylist(flat_rows)
    pq.write_table(table, path)
