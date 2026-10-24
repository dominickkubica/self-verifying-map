"""The transcript analyzers never print or write message content.

Every message in the fixture (prompts, injected text, the agent's text, tool inputs, tool
results, attachments, compaction summaries) carries a marker. Both tools run with every
option, and nothing they print or write may contain it. The only text either takes from a
transcript is a label (a tool name, an attachment type, a shell command's program), and a
label never comes from a message's words.
"""

from __future__ import annotations

import pytest
from transcripts import SECRET, Transcript

from lean_agent_kit import carry_cost, transcript_stats

#: Fragments that must not appear: the marker, and its distinctive halves.
FORBIDDEN = (SECRET, "SECRET", "7f3a")


def everything(root):
    """One session that puts the marker in every place a transcript holds text."""
    (
        Transcript()
        .prompt(f"please fix {SECRET} in the parser", at="2026-10-01T10:00:00Z")
        .injected(f"<system-reminder>{SECRET}</system-reminder>")
        .attachment("hook_output", f"context about {SECRET}")
        .attachment(f"type {SECRET}", "an attachment type that is not a name")
        .call(
            text=f"I will look at {SECRET}.",
            tools=[
                ("Read", {"file_path": f"src/{SECRET}.py"}, f"def {SECRET}(): pass"),
                ("Grep", {"pattern": SECRET}, f"src/{SECRET}.py:1"),
                ("Bash", {"command": f"python {SECRET}.py --flag {SECRET}"}, SECRET),
                ("Bash", {"command": f"./{SECRET}.sh"}, SECRET),
                ("Bash", {"command": f"TOKEN={SECRET} git push"}, SECRET),
                ("Bash", {"command": f"'{SECRET} sentence' | cat"}, SECRET),
                ("PowerShell", {"command": f"Get-Content {SECRET}.txt"}, SECRET),
                (f"mcp__server__{SECRET} x", {"q": SECRET}, SECRET),
            ],
        )
        .compact(f"summary mentioning {SECRET}")
        .call(
            tools=[("Edit", {"file_path": f"src/{SECRET}.py", "new_string": SECRET}, SECRET)],
            split_lines=True,
        )
        .prompt(f"and now {SECRET} again", at="2026-10-03T10:00:00Z")
        .call(text=SECRET)
        .write(root / "project", "session")
    )


def assert_clean(text: str) -> None:
    for fragment in FORBIDDEN:
        assert fragment not in text, f"output contains {fragment!r}:\n{text}"


@pytest.mark.parametrize(
    "args",
    [[], ["--project", "project"], ["--top", "1000"]],
)
def test_carry_cost_prints_no_message_content(tmp_path, capsys, args) -> None:
    everything(tmp_path)
    assert carry_cost.main(["--root", str(tmp_path), *args]) == 0
    out, err = capsys.readouterr()
    assert "Read" in out  # the report did run, with labels
    assert_clean(out + err)


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--split", "2026-10-02T00:00:00Z"],
        ["--match", "src/", "--edits-only"],
    ],
)
def test_transcript_stats_prints_and_writes_no_message_content(tmp_path, capsys, args) -> None:
    everything(tmp_path / "root")
    csv = tmp_path / "requests.csv"
    assert transcript_stats.main(["--root", str(tmp_path / "root"), "--csv", str(csv), *args]) == 0
    out, err = capsys.readouterr()
    assert "median" in out
    assert_clean(out + err)
    assert_clean(csv.read_text(encoding="utf-8"))


def test_the_check_itself_catches_a_leak(tmp_path, capsys, monkeypatch) -> None:
    """If labels were taken from command arguments, the test above would fail."""
    everything(tmp_path)
    monkeypatch.setattr(carry_cost, "_program", lambda command: command.split()[-1])
    carry_cost.main(["--root", str(tmp_path), "--top", "1000"])
    with pytest.raises(AssertionError, match="output contains"):
        assert_clean(capsys.readouterr().out)
