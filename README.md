# Lean agents: cut Claude Code costs ~90% without losing accuracy

[![CI](https://github.com/dominickkubica/self-verifying-map/actions/workflows/ci.yml/badge.svg)](https://github.com/dominickkubica/self-verifying-map/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)

Measured on a real 124-module Python and React codebase: the same questions and code
changes, answered correctly and passing the same hidden tests, at about a tenth of the
cost of the default agent.

| Task | Default agent | Lean setup (two runs) | Saving |
|---|---|---|---|
| Wiring and control questions | $0.27 to $0.35 | $0.01 to $0.03 | 92 to 95% |
| Code change: new CLI option | $1.80 | $0.21, $0.31 | 83 to 88% |
| Code change: new API parameter | $2.66 | $0.19, $0.23 | 91 to 93% |
| Code change: new scheduled job | $3.57 | $0.43, $0.30 | 88 to 91% |
| Code change: CLI output | $2.05 | $0.09, $0.08 | 96% |

Sample sizes are small: one default run per code change and two lean runs per task. Two of
the four default code changes stopped at the 40-turn limit, so their cost is a floor.
Every run is in `benchmark/results/`; `docs/results.md` lists each one with its sample
size, and `docs/benchmark.md` explains how the benchmark works.

## Quick start

1. **Install** (Python 3.10+, no dependencies):

   ```
   pip install git+https://github.com/dominickkubica/self-verifying-map
   ```

2. **See where your tokens go.** `lean-agents carry-cost` reads your local Claude Code
   transcripts (`~/.claude/projects/`; `--project <folder>` for one project) and ranks
   every source of context by **carried** tokens: its size times the number of later API
   calls that re-read it. It prints numbers and tool names, never message content.

   ```
   lean-agents carry-cost --top 15
   ```

   Read the top rows. `agent: tool inputs` high means whole-file writes and long scripts:
   prefer small edits. `Read`, `Bash: cat` or `Bash: sed` high means whole files read into
   context: search, then read line ranges. An `attachment:` row is something injected every
   turn (a listing, a reminder, a snapshot): turn off what you do not use.
   `person / injected user content` is your prompts plus text injected into your turns.

3. **Apply the lean settings** (`lean/README.md` has the measurements):
   - slim the instruction file into a core and sections read on demand:
     `lean-agents slim CLAUDE.md --keep "Rules,Layout" --dry-run`, then without
     `--dry-run`;
   - for headless agents, the flags and short system prompt in `lean/README.md`;
   - turn off connectors and plugins a project does not use;
   - with a generated map (below), add the prefetch hook from `lean/settings.json`.

4. **Measure again.** `lean-agents stats --split <time you changed things>` compares
   requests before and after: tokens, tool calls, searches and re-reads.

## Why agents are expensive

An agent re-reads its whole context on every turn: system prompt, every tool definition,
the project's instruction file, and everything it has read or written so far. In 14
long development sessions on this codebase, **98% of 2.5 billion tokens were re-reads**,
and each token that entered context was re-read about 220 times. The fixed part alone was
47,000 tokens per turn before the agent did any work.

## The toolkit

| Tool | What it does | Effect measured here |
|---|---|---|
| `lean-agents carry-cost` | Ranks what costs you tokens in your own Claude Code transcripts: each tool, injected content, your agent's own writes, weighted by how many later calls re-read it | Found that the agent's own whole-file writes were 32% of all carried tokens |
| `lean-agents stats` | Per-request tokens, tool calls, searches and re-reads, with a before/after split | |
| `lean-agents slim` | Splits `CLAUDE.md` into a small core and sections read on demand | 26.8 KB to 2.6 KB per turn |
| `lean/` | Flags, settings and a short system prompt for lean headless and interactive agents | 47k to 4.5k tokens of context per turn |
| `lean-agents prefetch` | A prompt hook that injects verified facts about whatever the prompt names | 5 of 7 questions answered with no tool calls, at half the cost |
| `lean-agents map` | A self-verifying map of a codebase's wiring: facts generated from the code, notes pinned to them, checked on every commit | What makes the prefetch safe: injected facts cannot be stale |
| `benchmark/` | Fixed tasks, isolated worktrees, interleaved configurations, frozen answers and hidden tests | Every number above |

## The levers, in order of effect

1. **Context per turn.** Define only the tools a task needs, drop the skills listing and
   dynamic prompt sections, slim the instruction file, and use a short system prompt for
   headless agents: 47k to 4.5k tokens on every turn.
2. **Model and effort per task.** Sonnet at low effort passed every code change in the
   benchmark and answered every question but one. Haiku was cheapest when it went straight to the
   answer but wandered on some questions (45 tool calls on one), so it is not recommended.
3. **Turns.** A verified map turns searches into a lookup, and the prefetch hook removes
   the lookup when the prompt names what it is asking about.
4. **What stays in context.** Small edits instead of rewrites, search before reading,
   page text before screenshots, targeted tests with short tracebacks, and a fresh
   session per topic.

Details and measurements: `benchmark/OPTIMIZATION.md`. A write-up of the findings:
`docs/findings.md`. Every run: `docs/results.md`.

## The self-verifying map

The map is generated from the code (modules, tables with the code that writes and reads
them, routes and what they reach, caches, views, jobs, commands) and checked on every
commit, so it cannot drift. People write only what code cannot say, such as why a table
exists or which lookups have caused bugs, and each note is pinned to a hash of the facts
it describes, so it is flagged the moment its wiring changes. Design: `docs/design.md`.

`lean-agents map generate` builds the map from `map/config.json`, and `lean-agents map check`
fails when it disagrees with the code. Run `check` in CI or a pre-commit hook. The built-in
extractors read source without importing it:

- modules and their docstrings;
- tables, with the code whose SQL writes and reads them;
- HTTP routes from decorators or an OpenAPI file.

Anything stack-specific is a plugin. `examples/optscan/extractors.py` is the one this map was
built with (FastAPI routers, SQLite migrations, a React API client, a job schedule). The
config format is documented in `src/lean_agent_kit/repomap/config.py`, and
`tests/fixtures/maprepo/` is a small working example.

## Roadmap

- The full benchmark (20 tasks, 5 repetitions) on the lean setup against the default.
- A multi-agent benchmark: shared stable prefixes, least tools per role, model per role.

## Contributing

See `CONTRIBUTING.md`.

## License

MIT
