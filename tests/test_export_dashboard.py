from __future__ import annotations

import json
from pathlib import Path

from quantvault.cli import main
from quantvault.exporters import backup_ledger, export_experiment, restore_ledger
from quantvault.ledger import Ledger
from quantvault.reports import research_report


def test_prefix_resolve_and_export_roundtrip(tmp_path: Path) -> None:
    with Ledger.open(tmp_path) as ledger:
        exp = ledger.create("alpha", strategy="mr", params={"n": 1}, metrics={"sharpe": 1.2})
        prefix = exp.id[:4]
        assert ledger.require(prefix).id == exp.id

        out = tmp_path / "out"
        path = export_experiment(ledger, prefix, out, fmt="json")
        assert path.exists()
        html_path = export_experiment(ledger, exp.id, out, fmt="html")
        assert "QuantVault" in html_path.read_text(encoding="utf-8")
        assert "Monte Carlo" in html_path.read_text(encoding="utf-8")
        csv_path = export_experiment(ledger, exp.id, out, fmt="csv")
        assert csv_path.exists()

        zip_path = backup_ledger(ledger, tmp_path / "backup.zip")
        assert zip_path.exists()

    restore_root = tmp_path / "restored"
    restore_ledger(zip_path, restore_root)
    with Ledger(restore_root / "ledger.db") as ledger2:
        assert ledger2.require(exp.id).name == "alpha"


def test_cli_compare_export_reproduce(tmp_path: Path, capsys) -> None:
    root = str(tmp_path)
    assert main(["--root", root, "init"]) == 0
    capsys.readouterr()
    assert main(["--root", root, "create", "a", "--metric", "sharpe=1"]) == 0
    left = json.loads(capsys.readouterr().out)["id"]
    assert main(["--root", root, "create", "b", "--metric", "sharpe=2"]) == 0
    right = json.loads(capsys.readouterr().out)["id"]

    assert main(["--root", root, "compare", left[:4], right[:4]]) == 0
    assert "changed" in capsys.readouterr().out

    out = tmp_path / "exports"
    assert main(["--root", root, "export", left, "--format", "json", "--out", str(out)]) == 0
    assert (out / f"{left}.json").exists()
    capsys.readouterr()

    assert main(["--root", root, "reproduce", left]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["experiment"]["id"] == left


def test_research_report(tmp_path: Path) -> None:
    with Ledger.open(tmp_path) as ledger:
        exp = ledger.create("r1")
        ledger.analyze(exp.id, equity=[1, 1.01, 1.02, 1.0, 1.03])
        report = research_report(ledger, exp.id)
        assert report["analysis"]["risk_adjusted"]["sharpe"] is not None
