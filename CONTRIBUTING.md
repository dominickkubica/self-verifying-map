# Contributing

Issues and pull requests are welcome: bugs, extractors for more stacks, measurements from
your own setup, and corrections to any number.

## Set up

```
git clone https://github.com/dominickkubica/self-verifying-map
cd self-verifying-map
python -m pip install -e ".[dev]"
```

The package has no runtime dependencies and supports Python 3.10 to 3.13. `dev` adds
pytest and Ruff.

## Check your change

```
python -m pytest
ruff check .
ruff format --check .
```

CI runs the same on Linux, macOS and Windows with every supported Python, then runs the
installed `lean-agents` command on the fixture map.

## Rules

- **Numbers come from runs.** Every number in the README or docs comes from a run in
  `benchmark/results/` or from a command in the kit, and small samples say so. A changed
  number names its source.
- **No real transcripts.** Never commit a real Claude Code transcript, prompt or answer:
  they hold private content. Tests build synthetic ones with `tests/transcripts.py`.
- **The analyzers print no message content.** `tests/test_privacy.py` guards it; extend it
  when you add an option or an output.
- **Docs describe the present.** No "new in", no history; that goes in commit messages and
  `CHANGELOG.md`.
- **Standard library only** in `src/lean_agent_kit/`. An optional dependency (such as
  PyYAML for YAML specs) is imported where it is used, with a clear message when missing.

## Adding an extractor

An extractor turns part of a codebase into map items without importing it: subclass
`lean_agent_kit.repomap.Extractor`, set `name`, `title`, `intro` and `columns`, and return
`Item`s from `items()`. Put what it could not resolve in `gaps()`; `check` fails when there
are more than `gap_budget`. A generic extractor (one that works for any repository of its
kind) belongs in `src/lean_agent_kit/repomap/extractors.py` with a case in
`tests/test_repomap.py`. A stack-specific one can live in the user's repository as a
`plugin` in `map/config.json`; `examples/optscan/extractors.py` is one.

## Benchmark runs

They cost real usage. Iterate with one repetition and `--only` on a few tasks, and repeat
only to confirm. A new result goes in `benchmark/results/` as the raw `runs.jsonl` lines,
with `docs/results.md` updated from them.

## Sharing a measurement

The "Measurement" issue template asks for `lean-agents carry-cost` or `stats` output from
your own setup. That output has no message content, but check it before posting: project
folder names in a `stats` CSV can reveal paths.
