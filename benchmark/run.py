"""Run the map benchmark: fixed tasks, two arms, repeated, interleaved, graded blind.

    python benchmark/run.py --repo ~/src/options-scanner --out bench-out --pilot
    python benchmark/run.py --repo ... --out bench-out            # the full 200 runs
    python benchmark/run.py --repo ... --out bench-out --dry-run  # plumbing only, no agent
    python benchmark/run.py --repo ... --out bench-out --cleanup  # remove the worktrees

See DESIGN.md for what is being tested and why. Each run is one fresh, non-interactive
Claude Code session in a git worktree at the benchmark commit:

- arm A ("no map") has the map, its design doc, its test and the map rule in the
  instruction file removed, committed on a detached HEAD inside its worktree;
- arm B ("map") is the commit unchanged.

Results append to `<out>/runs.jsonl`, one line per run, so an interrupted benchmark
resumes where it stopped. Answers and hidden tests never enter a worktree before the run
that is graded by them finishes.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src" / "lean_agent_kit"))

import transcript_stats  # noqa: E402

PILOT = ["w01", "w07", "c14", "k18"]
PILOT_REPS = 2
FULL_REPS = 5

#: Removed in arm A. Everything else is identical between the arms.
NO_MAP_PATHS = ["MAP.md", "map", "docs/design", "tests/test_map.py"]
#: Edits to the instruction file in arm A: (pattern, replacement), each must match once.
NO_MAP_EDITS = [
    (r"\*\*Read `MAP\.md` before tracing anything\.\*\*.*?enforce all of it\.\n\n", ""),
    (
        r"See `map/generated/modules\.md` for every module and what it does, and `MAP\.md` "
        r"for how\nthey connect\. ",
        "",
    ),
]

QUESTION_TOOLS = ["Read", "Grep", "Glob", "Bash"]
CHANGE_TOOLS = ["Read", "Grep", "Glob", "Bash", "Edit", "Write"]

#: Harness settings that shrink what every turn carries: only the task's tools are
#: defined (not just permitted), the skills listing is off, and the per-session dynamic
#: sections of the system prompt are left out. Measured: 47k -> 17k tokens of context.
LEAN_FLAGS = [
    "--disable-slash-commands",
    "--exclude-dynamic-system-prompt-sections",
    "--setting-sources",
    "project",
]

#: Sections of the instruction file every session keeps in the slim tree. The rest move
#: to docs/agent/, one file each, listed in the instruction file so they load on demand.
SLIM_KEEP = ("Stack", "Rules", "Layout", "Non-goals")

#: Each arm: the tree it runs in, whether the harness is lean, and a model per task kind
#: (falling back to --model). A and B are the map benchmark; L, S and R are optimizers.
ARMS = {
    "A": {"tree": "nomap"},
    "B": {"tree": "map"},
    "L": {"tree": "map", "lean": True},
    "S": {"tree": "slim", "lean": True},
    "R": {
        "tree": "slim",
        "lean": True,
        "models": {"wiring": "sonnet", "trap": "sonnet", "control": "sonnet"},
    },
    # Round 2. T: the smallest tool set per kind (Bash's definition alone is ~1.2k tokens).
    "T": {"tree": "slim", "lean": True, "tools": "tight"},
    # M: T with Claude Code's system prompt replaced by a short one (8.8k -> 4.5k context).
    "M": {"tree": "slim", "lean": True, "tools": "tight", "system": "minimal"},
    # H: M with the cheapest model for questions.
    "H": {
        "tree": "slim",
        "lean": True,
        "tools": "tight",
        "system": "minimal",
        "models": {"wiring": "haiku", "trap": "haiku", "control": "haiku"},
    },
    # E: M at low effort, for fewer output tokens (output is priced at 5x input).
    "E": {"tree": "slim", "lean": True, "tools": "tight", "system": "minimal", "effort": "low"},
    # Iteration 2: E's low effort with a cheaper model for questions.
    "ES": {
        "tree": "slim",
        "lean": True,
        "tools": "tight",
        "system": "minimal",
        "effort": "low",
        "models": {"wiring": "sonnet", "trap": "sonnet", "control": "sonnet"},
    },
    # Sonnet at low effort for everything, code changes included.
    "ESC": {
        "tree": "slim",
        "lean": True,
        "tools": "tight",
        "system": "minimal",
        "effort": "low",
        "models": {"wiring": "sonnet", "trap": "sonnet", "control": "sonnet", "change": "sonnet"},
    },
    # Iteration 5, all against ESC: grep-first map rule (G), and prefetch + self-regenerating
    # map (P).
    "G": {
        "tree": "slimg",
        "lean": True,
        "tools": "tight",
        "system": "minimal",
        "effort": "low",
        "models": {"wiring": "sonnet", "trap": "sonnet", "control": "sonnet", "change": "sonnet"},
    },
    "P": {
        "tree": "slimp",
        "lean": True,
        "tools": "tight",
        "system": "minimal",
        "effort": "low",
        "models": {"wiring": "sonnet", "trap": "sonnet", "control": "sonnet", "change": "sonnet"},
    },
    "EH": {
        "tree": "slim",
        "lean": True,
        "tools": "tight",
        "system": "minimal",
        "effort": "low",
        "models": {"wiring": "haiku", "trap": "haiku", "control": "haiku"},
    },
    # Q: P with a 5-minute prompt cache. A headless run finishes in minutes, so the
    # default 1-hour cache write (2x input, against 1.25x) is paid for and never used.
    "Q": {
        "tree": "slimp",
        "lean": True,
        "tools": "tight",
        "system": "minimal",
        "effort": "low",
        "cache_ttl": "5m",
        "models": {"wiring": "sonnet", "trap": "sonnet", "control": "sonnet", "change": "sonnet"},
    },
}

#: The reply Claude Code gives when the account's session or usage limit is reached.
LIMIT_ERROR = re.compile(r"(session|usage|rate) limit", re.I)

TIGHT_TOOLS = {
    "question": ["Read", "Grep", "Glob"],
    "change": ["Read", "Grep", "Glob", "Edit", "Bash"],
}

#: Replaces Claude Code's system prompt in arms with "system": "minimal".
MINIMAL_SYSTEM = (
    "You are a coding agent working in this repository. Follow CLAUDE.md. Use the tools "
    "to inspect and change files. Make independent tool calls together in one turn. Read "
    "only what the task needs, and stop as soon as you can answer or the change is done "
    "and verified. Do not commit. Reply concisely."
)


def git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def worktree(out: Path, tree: str) -> Path:
    return out / f"wt-{tree}"


def slim_instructions(path: Path) -> None:
    """Keep the instruction file's core sections; move the rest to docs/agent/."""
    instructions = path / "CLAUDE.md"
    text = instructions.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^(?=## )", text)
    kept, moved = [parts[0]], []
    folder = path / "docs" / "agent"
    folder.mkdir(parents=True, exist_ok=True)
    for part in parts[1:]:
        title = part.splitlines()[0].removeprefix("## ").strip()
        if title in SLIM_KEEP:
            kept.append(part)
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        (folder / f"{slug}.md").write_text(part, encoding="utf-8", newline="\n")
        moved.append(f"- `docs/agent/{slug}.md`: {title}")
    index = "## Read when relevant\n\n" + "\n".join(moved) + "\n"
    slim = "".join(kept).rstrip() + "\n\n" + index
    instructions.write_text(slim, encoding="utf-8", newline="\n")


def commit_tree(path: Path, message: str) -> None:
    git(["add", "-A"], path)
    git(
        [
            "-c",
            "user.name=bench",
            "-c",
            "user.email=bench@localhost",
            "commit",
            "-q",
            "--no-verify",
            "-m",
            message,
        ],
        path,
    )


MAP_RULE = r"\*\*Read `MAP\.md` before tracing anything\.\*\*.*?enforce all of it\.\n\n"
GREP_RULE = (
    "**Wiring facts are in `map/generated/` (one row per module, table, route, cache, view, "
    "job and command) and `map/notes.md` (why, and known traps). Grep them for a name "
    "instead of reading whole files; `MAP.md` is only the overview.** After a wiring change, "
    "run `optscan map generate`; if `optscan map check` reports a stale note, re-read it, "
    "fix it, then `optscan map stamp <key>`.\n\n"
)
PREFETCH_RULE = (
    "**Facts from the generated wiring map about what your prompt names are added to your "
    "context automatically; they are checked against the code, so trust them.** For anything "
    "else, Grep `map/generated/` and `map/notes.md` for a name rather than reading whole "
    "files. The map regenerates itself when you finish; if `optscan map check` reports a "
    "stale note after a change, re-read it, fix it, then `optscan map stamp <key>`.\n\n"
)


def replace_map_rule(path: Path, rule: str) -> None:
    instructions = path / "CLAUDE.md"
    text, count = re.subn(
        MAP_RULE, lambda _: rule, instructions.read_text(encoding="utf-8"), count=1, flags=re.S
    )
    if count != 1:
        raise SystemExit("the map rule in CLAUDE.md did not match")
    instructions.write_text(text, encoding="utf-8", newline="\n")


def repo_interpreter(repo: Path) -> str:
    """The Python in the repository's own virtual environment, on any platform."""
    for folder in ("venv", ".venv"):
        for interpreter in ("Scripts/python.exe", "bin/python"):
            if (repo / folder / interpreter).exists():
                return str(repo / folder / interpreter)
    raise SystemExit(f"no venv or .venv in {repo}; pass --python with the repo's interpreter")


def install_hooks(path: Path, python: str) -> None:
    """The prefetch hook on every prompt, and a map regeneration when the agent stops."""
    hooks = path / ".claude" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    shutil.copy(
        HERE.parent / "src" / "lean_agent_kit" / "map_prefetch.py", hooks / "map_prefetch.py"
    )
    interpreter = Path(python).as_posix()
    settings = {
        "hooks": {
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": f'"{interpreter}" .claude/hooks/map_prefetch.py',
                        }
                    ]
                }
            ],
            "Stop": [
                {
                    "hooks": [
                        {"type": "command", "command": f'"{interpreter}" -m optscan map generate'}
                    ]
                }
            ],
        }
    }
    (path / ".claude" / "settings.json").write_text(json.dumps(settings, indent=2), "utf-8")


def setup(repo: Path, out: Path, commit: str, trees: set[str], python: str = "python") -> None:
    out.mkdir(parents=True, exist_ok=True)
    for tree in sorted(trees):
        path = worktree(out, tree)
        if path.exists():
            continue
        git(["worktree", "add", "--detach", str(path), commit], repo)
        if tree in ("slim", "slimg", "slimp"):
            slim_instructions(path)
            if tree == "slimg":
                replace_map_rule(path, GREP_RULE)
            if tree == "slimp":
                replace_map_rule(path, PREFETCH_RULE)
                install_hooks(path, python)
            commit_tree(path, f"benchmark tree: {tree}")
        if tree == "nomap":
            for item in NO_MAP_PATHS:
                git(["rm", "-r", "-q", "--ignore-unmatch", item], path)
            instructions = path / "CLAUDE.md"
            text = instructions.read_text(encoding="utf-8")
            for pattern, replacement in NO_MAP_EDITS:
                text, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
                if count != 1:
                    raise SystemExit(f"arm A edit did not match: {pattern[:50]}")
            instructions.write_text(text, encoding="utf-8", newline="\n")
            git(["add", "-A"], path)
            git(
                [
                    "-c",
                    "user.name=bench",
                    "-c",
                    "user.email=bench@localhost",
                    "commit",
                    "-q",
                    "--no-verify",
                    "-m",
                    "benchmark arm A: no map",
                ],
                path,
            )


def reset(path: Path) -> None:
    git(["reset", "-q", "--hard", "HEAD"], path)
    git(["clean", "-q", "-fd"], path)


def cleanup(repo: Path, out: Path) -> None:
    for path in sorted([*out.glob("wt-*"), *out.glob("worker-*/wt-*")]):
        git(["worktree", "remove", "--force", str(path)], repo)


def read_rows(log: Path) -> list[dict]:
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def run_key(row: dict) -> tuple[str, int, str]:
    return (row["task"], row["rep"], row["arm"])


def shard(order: list[tuple[str, int, str]], index: int, count: int) -> list[tuple[str, int, str]]:
    """Worker `index` of `count`'s share of the schedule: whole (task, rep) pairs, dealt in
    turn, so both arms of a pair still run back to back on one worker, in schedule order."""
    pairs = list(dict.fromkeys((task, rep) for task, rep, _ in order))
    mine = {pair for number, pair in enumerate(pairs) if number % count == index}
    return [run for run in order if run[:2] in mine]


def merge_worker_logs(out: Path) -> int:
    """Append the workers' new runs to `<out>/runs.jsonl`; returns how many were added."""
    log = out / "runs.jsonl"
    seen = {run_key(row) for row in read_rows(log)}
    added = []
    for worker_log in sorted(out.glob("worker-*/runs.jsonl")):
        for row in read_rows(worker_log):
            if run_key(row) not in seen:
                seen.add(run_key(row))
                added.append(row)
    with log.open("a", encoding="utf-8") as handle:
        for row in added:
            handle.write(json.dumps(row) + "\n")
    return len(added)


def without_options(argv: list[str], names: set[str]) -> list[str]:
    """`argv` with the named options and their values removed."""
    out, skip = [], False
    for item in argv:
        if skip:
            skip = False
        elif item in names:
            skip = True
        elif item.split("=", 1)[0] not in names:
            out.append(item)
    return out


def run_workers(args, argv: list[str]) -> int:
    """Run the schedule on `args.workers` processes, each with its own worktrees and log.

    Each worker reads `<out>/runs.jsonl` for runs already done, takes every Nth pair, and
    gets an equal share of what is left of the budget. Their runs are merged into
    `<out>/runs.jsonl` when all have stopped; rerunning resumes.
    """
    args.out.mkdir(parents=True, exist_ok=True)
    merge_worker_logs(args.out)
    log = args.out / "runs.jsonl"
    spent = sum(row["cost_usd"] or 0 for row in read_rows(log))
    base = without_options(argv, {"--workers", "--out", "--budget-usd"})
    workers = []
    for index in range(args.workers):
        folder = args.out / f"worker-{index}"
        folder.mkdir(exist_ok=True)
        command = [sys.executable, str(Path(__file__).resolve()), *base, "--out", str(folder)]
        command += ["--shard", f"{index}/{args.workers}", "--prior-log", str(log)]
        if args.budget_usd is not None:
            command += ["--budget-usd", f"{(args.budget_usd - spent) / args.workers:.4f}"]
        output = (folder / "output.txt").open("a", encoding="utf-8")
        workers.append((index, subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)))
    codes = {index: process.wait() for index, process in workers}
    added = merge_worker_logs(args.out)
    for index, code in codes.items():
        tail = (args.out / f"worker-{index}" / "output.txt").read_text(encoding="utf-8")
        last = tail.strip().splitlines()[-1] if tail.strip() else ""
        print(f"worker {index}: exit {code}. {last}", flush=True)
    print(f"{added} runs added to {log}.", flush=True)
    return max(codes.values())


def schedule(
    task_ids: list[str], reps: int, seed: int, arm_names: list[str]
) -> list[tuple[str, int, str]]:
    """(task, rep, arm) in a seeded order, with every arm of a (task, rep) adjacent."""
    rng = random.Random(seed)
    pairs = [(t, r) for t in task_ids for r in range(reps)]
    rng.shuffle(pairs)
    order = []
    for task, rep in pairs:
        arms = list(arm_names)
        rng.shuffle(arms)
        order += [(task, rep, arm) for arm in arms]
    return order


def turn_limited(result: dict, max_turns: int) -> bool:
    """The session ended at the turn limit, not with the agent's own answer."""
    return result.get("subtype") == "error_max_turns" or bool(
        result.get("is_error") and (result.get("num_turns") or 0) > max_turns
    )


#: Cost assumed for a run of a kind no run in the log has shown yet, in dollars.
FIRST_RUN_ESTIMATE = {"change": 4.0, "question": 0.5}


def run_estimate(rows: list[dict], arm: str, kind: str) -> float:
    """The most a run of this arm and kind has cost so far, or a cautious default."""
    seen = [r["cost_usd"] or 0 for r in rows if r["arm"] == arm and r["kind"] == kind]
    default = FIRST_RUN_ESTIMATE["change" if kind == "change" else "question"]
    return max(seen) if seen else default


def grade_question(task: dict, answer: str) -> dict:
    text = answer.lower()
    hits = [any(alt.lower() in text for alt in group) for group in task["required"]]
    score = sum(hits) / len(hits)
    return {"score": score, "grade": "correct" if score == 1 else "partial" if score else "wrong"}


def grade_change(task: dict, path: Path, python: str, env: dict) -> dict:
    hidden = HERE / "hidden_tests" / task["hidden_test"]
    target = path / "tests" / f"_hidden_{hidden.name}"
    shutil.copy(hidden, target)
    try:
        run = subprocess.run(
            [python, "-m", "pytest", str(target), "-p", "no:cacheprovider", "-q"],
            cwd=path,
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
        )
    finally:
        target.unlink(missing_ok=True)
    passed = run.returncode == 0
    return {"score": 1.0 if passed else 0.0, "grade": "correct" if passed else "wrong"}


def find_transcript(session_id: str) -> Path | None:
    for found in transcript_stats.DEFAULT_ROOT.glob(f"*/{session_id}.jsonl"):
        return found
    return None


def run_agent(
    prompt: str, path: Path, tools: list[str], args, env: dict, arm: dict, kind: str
) -> dict:
    if arm.get("tools") == "tight":
        tools = TIGHT_TOOLS["change" if kind == "change" else "question"]
    # The prompt goes in on stdin: on Windows `claude` is a .cmd wrapper, and a newline in
    # an argument ends the command line there, silently dropping every flag after it.
    command = [
        args.claude,
        "-p",
        "--output-format",
        "json",
        "--max-turns",
        str(args.max_turns),
        "--allowedTools",
        *tools,
        "--strict-mcp-config",
        "--mcp-config",
        str(args.out / "no-mcp.json"),
    ]
    if arm.get("lean"):
        command += ["--tools", *tools, *LEAN_FLAGS]
    if arm.get("system") == "minimal":
        command += ["--system-prompt", MINIMAL_SYSTEM]
    if arm.get("effort"):
        command += ["--effort", arm["effort"]]
    model = arm.get("models", {}).get(kind) or args.model
    if model:
        command += ["--model", model]
    if arm.get("cache_ttl"):
        env = {**env, "CLAUDE_CODE_PROMPT_CACHE_TTL": arm["cache_ttl"]}
    started = time.time()
    finished = subprocess.run(
        command,
        input=prompt,
        cwd=path,
        env=env,
        capture_output=True,
        text=True,
        timeout=args.timeout,
        encoding="utf-8",
    )
    try:
        result = json.loads(finished.stdout)
    except json.JSONDecodeError:
        result = {"is_error": True, "result": "", "stderr": finished.stderr[-2000:]}
    result["wall_seconds"] = round(time.time() - started, 1)
    return result


def transcript_metrics(session_id: str | None) -> dict:
    found = find_transcript(session_id) if session_id else None
    if found is None:
        return {}
    requests = transcript_stats.requests_in(found, None)
    if not requests:
        return {}
    first = requests[0]
    return {
        "api_calls": first.calls,
        "tool_calls": first.tools,
        "searches": first.searches,
        "reads": first.reads,
        "edits": first.edits,
        "orientation": first.orientation,
        "rereads": first.rereads,
        "weighted_tokens": first.weighted_tokens,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, default=HERE / "tasks.json")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--reps", type=int, default=None)
    parser.add_argument("--seed", type=int, default=20261023)
    parser.add_argument("--model", default=None, help="Fix the model; recorded either way.")
    parser.add_argument("--max-turns", type=int, default=40)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--claude", default=shutil.which("claude") or "claude")
    parser.add_argument(
        "--python",
        default=None,
        help="Interpreter with the repo's deps (default: the repo's venv or .venv).",
    )
    parser.add_argument(
        "--budget-usd",
        type=float,
        default=None,
        help="Stop before a (task, repetition) pair whose runs could take the log's total "
        "cost past this, so a usage window is not exhausted mid-run.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Run pairs on this many processes at once, each with its own worktrees. "
        "Concurrent sessions share the provider's prompt cache, so their costs are not "
        "comparable with sequential runs.",
    )
    parser.add_argument("--shard", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--prior-log", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--arms", default="A,B", help="Comma-separated, from ARMS.")
    parser.add_argument("--only", default=None, help="Comma-separated task ids, for iterating.")
    args = parser.parse_args(argv)
    args.out = args.out.resolve()

    if args.cleanup:
        cleanup(args.repo, args.out)
        return 0
    if args.workers > 1:
        return run_workers(args, sys.argv[1:] if argv is None else argv)

    spec = json.loads(args.tasks.read_text(encoding="utf-8"))
    tasks = {t["id"]: t for t in spec["tasks"]}
    ids = args.only.split(",") if args.only else PILOT if args.pilot else list(tasks)
    reps = args.reps or (PILOT_REPS if args.pilot else FULL_REPS)
    python = args.python or repo_interpreter(args.repo)

    arm_names = args.arms.split(",")
    setup(
        args.repo,
        args.out,
        spec["repo_commit"],
        {ARMS[a]["tree"] for a in arm_names},
        python,
    )
    (args.out / "no-mcp.json").write_text('{"mcpServers": {}}', encoding="utf-8")
    log = args.out / "runs.jsonl"
    # A worker also reads the main log: runs done there are skipped and inform estimates,
    # but only its own new runs count against its share of the budget.
    prior = read_rows(args.prior_log) if args.prior_log else []
    prior_keys = {run_key(row) for row in prior}
    logged = prior + [row for row in read_rows(log) if run_key(row) not in prior_keys]
    done = {run_key(row) for row in logged}

    order = schedule(ids, reps, args.seed, arm_names)
    if args.shard:
        index, count = map(int, args.shard.split("/"))
        order = shard(order, index, count)
    print(f"{len(order)} runs, {len(done)} already done.", flush=True)
    pair = None
    for position, (task_id, rep, arm) in enumerate(order, start=1):
        if (task_id, rep, arm) in done:
            continue
        task = tasks[task_id]
        if args.budget_usd is not None and (task_id, rep) != pair:
            # Check once per pair, before its first run, so a pair is never left half done.
            pair = (task_id, rep)
            todo = [a for t, r, a in order if (t, r) == pair and (t, r, a) not in done]
            spent = sum(row["cost_usd"] or 0 for row in logged if run_key(row) not in prior_keys)
            needed = sum(run_estimate(logged, a, task["kind"]) for a in todo)
            if spent + needed > args.budget_usd:
                print(
                    f"Stopped before run {position}: ${spent:.2f} spent, the next pair could "
                    f"take ${needed:.2f} more, budget ${args.budget_usd:.2f}. Rerun to resume.",
                    flush=True,
                )
                return 3
        path = worktree(args.out, ARMS[arm]["tree"])
        reset(path)
        env = {**os.environ, "PYTHONPATH": str(path / "src")}
        change = task["kind"] == "change"
        prompt = f"{task['prompt']}\n\n{spec['suffix_change' if change else 'suffix_question']}"
        if args.dry_run:
            result = {"result": "", "session_id": None, "dry_run": True}
        else:
            result = run_agent(
                prompt,
                path,
                CHANGE_TOOLS if change else QUESTION_TOOLS,
                args,
                env,
                ARMS[arm],
                task["kind"],
            )
        if result.get("is_error") and LIMIT_ERROR.search(result.get("result") or ""):
            # Not the agent's answer: the account hit a usage limit. Recording it would
            # count an infrastructure stop as a wrong answer, so stop and resume later.
            reset(path)
            print(f"Stopped at run {position}: {result.get('result')}", flush=True)
            return 2
        if change:
            grade = grade_change(task, path, python, env)
        else:
            grade = grade_question(task, result.get("result", ""))
        touched = git(["status", "--porcelain"], path).splitlines()
        limited = turn_limited(result, args.max_turns)
        if limited:
            # DESIGN.md: a run that hits the turn limit is wrong, whatever it left behind.
            grade = {"score": 0.0, "grade": "wrong", "as_if_finished": grade["grade"]}
        row = {
            "task": task_id,
            "kind": task["kind"],
            "rep": rep,
            "arm": arm,
            "order": position,
            "model": ARMS[arm].get("models", {}).get(task["kind"]) or args.model,
            "models_used": sorted(result.get("modelUsage") or {}),
            "commit": spec["repo_commit"],
            "grade": grade["grade"],
            "score": grade["score"],
            "files_touched": len(touched),
            "cost_usd": result.get("total_cost_usd"),
            "num_turns": result.get("num_turns"),
            "usage": result.get("usage"),
            "is_error": result.get("is_error"),
            "turn_limited": limited,
            "as_if_finished": grade.get("as_if_finished"),
            "wall_seconds": result.get("wall_seconds"),
            "session_id": result.get("session_id"),
            "answer": result.get("result", ""),
            **transcript_metrics(result.get("session_id")),
        }
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
        logged.append(row)
        done.add((task_id, rep, arm))
        print(
            f"[{position}/{len(order)}] {task_id} rep {rep} arm {arm}: {grade['grade']}, "
            f"${row['cost_usd'] or 0:.3f}, {row.get('tool_calls', '-')} tools",
            flush=True,
        )
        reset(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
