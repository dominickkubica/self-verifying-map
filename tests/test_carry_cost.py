from __future__ import annotations

import json

import pytest
from transcripts import SECRET, Transcript

from lean_agent_kit import carry_cost

PROMPT = SECRET + " " + "p" * 28  # 40 characters: 10 tokens


def basic() -> Transcript:
    """Three API calls: a read, a shell command, then a closing line of text."""
    return (
        Transcript()
        .prompt(PROMPT)
        .call(text="t" * 8, tools=[("Read", {"file_path": "a.py"}, "r" * 400)])
        .call(tools=[("Bash", {"command": "git status"}, "b" * 80)])
        .call(text="d" * 4)
    )


def test_each_source_is_charged_for_every_later_call(tmp_path) -> None:
    totals = carry_cost.session_costs(basic().write(tmp_path))
    # [tokens entered, tokens carried]: entered once, carried by every call after it.
    assert totals["person / injected user content"] == [10, 30]
    assert totals["Read"] == [100, 200]
    assert totals["Bash: git"] == [20, 20]
    assert totals["agent: text"] == [3, 4]
    # '{"file_path": "a.py"}' is 21 characters, '{"command": "git status"}' 25.
    assert totals["agent: tool inputs"] == [11, 16]


def test_a_call_logged_over_several_lines_counts_once(tmp_path) -> None:
    whole = Transcript().prompt(PROMPT).call(text="t" * 8, tools=[("Grep", {}, "g" * 40)]).call()
    split = (
        Transcript()
        .prompt(PROMPT)
        .call(text="t" * 8, tools=[("Grep", {}, "g" * 40)], split_lines=True)
        .call()
    )
    assert carry_cost.session_costs(whole.write(tmp_path / "a")) == carry_cost.session_costs(
        split.write(tmp_path / "b")
    )


def test_compaction_drops_what_came_before_it(tmp_path) -> None:
    path = Transcript().prompt(PROMPT).call().compact("s" * 40).call().call().write(tmp_path)
    totals = carry_cost.session_costs(path)
    assert totals["person / injected user content"] == [10, 10]
    assert totals["compaction summary"] == [10, 20]


def test_a_pasted_image_costs_its_token_price_not_its_base64_length(tmp_path) -> None:
    path = Transcript().attachment("image", "A" * 40_000).call().write(tmp_path)
    entered, carried = carry_cost.session_costs(path)["attachment: image"]
    assert entered == len(json.dumps({"type": "image", "content": "x" * 6000})) // 4
    assert carried == entered


@pytest.mark.parametrize(
    ("name", "tool_input", "source"),
    [
        ("Bash", {"command": "cd /repo && pytest -q"}, "Bash: pytest"),
        ("Bash", {"command": "python -m pytest tests"}, "Bash: python pytest"),
        ("PowerShell", {"command": "Get-ChildItem -Recurse"}, "PowerShell: Get-ChildItem"),
        ("Bash", {"command": ""}, "Bash: ?"),
        ("mcp__server__search_threads", {}, "MCP: search_threads"),
        ("Edit", {"file_path": "x"}, "Edit"),
    ],
)
def test_tool_sources(name, tool_input, source) -> None:
    assert carry_cost._source_of_tool(name, tool_input) == source


def test_report_ranks_sources_by_carry(tmp_path, capsys) -> None:
    basic().write(tmp_path / "project-a")
    Transcript().prompt(PROMPT).call().write(tmp_path / "project-b", "other")
    assert carry_cost.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("2 sessions.")
    ranked = [line.split()[0] for line in out.splitlines()[3:]]
    assert ranked[0] == "Read"

    assert carry_cost.main(["--root", str(tmp_path), "--project", "project-b"]) == 0
    assert capsys.readouterr().out.startswith("1 sessions.")
