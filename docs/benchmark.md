# How the benchmark works

The benchmark asks one question: does a setup make a coding agent cheaper without making it
worse? It runs fixed tasks against one codebase at one commit, under two or more setups
("arms"), and records cost, effort and correctness for every run. The design, including the
hypotheses and pass criteria, is fixed in `benchmark/DESIGN.md` before the full run; the
results so far are in `docs/results.md`.

## The codebase and the tasks

Every run works on [options-scanner](https://github.com/dominickkubica/options-scanner) at
commit `90fe543`: 124 Python and React modules, with a self-verifying map. The tasks in
`benchmark/tasks.json` are of four kinds:

- **wiring questions** ("which modules write to `opportunity_log`?"), which the map should
  help with;
- **trap questions**, where the map's notes should prevent a known mistake;
- **control questions**, which the map should not help with, so a saving there means
  something other than the map is at work;
- **code changes** ("add a `--limit N` option to `optscan forward-test`").

## One run

1. `run.py` makes a git worktree per arm at the benchmark commit and prepares it once: arm
   A has the map removed, the lean arms have the slimmed instruction file, arm P has the
   prefetch hook installed. Each worktree's `venv` links to the benchmark's interpreter's
   environment (a junction on Windows), so the repo's `venv\Scripts\python` works there.
   Every run starts from that worktree reset to its commit.
2. It starts a fresh, non-interactive Claude Code session (`claude -p`) in the worktree,
   with the arm's model, tools, system prompt and effort, and a limit of 40 turns. The
   prompt goes in on stdin.
3. It records Claude Code's JSON result (dollar cost, token usage, turns, the answer) and
   reads the session's transcript with `transcript_stats` for tool calls, searches, reads
   and re-reads.
4. It grades the run:
   - a question passes if the answer names every required item (`required` in
     `tasks.json`, with accepted alternatives), is partial if it names some, and is wrong
     otherwise. The required items were frozen from the code by a script;
   - a code change passes if a hidden test passes on the worktree it left. The tests are
     in `benchmark/hidden_tests/` and enter the worktree only after the agent has finished.
5. It appends one line to `runs.jsonl`, so an interrupted benchmark resumes where it
   stopped. A session that ends on the account's usage limit stops the benchmark instead
   of being recorded.

Arms are interleaved: every arm of a (task, repetition) pair runs back to back, in an
order shuffled by a fixed seed, so the provider's prompt cache favours no arm.

Two differences from `DESIGN.md` to know about. The runner grades a code change on the
hidden test alone, without the map check DESIGN.md also lists. And it grades a run that
hit the turn limit on what it left, where DESIGN.md counts it as wrong; `docs/results.md`
marks every such run.

## Reading the results

`benchmark/analyze.py` summarises a `runs.jsonl`: per arm and kind, accuracy, median cost,
turns and tool calls; then, per task, each metric's median over repetitions as a ratio to a
base arm, and the median ratio across tasks with a 95% bootstrap interval that resamples
tasks. Accuracy is a guard: a cheaper setup counts only if it is as accurate.

```
python benchmark/analyze.py benchmark/results/optimizer-round1.jsonl --base B
```

## Running it yourself

It costs real usage: a default-agent code change has cost $1.80 to $3.57 per run so far,
and the full design is 200 runs. Run the pilot first.

1. Clone options-scanner, check out `90fe543`, and create its virtual environment with
   its dependencies (`venv` or `.venv`; or pass `--python`).
2. Install and sign in to Claude Code (`claude`).
3. From this repository:

```
python benchmark/run.py --repo ../options-scanner --out bench-out --pilot --dry-run
python benchmark/run.py --repo ../options-scanner --out bench-out --pilot
python benchmark/analyze.py bench-out/runs.jsonl
python benchmark/run.py --repo ../options-scanner --out bench-out --cleanup
```

`--dry-run` checks the plumbing without starting an agent. `--arms` picks setups (see
`ARMS` in `run.py`), `--only` picks tasks, and `--reps` sets repetitions.

The runner has been used on Windows only. It needs nothing Windows-specific, but no run on
Linux or macOS has been made yet.

## What the rounds so far were

The rounds in `docs/results.md` after the pilot were exploratory: one or two runs per
task, to find which levers matter before spending on the full design. They choose what
goes into the pre-registered run; they do not replace it.
