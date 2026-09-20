from __future__ import annotations

import json
from pathlib import Path

from quantvault.cli import main
from quantvault.ledger import Ledger


def test_create_list_tag_compare(tmp_path: Path) -> None:
    with Ledger.open(tmp_path) as ledger:
        a = ledger.create(
            "baseline",
            strategy="mean_reversion",
            params={"lookback": 20, "threshold": 1.5},
            tags=["pilot"],
        )
        b = ledger.create(
            "wider band",
            strategy="mean_reversion",
            params={"lookback": 20, "threshold": 2.0},
            parent_id=a.id,
            metrics={"sharpe": 1.1},
        )
        ledger.add_tags(b.id, "candidate")
        ledger.annotate(b.id, "looks promising on liquid names")

        found = ledger.list(tag="candidate", strategy="mean_reversion")
        assert [e.id for e in found] == [b.id]

        diff = ledger.compare(a.id, b.id)
        assert diff["params"]["changed"]["threshold"] == {
            "left": 1.5,
            "right": 2.0,
        }
        assert diff["tags"]["only_right"] == ["candidate"]

        lineage = ledger.lineage(b.id)
        assert [e.id for e in lineage] == [a.id, b.id]


def test_journal_checkpoint_profile(tmp_path: Path) -> None:
    with Ledger.open(tmp_path) as ledger:
        ledger.set_profile(
            "momentum",
            default_params={"lookback": 60},
            description="simple momentum",
        )
        exp = ledger.create("run-1", profile="momentum", params={"fee_bps": 1})
        assert exp.strategy == "momentum"
        assert exp.params == {"lookback": 60, "fee_bps": 1}

        entry = ledger.add_journal("starting sweep", experiment_id=exp.id)
        assert entry["body"] == "starting sweep"
        assert ledger.list_journal(experiment_id=exp.id)[0]["id"] == entry["id"]

        cp = ledger.checkpoint("week-1", [exp.id], note="freeze")
        assert cp["experiment_ids"] == [exp.id]
        assert ledger.list_checkpoints()[0]["name"] == "week-1"


def test_cli_create_and_compare(tmp_path: Path, capsys) -> None:
    root = str(tmp_path)
    assert main(["--root", root, "init"]) == 0
    capsys.readouterr()
    assert (
        main(
            [
                "--root",
                root,
                "create",
                "a",
                "--strategy",
                "s",
                "--param",
                "n=1",
                "--tag",
                "x",
            ]
        )
        == 0
    )
    left = json.loads(capsys.readouterr().out)["id"]
    assert (
        main(
            [
                "--root",
                root,
                "create",
                "b",
                "--strategy",
                "s",
                "--param",
                "n=2",
                "--parent",
                left,
            ]
        )
        == 0
    )
    right = json.loads(capsys.readouterr().out)["id"]
    assert main(["--root", root, "compare", left, right]) == 0
    diff = json.loads(capsys.readouterr().out)
    assert diff["params"]["changed"]["n"]["right"] == 2
