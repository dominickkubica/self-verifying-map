# Lean agents: cut Claude Code costs ~90% without losing accuracy

Measured on a real 124-module Python and React codebase: the same questions and code
changes, answered correctly and passing the same hidden tests, at about a tenth of the
cost of the default agent.

| Task | Default agent | Lean setup | Saving |
|---|---|---|---|
| Wiring questions | ~$0.31 | $0.01 to $0.04 | 90 to 96% |
| Code change: new API parameter | $2.66 | $0.19 | 93% |
| Code change: new scheduled job | $3.57 | $0.43 | 88% |
| Code change: CLI output | $2.05 | $0.09 | 96% |

Every run, every number and the pre-registered design are in `benchmark/`. Sample sizes are
small (one or two runs per task per setup so far); the results say so wherever they appear.

## Why agents are expensive

An agent re-reads its whole context on every turn: system prompt, every tool definition,
the project's instruction file, and everything it has read or written so far. In 14
long development sessions on this codebase, **98% of 2.5 billion tokens were re-reads**,
and each token that entered context was re-read about 220 times. The fixed part alone was
47,000 tokens per turn before the agent did any work.

## The toolkit

| Tool | What it does | Effect measured here |
|---|---|---|
| `measure/carry_cost.py` | Ranks what costs you tokens in your own Claude Code transcripts: each tool, injected content, your agent's own writes, weighted by how many later calls re-read it | Found that the agent's own whole-file writes were 32% of all carried tokens |
| `measure/transcript_stats.py` | Per-request tokens, tool calls, searches and re-reads, with a before/after split | |
| `tools/slim_claude_md.py` | Splits `CLAUDE.md` into a small core and sections read on demand | 26.8 KB to 2.6 KB per turn |
| `lean/` | Flags, settings and a short system prompt for lean headless and interactive agents | 47k to 4.5k tokens of context per turn |
| `benchmark/hooks/map_prefetch.py` | A prompt hook that injects verified facts about whatever the prompt names | 5 of 7 questions answered with no tool calls, at half the cost |
| `src/repomap.py` + `tests/test_map.py` | A self-verifying map of a codebase's wiring: facts generated from the code, notes pinned to them, checked on every commit | What makes the prefetch safe: injected facts cannot be stale |
| `benchmark/` | Fixed tasks, isolated worktrees, interleaved configurations, frozen answers and hidden tests | Every number above |

Start with `python measure/carry_cost.py`: it needs nothing but your local transcripts and
shows where your own tokens go.

## The levers, in order of effect

1. **Context per turn.** Define only the tools a task needs, drop the skills listing and
   dynamic prompt sections, slim the instruction file, and use a short system prompt for
   headless agents: 47k to 4.5k tokens on every turn.
2. **Model and effort per task.** Sonnet at low effort answered every question and passed
   every code change in the benchmark. Haiku was cheapest when it went straight to the
   answer but wandered on some questions (45 tool calls on one), so it is not recommended.
3. **Turns.** A verified map turns searches into a lookup, and the prefetch hook removes
   the lookup when the prompt names what it is asking about.
4. **What stays in context.** Small edits instead of rewrites, search before reading,
   page text before screenshots, targeted tests with short tracebacks, and a fresh
   session per topic.

Details and measurements: `benchmark/OPTIMIZATION.md`. A write-up of the findings:
`docs/findings.md`.

## The self-verifying map

The map is generated from the code (modules, tables with the code that writes and reads
them, routes and what they reach, caches, views, jobs, commands) and checked on every
commit, so it cannot drift. People write only what code cannot say, such as why a table
exists or which lookups have caused bugs, and each note is pinned to a hash of the facts
it describes, so it is flagged the moment its wiring changes. Design: `docs/design.md`.

The map's extractors (`src/repomap.py`) are specific to the stack they were built for
(FastAPI, SQLite migrations, a React API client); the approach and the tests carry over.

## Roadmap

- A pip-installable package with pluggable extractors for other stacks.
- The full benchmark (20 tasks, 5 repetitions) on the lean setup against the default.
- A multi-agent benchmark: shared stable prefixes, least tools per role, model per role.

## License

MIT
