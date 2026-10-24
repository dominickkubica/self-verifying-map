# Production brief: making the toolkit installable and trustworthy

## Goal

Someone who finds the repository can install it in one command, run one command to see
where their own agent tokens go, apply the savings to their own setup, and verify the
claims. It reads as a maintained open-source project, not a personal experiment.

## What exists

| Piece | State |
|---|---|
| `measure/carry_cost.py`, `measure/transcript_stats.py` | Work on any Claude Code transcripts; standard library only; no tests |
| `tools/slim_claude_md.py` | Works on any `CLAUDE.md`; no tests |
| `lean/` | Measured flags and settings; documentation only |
| `benchmark/hooks/map_prefetch.py` | Works on any repo with a `map/generated/` folder in the map's format |
| `src/repomap.py` | The map generator; imports the options-scanner app (FastAPI routers, SQLite migrations, schedule, CLI), so it only runs inside that repo |
| `benchmark/` | Runs against options-scanner at a fixed commit; Windows-tested only |
| Results | Pilot-sized: 1 to 2 runs per task per setup; every raw run is published |

## Work list, in order

1. **Package.** `pyproject.toml` with a package name (check PyPI availability first; the
   repo name may change, and that is the owner's call). Console scripts:
   `lean-agents carry-cost`, `lean-agents stats`, `lean-agents slim`, `lean-agents
   prefetch` (the hook). Python 3.10+. No runtime dependencies.
2. **Decouple the map generator.** Split `src/repomap.py` into a core (item model, fact
   hashes, notes parsing, stamping, checks, Markdown writer) and extractors behind a small
   interface (`Extractor.items() -> list[Item]`). Ship generic extractors that need no app
   import: modules (AST docstrings), SQL table writers and readers (string-literal scan
   against a table list or a schema file), and a JSON/YAML-configurable route list. Keep the
   options-scanner extractors as an example plugin.
3. **Tests and CI for the toolkit itself.** Unit tests with small fixture transcripts
   (synthetic, never real ones: real transcripts contain private content), fixture
   `CLAUDE.md` files, and a fixture repo for the map. GitHub Actions on Linux, macOS and
   Windows, Python 3.10 to 3.13. Ruff for lint and format.
4. **Cross-platform.** `build_doc.py` hard-codes Edge paths; make PDF building optional.
   `benchmark/run.py` assumes a Windows venv path; take the interpreter from a flag.
5. **Privacy.** `carry_cost.py` and `transcript_stats.py` must never print or write message
   content. Add a test that fails if any output contains text from a fixture message.
6. **Docs.** README quick start (install, run carry-cost, read the output, apply the lean
   settings), a results page with the tables and their sample sizes, `CONTRIBUTING.md`,
   `CHANGELOG.md`, issue templates, a short "how the benchmark works" page. Badges for CI,
   PyPI version and license once they exist.
7. **Release.** Semantic versioning starting at 0.1.0, a GitHub release with notes, PyPI
   publishing from CI on tags (trusted publishing, no tokens in the repo).
8. **Stronger evidence (costs usage, needs the owner's go-ahead).** The full benchmark: 20
   tasks, 5 repetitions, default agent against the lean setup with prefetch. Then a second
   repository.

## Constraints

- Every claim stays tied to published runs; keep the sample-size caveats.
- Never publish real transcripts, prompts or answers from the owner's sessions beyond the
  benchmark's own runs, which are already public.
- Ask before creating PyPI projects, renaming the repository, or anything else outward-facing.
