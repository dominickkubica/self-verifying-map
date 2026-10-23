"""Run the map benchmark: fixed tasks, two arms, repeated, interleaved, graded blind.

    python benchmark/run.py --repo C:/path/to/options-scanner --out bench-out --pilot
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
sys.path.insert(0, str(HERE.parent / "measure"))

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
}

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


def setup(repo: Path, out: Path, commit: str, trees: set[str]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for tree in sorted(trees):
        path = worktree(out, tree)
        if path.exists():
            continue
        git(["worktree", "add", "--detach", str(path), commit], repo)
        if tree == "slim":
            slim_instructions(path)
            commit_tree(path, "benchmark tree: slim instructions")
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
    for path in sorted(out.glob("wt-*")):
        git(["worktree", "remove", "--force", str(path)], repo)


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
    parser.add_argument("--python", default=None, help="Interpreter with the repo's deps.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--arms", default="A,B", help="Comma-separated, from ARMS.")
    args = parser.parse_args(argv)
    args.out = args.out.resolve()

    if args.cleanup:
        cleanup(args.repo, args.out)
        return 0

    spec = json.loads(args.tasks.read_text(encoding="utf-8"))
    tasks = {t["id"]: t for t in spec["tasks"]}
    ids = PILOT if args.pilot else list(tasks)
    reps = args.reps or (PILOT_REPS if args.pilot else FULL_REPS)
    python = args.python or str(args.repo / "venv" / "Scripts" / "python.exe")

    arm_names = args.arms.split(",")
    setup(args.repo, args.out, spec["repo_commit"], {ARMS[a]["tree"] for a in arm_names})
    (args.out / "no-mcp.json").write_text('{"mcpServers": {}}', encoding="utf-8")
    log = args.out / "runs.jsonl"
    done = set()
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            done.add((row["task"], row["rep"], row["arm"]))

    order = schedule(ids, reps, args.seed, arm_names)
    print(f"{len(order)} runs, {len(done)} already done.", flush=True)
    for position, (task_id, rep, arm) in enumerate(order, start=1):
        if (task_id, rep, arm) in done:
            continue
        task = tasks[task_id]
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
        if change:
            grade = grade_change(task, path, python, env)
            touched = git(["status", "--porcelain"], path).splitlines()
        else:
            grade = grade_question(task, result.get("result", ""))
            touched = git(["status", "--porcelain"], path).splitlines()
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
            "wall_seconds": result.get("wall_seconds"),
            "session_id": result.get("session_id"),
            "answer": result.get("result", ""),
            **transcript_metrics(result.get("session_id")),
        }
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")
        print(
            f"[{position}/{len(order)}] {task_id} rep {rep} arm {arm}: {grade['grade']}, "
            f"${row['cost_usd'] or 0:.3f}, {row.get('tool_calls', '-')} tools",
            flush=True,
        )
        reset(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
