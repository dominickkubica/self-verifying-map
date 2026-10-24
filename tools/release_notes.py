"""Print one version's section of CHANGELOG.md: the notes for its GitHub release.

    python tools/release_notes.py 0.1.0 > notes.md

Fails if the changelog has no section for the version, so a release cannot go out with
empty notes.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"


def notes(changelog: str, version: str) -> str | None:
    """The body under `## [version]`, up to the next `## ` heading or link references."""
    match = re.search(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## |^\[[^\]]+\]: |\Z)",
        changelog,
        re.M | re.S,
    )
    return match.group(1).strip() + "\n" if match and match.group(1).strip() else None


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    version = args[0].removeprefix("v")
    body = notes(CHANGELOG.read_text(encoding="utf-8"), version)
    if body is None:
        print(f"CHANGELOG.md has no notes for {version}", file=sys.stderr)
        return 1
    print(body, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
