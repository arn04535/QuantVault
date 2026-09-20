"""Professional CLI for QuantLedger (`quant-ledger`)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from quantledger import __version__
from quantledger.exporters import (
    backup_ledger,
    export_experiment,
    export_experiments,
    import_experiment_json,
    restore_ledger,
)
from quantledger.ledger import Ledger
from quantledger.reports import load_analysis_artifact, research_report, render_experiment_html


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
    with _ledger(args) as ledger:
        print(f"Initialized ledger at {ledger.path}")
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
        print(f"{'ID':12}  {'STATUS':10}  {'STRATEGY':20}  NAME")
        for exp in experiments:
            tags = f" [{', '.join(exp.tags)}]" if exp.tags else ""
            print(
                f"{exp.id:12}  {exp.status:10}  {(exp.strategy or '-'):20}  {exp.name}{tags}"
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
        target = ledger.require(args.id)
        chain = ledger.lineage(target.id)
        if args.json:
            _print_json([e.to_dict() for e in chain])
            return 0
        for exp in chain:
            mark = " *" if exp.id == target.id else ""
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


def cmd_dataset(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        if args.register:
            _print_json(
                ledger.register_dataset(
                    args.register,
                    path=args.path,
                    fingerprint=args.fingerprint,
                    version=args.version,
                    parent_id=args.parent,
                )
            )
            return 0
        if args.lineage:
            _print_json(ledger.dataset_lineage(args.lineage))
            return 0
        datasets = ledger.list_datasets(name=args.name)
        if args.json:
            _print_json(datasets)
            return 0
        if not datasets:
            print("No datasets.")
            return 0
        for ds in datasets:
            print(f"{ds['id']}  {ds['name']}@{ds['version']}  {ds['fingerprint'][:12]}…")
    return 0


def cmd_artifact(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        if args.file:
            _print_json(
                ledger.store_artifact(
                    args.experiment,
                    args.name or Path(args.file).name,
                    source=args.file,
                )
            )
            return 0
        arts = ledger.list_artifacts(args.experiment)
        if args.json:
            _print_json(arts)
            return 0
        for art in arts:
            print(f"{art['id']}  {art['kind']:8}  {art['name']}")
    return 0


def cmd_repro(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        if args.attach:
            config = None
            if args.config:
                config = json.loads(Path(args.config).read_text(encoding="utf-8"))
            _print_json(
                ledger.attach_repro(
                    args.attach,
                    config=config,
                    dataset_id=args.dataset,
                    seed=args.seed,
                    packages=args.package,
                )
            )
            return 0
        if not args.show:
            raise SystemExit("use --attach ID or --show ID")
        _print_json(ledger.get_repro(args.show) or {})
    return 0


def cmd_reproduce(args: argparse.Namespace) -> int:
    """Show the reproducibility record needed to re-run an experiment."""
    with _ledger(args) as ledger:
        exp = ledger.require(args.id)
        repro = ledger.get_repro(exp.id)
        payload = {
            "experiment": exp.to_dict(),
            "repro": repro,
            "artifacts": ledger.list_artifacts(exp.id),
        }
        if not repro:
            print(
                f"warning: no reproducibility record attached to {exp.id}",
                file=sys.stderr,
            )
        _print_json(payload)
    return 0


def cmd_sweep(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        if args.name:
            grid = json.loads(args.grid) if args.grid else {}
            _print_json(
                ledger.create_sweep(
                    args.name,
                    strategy=args.strategy or "",
                    base_params=_parse_kv(args.param),
                    grid=grid,
                    parent_id=args.parent,
                )
            )
            return 0
        _print_json(ledger.list_sweeps())
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        if args.file:
            specs = json.loads(Path(args.file).read_text(encoding="utf-8"))
            _print_json(ledger.create_batch(args.name or "batch", specs))
            return 0
        _print_json(ledger.list_batches())
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        exp = ledger.require(args.id)
        if args.file:
            payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
            _print_json(
                ledger.analyze(
                    exp.id,
                    equity=payload.get("equity"),
                    returns=payload.get("returns"),
                    trades=payload.get("trades"),
                    benchmark_returns=payload.get("benchmark_returns"),
                    cost_bps=args.cost_bps,
                    slippage_bps=args.slippage_bps,
                )
            )
            return 0
        stored = load_analysis_artifact(ledger, exp.id)
        if stored is None:
            raise SystemExit(
                f"no stored analysis for {exp.id}; pass --file with equity/returns/trades"
            )
        _print_json(stored)
    return 0


def cmd_srsi(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        exp = ledger.require(args.id)
        if args.file:
            payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
            from quantledger.analytics import returns_from_equity, srsi_analysis

            returns = payload.get("returns")
            if returns is None and payload.get("equity"):
                returns = returns_from_equity(payload["equity"])
            if not returns:
                raise SystemExit("file must include returns or equity")
            result = srsi_analysis(returns, window=args.window)
            ledger.store_artifact(exp.id, "srsi.json", data=result, kind="analysis")
            _print_json(result)
            return 0
        stored = load_analysis_artifact(ledger, exp.id)
        if stored and stored.get("srsi"):
            _print_json(stored["srsi"])
            return 0
        if "srsi" in exp.metrics:
            _print_json({"srsi": exp.metrics["srsi"]})
            return 0
        raise SystemExit(
            f"no SRSI for {exp.id}; run analyze first or pass --file with returns/equity"
        )


def cmd_montecarlo(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    returns = payload.get("returns") or []
    with _ledger(args) as ledger:
        _print_json(
            ledger.run_monte_carlo(
                args.id,
                returns,
                n_sims=args.sims,
                seed=args.seed,
            )
        )
    return 0


def cmd_robustness(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        ids = [ledger.require(i).id for i in args.experiments]
        _print_json(ledger.robustness_of(ids, metric=args.metric))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        if args.id:
            report = research_report(ledger, args.id)
            if args.format == "html":
                out = Path(args.out or f"{ledger.require(args.id).id}.html")
                out.write_text(render_experiment_html(ledger, args.id), encoding="utf-8")
                print(out)
                return 0
            _print_json(report)
            return 0
        path = export_experiments(ledger, args.out or ".", fmt=args.format)
        print(path)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        dest = Path(args.out or ".")
        if args.id:
            path = export_experiment(ledger, args.id, dest, fmt=args.format)
        else:
            path = export_experiments(ledger, dest, fmt=args.format)
        print(path)
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        _print_json(import_experiment_json(ledger, args.file))
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    with _ledger(args) as ledger:
        path = backup_ledger(ledger, args.out or "quantledger-backup.zip")
        print(path)
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd() / ".quantledger"
    path = restore_ledger(args.archive, root)
    print(path)
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    from quantledger.dashboard import start_dashboard

    ledger = _ledger(args)
    server = start_dashboard(ledger, host=args.host, port=args.port)
    url = f"http://{args.host}:{args.port}/"
    print(f"QuantLedger dashboard at {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
        ledger.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quant-ledger",
        description="Local experiment ledger for quantitative research.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--root", help="Ledger directory (default: ./.quantledger)")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help: str, func: Any, **opts: Any) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help, **opts)
        p.set_defaults(func=func)
        return p

    add("init", "Create a local ledger", cmd_init)

    p = add("create", "Register a new experiment", cmd_create)
    p.add_argument("name")
    p.add_argument("--strategy", default="")
    p.add_argument("--status", default="created")
    p.add_argument("--parent")
    p.add_argument("--profile")
    p.add_argument("--notes", default="")
    p.add_argument("--param", action="append", default=[])
    p.add_argument("--metric", action="append", default=[])
    p.add_argument("--tag", action="append", default=[])

    p = add("list", "List and filter experiments", cmd_list)
    p.add_argument("--strategy")
    p.add_argument("--status")
    p.add_argument("--tag")
    p.add_argument("--query", "-q")
    p.add_argument("--json", action="store_true")

    p = add("show", "Show one experiment", cmd_show)
    p.add_argument("id")

    p = add("tag", "Add tags", cmd_tag)
    p.add_argument("id")
    p.add_argument("tags", nargs="+")

    p = add("note", "Append a note", cmd_note)
    p.add_argument("id")
    p.add_argument("text")

    p = add("set", "Update experiment fields", cmd_set)
    p.add_argument("id")
    p.add_argument("--name")
    p.add_argument("--strategy")
    p.add_argument("--status")
    p.add_argument("--param", action="append", default=[])
    p.add_argument("--metric", action="append", default=[])

    p = add("compare", "Diff two experiments", cmd_compare)
    p.add_argument("left")
    p.add_argument("right")

    p = add("lineage", "Show experiment lineage", cmd_lineage)
    p.add_argument("id")
    p.add_argument("--json", action="store_true")

    p = add("journal", "Research journal", cmd_journal)
    p.add_argument("text", nargs="?")
    p.add_argument("--experiment")
    p.add_argument("--json", action="store_true")

    p = add("checkpoint", "Research checkpoints", cmd_checkpoint)
    p.add_argument("name", nargs="?")
    p.add_argument("experiments", nargs="*")
    p.add_argument("--note", default="")
    p.add_argument("--json", action="store_true")

    p = add("profile", "Strategy profiles", cmd_profile)
    p.add_argument("name", nargs="?")
    p.add_argument("--set", action="store_true")
    p.add_argument("--description", default="")
    p.add_argument("--param", action="append", default=[])
    p.add_argument("--json", action="store_true")

    p = add("dataset", "Dataset registry", cmd_dataset)
    p.add_argument("--register")
    p.add_argument("--path")
    p.add_argument("--fingerprint")
    p.add_argument("--version", default="1")
    p.add_argument("--parent")
    p.add_argument("--name")
    p.add_argument("--lineage")
    p.add_argument("--json", action="store_true")

    p = add("artifact", "Artifact storage", cmd_artifact)
    p.add_argument("experiment")
    p.add_argument("--file")
    p.add_argument("--name")
    p.add_argument("--json", action="store_true")

    p = add("repro", "Attach reproducibility metadata", cmd_repro)
    p.add_argument("--attach")
    p.add_argument("--show")
    p.add_argument("--config")
    p.add_argument("--dataset")
    p.add_argument("--seed", type=int)
    p.add_argument("--package", action="append", default=[])

    p = add("reproduce", "Show how to reproduce an experiment", cmd_reproduce)
    p.add_argument("id")

    p = add("sweep", "Parameter sweeps", cmd_sweep)
    p.add_argument("name", nargs="?")
    p.add_argument("--strategy", default="")
    p.add_argument("--param", action="append", default=[])
    p.add_argument("--grid")
    p.add_argument("--parent")

    p = add("batch", "Experiment batches", cmd_batch)
    p.add_argument("--name")
    p.add_argument("--file")

    p = add("analyze", "Performance analysis", cmd_analyze)
    p.add_argument("id")
    p.add_argument("--file")
    p.add_argument("--cost-bps", type=float, default=0.0)
    p.add_argument("--slippage-bps", type=float, default=0.0)

    p = add("srsi", "Sharpe Ratio Stability Index", cmd_srsi)
    p.add_argument("id")
    p.add_argument("--file")
    p.add_argument("--window", type=int, default=20)

    p = add("montecarlo", "Monte Carlo analysis", cmd_montecarlo)
    p.add_argument("id")
    p.add_argument("--file", required=True)
    p.add_argument("--sims", type=int, default=500)
    p.add_argument("--seed", type=int)

    p = add("robustness", "Parameter robustness", cmd_robustness)
    p.add_argument("experiments", nargs="+")
    p.add_argument("--metric", default="sharpe")

    p = add("report", "Research report", cmd_report)
    p.add_argument("id", nargs="?")
    p.add_argument("--format", default="json", choices=["json", "html", "csv", "parquet"])
    p.add_argument("--out")

    p = add("export", "Export experiments", cmd_export)
    p.add_argument("id", nargs="?")
    p.add_argument("--format", default="json", choices=["json", "csv", "html", "parquet"])
    p.add_argument("--out", default=".")

    p = add("import", "Import an experiment JSON pack", cmd_import)
    p.add_argument("file")

    p = add("backup", "Backup ledger database and artifacts", cmd_backup)
    p.add_argument("--out", default="quantledger-backup.zip")

    p = add("restore", "Restore ledger from a backup zip", cmd_restore)
    p.add_argument("archive")

    p = add("dashboard", "Start local visualization dashboard", cmd_dashboard)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8787)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
