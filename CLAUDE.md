# Project: Lean agents (self-verifying-map)

A toolkit for cutting AI coding-agent token costs, with a benchmark behind every claim.
Public at github.com/dominickkubica/self-verifying-map. Owner: Dominick. MIT.

## Rules
- Every number in the README or docs comes from a run in `benchmark/results/` or from a
  script in the kit (`lean-agents carry-cost`, `lean-agents stats`). No estimates presented
  as measurements; small samples say so.
- Documents describe the present only: no "v1/v2", no change history. History goes in
  commit messages.
- Edit with small targeted edits; search, then read line ranges; run only relevant tests.
- Commit and push only when asked. End commit messages with the attribution line.
- Benchmark runs cost real usage: one repetition while iterating, more only to confirm.

## Layout
- `src/lean_agent_kit/`: the installable package (`pyproject.toml`, name `lean-agent-kit`,
  command `lean-agents`). `carry_cost.py` (what costs tokens in a user's transcripts,
  weighted by re-reads), `transcript_stats.py` (per-request metrics), `slim_claude_md.py`
  (split an instruction file), `map_prefetch.py` (the prompt hook), `cli.py`, and
  `repomap/` (the self-verifying map: `core.py`, generic `extractors.py`, `config.py` for
  `map/config.json`, `cli.py` for `lean-agents map`). Standard library only, Python 3.10+.
- `tools/`: `build_doc.py` (Markdown to PDF via headless Edge).
- `lean/`: flags, `settings.json` and the short system prompt for lean agents.
- `benchmark/`: `run.py` (arms, worktrees, grading), `analyze.py`, `tasks.json`,
  `hidden_tests/`, `results/` (raw runs), `DESIGN.md`,
  `OPTIMIZATION.md`.
- `tests/fixtures/maprepo/`: a small repo with a map that passes `lean-agents map check`.
- `examples/optscan/`: the options-scanner repo's map plugin and its map tests
  (`C:\Users\kubic\options-scanner`); they import that app and run only there.
  `examples/generated/`, `MAP.md`, `notes.md`: that map's output.
- `docs/`: `findings.md` (the write-up), `design.md` (the map's design doc), `measuring.md`
  (using `lean-agents stats`).

## Read when relevant
- `docs/production-brief.md`: what "production-worthy" means for this repo, and the work
  list to get there.
