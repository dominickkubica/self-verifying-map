"""The wiring map has to match the code, both ways, and its notes have to be current.

`lean-agents map check` covers what every repository's map needs: the generated files
are what the code produces today, every table and job has a note, every note names
something that exists and is pinned to its item's current facts, every trap names a test
that exists, `MAP.md` points at every generated file, and the hand-written files stay in
their byte budgets (`map/config.json`). The tests below add what only this app can check.

What none of this can check is whether a note's prose is true. It can only make sure
someone looks at it again whenever the wiring under it changes.
"""

from __future__ import annotations

import re

from optscan.config import REPO_ROOT, Settings

from lean_agent_kit.repomap import generate
from lean_agent_kit.repomap.cli import check
from lean_agent_kit.repomap.config import MapConfig

CONFIG = MapConfig.load(REPO_ROOT)


def test_the_map_passes_its_checks() -> None:
    failures = check(CONFIG)
    assert not failures, "\n".join(failures)


def test_every_route_the_app_serves_is_generated(tmp_path) -> None:
    """The generator reads the routers; this reads the app, so a route mounted any other
    way cannot hide from the map."""
    from optscan.api.app import create_app

    app = create_app(Settings(_env_file=None, data_dir=tmp_path))
    served = {path.removeprefix("/api") for path in app.openapi()["paths"]}
    items = generate(CONFIG.extractors()).items
    generated = {key.removeprefix("route:") for key in items if key.startswith("route:")}
    assert served == generated


def _named_paths(text: str) -> set[str]:
    return set(re.findall(r"`([\w./-]+\.(?:py|md|jsx|js|ps1|yaml|toml))`", text))


def test_every_path_the_hand_written_files_name_exists() -> None:
    """The reverse direction for prose: a renamed or deleted file cannot linger."""
    roots = [REPO_ROOT, REPO_ROOT / "src" / "optscan", REPO_ROOT / "frontend" / "src"]
    text = CONFIG.index.read_text(encoding="utf-8") + CONFIG.notes.read_text(encoding="utf-8")
    missing = sorted(
        path for path in _named_paths(text) if not any((root / path).exists() for root in roots)
    )
    assert not missing, f"MAP.md or map/notes.md names files that do not exist: {missing}"


def test_the_map_says_how_to_keep_it_current() -> None:
    """The rule has to live in the file it governs, where the next editor will see it."""
    index = CONFIG.index.read_text(encoding="utf-8")
    assert "Keep it current" in index
    assert "optscan map generate" in index
    assert "tests/test_map.py" in index
