from __future__ import annotations

import json
import shutil
import textwrap
from pathlib import Path

import pytest

from lean_agent_kit.repomap import core
from lean_agent_kit.repomap.cli import check, main
from lean_agent_kit.repomap.config import MapConfig
from lean_agent_kit.repomap.extractors import RoutesExtractor, SqlExtractor, tables_in_schema

MAPREPO = Path(__file__).parent / "fixtures" / "maprepo"


@pytest.fixture
def repo(tmp_path) -> Path:
    """A writable copy of the fixture repository."""
    target = tmp_path / "repo"
    shutil.copytree(MAPREPO, target)
    return target


def items(root: Path) -> dict[str, core.Item]:
    return core.generate(MapConfig.load(root).extractors()).items


def append(path: Path, text: str) -> None:
    path.write_text(path.read_text(encoding="utf-8") + textwrap.dedent(text), encoding="utf-8")


# ---- the committed fixture ----------------------------------------------------------


def test_the_fixture_map_is_current() -> None:
    assert check(MapConfig.load(MAPREPO)) == []


def test_tables_with_their_writers_and_readers() -> None:
    found = items(MAPREPO)
    assert found["table:orders"].facts == ["writers:", "storage/db.py", "readers:", "storage/db.py"]
    assert found["table:customers"].facts == ["writers:", "readers:", "storage/db.py"]
    assert found["table:audit"].facts == ["writers:", "readers:"]


def test_routes_from_decorators_with_prefixes_methods_and_reach() -> None:
    found = items(MAPREPO)
    assert found["route:/orders/{order_id}"].facts == [
        "GET",
        "api.py",
        "get_order",
        "storage/db.py: fetch_order",  # reached through the helper `_load`
    ]
    assert found["route:/orders/"].facts[:3] == ["POST", "api.py", "create_order"]  # async
    assert found["route:/health"].facts == ["GET", "HEAD", "web.py", "health"]


def test_routes_from_an_openapi_file() -> None:
    found = items(MAPREPO)
    assert found["route:/v1/orders"].facts == ["GET", "POST", "createOrder", "listOrders"]
    assert found["route:/v1/orders/{id}"].facts == ["GET", "getOrder"]


def test_modules_are_grouped_by_package() -> None:
    text = (MAPREPO / "map" / "generated" / "modules.md").read_text(encoding="utf-8")
    assert text.index("## (top level)") < text.index("## storage/")
    assert "| `storage/db.py` | Order storage. |" in text


# ---- drift: every way the map can fall behind the code ------------------------------


def test_a_new_reader_makes_the_map_and_its_note_stale(repo) -> None:
    append(
        repo / "src/shop/api.py",
        '\n\ndef count(conn):\n    return conn.execute("SELECT 1 FROM customers")\n',
    )
    failures = check(MapConfig.load(repo))
    assert any("out of date: storage.md" in f for f in failures)
    assert any("wiring changed" in f and "table:customers" in f for f in failures)

    assert main(["--root", str(repo), "generate"]) == 0
    assert [f for f in check(MapConfig.load(repo)) if "out of date" in f] == []
    assert main(["--root", str(repo), "stamp", "table:customers"]) == 0
    assert check(MapConfig.load(repo)) == []


def test_an_unrelated_edit_leaves_notes_alone(repo) -> None:
    append(repo / "src/shop/storage/db.py", "\n\nRETRIES = 3\n")
    assert check(MapConfig.load(repo)) == []


def test_a_new_module_appears_without_anyone_remembering_it(repo) -> None:
    (repo / "src/shop/mail.py").write_text('"""Order emails."""\n', encoding="utf-8")
    assert any("out of date: modules.md" in f for f in check(MapConfig.load(repo)))


def test_a_stray_generated_file_is_drift(repo) -> None:
    (repo / "map/generated/old.md").write_text("# gone\n", encoding="utf-8")
    assert any("old.md" in f for f in check(MapConfig.load(repo)))
    main(["--root", str(repo), "generate"])
    assert not (repo / "map/generated/old.md").exists()


def test_a_new_table_needs_a_note(repo) -> None:
    append(repo / "schema.sql", "CREATE TABLE refunds (id INTEGER);\n")
    main(["--root", str(repo), "generate"])
    assert check(MapConfig.load(repo)) == ["items with no note in map/notes.md: table:refunds"]


def test_a_note_for_a_dropped_item_is_dead(repo) -> None:
    schema = repo / "schema.sql"
    schema.write_text(
        schema.read_text(encoding="utf-8").replace('CREATE TABLE "audit"', "-- "), encoding="utf-8"
    )
    main(["--root", str(repo), "generate"])
    assert check(MapConfig.load(repo)) == ["notes for items that no longer exist: table:audit"]


def test_a_trap_whose_test_is_gone(repo) -> None:
    (repo / "tests/test_db.py").write_text("def test_other():\n    pass\n", encoding="utf-8")
    failures = check(MapConfig.load(repo))
    assert failures == [
        "traps pointing at tests that do not exist: "
        "trap:purge-takes-any-table -> tests/test_db.py::test_purge_is_never_called_with_user_input"
    ]


def test_unresolved_sql_over_budget_fails(repo) -> None:
    append(
        repo / "src/shop/storage/db.py",
        '\n\ndef wipe(conn, t):\n    conn.execute(f"UPDATE {t} SET x = 1")\n',
    )
    main(["--root", str(repo), "generate"])
    (failure,) = check(MapConfig.load(repo))
    assert failure.startswith("storage: SQL the scanner could not resolve")
    assert "UPDATE {?} SET x = 1" in failure


def test_index_and_budgets(repo) -> None:
    (repo / "MAP.md").write_text("Only `map/generated/storage.md` is listed.\n", encoding="utf-8")
    config = json.loads((repo / "map/config.json").read_text(encoding="utf-8"))
    config["budgets"] = {"map/notes.md": 10}
    (repo / "map/config.json").write_text(json.dumps(config), encoding="utf-8")
    failures = check(MapConfig.load(repo))
    assert failures[0].startswith("MAP.md does not point at: modules.md, public-api.md, routes.md")
    assert failures[1].startswith("map/notes.md is ") and failures[1].endswith("budget 10")


def test_cli_check_exit_codes(repo, capsys) -> None:
    assert main(["--root", str(repo), "check"]) == 0
    assert capsys.readouterr().out.strip() == "map is current"
    (repo / "tests/test_db.py").unlink()
    assert main(["--root", str(repo), "check"]) == 1
    assert capsys.readouterr().out.startswith("FAIL traps")


# ---- notes and stamping -------------------------------------------------------------


NOTES = """\
# Notes

### table:a
fact: 000000000000
About a.

### table:b
About b.

### trap:x
test: none
A trap nobody can test.
"""


def test_load_notes() -> None:
    a, b, trap = core.load_notes(NOTES)
    assert (a.key, a.fact, a.test, a.body) == (
        "table:a",
        "000000000000",
        None,
        "fact: 000000000000\nAbout a.",
    )
    assert (b.fact, b.test) == (None, None)
    assert (trap.key, trap.test) == ("trap:x", "none")


def test_stamp_rewrites_or_adds_the_hash() -> None:
    repo_map = core.RepoMap(files={}, items={k: core.Item(k, [k]) for k in ("table:a", "table:b")})
    text, stamped = core.stamp(NOTES, [], repo_map, every=True)
    assert stamped == ["table:a", "table:b"]
    assert f"### table:a\nfact: {core.fact_hash(['table:a'])}\nAbout a." in text
    assert f"### table:b\nfact: {core.fact_hash(['table:b'])}\nAbout b." in text
    assert core.stamp(text, ["table:a"], repo_map) == (text, [])  # already current


def test_problems() -> None:
    notes = core.load_notes(NOTES)
    repo_map = core.RepoMap(
        files={}, items={k: core.Item(k, ["f"]) for k in ("table:a", "table:c", "module:m.py")}
    )
    assert core.problems(repo_map, notes) == {
        "missing": ["table:c"],
        "dead": ["table:b"],
        "stale": ["table:a"],
        "unpinned": ["table:b"],
    }


def test_fact_hash_is_stable_and_order_sensitive() -> None:
    assert core.fact_hash(["a", "b"]) == core.fact_hash(["a", "b"])
    assert core.fact_hash(["a", "b"]) != core.fact_hash(["b", "a"])
    assert len(core.fact_hash([])) == 12


# ---- extractors in isolation ---------------------------------------------------------


def test_tables_in_schema() -> None:
    schema = """
        create table if not exists Users (id int);
        CREATE TEMP TABLE `scratch` (x);
        CREATE TABLE [audit] (x);
        CREATE INDEX idx ON users (id);
    """
    assert tables_in_schema(schema) == ["Users", "audit", "scratch"]


def test_sql_scan_is_case_insensitive_and_skips_docstrings(tmp_path) -> None:
    (tmp_path / "m.py").write_text(
        textwrap.dedent(
            '''
            """Writes to users: INSERT INTO users is only mentioned here."""

            def go(db):
                db.execute("insert into Users values (1)")
                db.execute("DELETE FROM sessions WHERE 1")
            '''
        ),
        encoding="utf-8",
    )
    found = {i.key: i.facts for i in SqlExtractor(tmp_path, ["users", "sessions"]).items()}
    assert found["table:users"] == ["writers:", "m.py", "readers:"]
    assert found["table:sessions"] == ["writers:", "m.py", "readers:"]  # DELETE FROM is no read


def test_route_decorator_keywords(tmp_path) -> None:
    (tmp_path / "app.py").write_text(
        textwrap.dedent(
            """
            bp = Blueprint("x", __name__, url_prefix="/admin")

            @bp.route(rule="/users", methods=("POST", "put"))
            def users():
                pass

            @bp.get(path="/ping")
            def ping():
                pass

            @cache.get_or_set("not a route")
            def helper():
                pass
            """
        ),
        encoding="utf-8",
    )
    found = {i.key: i.facts[:2] for i in RoutesExtractor(tmp_path).items()}
    assert found == {"route:/admin/ping": ["GET", "app.py"], "route:/admin/users": ["POST", "PUT"]}


def test_two_extractors_cannot_claim_one_item(tmp_path) -> None:
    class Same(core.Extractor):
        name = "same"

        def items(self):
            return [core.Item("route:/x", [])]

    with pytest.raises(ValueError, match="route:/x"):
        core.generate([Same(), Same()])


def test_a_plugin_extractor_from_the_config(tmp_path) -> None:
    (tmp_path / "map").mkdir()
    (tmp_path / "my_map.py").write_text(
        textwrap.dedent(
            """
            from lean_agent_kit.repomap import Extractor, Item

            class Jobs(Extractor):
                name = "jobs"
                title = "Jobs"
                intro = "From the scheduler."
                columns = ["job", "at"]

                def items(self):
                    return [Item("job:nightly", ["02:00"])]

            def extractors():
                return [Jobs()]
            """
        ),
        encoding="utf-8",
    )
    (tmp_path / "map/config.json").write_text(
        json.dumps({"extractors": [{"type": "plugin", "factory": "my_map:extractors"}]}),
        encoding="utf-8",
    )
    repo_map = core.generate(MapConfig.load(tmp_path).extractors())
    assert repo_map.files["jobs.md"].endswith(
        "# Jobs\n\nFrom the scheduler.\n\n| job | at |\n|---|---|\n| `nightly` | 02:00 |\n"
    )
    assert check(MapConfig.load(tmp_path)) == [
        "map/generated is out of date: jobs.md (run `lean-agents map generate`)",
        "items with no note in map/notes.md: job:nightly",
    ]


def test_config_errors(tmp_path) -> None:
    with pytest.raises(SystemExit, match="no map config"):
        MapConfig.load(tmp_path)
    (tmp_path / "map").mkdir()
    (tmp_path / "map/config.json").write_text(
        '{"extractors": [{"type": "nope"}]}', encoding="utf-8"
    )
    with pytest.raises(SystemExit, match="unknown extractor type 'nope'"):
        MapConfig.load(tmp_path).extractors()
