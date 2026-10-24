"""The repository's scripts outside the package: PDF building and the benchmark runner."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if not (ROOT / "tools" / "build_doc.py").exists():  # an sdist ships the package only
    pytest.skip("repository scripts are not in this checkout", allow_module_level=True)
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "benchmark")]

import build_doc  # noqa: E402
import release_notes  # noqa: E402
import run  # noqa: E402


def test_markdown_to_html() -> None:
    markdown = (
        "# Title\n\nSome **bold** and `code <x>`.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
        "- one\n- two\n\n```\nprint(1 < 2)\n```\n"
    )
    page = build_doc.to_html(markdown, ROOT)
    assert "<h1>Title</h1>" in page
    assert "<strong>bold</strong>" in page and "<code>code &lt;x&gt;</code>" in page
    assert "<th>a</th>" in page and "<td>2</td>" in page
    assert "<ul><li>one</li><li>two</li></ul>" in page
    assert "<pre><code>print(1 &lt; 2)</code></pre>" in page


def test_html_only_needs_no_browser(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(build_doc, "REPO", tmp_path)
    (tmp_path / "doc.md").write_text("# Doc\n", encoding="utf-8")
    monkeypatch.setattr(build_doc, "find_browser", lambda: pytest.fail("looked for a browser"))
    assert build_doc.main(["doc.md", "--html"]) == 0
    assert "<h1>Doc</h1>" in (tmp_path / "dist" / "doc.html").read_text(encoding="utf-8")


def test_no_browser_is_a_clear_failure(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(build_doc, "REPO", tmp_path)
    (tmp_path / "doc.md").write_text("# Doc\n", encoding="utf-8")
    monkeypatch.setattr(build_doc, "find_browser", lambda: None)
    assert build_doc.main(["doc.md"]) == 1
    assert "Pass --browser, or --html" in capsys.readouterr().out


@pytest.mark.parametrize(
    "layout", ["venv/Scripts/python.exe", "venv/bin/python", ".venv/bin/python"]
)
def test_the_benchmark_finds_the_repo_interpreter_on_any_platform(tmp_path, layout) -> None:
    interpreter = tmp_path / layout
    interpreter.parent.mkdir(parents=True)
    interpreter.touch()
    assert run.repo_interpreter(tmp_path) == str(interpreter)


def test_the_benchmark_asks_for_an_interpreter_when_there_is_no_venv(tmp_path) -> None:
    with pytest.raises(SystemExit, match="pass --python"):
        run.repo_interpreter(tmp_path)


def test_release_notes_are_the_versions_section() -> None:
    changelog = (
        "# Changelog\n\n## [Unreleased]\n\n## [0.2.0] - 2026-11-01\n\n- Two.\n\n"
        "## [0.1.0] - 2026-10-24\n\n- One.\n\n[0.1.0]: https://example.com\n"
    )
    assert release_notes.notes(changelog, "0.2.0") == "- Two.\n"
    assert release_notes.notes(changelog, "0.1.0") == "- One.\n"
    assert release_notes.notes(changelog, "Unreleased") is None  # empty
    assert release_notes.notes(changelog, "0.3.0") is None


def test_the_changelog_has_notes_for_the_package_version(capsys) -> None:
    from lean_agent_kit import __version__

    assert release_notes.main([f"v{__version__}"]) == 0
    assert capsys.readouterr().out.strip()  # a tag for this version would have notes
