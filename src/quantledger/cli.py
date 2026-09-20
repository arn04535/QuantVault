"""Command-line entry point for QuantLedger."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from quantledger import __version__
from quantledger.ledger import Ledger


def _parse_kv(pairs: list[str] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in pairs or []:
        if "=" not in item:
            raise SystemExit(f"expected key=value, got: {item}")
        key, raw = item.split("=", 1)
        try:
            out[key] = json.loads(raw)
        except json.JSONDecodeError:
            out[key] = raw
    return out


def _ledger(args: argparse.Namespace) -> Ledger:
    root = Path(args.root) if getattr(args, "root", None) else None
    return Ledger.open(root)


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True, default=str))


def cmd_init(args: argparse.Namespace) -> int:
    ledger = _ledger(args)
    print(f"Initialized ledger at {ledger.path}")
    ledger.close()
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        exp = ledger.create(
            args.name,
            strategy=args.strategy or "",
            params=_parse_kv(args.param),
            metrics=_parse_kv(args.metric),
            tags=args.tag or [],
            notes=args.notes or "",
            parent_id=args.parent,
            status=args.status,
            profile=args.profile,
        )
        _print_json(exp.to_dict())
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        experiments = ledger.list(
            strategy=args.strategy,
            status=args.status,
            tag=args.tag,
            q=args.query,
        )
        if args.json:
            _print_json([e.to_dict() for e in experiments])
            return 0
        if not experiments:
            print("No experiments found.")
            return 0
        for exp in experiments:
            tags = f" [{', '.join(exp.tags)}]" if exp.tags else ""
            print(
                f"{exp.id}  {exp.status:10}  {exp.strategy or '-':20}  {exp.name}{tags}"
            )
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        _print_json(ledger.require(args.id).to_dict())
    return 0


def cmd_tag(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        _print_json(ledger.add_tags(args.id, *args.tags).to_dict())
    return 0


def cmd_note(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        _print_json(ledger.annotate(args.id, args.text).to_dict())
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        exp = ledger.require(args.id)
        kwargs: dict[str, Any] = {}
        if args.name is not None:
            kwargs["name"] = args.name
        if args.strategy is not None:
            kwargs["strategy"] = args.strategy
        if args.status is not None:
            kwargs["status"] = args.status
        if args.param:
            params = dict(exp.params)
            params.update(_parse_kv(args.param))
            kwargs["params"] = params
        if args.metric:
            metrics = dict(exp.metrics)
            metrics.update(_parse_kv(args.metric))
            kwargs["metrics"] = metrics
        _print_json(ledger.update(args.id, **kwargs).to_dict())
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        _print_json(ledger.compare(args.left, args.right))
    return 0


def cmd_lineage(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        chain = ledger.lineage(args.id)
        if args.json:
            _print_json([e.to_dict() for e in chain])
            return 0
        for exp in chain:
            mark = " *" if exp.id == args.id else ""
            parent = f" (parent={exp.parent_id})" if exp.parent_id else ""
            print(f"{exp.id}{mark}  {exp.name}{parent}")
    return 0


def cmd_journal(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        if args.text:
            _print_json(ledger.add_journal(args.text, experiment_id=args.experiment))
            return 0
        entries = ledger.list_journal(experiment_id=args.experiment)
        if args.json:
            _print_json(entries)
            return 0
        if not entries:
            print("No journal entries.")
            return 0
        for entry in entries:
            link = f" exp={entry['experiment_id']}" if entry["experiment_id"] else ""
            print(f"[{entry['created_at']}]#{entry['id']}{link}  {entry['body']}")
    return 0


def cmd_checkpoint(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        if args.name:
            _print_json(
                ledger.checkpoint(args.name, args.experiments, note=args.note or "")
            )
            return 0
        checkpoints = ledger.list_checkpoints()
        if args.json:
            _print_json(checkpoints)
            return 0
        if not checkpoints:
            print("No checkpoints.")
            return 0
        for cp in checkpoints:
            ids = ", ".join(cp["experiment_ids"])
            print(f"{cp['id']}  {cp['name']}  [{ids}]")
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        if args.name and args.set:
            _print_json(
                ledger.set_profile(
                    args.name,
                    default_params=_parse_kv(args.param),
                    description=args.description or "",
                )
            )
            return 0
        if args.name:
            profile = ledger.get_profile(args.name)
            if profile is None:
                raise SystemExit(f"unknown strategy profile: {args.name}")
            _print_json(profile)
            return 0
        profiles = ledger.list_profiles()
        if args.json:
            _print_json(profiles)
            return 0
        if not profiles:
            print("No strategy profiles.")
            return 0
        for profile in profiles:
            print(f"{profile['name']}  {profile['description'] or '-'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quantledger",
        description="Local experiment ledger for quantitative research.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--root",
        help="Ledger directory (default: ./.quantledger)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Create a local ledger")
    p_init.set_defaults(func=cmd_init)

    p_create = sub.add_parser("create", help="Register a new experiment")
    p_create.add_argument("name")
    p_create.add_argument("--strategy", default="")
    p_create.add_argument("--status", default="created")
    p_create.add_argument("--parent", default=None)
    p_create.add_argument("--profile", default=None)
    p_create.add_argument("--notes", default="")
    p_create.add_argument("--param", action="append", default=[])
    p_create.add_argument("--metric", action="append", default=[])
    p_create.add_argument("--tag", action="append", default=[])
    p_create.set_defaults(func=cmd_create)

    p_list = sub.add_parser("list", help="Search and filter experiments")
    p_list.add_argument("--strategy")
    p_list.add_argument("--status")
    p_list.add_argument("--tag")
    p_list.add_argument("--query", "-q")
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="Show one experiment")
    p_show.add_argument("id")
    p_show.set_defaults(func=cmd_show)

    p_tag = sub.add_parser("tag", help="Add tags to an experiment")
    p_tag.add_argument("id")
    p_tag.add_argument("tags", nargs="+")
    p_tag.set_defaults(func=cmd_tag)

    p_note = sub.add_parser("note", help="Append a note to an experiment")
    p_note.add_argument("id")
    p_note.add_argument("text")
    p_note.set_defaults(func=cmd_note)

    p_set = sub.add_parser("set", help="Update experiment fields")
    p_set.add_argument("id")
    p_set.add_argument("--name")
    p_set.add_argument("--strategy")
    p_set.add_argument("--status")
    p_set.add_argument("--param", action="append", default=[])
    p_set.add_argument("--metric", action="append", default=[])
    p_set.set_defaults(func=cmd_set)

    p_compare = sub.add_parser("compare", help="Diff two experiments")
    p_compare.add_argument("left")
    p_compare.add_argument("right")
    p_compare.set_defaults(func=cmd_compare)

    p_lineage = sub.add_parser("lineage", help="Show experiment lineage")
    p_lineage.add_argument("id")
    p_lineage.add_argument("--json", action="store_true")
    p_lineage.set_defaults(func=cmd_lineage)

    p_journal = sub.add_parser("journal", help="Add or list research journal entries")
    p_journal.add_argument("text", nargs="?")
    p_journal.add_argument("--experiment")
    p_journal.add_argument("--json", action="store_true")
    p_journal.set_defaults(func=cmd_journal)

    p_cp = sub.add_parser("checkpoint", help="Create or list research checkpoints")
    p_cp.add_argument("name", nargs="?")
    p_cp.add_argument("experiments", nargs="*")
    p_cp.add_argument("--note", default="")
    p_cp.add_argument("--json", action="store_true")
    p_cp.set_defaults(func=cmd_checkpoint)

    p_profile = sub.add_parser("profile", help="Manage strategy profiles")
    p_profile.add_argument("name", nargs="?")
    p_profile.add_argument("--set", action="store_true")
    p_profile.add_argument("--description", default="")
    p_profile.add_argument("--param", action="append", default=[])
    p_profile.add_argument("--json", action="store_true")
    p_profile.set_defaults(func=cmd_profile)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
