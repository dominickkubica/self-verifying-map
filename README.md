# Self-verifying project map

A map of a codebase's wiring that cannot drift from the code. The facts (what each module
does, which code writes and reads each table, what each API route reaches, which screen
calls which route, what runs on a schedule) are **generated from the code** and checked
against it on every commit. People write only what code cannot say about itself, such as
why a table exists or which lookups have caused bugs, and each of those notes is **pinned
to a hash of the facts it describes**, so it is flagged for review the moment its wiring
changes.

Built for a codebase developed mostly through an AI coding assistant, which starts every
session with no memory of the system. A map it can trust replaces re-deriving the wiring
from source each session, which costs time and tokens and is where wrong guesses become
bugs.

![How the map works](docs/map-overview.svg)

## How it works

| Part | What it does |
|---|---|
| Generator (`src/repomap.py`) | Reads each fact from its source of truth: the source tree, the database migrations, the SQL in string literals, the web framework's routers, the frontend's API client, the job scheduler and the CLI. Writes one Markdown file per section, sorted and deterministic. |
| Notes (`examples/notes.md`) | One note per table and scheduled job, plus traps. Each is pinned with `fact: <hash>` of its item's generated facts, or `test: <file>::<name>` for a trap guarded by a test. |
| Index (`examples/MAP.md`) | A short file read at the start of every session: the rules, a system diagram, and which file answers which question. Everything else is opened on demand. |
| Checks (`tests/test_map.py`) | Fail when a generated file differs from the code, a table or job has no note, a note names something that no longer exists, a note's wiring changed since it was last read, a hand-written file names a path that does not exist, or the hand-written files exceed their size budget. |
| Traps as tests (`tests/test_traps.py`) | Lookups that caused real bugs, written as assertions, for example "every call to the scorer states its IV-history input" and "a study refuses to run on a fraction of its symbols". |

The hash covers an item's **wiring, not its file**: a new writer or a dropped reader flags
the note, an unrelated edit to the same file does not. That keeps reviews rare enough that
nobody learns to re-stamp without reading.

## In use

On the project it was built for, a FastAPI + React options-trading research app:

- **Scope:** 124 modules, 22 tables, 32 routes, 21 dashboard files, 8 scheduled jobs,
  28 commands and 7 caches, generated into six files.
- **Size:** the index is 4.7 KB against a 6 KB budget. With wiring moved to the map and
  history to a decision log, what a session reads at start fell from 61 KB to 31 KB.
- **Every check proven to fail:** a dummy module, a rewired table, a renamed note key and
  a removed guarded argument each fail the suite, and pass again once restored.
- **Generation found what hand-writing missed:** on its first run it listed a module
  reading a table the hand-written map omitted, migration code writing two tables, and an
  API route that no screen calls.
- **Enforcement:** a pre-commit hook runs the map checks on every commit (including
  frontend-only commits), and CI runs them with the full suite (2,000+ tests) on push.

## What is in this repository

| Path | Contents |
|---|---|
| `src/repomap.py` | the generator, notes parser and stamping |
| `tests/` | the map checks and the trap tests |
| `examples/` | the index, a sample of the notes, and trimmed generated files |
| `examples/ci/` | the pre-commit and CI configuration |
| `docs/design.md` | the design document: goals, design, checks, measurement, alternatives, risks |

This is a case study: the code runs inside the project it was built for and imports that
project's settings, routers and scheduler. The extractors (`_modules`, `_storage`,
`_routes`, `_dashboard`, `_schedule`, `_commands`) are the stack-specific part; the
approach carries over to any codebase.

## Adopting the approach

1. List the questions readers arrive with and the source of truth that answers each.
2. Write an extractor per source of truth; keep the output deterministic.
3. Split the map into a short index, generated files read on demand, and pinned notes.
4. Test for drift, both directions, freshness, size and unresolved extraction.
5. Turn every trap that can be a test into one, and point its note at the test.
6. Prove each check fails before trusting it.
7. Run the checks on every commit and in CI.

## Roadmap

A reusable package with pluggable extractors, so the generator can be pointed at any
repository without editing it.

## License

MIT
