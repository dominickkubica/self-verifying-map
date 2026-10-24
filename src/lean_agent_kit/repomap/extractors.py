"""Extractors that need no app import: they read source files and spec files only.

- `ModulesExtractor`: every Python module under a folder, with its docstring's first line.
- `SqlExtractor`: every table, with the modules whose SQL string literals write and read it.
  Tables come from a list or from `CREATE TABLE` statements in schema files.
- `RoutesExtractor`: every HTTP route declared by a decorator (`@router.get("/x")`,
  `@app.route("/x", methods=[...])`) with what its handler reaches through the package's
  imports, or every route in an OpenAPI file (JSON, or YAML when PyYAML is installed).
"""

from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from pathlib import Path

from .core import Extractor, Item
from .pysource import PLACEHOLDER, Imports, group_calls, parse, python_files, strings, summary


class ModulesExtractor(Extractor):
    name = "modules"
    title = "Modules"
    columns = ["module", "purpose"]

    def __init__(self, source: Path, label: str | None = None) -> None:
        self.source = source
        self.intro = f"Every module under `{label or source.as_posix()}`, with its docstring's first line."

    def items(self) -> list[Item]:
        out = []
        for path in python_files(self.source):
            module = path.relative_to(self.source).as_posix()
            line = summary(parse(path))
            # "(" sorts before every character a package name can start with.
            package = module.rsplit("/", 1)[0] + "/" if "/" in module else "(top level)"
            out.append(Item(f"module:{module}", [line], [f"`{module}`", line], package))
        return out


_SQL_HINT = re.compile(r"\b(?:SELECT|INSERT|UPDATE|DELETE|REPLACE)\b", re.I)
_WRITE = re.compile(
    r"\b(?:INSERT(?:\s+OR\s+\w+)?\s+INTO|REPLACE\s+INTO|UPDATE|DELETE\s+FROM)\s+[\"`\[]?(\{\?\}|\w+)",
    re.I,
)
_DELETE_FROM = re.compile(r"\bDELETE\s+FROM\b", re.I)
_READ = re.compile(r"\b(?:FROM|JOIN)\s+[\"`\[]?(\{\?\}|\w+)", re.I)
_CREATE = re.compile(
    r"\bCREATE\s+(?:TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`\[]?(\w+)", re.I
)


def tables_in_schema(text: str) -> list[str]:
    """Table names from `CREATE TABLE` statements."""
    return sorted(set(_CREATE.findall(text)))


class SqlExtractor(Extractor):
    name = "storage"
    title = "Storage"
    columns = ["table", "written by", "read by"]

    def __init__(self, source: Path, tables: list[str], label: str | None = None) -> None:
        self.source = source
        self.tables = sorted(set(tables))
        self.unresolved: list[str] = []
        self.intro = (
            f"Every table, with the modules under `{label or source.as_posix()}` whose SQL "
            "writes it and reads it. Found by scanning string literals for INSERT, UPDATE, "
            "DELETE, REPLACE, FROM and JOIN against the table names."
        )

    def items(self) -> list[Item]:
        known = {name.lower(): name for name in self.tables}
        writers: dict[str, set[str]] = defaultdict(set)
        readers: dict[str, set[str]] = defaultdict(set)
        unresolved: set[str] = set()
        for path in python_files(self.source):
            module = path.relative_to(self.source).as_posix()
            for text in strings(parse(path)):
                if not _SQL_HINT.search(text):
                    continue
                for pattern, target in ((_WRITE, writers), (_READ, readers)):
                    scanned = _DELETE_FROM.sub("", text) if pattern is _READ else text
                    for name in pattern.findall(scanned):
                        if name == PLACEHOLDER:
                            unresolved.add(f"`{module}`: `{' '.join(text.split())[:80]}`")
                        elif name.lower() in known:
                            target[known[name.lower()]].add(module)
        self.unresolved = sorted(unresolved)
        out = []
        for table in self.tables:
            wrote, read = sorted(writers[table]), sorted(readers[table])
            row = [
                f"`{table}`",
                ", ".join(f"`{m}`" for m in wrote) or "none found",
                ", ".join(f"`{m}`" for m in read) or "none found",
            ]
            out.append(Item(f"table:{table}", ["writers:", *wrote, "readers:", *read], row))
        return out

    def gaps(self) -> dict[str, list[str]]:
        return {"SQL the scanner could not resolve (a table name built at run time)": self.unresolved}


HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")


class RoutesExtractor(Extractor):
    """Routes from decorators in the source, or from an OpenAPI file when `spec` is set.

    A decorator counts when its name is an HTTP method (`@router.get(path)`) or one of
    `route_decorators` (`@app.route(path, methods=[...])`, default GET). A prefix is read
    from the object the decorator hangs off when that object is assigned at module level
    with a `prefix=` or `url_prefix=` argument; prefixes added when mounting are not seen.
    """

    name = "routes"
    title = "HTTP routes"
    columns = ["route", "methods", "file", "handler", "uses"]

    def __init__(
        self,
        source: Path | None = None,
        package: str | None = None,
        spec: Path | None = None,
        quiet: tuple[str, ...] = (),
        route_decorators: tuple[str, ...] = ("route", "api_route"),
    ) -> None:
        self.source = source
        self.spec = spec
        self.route_decorators = route_decorators
        if spec is not None:
            self.intro = f"Every route in `{spec.name}`, with its methods and operation ids."
            self.columns = ["route", "methods", "operations"]
        else:
            assert source is not None, "routes need a source folder or a spec file"
            self.imports = Imports(package or source.name, source, quiet)
            self.intro = (
                "Every route declared by a decorator, its handler, and what the handler "
                "reaches through the package's own imports (following helper functions in "
                "the same file)."
            )

    def items(self) -> list[Item]:
        return self._from_spec() if self.spec is not None else self._from_source()

    def _from_spec(self) -> list[Item]:
        text = self.spec.read_text(encoding="utf-8")
        if self.spec.suffix in (".yaml", ".yml"):
            try:
                import yaml  # optional: the kit has no dependencies
            except ImportError as error:
                raise SystemExit("reading a YAML spec needs PyYAML; use JSON or install it") from error
            spec = yaml.safe_load(text)
        else:
            spec = json.loads(text)
        out = []
        for path, operations in sorted(spec.get("paths", {}).items()):
            methods = sorted(m.upper() for m in operations if m in HTTP_METHODS)
            ids = sorted(op.get("operationId", "") for m, op in operations.items() if m in HTTP_METHODS)
            ids = [i for i in ids if i]
            row = [f"`{path}`", " ".join(methods), ", ".join(f"`{i}`" for i in ids) or "-"]
            out.append(Item(f"route:{path}", [*methods, *ids], row))
        return out

    def _decorated(self, tree: ast.Module):
        """(path, methods, handler) for every route decorator in a module."""
        prefixes = {}
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                for keyword in node.value.keywords:
                    if keyword.arg in ("prefix", "url_prefix") and isinstance(keyword.value, ast.Constant):
                        prefixes[node.targets[0].id] = str(keyword.value.value)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)):
                    continue
                verb = decorator.func.attr
                if verb not in HTTP_METHODS and verb not in self.route_decorators:
                    continue
                path_arg = decorator.args[0] if decorator.args else None
                for keyword in decorator.keywords:
                    if keyword.arg in ("path", "rule"):
                        path_arg = keyword.value
                if not (isinstance(path_arg, ast.Constant) and isinstance(path_arg.value, str)):
                    continue
                methods = {verb.upper()} if verb in HTTP_METHODS else {"GET"}
                for keyword in decorator.keywords:
                    if keyword.arg == "methods" and isinstance(keyword.value, (ast.List, ast.Tuple, ast.Set)):
                        methods = {
                            str(e.value).upper() for e in keyword.value.elts if isinstance(e, ast.Constant)
                        }
                owner = decorator.func.value
                prefix = prefixes.get(owner.id, "") if isinstance(owner, ast.Name) else ""
                yield prefix + path_arg.value, methods, node.name

    def _from_source(self) -> list[Item]:
        routes: dict[str, dict] = {}
        for path in python_files(self.source):
            tree = parse(path)
            file = path.relative_to(self.source).as_posix()
            for route, methods, handler in self._decorated(tree):
                entry = routes.setdefault(route, {"methods": set(), "where": set(), "uses": set()})
                entry["methods"] |= methods
                entry["where"].add((file, handler))
                entry["uses"] |= self.imports.reach(tree, handler) if handler in _top_level(tree) else set()
        out = []
        for route in sorted(routes):
            entry = routes[route]
            methods = sorted(entry["methods"])
            files = sorted({f for f, _ in entry["where"]})
            handlers = sorted({h for _, h in entry["where"]})
            uses = group_calls(entry["uses"])
            row = [
                f"`{route}`",
                " ".join(methods),
                ", ".join(f"`{f}`" for f in files),
                ", ".join(f"`{h}`" for h in handlers),
                "; ".join(uses) or "-",
            ]
            out.append(Item(f"route:{route}", [*methods, *files, *handlers, *uses], row))
        return out


def _top_level(tree: ast.Module) -> set[str]:
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
