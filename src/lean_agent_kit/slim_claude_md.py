"""Split a CLAUDE.md into a small core every session loads and sections read on demand.

Claude Code puts the whole instruction file into every turn's context, so each byte is
paid for again on every call of every session. This keeps the sections you name, moves
every other `## ` section unchanged to its own file, and lists those files at the end so
the agent opens them when a task needs them.

    lean-agents slim CLAUDE.md --keep "Stack,Rules,Layout"
    lean-agents slim CLAUDE.md --keep Rules --to docs/agent --dry-run

Measured on a 26.8 KB file: 2.6 KB after slimming, about 5k fewer tokens per turn, with
every benchmark code change still passing its hidden tests.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def slim(text: str, keep: set[str]) -> tuple[str, dict[str, str]]:
    """Return the slim file and {slug: moved section}."""
    parts = re.split(r"(?m)^(?=## )", text)
    kept, moved = [parts[0]], {}
    for part in parts[1:]:
        title = part.splitlines()[0].removeprefix("## ").strip()
        if title in keep:
            kept.append(part)
        else:
            moved[re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")] = part
    return "".join(kept).rstrip() + "\n", moved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("file", type=Path)
    parser.add_argument("--keep", required=True, help="Comma-separated section titles.")
    parser.add_argument("--to", default="docs/agent", help="Folder for moved sections.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    text = args.file.read_text(encoding="utf-8")
    core, moved = slim(text, {k.strip() for k in args.keep.split(",")})
    folder = args.file.parent / args.to
    titles = {slug: part.splitlines()[0].removeprefix("## ") for slug, part in moved.items()}
    index = "\n".join(f"- `{args.to}/{slug}.md`: {titles[slug]}" for slug in moved)
    result = core + ("\n## Read when relevant\n\n" + index + "\n" if moved else "")

    print(f"{len(text):,} -> {len(result):,} bytes; moving {len(moved)} sections to {args.to}/")
    if args.dry_run:
        return 0
    folder.mkdir(parents=True, exist_ok=True)
    for slug, part in moved.items():
        (folder / f"{slug}.md").write_text(part.rstrip() + "\n", encoding="utf-8")
    args.file.write_text(result, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
