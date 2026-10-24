from __future__ import annotations

import csv

from transcripts import SECRET, Transcript

from lean_agent_kit import transcript_stats as stats

USAGE = {
    "input_tokens": 100,
    "cache_creation_input_tokens": 10,
    "cache_read_input_tokens": 1000,
    "output_tokens": 50,
}


def navigating() -> Transcript:
    """One request that searches, reads a file twice, then edits; then a question."""
    return (
        Transcript()
        .prompt(f"fix it {SECRET}", at="2026-10-01T10:00:00Z")
        .injected(f"<system-reminder>{SECRET}</system-reminder>")
        .call(
            tools=[
                ("Grep", {"pattern": "parse"}, SECRET),
                ("Read", {"file_path": "src/app/parse.py"}, SECRET),
            ],
            usage=USAGE,
        )
        .call(
            tools=[
                ("Bash", {"command": "rg -n parse src"}, SECRET),
                ("Read", {"file_path": "src/app/parse.py"}, SECRET),
            ],
            usage=USAGE,
            split_lines=True,
        )
        .call(tools=[("Edit", {"file_path": "src/app/parse.py"}, "ok")], usage=USAGE)
        .prompt(f"<system-reminder>{SECRET}</system-reminder>")
        .prompt(f"what does parse do? {SECRET}", at="2026-10-03T10:00:00Z")
        .call(text=SECRET, usage=USAGE)
    )


def test_requests_start_at_each_typed_prompt(tmp_path) -> None:
    first, second = stats.requests_in(navigating().write(tmp_path / "proj"), None)
    assert (first.project, first.session) == ("proj", "session-1")
    assert first.calls == 3  # the split call counts once
    assert (first.tools, first.searches, first.reads, first.edits) == (5, 2, 2, 1)
    assert first.orientation == 4
    assert first.rereads == 1
    assert first.tool_names == {"Grep": 1, "Read": 2, "Bash": 1, "Edit": 1}
    assert (second.calls, second.tools, second.orientation) == (1, 0, None)


def test_token_totals_and_weights(tmp_path) -> None:
    first, _ = stats.requests_in(navigating().write(tmp_path / "proj"), None)
    assert first.input_tokens == 300 and first.cache_read == 3000 and first.output_tokens == 150
    assert first.context_tokens == 300 + 30 + 3000
    assert first.context_per_call == (300 + 30 + 3000) / 3
    assert first.weighted_tokens == 300 + 0.1 * 3000 + 2.0 * 30 + 5.0 * 150


def test_match_marks_requests_whose_tools_touch_a_path(tmp_path) -> None:
    first, second = stats.requests_in(navigating().write(tmp_path / "proj"), "src/app")
    assert first.matched and not second.matched


def test_collect_skips_requests_with_no_api_call(tmp_path) -> None:
    Transcript().prompt("hello").write(tmp_path / "proj")
    assert stats.collect(tmp_path, None) == []


def test_split_report(tmp_path, capsys) -> None:
    navigating().write(tmp_path / "proj")
    assert stats.main(["--root", str(tmp_path), "--split", "2026-10-02T00:00:00Z"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["before", "after"]
    assert lines[1].split()[-2:] == ["1", "1"]


def test_csv_has_one_row_per_request(tmp_path) -> None:
    navigating().write(tmp_path / "proj")
    out = tmp_path / "requests.csv"
    assert stats.main(["--root", str(tmp_path), "--csv", str(out)]) == 0
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert [r["calls"] for r in rows] == ["3", "1"]
    assert rows[0]["context_tokens"] == "3330"


def test_csv_with_no_matching_requests(tmp_path) -> None:
    navigating().write(tmp_path / "proj")
    out = tmp_path / "requests.csv"
    assert (
        stats.main(
            ["--root", str(tmp_path), "--edits-only", "--match", "nowhere", "--csv", str(out)]
        )
        == 0
    )
    assert out.read_text(encoding="utf-8").startswith("session,project,started,")
