"""Where a long agent session's tokens go: the carry cost of everything put into context.

Anything that enters an agent's context (a tool result, an injected reminder, the agent's
own output) is re-read by every later API call until the conversation is compacted. Its
real cost is therefore its size times the number of calls that carry it, not its size.
This reads Claude Code transcripts and attributes that carry cost to sources: each tool
(and, for shell commands, the command's first word), injected attachments, the person's
messages, and the agent's own text and tool inputs.

    lean-agents stats ...        # per request
    lean-agents carry-cost       # per source, across all sessions

Tokens are estimated as characters / 4. No message content is printed: sources are labelled
by tool name, attachment type, or the program a shell command runs, and nothing else.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

DEFAULT_ROOT = Path.home() / ".claude" / "projects"
CHARS_PER_TOKEN = 4
BASE64_RUN = re.compile(r"[A-Za-z0-9+/=]{2000,}")


def _text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_text(v) for v in value)
    if isinstance(value, dict):
        if value.get("type") == "image":
            return "x" * 6000  # an image costs on the order of 1.5k tokens
        return _text(value.get("text") or value.get("content") or "")
    return ""


#: The only text this report takes from a transcript is a label: a tool name, an attachment
#: type, or the program a shell command runs. A label must look like a name; anything else
#: (a path, a value, a sentence) prints as "?", so no message content reaches the output.
_NAME = re.compile(r"[A-Za-z][\w.+-]{0,39}")
#: Programs a command may name by path (`venv/bin/python`) and still be reported by name.
#: Any other program given as a path is a local script, and its name is the agent's own.
_KNOWN_BY_PATH = set(
    "bash sh zsh pwsh powershell cmd node npm npx git pip pip3 pytest py python python3 "
    "ruff uv claude".split()
)
_PYTHONS = {"py", "python", "python3"}


def _label(text: str) -> str:
    return text if _NAME.fullmatch(text or "") else "?"


#: A shell word: a quoted string kept whole (so its words are never mistaken for a
#: program), or a run of non-space characters.
_WORD = re.compile(r"\"[^\"]*\"|'[^']*'|\S+")


def _program(command: str) -> str:
    """The program a shell command runs, as a label: `cd x && pytest -q` -> `pytest`."""
    words = [w.strip("\"'&") for w in _WORD.findall(command)]
    while words and (words[0] in ("cd", "") or "=" in words[0]):
        if words[0] == "cd":
            words = words[2:] if len(words) > 1 and words[1] != "/d" else words[3:]
        else:
            words = words[1:]
    if not words:
        return "?"
    program = words[0]
    name = re.split(r"[\\/]", program)[-1].removesuffix(".exe")
    if name != program and name.lower() not in _KNOWN_BY_PATH:
        return "(local script)"
    if name.lower() in _PYTHONS and len(words) > 2 and words[1] == "-m":
        return f"{_label(name)} {_label(words[2])}"
    return _label(name)


def _source_of_tool(name: str, tool_input: dict) -> str:
    if name in ("Bash", "PowerShell"):
        return f"{name}: {_program(str(tool_input.get('command', '')))}"
    if name.startswith("mcp__"):
        return "MCP: " + _label(name.split("__")[-1])
    return _label(name)


def session_costs(path: Path) -> dict[str, list[float]]:
    """{source: [tokens entered, carry tokens]} for one transcript."""
    entries = []
    calls_seen = set()
    tool_names: dict[str, str] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    # Index of each API call, and where compactions happen.
    events: list[tuple[str, str, int]] = []  # (kind, source, tokens)
    for entry in entries:
        kind = entry.get("type")
        message = entry.get("message") or {}
        if entry.get("isCompactSummary"):
            size = len(_text(message.get("content"))) // CHARS_PER_TOKEN
            events.append(("compact", "compaction summary", size))
            continue
        if kind == "assistant":
            identifier = message.get("id")
            if message.get("usage") and identifier not in calls_seen:
                calls_seen.add(identifier)
                events.append(("call", "", 0))
            for block in message.get("content") or []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    events.append(("enter", "agent: text", len(block.get("text", "")) // 4))
                elif block.get("type") == "tool_use":
                    tool_names[block.get("id")] = _source_of_tool(
                        block.get("name", "?"), block.get("input") or {}
                    )
                    size = len(json.dumps(block.get("input") or {})) // CHARS_PER_TOKEN
                    events.append(("enter", "agent: tool inputs", size))
        elif kind == "user":
            content = message.get("content")
            if isinstance(content, list) and any(
                isinstance(c, dict) and c.get("type") == "tool_result" for c in content
            ):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        source = tool_names.get(block.get("tool_use_id"), "tool: ?")
                        size = len(_text(block.get("content"))) // CHARS_PER_TOKEN
                        events.append(("enter", source, size))
            else:
                size = len(_text(content)) // CHARS_PER_TOKEN
                events.append(("enter", "person / injected user content", size))
        elif kind == "attachment":
            attachment = entry.get("attachment") or {}
            # A pasted image travels as base64 text in the log but costs ~1.5k tokens.
            raw = BASE64_RUN.sub("x" * 6000, json.dumps(attachment))
            size = len(raw) // CHARS_PER_TOKEN
            label = _label(str(attachment.get("type", "")))
            events.append(("enter", f"attachment: {label}", size))

    # Calls after each event, up to the next compaction.
    totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    pending: list[tuple[str, int]] = []
    for kind, source, tokens in events:
        if kind == "call":
            for src, size in pending:
                totals[src][1] += size
            continue
        if kind == "compact":
            pending = [(source, tokens)]
            totals[source][0] += tokens
            continue
        pending.append((source, tokens))
        totals[source][0] += tokens
    return totals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--project", default=None, help="Only this project folder name.")
    parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args(argv)

    totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    folders = [args.root / args.project] if args.project else args.root.iterdir()
    sessions = 0
    for folder in folders:
        for path in sorted(Path(folder).glob("*.jsonl")):
            sessions += 1
            for source, (entered, carried) in session_costs(path).items():
                totals[source][0] += entered
                totals[source][1] += carried
    carry_total = sum(c for _, c in totals.values()) or 1
    print(f"{sessions} sessions. Carry = tokens x later API calls that re-read them.\n")
    print(f"{'source':44} {'entered':>12} {'carried':>15} {'share':>7}")
    ranked = sorted(totals.items(), key=lambda kv: -kv[1][1])
    for source, (entered, carried) in ranked[: args.top]:
        print(f"{source[:44]:44} {entered:>12,.0f} {carried:>15,.0f} {carried / carry_total:>7.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
