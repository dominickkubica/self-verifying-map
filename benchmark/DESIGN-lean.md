# Benchmark: the default agent against the lean setup

The same 20 tasks and grading as `DESIGN.md`, on the same commit, comparing the default
agent with the lean setup the exploratory rounds converged on (`docs/results.md`).
Everything below is fixed before the first run; a change after that is a new benchmark.

## Questions

- **H1 (cost).** The lean setup costs at least 50% less per task: median ratio, lean over
  default, with a 95% bootstrap interval over tasks below 0.5, for questions and for code
  changes separately.
- **H2 (accuracy guard).** The lean setup's correctness is no more than 5 percentage
  points below the default's on any task kind.

H1 counts only if H2 holds.

## Arms

| Arm | Setup |
|---|---|
| B: default | Claude Code's default harness and system prompt on the repository with its map, Opus; permitted tools Read, Grep, Glob, Bash (and Edit, Write for changes), every built-in tool defined, no MCP servers |
| P: lean | Sonnet at low effort, only the tools a task kind needs defined (Read, Grep, Glob; plus Edit, Bash for changes), the short system prompt, the slimmed instruction file, the prefetch hook, and a Stop hook that regenerates the map (`ARMS["P"]` in `run.py`) |

## Runs

- 20 tasks (`tasks.json`), 5 repetitions, 2 arms: 200 runs, interleaved in a seeded order,
  every run in a fresh session in its own reset worktree, at most 40 turns.
- Repetition 1 runs first and is reported before repetitions 2 to 5 run.
- Runs stop at a spending cap or a usage limit only between (task, repetition) pairs or
  before a run starts; a stopped run is not recorded, and the benchmark resumes where it
  stopped.

## Grading

- Questions: the answer names every required item (`tasks.json`).
- Code changes: the hidden test passes on the worktree the agent left.
- A run that ends at the turn limit is **wrong**, at its full cost, whatever it left behind.
  Whether its hidden test or answer would have passed is recorded alongside.

## Analysis

`python benchmark/analyze.py <runs.jsonl> --base B`, reported per task kind, with every
run published in `benchmark/results/`.
