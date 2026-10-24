from __future__ import annotations

from pathlib import Path

from lean_agent_kit import slim_claude_md as slim

FIXTURE = Path(__file__).parent / "fixtures" / "CLAUDE.md"


def test_kept_sections_stay_and_the_rest_move_whole() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    core, moved = slim.slim(text, {"Rules", "Layout"})
    assert core.startswith("# Project: shop\n")
    assert "## Rules" in core and "## Layout" in core
    assert "## Stack" not in core and "## Deploying" not in core
    assert set(moved) == {"stack", "deploying", "c", "c-2"}
    assert moved["deploying"].startswith("## Deploying\n")
    assert "### Rollback" in moved["deploying"]  # subsections travel with their section
    # Nothing is lost or reworded: every line lands in the core or in one moved section.
    pieces = [core, *moved.values()]
    for line in filter(None, text.splitlines()):
        assert sum(line in piece.splitlines() for piece in pieces) == 1, line


def test_titles_that_slug_alike_do_not_overwrite_each_other() -> None:
    _, moved = slim.slim(FIXTURE.read_text(encoding="utf-8"), set())
    assert moved["c"].startswith("## C\n")
    assert moved["c-2"].startswith("## C++\n")


def test_main_writes_the_core_and_one_file_per_section(tmp_path, capsys) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    assert slim.main([str(target), "--keep", "Rules, Layout", "--to", "docs/agent"]) == 0
    assert "moving 4 sections to docs/agent/" in capsys.readouterr().out
    result = target.read_text(encoding="utf-8")
    assert result.rstrip().endswith("- `docs/agent/c-2.md`: C++")
    assert "- `docs/agent/stack.md`: Stack" in result
    assert (
        (tmp_path / "docs" / "agent" / "deploying.md")
        .read_text(encoding="utf-8")
        .startswith("## Deploying")
    )


def test_dry_run_writes_nothing(tmp_path) -> None:
    target = tmp_path / "CLAUDE.md"
    original = FIXTURE.read_text(encoding="utf-8")
    target.write_text(original, encoding="utf-8")
    assert slim.main([str(target), "--keep", "Rules", "--dry-run"]) == 0
    assert target.read_text(encoding="utf-8") == original
    assert not (tmp_path / "docs").exists()
