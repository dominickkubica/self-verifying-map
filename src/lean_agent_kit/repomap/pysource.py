"""Reading Python source without importing it: files, docstrings, strings and calls."""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

#: Stands in for an f-string hole, so a table name built at run time is visible as one.
PLACEHOLDER = "{?}"


def python_files(root: Path) -> list[Path]:
    return [
        path
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts and path.name != "__init__.py"
    ]


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def summary(tree: ast.Module) -> str:
    """The docstring's first sentence: the module's purpose in one line."""
    doc = ast.get_docstring(tree) or ""
    paragraph = doc.strip().split("\n\n")[0].replace("\n", " ")
    return re.split(r"(?<=[.!?])\s", paragraph, maxsplit=1)[0].strip()


def _docstring_ids(tree: ast.Module) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                ids.add(id(body[0].value))
    return ids


def strings(tree: ast.Module) -> list[str]:
    """Every string literal that is not a docstring, with f-string holes as `{?}`."""
    skip = _docstring_ids(tree)
    inside_fstrings: set[int] = set()
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            text = ""
            for value in node.values:
                inside_fstrings.add(id(value))
                text += value.value if isinstance(value, ast.Constant) else PLACEHOLDER
            out.append(text)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in skip
            and id(node) not in inside_fstrings
        ):
            out.append(node.value)
    return out


class Imports:
    """Resolves a package's own imports to paths under its source folder.

    `package` is the import name (`myapp`) and `source` the folder it lives in
    (`src/myapp`). Imports starting with any of `quiet` (wire formats, settings, logging)
    are ignored: listing them under every route would bury the calls that matter.
    """

    def __init__(self, package: str, source: Path, quiet: tuple[str, ...] = ()) -> None:
        self.package = package
        self.source = source
        self.quiet = quiet

    def _ours(self, module: str) -> bool:
        return (module == self.package or module.startswith(self.package + ".")) and not (
            self.quiet and module.startswith(self.quiet)
        )

    def module_path(self, dotted: str) -> str | None:
        """`myapp.api.deps` -> `api/deps.py`; a package -> `providers/`; else None."""
        parts = dotted.split(".")[1:]
        if not parts:
            return None
        base = self.source.joinpath(*parts)
        if base.with_suffix(".py").exists():
            return "/".join(parts) + ".py"
        if base.is_dir():
            return "/".join(parts) + "/"
        return None

    def table(self, tree: ast.AST) -> dict[str, tuple[str, str | None]]:
        """Local name -> (module path, attribute or None when the name is a module)."""
        names: dict[str, tuple[str, str | None]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and self._ours(node.module):
                for alias in node.names:
                    local = alias.asname or alias.name
                    whole = self.module_path(f"{node.module}.{alias.name}")
                    if whole:
                        names[local] = (whole, None)
                    else:
                        names[local] = (self.module_path(node.module) or node.module, alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if self._ours(alias.name) and alias.asname:
                        path = self.module_path(alias.name) or alias.name
                        names[alias.asname] = (path, None)
        return names

    def reach(self, tree: ast.Module, start: str) -> set[str]:
        """What a function reaches through the package's imports, as `module: name`,
        following every same-module function it calls, transitively."""
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        imports = self.table(tree)
        seen, queue, found = {start}, [start], set()
        while queue:
            function = functions[queue.pop()]
            local = {**imports, **self.table(function)}
            body = ast.Module(body=function.body + function.args.defaults, type_ignores=[])
            found |= _calls(body, local)
            for node in ast.walk(body):
                if isinstance(node, ast.Name) and node.id in functions and node.id not in seen:
                    seen.add(node.id)
                    queue.append(node.id)
        return found


def _calls(tree: ast.AST, imports: dict[str, tuple[str, str | None]]) -> set[str]:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            target = imports.get(node.value.id)
            if target and target[1] is None:
                found.add(f"{target[0]}: {node.attr}")
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            target = imports.get(node.id)
            if target and target[1] is not None:
                found.add(f"{target[0]}: {target[1]}")
    return found


def group_calls(calls: set[str]) -> list[str]:
    """`{"a.py: f", "a.py: g"}` -> `["a.py: f, g"]`."""
    by_module: dict[str, list[str]] = defaultdict(list)
    for call in calls:
        module, name = call.split(": ", 1)
        by_module[module].append(name)
    return [f"{module}: {', '.join(sorted(names))}" for module, names in sorted(by_module.items())]
