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
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    @classmethod
    def open(cls, root: Path | str | None = None) -> Ledger:
        base = Path(root) if root is not None else Path.cwd() / ".quantledger"
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
            """
        )
        self._conn.commit()

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

    def require(self, experiment_id: str) -> Experiment:
        exp = self.get(experiment_id)
        if exp is None:
            raise KeyError(f"experiment not found: {experiment_id}")
        return exp

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
