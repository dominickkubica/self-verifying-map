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


def git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def worktree(out: Path, arm: str) -> Path:
    return out / f"wt-{arm}"


def setup(repo: Path, out: Path, commit: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for arm in ("A", "B"):
        path = worktree(out, arm)
        if path.exists():
            continue
        git(["worktree", "add", "--detach", str(path), commit], repo)
        if arm == "A":
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
    for arm in ("A", "B"):
        path = worktree(out, arm)
        if path.exists():
            git(["worktree", "remove", "--force", str(path)], repo)


def schedule(task_ids: list[str], reps: int, seed: int) -> list[tuple[str, int, str]]:
    """(task, rep, arm) in a seeded order, with the two arms of each pair adjacent."""
    rng = random.Random(seed)
    pairs = [(t, r) for t in task_ids for r in range(reps)]
    rng.shuffle(pairs)
    order = []
    for task, rep in pairs:
        arms = ["A", "B"]
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


def run_agent(prompt: str, path: Path, tools: list[str], args, env: dict) -> dict:
    command = [
        args.claude,
        "-p",
        prompt,
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
    if args.model:
        command += ["--model", args.model]
    started = time.time()
    finished = subprocess.run(
        command,
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

    setup(args.repo, args.out, spec["repo_commit"])
    (args.out / "no-mcp.json").write_text('{"mcpServers": {}}', encoding="utf-8")
    log = args.out / "runs.jsonl"
    done = set()
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            done.add((row["task"], row["rep"], row["arm"]))

    order = schedule(ids, reps, args.seed)
    print(f"{len(order)} runs, {len(done)} already done.", flush=True)
    for position, (task_id, rep, arm) in enumerate(order, start=1):
        if (task_id, rep, arm) in done:
            continue
        task = tasks[task_id]
        path = worktree(args.out, arm)
        reset(path)
        env = {**os.environ, "PYTHONPATH": str(path / "src")}
        change = task["kind"] == "change"
        prompt = f"{task['prompt']}\n\n{spec['suffix_change' if change else 'suffix_question']}"
        if args.dry_run:
            result = {"result": "", "session_id": None, "dry_run": True}
        else:
            result = run_agent(prompt, path, CHANGE_TOOLS if change else QUESTION_TOOLS, args, env)
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
            "model": args.model,
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
