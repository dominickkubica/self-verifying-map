"""The repository's scripts outside the package: PDF building and the benchmark runner."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if not (ROOT / "tools" / "build_doc.py").exists():  # an sdist ships the package only
    pytest.skip("repository scripts are not in this checkout", allow_module_level=True)
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "benchmark")]

import build_doc  # noqa: E402
import release_notes  # noqa: E402
import run  # noqa: E402


def test_markdown_to_html() -> None:
    markdown = (
        "# Title\n\nSome **bold** and `code <x>`.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
        "- one\n- two\n\n```\nprint(1 < 2)\n```\n"
    )
    page = build_doc.to_html(markdown, ROOT)
    assert "<h1>Title</h1>" in page
    assert "<strong>bold</strong>" in page and "<code>code &lt;x&gt;</code>" in page
    assert "<th>a</th>" in page and "<td>2</td>" in page
    assert "<ul><li>one</li><li>two</li></ul>" in page
    assert "<pre><code>print(1 &lt; 2)</code></pre>" in page


def test_html_only_needs_no_browser(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(build_doc, "REPO", tmp_path)
    (tmp_path / "doc.md").write_text("# Doc\n", encoding="utf-8")
    monkeypatch.setattr(build_doc, "find_browser", lambda: pytest.fail("looked for a browser"))
    assert build_doc.main(["doc.md", "--html"]) == 0
    assert "<h1>Doc</h1>" in (tmp_path / "dist" / "doc.html").read_text(encoding="utf-8")


def test_no_browser_is_a_clear_failure(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(build_doc, "REPO", tmp_path)
    (tmp_path / "doc.md").write_text("# Doc\n", encoding="utf-8")
    monkeypatch.setattr(build_doc, "find_browser", lambda: None)
    assert build_doc.main(["doc.md"]) == 1
    assert "Pass --browser, or --html" in capsys.readouterr().out


@pytest.mark.parametrize(
    "layout", ["venv/Scripts/python.exe", "venv/bin/python", ".venv/bin/python"]
)
def test_the_benchmark_finds_the_repo_interpreter_on_any_platform(tmp_path, layout) -> None:
    interpreter = tmp_path / layout
    interpreter.parent.mkdir(parents=True)
    interpreter.touch()
    assert run.repo_interpreter(tmp_path) == str(interpreter)


def test_the_benchmark_asks_for_an_interpreter_when_there_is_no_venv(tmp_path) -> None:
    with pytest.raises(SystemExit, match="pass --python"):
        run.repo_interpreter(tmp_path)


def test_release_notes_are_the_versions_section() -> None:
    changelog = (
        "# Changelog\n\n## [Unreleased]\n\n## [0.2.0] - 2026-11-01\n\n- Two.\n\n"
        "## [0.1.0] - 2026-10-24\n\n- One.\n\n[0.1.0]: https://example.com\n"
    )
    assert release_notes.notes(changelog, "0.2.0") == "- Two.\n"
    assert release_notes.notes(changelog, "0.1.0") == "- One.\n"
    assert release_notes.notes(changelog, "Unreleased") is None  # empty
    assert release_notes.notes(changelog, "0.3.0") is None


def test_the_changelog_has_notes_for_the_package_version(capsys) -> None:
    from lean_agent_kit import __version__

    assert release_notes.main([f"v{__version__}"]) == 0
    assert capsys.readouterr().out.strip()  # a tag for this version would have notes


def test_a_run_that_hits_the_turn_limit_is_turn_limited() -> None:
    assert run.turn_limited({"subtype": "error_max_turns"}, 40)
    assert run.turn_limited({"is_error": True, "num_turns": 41}, 40)
    assert not run.turn_limited({"is_error": False, "num_turns": 41}, 40)
    assert not run.turn_limited({"is_error": True, "num_turns": 3}, 40)  # another error


def test_run_estimate_uses_the_costliest_run_seen() -> None:
    rows = [
        {"arm": "B", "kind": "wiring", "cost_usd": 0.3},
        {"arm": "B", "kind": "wiring", "cost_usd": 0.4},
        {"arm": "P", "kind": "change", "cost_usd": None},
    ]
    assert run.run_estimate(rows, "B", "wiring") == 0.4
    assert run.run_estimate(rows, "B", "change") == run.FIRST_RUN_ESTIMATE["change"]
    assert run.run_estimate(rows, "P", "trap") == run.FIRST_RUN_ESTIMATE["question"]
    assert run.run_estimate(rows, "P", "change") == 0


def test_shards_split_whole_pairs_and_cover_the_schedule_once() -> None:
    order = run.schedule(["w01", "w02", "c14", "k18", "t11"], 2, 7, ["B", "P"])
    shards = [run.shard(order, index, 3) for index in range(3)]
    assert sorted(r for s in shards for r in s) == sorted(order)
    for part in shards:
        assert part == [r for r in order if r in part]  # schedule order kept
        pairs = [r[:2] for r in part]
        assert all(pairs.count(p) == 2 for p in pairs)  # both arms of a pair together
    assert {r[:2] for r in shards[0]}.isdisjoint({r[:2] for r in shards[1]})


def test_without_options() -> None:
    argv = ["--repo", "x", "--workers", "3", "--out=o", "--budget-usd", "9", "--dry-run"]
    assert run.without_options(argv, {"--workers", "--out", "--budget-usd"}) == [
        "--repo",
        "x",
        "--dry-run",
    ]


def test_merge_worker_logs_adds_each_run_once(tmp_path) -> None:
    import json

    row = {"task": "w01", "rep": 0, "arm": "B", "cost_usd": 0.1}
    (tmp_path / "runs.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    for index, rows in enumerate([[row, {**row, "arm": "P"}], [{**row, "task": "w02"}]]):
        (tmp_path / f"worker-{index}").mkdir()
        text = "".join(json.dumps(r) + "\n" for r in rows)
        (tmp_path / f"worker-{index}" / "runs.jsonl").write_text(text, encoding="utf-8")
    assert run.merge_worker_logs(tmp_path) == 2
    assert run.merge_worker_logs(tmp_path) == 0
    assert len(run.read_rows(tmp_path / "runs.jsonl")) == 3
