"""Local experiment ledger backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _loads(text: str, default: Any) -> Any:
    if not text:
        return default
    return json.loads(text)


@dataclass
class Experiment:
    id: str
    name: str
    strategy: str = ""
    status: str = "created"
    params: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    parent_id: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Ledger:
    """Experiment registry stored in a local SQLite database."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    @classmethod
    def open(cls, root: Path | str | None = None) -> Ledger:
        if root is None:
            import os

            env = os.environ.get("QUANTVAULT_ROOT")
            base = Path(env) if env else Path.cwd() / ".quantvault"
        else:
            base = Path(root)
        return cls(Path(base) / "ledger.db")

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Ledger:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _migrate(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                strategy TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'created',
                params_json TEXT NOT NULL DEFAULT '{}',
                metrics_json TEXT NOT NULL DEFAULT '{}',
                tags_json TEXT NOT NULL DEFAULT '[]',
                notes TEXT NOT NULL DEFAULT '',
                parent_id TEXT REFERENCES experiments(id),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id TEXT REFERENCES experiments(id),
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                experiment_ids_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS strategy_profiles (
                name TEXT PRIMARY KEY,
                description TEXT NOT NULL DEFAULT '',
                default_params_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS datasets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT NOT NULL DEFAULT '1',
                fingerprint TEXT NOT NULL,
                uri TEXT NOT NULL DEFAULT '',
                meta_json TEXT NOT NULL DEFAULT '{}',
                parent_id TEXT REFERENCES datasets(id),
                created_at TEXT NOT NULL,
                UNIQUE(name, version)
            );
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                experiment_id TEXT NOT NULL REFERENCES experiments(id),
                name TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'file',
                path TEXT NOT NULL,
                fingerprint TEXT NOT NULL DEFAULT '',
                meta_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS experiment_repro (
                experiment_id TEXT PRIMARY KEY REFERENCES experiments(id),
                dataset_id TEXT REFERENCES datasets(id),
                config_json TEXT NOT NULL DEFAULT '{}',
                env_json TEXT NOT NULL DEFAULT '{}',
                seed INTEGER,
                repro_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sweeps (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                base_params_json TEXT NOT NULL,
                grid_json TEXT NOT NULL,
                experiment_ids_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS batches (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                experiment_ids_json TEXT NOT NULL,
                meta_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS experiment_meta (
                experiment_id TEXT PRIMARY KEY REFERENCES experiments(id),
                meta_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS portfolios (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                weights_json TEXT NOT NULL,
                experiment_ids_json TEXT NOT NULL,
                meta_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS live_runs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'paper',
                backtest_id TEXT REFERENCES experiments(id),
                fills_json TEXT NOT NULL DEFAULT '[]',
                equity_json TEXT NOT NULL DEFAULT '[]',
                metrics_json TEXT NOT NULL DEFAULT '{}',
                meta_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    @property
    def root(self) -> Path:
        return self.path.parent

    @property
    def artifacts_dir(self) -> Path:
        path = self.root / "artifacts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _row_to_experiment(self, row: sqlite3.Row) -> Experiment:
        return Experiment(
            id=row["id"],
            name=row["name"],
            strategy=row["strategy"],
            status=row["status"],
            params=_loads(row["params_json"], {}),
            metrics=_loads(row["metrics_json"], {}),
            tags=_loads(row["tags_json"], []),
            notes=row["notes"],
            parent_id=row["parent_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def create(
        self,
        name: str,
        *,
        strategy: str = "",
        params: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        notes: str = "",
        parent_id: str | None = None,
        status: str = "created",
        profile: str | None = None,
    ) -> Experiment:
        params = dict(params or {})
        if profile:
            prof = self.get_profile(profile)
            if prof is None:
                raise KeyError(f"unknown strategy profile: {profile}")
            merged = dict(prof["default_params"])
            merged.update(params)
            params = merged
            strategy = strategy or profile

        now = _now()
        exp = Experiment(
            id=uuid.uuid4().hex[:12],
            name=name,
            strategy=strategy,
            status=status,
            params=params,
            metrics=dict(metrics or {}),
            tags=sorted(set(tags or [])),
            notes=notes,
            parent_id=parent_id,
            created_at=now,
            updated_at=now,
        )
        self._conn.execute(
            """
            INSERT INTO experiments (
                id, name, strategy, status, params_json, metrics_json,
                tags_json, notes, parent_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exp.id,
                exp.name,
                exp.strategy,
                exp.status,
                _dumps(exp.params),
                _dumps(exp.metrics),
                _dumps(exp.tags),
                exp.notes,
                exp.parent_id,
                exp.created_at,
                exp.updated_at,
            ),
        )
        self._conn.commit()
        return exp

    def get(self, experiment_id: str) -> Experiment | None:
        row = self._conn.execute(
            "SELECT * FROM experiments WHERE id = ?",
            (experiment_id,),
        ).fetchone()
        return self._row_to_experiment(row) if row else None

    def resolve(self, experiment_id: str) -> Experiment:
        """Resolve a full id or unambiguous prefix (e.g. ``183``)."""
        exact = self.get(experiment_id)
        if exact is not None:
            return exact
        matches = [
            e
            for e in self._conn.execute(
                "SELECT * FROM experiments WHERE id LIKE ?",
                (f"{experiment_id}%",),
            ).fetchall()
        ]
        experiments = [self._row_to_experiment(row) for row in matches]
        if len(experiments) == 1:
            return experiments[0]
        if not experiments:
            raise KeyError(f"experiment not found: {experiment_id}")
        ids = ", ".join(e.id for e in experiments)
        raise KeyError(f"ambiguous experiment id {experiment_id!r}: {ids}")

    def require(self, experiment_id: str) -> Experiment:
        return self.resolve(experiment_id)

    def list(
        self,
        *,
        strategy: str | None = None,
        status: str | None = None,
        tag: str | None = None,
        q: str | None = None,
        parent_id: str | None = None,
    ) -> list[Experiment]:
        sql = "SELECT * FROM experiments WHERE 1=1"
        args: list[Any] = []
        if strategy is not None:
            sql += " AND strategy = ?"
            args.append(strategy)
        if status is not None:
            sql += " AND status = ?"
            args.append(status)
        if parent_id is not None:
            sql += " AND parent_id = ?"
            args.append(parent_id)
        if q is not None:
            sql += " AND (name LIKE ? OR notes LIKE ? OR strategy LIKE ?)"
            like = f"%{q}%"
            args.extend([like, like, like])
        sql += " ORDER BY created_at DESC"
        rows = self._conn.execute(sql, args).fetchall()
        experiments = [self._row_to_experiment(row) for row in rows]
        if tag is not None:
            experiments = [e for e in experiments if tag in e.tags]
        return experiments

    def update(
        self,
        experiment_id: str,
        *,
        name: str | None = None,
        strategy: str | None = None,
        status: str | None = None,
        params: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
        parent_id: str | None = ...,  # type: ignore[assignment]
    ) -> Experiment:
        exp = self.require(experiment_id)
        if name is not None:
            exp.name = name
        if strategy is not None:
            exp.strategy = strategy
        if status is not None:
            exp.status = status
        if params is not None:
            exp.params = params
        if metrics is not None:
            exp.metrics = metrics
        if tags is not None:
            exp.tags = sorted(set(tags))
        if notes is not None:
            exp.notes = notes
        if parent_id is not ...:
            exp.parent_id = parent_id
        exp.updated_at = _now()
        self._conn.execute(
            """
            UPDATE experiments SET
                name = ?, strategy = ?, status = ?, params_json = ?,
                metrics_json = ?, tags_json = ?, notes = ?, parent_id = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                exp.name,
                exp.strategy,
                exp.status,
                _dumps(exp.params),
                _dumps(exp.metrics),
                _dumps(exp.tags),
                exp.notes,
                exp.parent_id,
                exp.updated_at,
                exp.id,
            ),
        )
        self._conn.commit()
        return exp

    def add_tags(self, experiment_id: str, *tags: str) -> Experiment:
        exp = self.require(experiment_id)
        return self.update(experiment_id, tags=sorted(set(exp.tags) | set(tags)))

    def annotate(self, experiment_id: str, text: str) -> Experiment:
        exp = self.require(experiment_id)
        notes = f"{exp.notes}\n{text}".strip() if exp.notes else text
        return self.update(experiment_id, notes=notes)

    def children(self, experiment_id: str) -> list[Experiment]:
        self.require(experiment_id)
        return self.list(parent_id=experiment_id)

    def lineage(self, experiment_id: str) -> list[Experiment]:
        """Return ancestors root→…→self, then direct children."""
        chain: list[Experiment] = []
        current = self.require(experiment_id)
        seen: set[str] = set()
        while current is not None:
            if current.id in seen:
                break
            seen.add(current.id)
            chain.append(current)
            current = self.get(current.parent_id) if current.parent_id else None
        chain.reverse()
        kids = [c for c in self.children(experiment_id) if c.id not in seen]
        return chain + kids

    def compare(self, left_id: str, right_id: str) -> dict[str, Any]:
        left = self.require(left_id)
        right = self.require(right_id)
        return {
            "left": left.id,
            "right": right.id,
            "name": {"left": left.name, "right": right.name},
            "strategy": {"left": left.strategy, "right": right.strategy},
            "status": {"left": left.status, "right": right.status},
            "params": _diff_maps(left.params, right.params),
            "metrics": _diff_maps(left.metrics, right.metrics),
            "tags": {
                "only_left": sorted(set(left.tags) - set(right.tags)),
                "only_right": sorted(set(right.tags) - set(left.tags)),
                "shared": sorted(set(left.tags) & set(right.tags)),
            },
            "parent_id": {"left": left.parent_id, "right": right.parent_id},
        }

    def add_journal(self, body: str, *, experiment_id: str | None = None) -> dict[str, Any]:
        if experiment_id is not None:
            self.require(experiment_id)
        created = _now()
        cur = self._conn.execute(
            "INSERT INTO journal (experiment_id, body, created_at) VALUES (?, ?, ?)",
            (experiment_id, body, created),
        )
        self._conn.commit()
        return {
            "id": cur.lastrowid,
            "experiment_id": experiment_id,
            "body": body,
            "created_at": created,
        }

    def list_journal(self, *, experiment_id: str | None = None) -> list[dict[str, Any]]:
        if experiment_id is None:
            rows = self._conn.execute(
                "SELECT * FROM journal ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM journal WHERE experiment_id = ? ORDER BY created_at DESC",
                (experiment_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def checkpoint(
        self,
        name: str,
        experiment_ids: list[str],
        *,
        note: str = "",
    ) -> dict[str, Any]:
        for eid in experiment_ids:
            self.require(eid)
        created = _now()
        cp = {
            "id": uuid.uuid4().hex[:12],
            "name": name,
            "note": note,
            "experiment_ids": list(experiment_ids),
            "created_at": created,
        }
        self._conn.execute(
            """
            INSERT INTO checkpoints (id, name, note, experiment_ids_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (cp["id"], name, note, _dumps(experiment_ids), created),
        )
        self._conn.commit()
        return cp

    def list_checkpoints(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM checkpoints ORDER BY created_at DESC"
        ).fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "note": row["note"],
                "experiment_ids": _loads(row["experiment_ids_json"], []),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def set_profile(
        self,
        name: str,
        *,
        default_params: dict[str, Any] | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        now = _now()
        existing = self.get_profile(name)
        params = dict(default_params or {})
        if existing is None:
            self._conn.execute(
                """
                INSERT INTO strategy_profiles
                    (name, description, default_params_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, description, _dumps(params), now, now),
            )
            created = now
        else:
            if default_params is None:
                params = existing["default_params"]
            if not description and existing["description"]:
                description = existing["description"]
            self._conn.execute(
                """
                UPDATE strategy_profiles
                SET description = ?, default_params_json = ?, updated_at = ?
                WHERE name = ?
                """,
                (description, _dumps(params), now, name),
            )
            created = existing["created_at"]
        self._conn.commit()
        return {
            "name": name,
            "description": description,
            "default_params": params,
            "created_at": created,
            "updated_at": now,
        }

    def get_profile(self, name: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM strategy_profiles WHERE name = ?",
            (name,),
        ).fetchone()
        if row is None:
            return None
        return {
            "name": row["name"],
            "description": row["description"],
            "default_params": _loads(row["default_params_json"], {}),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_profiles(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM strategy_profiles ORDER BY name"
        ).fetchall()
        return [
            {
                "name": row["name"],
                "description": row["description"],
                "default_params": _loads(row["default_params_json"], {}),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    # --- Data & reproducibility ---

    def register_dataset(
        self,
        name: str,
        *,
        path: Path | str | None = None,
        fingerprint: str | None = None,
        version: str = "1",
        uri: str = "",
        parent_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from quantvault.repro import fingerprint_path

        if fingerprint is None:
            if path is None:
                raise ValueError("provide path or fingerprint")
            fingerprint = fingerprint_path(path)
            uri = uri or str(Path(path))
        created = _now()
        ds = {
            "id": uuid.uuid4().hex[:12],
            "name": name,
            "version": version,
            "fingerprint": fingerprint,
            "uri": uri,
            "meta": dict(meta or {}),
            "parent_id": parent_id,
            "created_at": created,
        }
        self._conn.execute(
            """
            INSERT INTO datasets
                (id, name, version, fingerprint, uri, meta_json, parent_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ds["id"],
                name,
                version,
                fingerprint,
                uri,
                _dumps(ds["meta"]),
                parent_id,
                created,
            ),
        )
        self._conn.commit()
        return ds

    def get_dataset(self, dataset_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM datasets WHERE id = ?", (dataset_id,)
        ).fetchone()
        return self._row_to_dataset(row) if row else None

    def list_datasets(self, *, name: str | None = None) -> list[dict[str, Any]]:
        if name is None:
            rows = self._conn.execute(
                "SELECT * FROM datasets ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM datasets WHERE name = ? ORDER BY created_at DESC",
                (name,),
            ).fetchall()
        return [self._row_to_dataset(row) for row in rows]

    def dataset_lineage(self, dataset_id: str) -> list[dict[str, Any]]:
        chain: list[dict[str, Any]] = []
        current = self.get_dataset(dataset_id)
        if current is None:
            raise KeyError(f"dataset not found: {dataset_id}")
        seen: set[str] = set()
        while current is not None:
            if current["id"] in seen:
                break
            seen.add(current["id"])
            chain.append(current)
            current = (
                self.get_dataset(current["parent_id"]) if current["parent_id"] else None
            )
        chain.reverse()
        return chain

    def _row_to_dataset(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "name": row["name"],
            "version": row["version"],
            "fingerprint": row["fingerprint"],
            "uri": row["uri"],
            "meta": _loads(row["meta_json"], {}),
            "parent_id": row["parent_id"],
            "created_at": row["created_at"],
        }

    def store_artifact(
        self,
        experiment_id: str,
        name: str,
        *,
        source: Path | str | None = None,
        data: bytes | str | dict[str, Any] | None = None,
        kind: str = "file",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from quantvault.repro import fingerprint_bytes, fingerprint_file, fingerprint_json

        self.require(experiment_id)
        dest_dir = self.artifacts_dir / experiment_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / name
        if source is not None:
            src = Path(source)
            dest.write_bytes(src.read_bytes())
            fp = fingerprint_file(dest)
        elif isinstance(data, (dict, list)):
            text = json.dumps(data, indent=2, sort_keys=True, default=str)
            dest.write_text(text, encoding="utf-8")
            fp = fingerprint_json(data)
            kind = "json" if kind == "file" else kind
        elif isinstance(data, str):
            dest.write_text(data, encoding="utf-8")
            fp = fingerprint_bytes(data.encode("utf-8"))
        elif isinstance(data, bytes):
            dest.write_bytes(data)
            fp = fingerprint_bytes(data)
        else:
            raise ValueError("provide source or data")

        created = _now()
        art = {
            "id": uuid.uuid4().hex[:12],
            "experiment_id": experiment_id,
            "name": name,
            "kind": kind,
            "path": str(dest),
            "fingerprint": fp,
            "meta": dict(meta or {}),
            "created_at": created,
        }
        self._conn.execute(
            """
            INSERT INTO artifacts
                (id, experiment_id, name, kind, path, fingerprint, meta_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                art["id"],
                experiment_id,
                name,
                kind,
                art["path"],
                fp,
                _dumps(art["meta"]),
                created,
            ),
        )
        self._conn.commit()
        return art

    def list_artifacts(self, experiment_id: str) -> list[dict[str, Any]]:
        self.require(experiment_id)
        rows = self._conn.execute(
            "SELECT * FROM artifacts WHERE experiment_id = ? ORDER BY created_at DESC",
            (experiment_id,),
        ).fetchall()
        return [
            {
                "id": row["id"],
                "experiment_id": row["experiment_id"],
                "name": row["name"],
                "kind": row["kind"],
                "path": row["path"],
                "fingerprint": row["fingerprint"],
                "meta": _loads(row["meta_json"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def attach_repro(
        self,
        experiment_id: str,
        *,
        config: dict[str, Any] | None = None,
        dataset_id: str | None = None,
        seed: int | None = None,
        packages: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from quantvault.repro import capture_environment, reproducibility_record

        self.require(experiment_id)
        dataset_fp = None
        if dataset_id is not None:
            ds = self.get_dataset(dataset_id)
            if ds is None:
                raise KeyError(f"dataset not found: {dataset_id}")
            dataset_fp = ds["fingerprint"]
        env = capture_environment(packages)
        record = reproducibility_record(
            config=config or self.require(experiment_id).params,
            dataset_fingerprint=dataset_fp,
            seed=seed,
            environment=env,
            extra=extra,
        )
        now = _now()
        self._conn.execute(
            """
            INSERT INTO experiment_repro (
                experiment_id, dataset_id, config_json, env_json, seed, repro_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(experiment_id) DO UPDATE SET
                dataset_id=excluded.dataset_id,
                config_json=excluded.config_json,
                env_json=excluded.env_json,
                seed=excluded.seed,
                repro_json=excluded.repro_json,
                updated_at=excluded.updated_at
            """,
            (
                experiment_id,
                dataset_id,
                _dumps(record["config"]),
                _dumps(env),
                seed,
                _dumps(record),
                now,
            ),
        )
        self._conn.commit()
        record["experiment_id"] = experiment_id
        record["dataset_id"] = dataset_id
        record["updated_at"] = now
        return record

    def get_repro(self, experiment_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM experiment_repro WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()
        if row is None:
            return None
        data = _loads(row["repro_json"], {})
        data.update(
            {
                "experiment_id": row["experiment_id"],
                "dataset_id": row["dataset_id"],
                "seed": row["seed"],
                "updated_at": row["updated_at"],
            }
        )
        return data

    def create_sweep(
        self,
        name: str,
        *,
        strategy: str = "",
        base_params: dict[str, Any] | None = None,
        grid: dict[str, list[Any]] | None = None,
        parent_id: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        from quantvault.analytics import expand_param_grid

        base = dict(base_params or {})
        grid = dict(grid or {})
        combos = expand_param_grid(base, grid)
        experiment_ids: list[str] = []
        for i, params in enumerate(combos):
            exp = self.create(
                f"{name}[{i}]",
                strategy=strategy,
                params=params,
                parent_id=parent_id,
                tags=list(tags or []) + ["sweep"],
            )
            experiment_ids.append(exp.id)
        created = _now()
        sweep = {
            "id": uuid.uuid4().hex[:12],
            "name": name,
            "base_params": base,
            "grid": grid,
            "experiment_ids": experiment_ids,
            "created_at": created,
        }
        self._conn.execute(
            """
            INSERT INTO sweeps
                (id, name, base_params_json, grid_json, experiment_ids_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                sweep["id"],
                name,
                _dumps(base),
                _dumps(grid),
                _dumps(experiment_ids),
                created,
            ),
        )
        self._conn.commit()
        return sweep

    def list_sweeps(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM sweeps ORDER BY created_at DESC"
        ).fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "base_params": _loads(row["base_params_json"], {}),
                "grid": _loads(row["grid_json"], {}),
                "experiment_ids": _loads(row["experiment_ids_json"], []),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def create_batch(
        self,
        name: str,
        specs: list[dict[str, Any]],
        *,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        experiment_ids: list[str] = []
        for i, spec in enumerate(specs):
            exp = self.create(
                spec.get("name", f"{name}[{i}]"),
                strategy=spec.get("strategy", ""),
                params=spec.get("params"),
                metrics=spec.get("metrics"),
                tags=list(spec.get("tags") or []) + ["batch"],
                notes=spec.get("notes", ""),
                parent_id=spec.get("parent_id"),
                status=spec.get("status", "created"),
                profile=spec.get("profile"),
            )
            experiment_ids.append(exp.id)
        created = _now()
        batch = {
            "id": uuid.uuid4().hex[:12],
            "name": name,
            "experiment_ids": experiment_ids,
            "meta": dict(meta or {}),
            "created_at": created,
        }
        self._conn.execute(
            """
            INSERT INTO batches (id, name, experiment_ids_json, meta_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (batch["id"], name, _dumps(experiment_ids), _dumps(batch["meta"]), created),
        )
        self._conn.commit()
        return batch

    def list_batches(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM batches ORDER BY created_at DESC"
        ).fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "experiment_ids": _loads(row["experiment_ids_json"], []),
                "meta": _loads(row["meta_json"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def analyze(
        self,
        experiment_id: str,
        *,
        equity: list[float] | None = None,
        returns: list[float] | None = None,
        trades: list[dict[str, Any]] | None = None,
        benchmark_returns: list[float] | None = None,
        cost_bps: float = 0.0,
        slippage_bps: float = 0.0,
        store: bool = True,
    ) -> dict[str, Any]:
        from quantvault.analytics import performance_report

        self.require(experiment_id)
        report = performance_report(
            equity=equity,
            returns=returns,
            trades=trades,
            benchmark_returns=benchmark_returns,
            cost_bps=cost_bps,
            slippage_bps=slippage_bps,
        )
        metrics = dict(self.require(experiment_id).metrics)
        metrics.update(
            {
                "sharpe": report["risk_adjusted"]["sharpe"],
                "sortino": report["risk_adjusted"]["sortino"],
                "calmar": report["risk_adjusted"]["calmar"],
                "max_drawdown": report["drawdown"]["max_drawdown"],
                "total_return": report["equity_curve"].get("total_return"),
                "srsi": report["srsi"]["srsi"],
            }
        )
        self.update(experiment_id, metrics=metrics)
        if store:
            self.store_artifact(
                experiment_id,
                "performance_report.json",
                data=report,
                kind="analysis",
            )
        return report

    def run_monte_carlo(
        self,
        experiment_id: str,
        returns: list[float],
        *,
        n_sims: int = 500,
        seed: int | None = None,
        store: bool = True,
    ) -> dict[str, Any]:
        from quantvault.analytics import monte_carlo_analysis

        self.require(experiment_id)
        result = monte_carlo_analysis(returns, n_sims=n_sims, seed=seed)
        if store:
            self.store_artifact(
                experiment_id,
                "monte_carlo.json",
                data=result,
                kind="analysis",
            )
        return result

    def record_walk_forward(
        self,
        experiment_id: str,
        windows: list[dict[str, Any]],
        *,
        store: bool = True,
    ) -> dict[str, Any]:
        from quantvault.analytics import walk_forward_analysis

        self.require(experiment_id)
        result = walk_forward_analysis(windows)
        metrics = dict(self.require(experiment_id).metrics)
        metrics["walk_forward_test_mean"] = result.get("test_mean")
        metrics["walk_forward_gap_mean"] = result.get("gap_mean")
        self.update(experiment_id, metrics=metrics)
        if store:
            self.store_artifact(
                experiment_id,
                "walk_forward.json",
                data=result,
                kind="analysis",
            )
        return result

    def record_overfitting(
        self,
        experiment_id: str,
        *,
        in_sample: float | None = None,
        out_of_sample: float | None = None,
        n_trials: int = 1,
        store: bool = True,
    ) -> dict[str, Any]:
        from quantvault.analytics import overfitting_analysis

        exp = self.require(experiment_id)
        metrics = dict(exp.metrics)
        is_m = float(in_sample if in_sample is not None else metrics.get("in_sample_sharpe", 0.0))
        oos_m = float(
            out_of_sample if out_of_sample is not None else metrics.get("oos_sharpe", 0.0)
        )
        result = overfitting_analysis(is_m, oos_m, n_trials=n_trials)
        metrics["in_sample_sharpe"] = is_m
        metrics["oos_sharpe"] = oos_m
        metrics["overfit_relative_gap"] = result.get("relative_gap")
        self.update(experiment_id, metrics=metrics)
        if store:
            self.store_artifact(experiment_id, "overfitting.json", data=result, kind="analysis")
        return result

    def store_custom_chart(
        self,
        experiment_id: str,
        chart: dict[str, Any],
        *,
        name: str = "custom_chart",
    ) -> dict[str, Any]:
        """Store a Chart.js-friendly custom chart spec on an experiment.

        Expected keys: title?, type (line|bar), labels, datasets[{label, data, ...}]
        Multiple charts can be stored under custom_charts.json as a list.
        """
        self.require(experiment_id)
        existing = None
        for art in self.list_artifacts(experiment_id):
            if art["name"] == "custom_charts.json":
                existing = json.loads(Path(art["path"]).read_text(encoding="utf-8"))
                break
        charts = list(existing) if isinstance(existing, list) else ([] if existing is None else [existing])
        entry = {"name": name, **chart}
        charts = [c for c in charts if c.get("name") != name]
        charts.append(entry)
        return self.store_artifact(experiment_id, "custom_charts.json", data=charts, kind="chart")

    def robustness_of(
        self,
        experiment_ids: list[str],
        *,
        metric: str = "sharpe",
    ) -> dict[str, Any]:
        from quantvault.analytics import parameter_robustness

        results = []
        for eid in experiment_ids:
            exp = self.require(eid)
            results.append({"id": eid, "params": exp.params, "metrics": exp.metrics})
        return parameter_robustness(results, metric=metric)

    def sensitivity_sweep(
        self,
        name: str,
        base_params: dict[str, Any],
        perturbations: dict[str, list[Any]],
        *,
        strategy: str = "",
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        from quantvault.analytics import sensitivity_analysis

        specs = sensitivity_analysis(base_params, perturbations)
        children = [s for s in specs if s["kind"] != "base"]
        return self.create_batch(
            name,
            [
                {
                    "name": f"{name}:{s.get('varied')}",
                    "strategy": strategy,
                    "params": s["params"],
                    "parent_id": parent_id,
                    "tags": ["sensitivity"],
                }
                for s in children
            ],
            meta={"kind": "sensitivity", "perturbations": perturbations},
        )

    def record(
        self,
        strategy: str,
        *,
        name: str | None = None,
        parameters: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        notes: str = "",
        parent_id: str | None = None,
        meta: dict[str, Any] | None = None,
        trades: list[dict[str, Any]] | None = None,
        data: Any = None,
        profile: str | None = None,
        status: str = "created",
    ) -> Experiment:
        """Record a research run (friendly API alias around create + optional meta/trades)."""
        exp = self.create(
            name or strategy,
            strategy=strategy,
            params=parameters if parameters is not None else params,
            metrics=metrics,
            tags=tags,
            notes=notes,
            parent_id=parent_id,
            profile=profile,
            status=status,
        )
        if meta:
            self.set_meta(exp.id, meta)
        if trades is not None:
            self.store_artifact(exp.id, "trades.json", data={"trades": trades}, kind="trades")
        if data is not None:
            # store a lightweight fingerprint note only — do not ingest raw market data by default
            from quantvault.repro import fingerprint_json

            self.set_meta(
                exp.id,
                {
                    **(self.get_meta(exp.id) or {}),
                    "data_fingerprint": fingerprint_json(data)
                    if not isinstance(data, (str, Path))
                    else str(data),
                },
            )
        return exp

    def set_meta(self, experiment_id: str, meta: dict[str, Any]) -> dict[str, Any]:
        self.require(experiment_id)
        now = _now()
        self._conn.execute(
            """
            INSERT INTO experiment_meta (experiment_id, meta_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(experiment_id) DO UPDATE SET
                meta_json=excluded.meta_json,
                updated_at=excluded.updated_at
            """,
            (experiment_id, _dumps(meta), now),
        )
        self._conn.commit()
        return {"experiment_id": experiment_id, "meta": meta, "updated_at": now}

    def get_meta(self, experiment_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT meta_json FROM experiment_meta WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()
        return _loads(row["meta_json"], {}) if row else {}

    def validate(self, experiment_id: str, *, data_meta: dict[str, Any] | None = None) -> dict[str, Any]:
        from quantvault.reports import load_analysis_artifact
        from quantvault.validation import validate_experiment_bundle

        exp = self.require(experiment_id)
        analysis = load_analysis_artifact(self, exp.id)
        trades = None
        for art in self.list_artifacts(exp.id):
            if art["name"] == "trades.json":
                payload = json.loads(Path(art["path"]).read_text(encoding="utf-8"))
                trades = payload.get("trades", payload)
                break
        report = validate_experiment_bundle(
            experiment=exp.to_dict(),
            repro=self.get_repro(exp.id),
            analysis=analysis,
            trades=trades,
            data_meta={**(self.get_meta(exp.id)), **(data_meta or {})},
        )
        self.store_artifact(exp.id, "validation.json", data=report, kind="validation")
        return report

    def create_portfolio(
        self,
        name: str,
        legs: list[dict[str, Any]],
        *,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """legs: [{experiment_id, weight}] or [{name, equity, weight}]"""
        from quantvault.portfolio import (
            allocation_analysis,
            portfolio_drawdown,
            portfolio_from_strategies,
            portfolio_risk_analytics,
            strategy_correlation,
        )

        built_legs = []
        experiment_ids = []
        weights: dict[str, float] = {}
        series_map: dict[str, list[float]] = {}
        for leg in legs:
            if "experiment_id" in leg:
                eid = self.require(leg["experiment_id"]).id
                experiment_ids.append(eid)
                analysis = None
                from quantvault.reports import load_analysis_artifact

                analysis = load_analysis_artifact(self, eid)
                equity = ((analysis or {}).get("series") or {}).get("equity") or []
                if not equity:
                    raise ValueError(f"experiment {eid} has no stored equity series; run analyze first")
                name_leg = leg.get("name") or eid
                weight = float(leg.get("weight", 1.0))
                built_legs.append({"name": name_leg, "equity": equity, "weight": weight})
                weights[name_leg] = weight
                series_map[name_leg] = equity
            else:
                built_legs.append(leg)
                weights[leg["name"]] = float(leg.get("weight", 1.0))
                series_map[leg["name"]] = list(leg["equity"])

        combined = portfolio_from_strategies(built_legs)
        risk = portfolio_risk_analytics(combined["equity"])
        created = _now()
        pid = uuid.uuid4().hex[:12]
        portfolio = {
            "id": pid,
            "name": name,
            "weights": combined["weights"],
            "experiment_ids": experiment_ids,
            "meta": dict(meta or {}),
            "allocation": allocation_analysis(combined["weights"]),
            "risk": risk,
            "drawdown": portfolio_drawdown(combined["equity"]),
            "correlation": strategy_correlation(series_map),
            "equity": combined["equity"],
            "created_at": created,
        }
        self._conn.execute(
            """
            INSERT INTO portfolios (id, name, weights_json, experiment_ids_json, meta_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (pid, name, _dumps(combined["weights"]), _dumps(experiment_ids), _dumps(portfolio["meta"]), created),
        )
        self._conn.commit()
        # store analytics artifact under a synthetic folder via first experiment if available
        dest = self.artifacts_dir / f"portfolio_{pid}"
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "portfolio.json").write_text(
            json.dumps(portfolio, indent=2, sort_keys=True, default=str), encoding="utf-8"
        )
        return portfolio

    def list_portfolios(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM portfolios ORDER BY created_at DESC").fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "weights": _loads(row["weights_json"], {}),
                "experiment_ids": _loads(row["experiment_ids_json"], []),
                "meta": _loads(row["meta_json"], {}),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def track_live(
        self,
        name: str,
        *,
        kind: str = "paper",
        backtest_id: str | None = None,
        fills: list[dict[str, Any]] | None = None,
        equity: list[float] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from quantvault.live import live_vs_backtest, paper_summary

        if backtest_id:
            self.require(backtest_id)
        now = _now()
        fills = list(fills or [])
        equity = list(equity or [])
        summary = paper_summary(fills)
        comparison = None
        if backtest_id and equity:
            from quantvault.reports import load_analysis_artifact

            analysis = load_analysis_artifact(self, backtest_id) or {}
            bt_eq = (analysis.get("series") or {}).get("equity") or []
            if bt_eq:
                comparison = live_vs_backtest(backtest_equity=bt_eq, live_equity=equity)
        rid = uuid.uuid4().hex[:12]
        metrics = {"summary": summary, "comparison": comparison}
        self._conn.execute(
            """
            INSERT INTO live_runs (
                id, name, kind, backtest_id, fills_json, equity_json, metrics_json, meta_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid,
                name,
                kind,
                backtest_id,
                _dumps(fills),
                _dumps(equity),
                _dumps(metrics),
                _dumps(meta or {}),
                now,
                now,
            ),
        )
        self._conn.commit()
        return {
            "id": rid,
            "name": name,
            "kind": kind,
            "backtest_id": backtest_id,
            "metrics": metrics,
            "meta": meta or {},
            "created_at": now,
        }

    def list_live(self, *, kind: str | None = None) -> list[dict[str, Any]]:
        if kind:
            rows = self._conn.execute(
                "SELECT * FROM live_runs WHERE kind = ? ORDER BY created_at DESC", (kind,)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM live_runs ORDER BY created_at DESC").fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "kind": row["kind"],
                "backtest_id": row["backtest_id"],
                "metrics": _loads(row["metrics_json"], {}),
                "meta": _loads(row["meta_json"], {}),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def risk(self, experiment_id: str) -> dict[str, Any]:
        from quantvault.reports import load_analysis_artifact

        exp = self.require(experiment_id)
        analysis = load_analysis_artifact(self, exp.id) or {}
        return {
            "experiment_id": exp.id,
            "risk_adjusted": analysis.get("risk_adjusted") or {},
            "drawdown": analysis.get("drawdown") or {},
            "metrics": exp.metrics,
        }


def _diff_maps(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    keys = sorted(set(left) | set(right))
    changed: dict[str, Any] = {}
    only_left: dict[str, Any] = {}
    only_right: dict[str, Any] = {}
    for key in keys:
        in_left = key in left
        in_right = key in right
        if in_left and not in_right:
            only_left[key] = left[key]
        elif in_right and not in_left:
            only_right[key] = right[key]
        elif left[key] != right[key]:
            changed[key] = {"left": left[key], "right": right[key]}
    return {
        "changed": changed,
        "only_left": only_left,
        "only_right": only_right,
    }
