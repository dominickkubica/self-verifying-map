"""Measure how much an AI coding session spends finding its way, from Claude Code transcripts.

Claude Code keeps every session as a JSONL transcript under ~/.claude/projects/. Each
assistant API call records its token usage, including prompt-cache reads and writes, and
each tool call is recorded with its name and input. This reads them and reports, per
**request** (one prompt typed by the person, up to the next one):

- tokens: fresh input, cache writes, cache reads, output;
- tool calls, and how many were searches or file reads;
- orientation: searches and reads before the request's first code edit;
- re-reads: files read more than once within one request.

Then it compares requests before and after a cutoff (for example the day a project map
was introduced), optionally only those that touched a given path.

It prints numbers only. No prompt, reply or file content is ever written out.

    lean-agents stats --split 2026-10-22T15:26:55Z --match options-scanner
    lean-agents stats --csv requests.csv

Caveats it cannot remove, and the report repeats: requests differ in kind, so a
before/after difference mixes the intervention with the task mix; medians resist a few
huge requests but not a shifted mix; and one session's prompt cache makes later requests
in it cheaper than earlier ones regardless of anything else.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ROOT = Path.home() / ".claude" / "projects"

EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
SEARCH_TOOLS = {"Grep", "Glob"}
READ_TOOLS = {"Read"}
#: Shell commands that are searching or reading rather than doing.
SHELL_SEARCH = re.compile(
    r"(^|[|;&\s])(grep|rg|find|ls|cat|head|tail|sed -n|awk|wc"
    r"|Select-String|Get-ChildItem|Get-Content)\b"
)
SHELL_TOOLS = {"Bash", "PowerShell"}


@dataclass
class Request:
    session: str
    project: str
    started: datetime
    calls: int = 0
    input_tokens: int = 0
    cache_write: int = 0
    cache_read: int = 0
    output_tokens: int = 0
    tools: int = 0
    searches: int = 0
    reads: int = 0
    edits: int = 0
    orientation: int | None = None
    rereads: int = 0
    matched: bool = False
    tool_names: Counter = field(default_factory=Counter)

    @property
    def context_tokens(self) -> int:
        return self.input_tokens + self.cache_write + self.cache_read

    @property
    def context_per_call(self) -> float:
        """How much context each API call carried. Tracks session length, not the task."""
        return self.context_tokens / self.calls if self.calls else 0.0

    @property
    def weighted_tokens(self) -> float:
        """Input-equivalent tokens at relative prices: a cache read costs a tenth of fresh
        input, a cache write about double (one-hour cache), output five times."""
        return (
            self.input_tokens
            + 0.1 * self.cache_read
            + 2.0 * self.cache_write
            + 5.0 * self.output_tokens
        )


def _is_prompt(entry: dict) -> bool:
    """A message the person typed, as opposed to a tool result or injected context."""
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isCompactSummary"):
        return False
    if entry.get("isSidechain"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        if any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content):
            return False
        text = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
    else:
        return False
    text = text.strip()
    return bool(text) and not text.startswith(
        ("<system-reminder>", "<task-notification>", "<local-command", "<command-")
    )


def _when(entry: dict) -> datetime | None:
    stamp = entry.get("timestamp")
    if not stamp:
        return None
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(timezone.utc)


def _tool_kind(name: str, tool_input: dict) -> str:
    if name in EDIT_TOOLS:
        return "edit"
    if name in SEARCH_TOOLS:
        return "search"
    if name in READ_TOOLS:
        return "read"
    if name in SHELL_TOOLS and SHELL_SEARCH.search(str(tool_input.get("command", ""))):
        return "search"
    return "other"


def requests_in(path: Path, match: str | None) -> list[Request]:
    out: list[Request] = []
    current: Request | None = None
    seen_messages: set[str] = set()
    read_paths: Counter = Counter()
    project = path.parent.name
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if _is_prompt(entry):
                when = _when(entry)
                if when is None:
                    continue
                current = Request(session=path.stem, project=project, started=when)
                read_paths = Counter()
                out.append(current)
                continue
            if current is None or entry.get("type") != "assistant":
                continue
            message = entry.get("message") or {}
            # One API call can be logged as several lines, one per content block, each
            # carrying the same usage. Count the usage once per message id.
            identifier = message.get("id")
            usage = message.get("usage")
            if usage and identifier not in seen_messages:
                seen_messages.add(identifier)
                current.calls += 1
                current.input_tokens += usage.get("input_tokens", 0) or 0
                current.cache_write += usage.get("cache_creation_input_tokens", 0) or 0
                current.cache_read += usage.get("cache_read_input_tokens", 0) or 0
                current.output_tokens += usage.get("output_tokens", 0) or 0
            for block in message.get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name = block.get("name", "?")
                tool_input = block.get("input") or {}
                current.tools += 1
                current.tool_names[name] += 1
                if match and match in json.dumps(tool_input):
                    current.matched = True
                kind = _tool_kind(name, tool_input)
                if kind == "edit":
                    current.edits += 1
                    if current.orientation is None:
                        current.orientation = current.searches + current.reads
                elif kind == "search":
                    current.searches += 1
                elif kind == "read":
                    current.reads += 1
                    target = tool_input.get("file_path")
                    if target:
                        read_paths[target] += 1
                        if read_paths[target] == 2:
                            current.rereads += 1
    return out


def collect(root: Path, match: str | None) -> list[Request]:
    found: list[Request] = []
    for path in sorted(root.glob("*/*.jsonl")):
        found.extend(requests_in(path, match))
    return [r for r in found if r.calls]


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def summary(rows: list[Request]) -> dict[str, float | int | None]:
    edited = [r for r in rows if r.orientation is not None]
    return {
        "requests": len(rows),
        "with an edit": len(edited),
        "median weighted tokens (input-equivalent)": _median([r.weighted_tokens for r in rows]),
        "median context per API call": _median([r.context_per_call for r in rows]),
        "median output tokens": _median([r.output_tokens for r in rows]),
        "median API calls": _median([r.calls for r in rows]),
        "median tool calls": _median([r.tools for r in rows]),
        "median searches": _median([r.searches for r in rows]),
        "median reads": _median([r.reads for r in rows]),
        "median orientation (searches+reads before first edit)": _median(
            [r.orientation for r in edited]
        ),
        "share of requests with a re-read": (
            sum(1 for r in rows if r.rereads) / len(rows) if rows else None
        ),
    }


def _fmt(value, metric: str = "") -> str:
    if value is None:
        return "-"
    if metric.startswith("share"):
        return f"{value:.0%}"
    return f"{value:,.0f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--split", help="ISO time; compare requests before and after it.")
    parser.add_argument("--match", help="Only requests whose tool calls mention this text.")
    parser.add_argument("--csv", type=Path, help="Also write one row per request.")
    parser.add_argument(
        "--edits-only",
        action="store_true",
        help="Only requests that edited code: closer to like-for-like across a split.",
    )
    args = parser.parse_args(argv)

    rows = collect(args.root, args.match)
    if args.match:
        rows = [r for r in rows if r.matched]
    if args.edits_only:
        rows = [r for r in rows if r.edits]
    if args.csv:
        with args.csv.open("w", newline="", encoding="utf-8") as handle:
            fields = [k for k in asdict(rows[0]) if k != "tool_names"] + ["context_tokens"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for r in rows:
                data = {k: v for k, v in asdict(r).items() if k != "tool_names"}
                writer.writerow({**data, "context_tokens": r.context_tokens})

    groups = {"all": rows}
    if args.split:
        cut = datetime.fromisoformat(args.split.replace("Z", "+00:00")).astimezone(timezone.utc)
        groups = {
            "before": [r for r in rows if r.started < cut],
            "after": [r for r in rows if r.started >= cut],
        }
    tables = {name: summary(group) for name, group in groups.items()}
    names = list(tables)
    print(f"{'':58}" + "".join(f"{n:>14}" for n in names))
    for metric in tables[names[0]]:
        print(f"{metric:58}" + "".join(f"{_fmt(tables[n][metric], metric):>14}" for n in names))
    print("\nRequests differ in kind, so a before/after gap mixes the change with the task mix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
