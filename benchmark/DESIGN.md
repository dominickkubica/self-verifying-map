# Benchmark: what does the map save, and does it cost accuracy?

Fixed tasks, run repeatedly by a coding agent on the same commit of the same codebase,
with the map and without it. Everything below is fixed before the first run; a change
after that is a new benchmark with a new name.

## Questions

- **H1 (cost).** With the map, question tasks use at least 25% fewer weighted tokens
  (median ratio, map over no map, with a 95% bootstrap interval below 0.75).
- **H2 (effort).** With the map, fewer tool calls before the first edit on change tasks.
- **H3 (accuracy guard).** With the map, correctness does not fall by more than 5
  percentage points on any task type.

H1 and H2 count only if H3 holds. A cheaper wrong answer is not a saving.

## Arms

| Arm | Setup |
|---|---|
| A: no map | Worktree at the benchmark commit with `MAP.md`, `map/` and the map rule in `CLAUDE.md` removed |
| B: map | The same worktree, unchanged |

Both arms run in fresh git worktrees at one commit, so no arm sees another's edits. A
worktree path has its own project key, so neither arm loads the assistant's long-term
memory of the real repository. User-level settings are the same for both.

Later arms, each added as its own benchmark: capped tool output, a size budget on the
instruction file, fixed briefs for subagents, and shared-map swarms.

## Runner

Each run is one non-interactive session:

```
claude -p "<task>" --output-format json --model <fixed> --max-turns 40 \
  --allowedTools "Read,Grep,Glob,Bash(...),Edit" --permission-mode acceptEdits
```

- one fresh session per run; nothing carries over except the provider's prompt cache,
  which both arms share, so arms are **interleaved** (A, B, A, B ...) in a shuffled order
  fixed by a seed;
- change tasks reset the worktree (`git checkout -- . && git clean -fd`) before each run;
- the session's JSON result (usage, cost, turns) and its transcript are kept per run;
  `transcript_stats` (`lean-agents stats`) reads the transcripts for tool counts and orientation.

## Tasks (20)

Answers are frozen at the benchmark commit by a script, not written from memory.

**Wiring questions (10)**, the map's main use:

1. Which modules write to `opportunity_log`, and which read it?
2. What clears the `_OI_CHAINS` cache, and what is its TTL?
3. Which dashboard files call `/symbols/{symbol}/chain`?
4. At what market time does the `record` job run, and is it installed by default?
5. Which modules does the `ideas` command's handler import?
6. Which tables does migration code write besides creating them?
7. Which route is served but called by no dashboard file?
8. What reads `vendor_daily` outside `storage/`?
9. Which job writes `daily_condition`, and when?
10. Which router serves `/symbols/{symbol}/gex`, and which deps functions does it reach?

**Trap questions (3)**, where the notes should prevent a known mistake:

11. How should a study load a symbol's IV history?
12. What must every call to `analyze_snapshot` pass?
13. Why might `localhost:8000` show an old build?

**Change tasks (4)**, graded by hidden tests added after the run:

14. Add a `--limit N` option to `optscan forward-test`.
15. Add a `max_symbols` query parameter to `/api/gaps`.
16. Add a new scheduled job `report` at the market close, off by default, with its note.
17. Make `optscan position list` show each position's strategy.

**Control tasks (3)**, which the map should not help, to catch a general effect:

18. What does `bsm_price` return for degenerate inputs?
19. How does the screener's liquidity score treat a contract with no trades today?
20. What does `tickers.normalize_ticker` reject?

## Scoring

- **Correctness:** questions graded against the frozen answers by a rubric (each answer
  lists required items; all present = correct, some = partial, none = wrong), graded
  blind to arm. Change tasks graded by the hidden tests plus the map check.
- **Cost:** weighted tokens (fresh input 1, cache read 0.1, cache write 2, output 5),
  and the reported dollar cost.
- **Effort:** API calls, tool calls, searches, reads, calls before the first edit.

## Analysis

- Per task, the median over repetitions; then the ratio B/A per task.
- Across tasks, the median ratio with a 95% bootstrap interval, resampling tasks.
- Reported separately for wiring, trap, change and control tasks. A drop on control
  tasks as large as on wiring tasks means the effect is not the map.
- Every run kept; none excluded after the fact. A run that hits the turn limit counts as
  wrong and at full cost.

## Size and cost

5 repetitions × 20 tasks × 2 arms = 200 runs. A pilot first: 4 tasks (two wiring, one
change, one control) × 2 arms × 2 repetitions = 16 runs, to measure the cost per run and
check the runner, the grading and the transcript parsing end to end. The full run is
sized from the pilot's cost.

## Threats

| Threat | Handling |
|---|---|
| The map contains the answers to wiring questions | Intended: that is the map's job. Trap, change and control tasks show whether it helps beyond lookup |
| Run-to-run variation | 5 repetitions, medians, bootstrap intervals over tasks |
| Prompt cache favours whichever arm runs second | Interleaved, seeded order |
| Task choice favours the map | Tasks fixed here before any run, including 3 controls; the full list is published with the results |
| One codebase | Stated as a limit; a second repository is the next benchmark |
| Grader bias | Frozen answers, rubric, grading blind to arm |
