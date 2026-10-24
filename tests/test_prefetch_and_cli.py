from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from lean_agent_kit import __version__, cli, map_prefetch

MAPREPO = Path(__file__).parent / "fixtures" / "maprepo"


def run_hook(monkeypatch, capsys, stdin: str) -> str:
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    assert map_prefetch.main() == 0
    return capsys.readouterr().out


@pytest.fixture
def in_maprepo(monkeypatch):
    monkeypatch.chdir(MAPREPO)


def test_prefetch_injects_the_rows_and_notes_a_prompt_names(
    in_maprepo, monkeypatch, capsys
) -> None:
    out = run_hook(monkeypatch, capsys, json.dumps({"prompt": "who writes `orders`?"}))
    payload = json.loads(out)["hookSpecificOutput"]
    assert payload["hookEventName"] == "UserPromptSubmit"
    context = payload["additionalContext"]
    assert "| `orders` | `storage/db.py` | `storage/db.py` |" in context
    assert "### table:orders" in context
    assert "customers" not in context.split("### table:orders")[0].split("\n", 3)[-1]


def test_prefetch_matches_a_module_by_its_short_name(in_maprepo, monkeypatch, capsys) -> None:
    out = run_hook(monkeypatch, capsys, json.dumps({"prompt": "what is in storage/db.py"}))
    assert "`storage/db.py` | Order storage." in out


@pytest.mark.parametrize(
    "stdin",
    [
        json.dumps({"prompt": "thanks, that is all"}),  # names nothing on the map
        "not json",
        json.dumps(["a", "list"]),
    ],
)
def test_prefetch_stays_silent_when_it_has_nothing(in_maprepo, monkeypatch, capsys, stdin) -> None:
    assert run_hook(monkeypatch, capsys, stdin) == ""


def test_prefetch_without_a_map_is_silent(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert run_hook(monkeypatch, capsys, json.dumps({"prompt": "who writes `orders`?"})) == ""


def test_prefetch_respects_its_budget(tmp_path, monkeypatch, capsys) -> None:
    shutil.copytree(MAPREPO / "map", tmp_path / "map")
    monkeypatch.chdir(tmp_path)
    prompt = "`orders` `customers` `audit`"
    monkeypatch.setattr(map_prefetch, "BUDGET", 10_000)
    everything = run_hook(monkeypatch, capsys, json.dumps({"prompt": prompt}))
    monkeypatch.setattr(map_prefetch, "BUDGET", 120)
    capped = run_hook(monkeypatch, capsys, json.dumps({"prompt": prompt}))
    assert row_count(everything) > 3
    assert row_count(capped) == 1


def row_count(hook_output: str) -> int:
    return json.loads(hook_output)["hookSpecificOutput"]["additionalContext"].count("\n| `")


def test_candidates() -> None:
    found = map_prefetch.candidates("does `app` touch orders_v2 or the record in src/api.py?")
    assert {"app", "orders_v2", "src/api.py", "record"} <= found
    assert not {"the", "does", "touch"} & found  # plain words under six letters
    assert "db" not in map_prefetch.candidates("`db`")  # too short even when quoted


def test_cli_lists_every_command(capsys) -> None:
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    for command in ("carry-cost", "stats", "slim", "prefetch", "map"):
        assert f"  {command} " in out


def test_cli_version_and_unknown_command(capsys) -> None:
    assert cli.main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"lean-agent-kit {__version__}"
    assert cli.main(["nope"]) == 2
    assert "unknown command 'nope'" in capsys.readouterr().err


def test_cli_dispatches_with_the_subcommand_as_program_name(capsys) -> None:
    with pytest.raises(SystemExit):
        cli.main(["slim", "--help"])
    assert capsys.readouterr().out.startswith("usage: lean-agents slim ")


def test_module_entry_point_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "lean_agent_kit", "--version"],
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(Path(cli.__file__).parents[1])},
        check=True,
    )
    assert result.stdout.strip() == f"lean-agent-kit {__version__}"
