# Handoff: state of the work

Read this first in a new session; it replaces re-reading old conversations. Numbers come
from `benchmark/results/` (files named below); most cells are 1 to 4 runs, so treat them
as pilot results.

## Where things stand

- Production brief (`docs/production-brief.md`): items 1 to 7 are done and pushed, except
  the release itself: PyPI trusted publisher (`lean-agent-kit`, workflow `release.yml`,
  environment `pypi`) not yet set up by the owner, tag `v0.1.0` not pushed.
- Item 8 (benchmark): the owner chose to iterate lean against improved lean, and run a
  final lean' against default only when no more gains are found. That final run needs
  held-out tasks never used for tuning (`DESIGN-lean.md` is fixed for B against P).
- Raw runs: `lean-rep1-2026-10-24.jsonl` (B and P, all 20 tasks, repetition 1) and
  `lean-iterations-2026-10-24.jsonl` (everything after: B/P question pairs from
  repetitions 2 to 5, and arms Q, X1, X2, R2, R3). Arms are defined in `run.py` `ARMS`.

## Findings

| Comparison | Result | Runs |
|---|---|---|
| Lean P against default B, 20 tasks | P 19 of 20 correct for $0.96; B 16 of 20 for $15.01; P costs 0.04 to 0.08 of B per task kind. Two B misses hit the 40-turn limit | 40 |
| Questions, all repetitions | B 27 of 28 correct, median $0.273; P 26 of 28, median $0.012 | 56 |
| Q: P with a 5-minute cache | Questions 31% cheaper (median); code changes unchanged. Pays only when runs are under 5 minutes apart | 20 |
| X1, X2: explorer helper agents (Haiku) | Code changes cost +53% and +116%. Defining the `Agent` tool adds ~4k tokens per call, and the main agent kept searching anyway. Zero helpers is best at this task size | 8 |
| Fixed context of a lean code change | 10.2k tokens per call: Bash definition 4.2k, Grep 1.4k, Edit 0.6k, Glob 0.35k, slim CLAUDE.md and map rule 1.2k. Claude Code's default system prompt alone is 10.4k | measured with one-word replies |
| R3: Bash replaced by the kit's `run` tool | Per-call context 10.1k to 6.1k, but more turns (median 22 against 19); total $2.78 against $2.91, medians equal, all 32 correct. Not better: Bash stays | 32 |
| R2 | An earlier run tool that hung and was launched with a broken PYTHONPATH. Not comparable; ignore | 11 |

Not yet explained: the agent in the benchmark worktrees often hunts for `venv\Scripts\python`
(the instruction file names it, the worktree has none), sometimes with `find /`. This
costs turns in every arm.

## Next candidates

1. Give the worktrees the repository's venv (or tell the agent `python -m optscan` works),
   so no arm wastes turns finding an interpreter. Affects every arm equally; rerun P after.
2. Trim the remaining fixed context: the slim instruction file and map rule (1.2k).
3. Larger, multi-file change tasks, to see whether helpers pay off at bigger sizes, with
   hidden tests; they double as held-out tasks for the final run.
4. Fold the findings into `docs/results.md` and `lean/README.md` (both describe only the
   earlier rounds).

## Working on this repository lean

The findings apply to these sessions too. This session's own fixed context was about
74k tokens per call (37k built-in tools, 20k MCP tools, 10k system prompt, 6k skills,
from the app's usage panel), and it grew past 600k tokens, re-read on every call.

- One topic per session. When a session passes about 150k tokens or the topic changes,
  update this file and start a fresh session from it.
- Turn off connectors a session does not use (mail, documents, browsers): their tool
  definitions ride on every call.
- Benchmark runs: always `--budget-usd`, one repetition while iterating, and check the
  5-hour and weekly usage before a batch (`lean-agents carry-cost` for where tokens go).
- Small edits, search then read line ranges, run only the relevant tests, no polling of
  background runs (wait for the notification).
