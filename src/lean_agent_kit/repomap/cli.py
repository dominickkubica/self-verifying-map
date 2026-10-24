"""`lean-agents map`: generate the map, check it against the code, stamp notes.

    lean-agents map generate          # write map/generated/ from the code
    lean-agents map check             # fail if the map or its notes disagree with the code
    lean-agents map stamp KEY [KEY]   # re-pin notes after re-reading them (or --all)

Configured by `map/config.json` (see `lean_agent_kit.repomap.config`). Run `check` in CI
or a pre-commit hook: that is what keeps the map from drifting.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import core
from .config import MapConfig


def check(config: MapConfig) -> list[str]:
    """Every reason the map cannot be trusted right now, one line each."""
    repo_map = core.generate(config.extractors())
    failures = []
    stale = core.stale_files(repo_map, config.generated)
    if stale:
        failures.append(f"map/generated is out of date: {', '.join(stale)} (run `lean-agents map generate`)")
    for heading, lines in repo_map.gaps.items():
        failures.append(f"{heading}: {len(lines)} over budget: " + "; ".join(lines))
    notes = core.load_notes(config.notes.read_text(encoding="utf-8")) if config.notes.exists() else []
    advice = {
        "missing": "items with no note in map/notes.md",
        "dead": "notes for items that no longer exist",
        "stale": "notes whose wiring changed (re-read, then `lean-agents map stamp <key>`)",
        "unpinned": "notes with neither `fact:` nor `test:`",
    }
    for check_name, keys in core.problems(repo_map, notes, config.required_notes).items():
        if keys:
            failures.append(f"{advice[check_name]}: {', '.join(keys)}")
    broken = core.broken_traps(notes, config.root)
    if broken:
        failures.append(f"traps pointing at tests that do not exist: {', '.join(broken)}")
    if config.index.exists():
        index = config.index.read_text(encoding="utf-8")
        unlisted = [name for name in repo_map.files if f"map/generated/{name}" not in index]
        if unlisted:
            failures.append(f"MAP.md does not point at: {', '.join(unlisted)}")
    for name, budget in config.budgets.items():
        path = config.root / name
        if path.exists() and path.stat().st_size > budget:
            failures.append(f"{name} is {path.stat().st_size} bytes, budget {budget}")
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("generate", help="write map/generated/ from the code")
    commands.add_parser("check", help="fail if the map or its notes disagree with the code")
    stamp = commands.add_parser("stamp", help="re-pin notes to their items' current facts")
    stamp.add_argument("keys", nargs="*")
    stamp.add_argument("--all", action="store_true", help="every note")
    args = parser.parse_args(argv)
    config = MapConfig.load(args.root.resolve())

    if args.command == "generate":
        changed = core.write(core.generate(config.extractors()), config.generated)
        print("\n".join(f"wrote map/generated/{name}" for name in changed) or "map is current")
        return 0
    if args.command == "check":
        failures = check(config)
        print("\n".join(f"FAIL {line}" for line in failures) or "map is current")
        return 1 if failures else 0
    if not (args.keys or args.all):
        parser.error("stamp needs note keys or --all")
    repo_map = core.generate(config.extractors())
    text, stamped = core.stamp(config.notes.read_text(encoding="utf-8"), args.keys, repo_map, every=args.all)
    config.notes.write_text(text, encoding="utf-8", newline="\n")
    print("\n".join(f"stamped {key}" for key in stamped) or "nothing to stamp")
    return 0
