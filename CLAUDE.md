# Project: Lean agents (self-verifying-map)

A toolkit for cutting AI coding-agent token costs, with a benchmark behind every claim.
Public at github.com/dominickkubica/self-verifying-map. Owner: Dominick. MIT.

## Rules
- Every number in the README or docs comes from a run in `benchmark/results/` or from a
  script in `measure/`. No estimates presented as measurements; small samples say so.
- Documents describe the present only: no "v1/v2", no change history. History goes in
  commit messages.
- Edit with small targeted edits; search, then read line ranges; run only relevant tests.
- Commit and push only when asked. End commit messages with the attribution line.
- Benchmark runs cost real usage: one repetition while iterating, more only to confirm.

## Layout
- `measure/`: `carry_cost.py` (what costs tokens in a user's transcripts, weighted by
  re-reads), `transcript_stats.py` (per-request metrics). Standard library only.
- `tools/`: `slim_claude_md.py` (split an instruction file), `build_doc.py` (Markdown to PDF
  via headless Edge).
- `lean/`: flags, `settings.json` and the short system prompt for lean agents.
- `benchmark/`: `run.py` (arms, worktrees, grading), `analyze.py`, `tasks.json`,
  `hidden_tests/`, `hooks/map_prefetch.py`, `results/` (raw runs), `DESIGN.md`,
  `OPTIMIZATION.md`.
- `src/repomap.py`, `tests/`: the self-verifying map, copied from the options-scanner repo
  (`C:\Users\kubic\options-scanner`), where it runs; it imports that app's modules and does
  not run standalone here.
- `docs/`: `findings.md` (the write-up), `design.md` (the map's design doc).

## Read when relevant
- `docs/production-brief.md`: what "production-worthy" means for this repo, and the work
  list to get there.
