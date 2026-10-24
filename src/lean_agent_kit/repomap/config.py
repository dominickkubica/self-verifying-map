"""`map/config.json`: which extractors build a repository's map, and what `check` enforces.

    {
      "required_notes": ["table", "job"],
      "budgets": {"MAP.md": 6144, "map/notes.md": 10240},
      "extractors": [
        {"type": "modules", "source": "src/myapp"},
        {"type": "sql", "source": "src/myapp", "schema": ["migrations/*.sql"]},
        {"type": "routes", "source": "src/myapp", "package": "myapp", "quiet": ["myapp.schemas"]},
        {"type": "routes", "name": "public-api", "spec": "openapi.json"},
        {"type": "plugin", "factory": "tools.map_extractors:extractors"}
      ]
    }

Paths are relative to the repository root. `sql` takes `tables` (a list) or `schema`
(files or globs holding `CREATE TABLE` statements). Any extractor takes `name` (its file
in `map/generated/`) and `gap_budget`. A `plugin` names a `module:callable`, imported
with the repository root on the path, that returns a list of `Extractor`s.
"""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .core import Extractor
from .extractors import ModulesExtractor, RoutesExtractor, SqlExtractor, tables_in_schema

CONFIG = Path("map") / "config.json"


@dataclass
class MapConfig:
    root: Path
    extractor_specs: list[dict]
    required_notes: tuple[str, ...] = ("table", "job")
    budgets: dict[str, int] = field(default_factory=dict)

    @property
    def generated(self) -> Path:
        return self.root / "map" / "generated"

    @property
    def notes(self) -> Path:
        return self.root / "map" / "notes.md"

    @property
    def index(self) -> Path:
        return self.root / "MAP.md"

    @classmethod
    def load(cls, root: Path) -> MapConfig:
        path = root / CONFIG
        if not path.is_file():
            raise SystemExit(f"no map config at {path}; see `lean-agents map --help`")
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            root=root,
            extractor_specs=data.get("extractors", []),
            required_notes=tuple(data.get("required_notes", ("table", "job"))),
            budgets=data.get("budgets", {}),
        )

    def extractors(self) -> list[Extractor]:
        out: list[Extractor] = []
        for spec in self.extractor_specs:
            built = self._build(dict(spec))
            for extractor in built:
                if "name" in spec and len(built) == 1:
                    extractor.name = spec["name"]
                if "gap_budget" in spec:
                    extractor.gap_budget = int(spec["gap_budget"])
            out += built
        return out

    def _build(self, spec: dict) -> list[Extractor]:
        kind = spec.get("type")
        source = self.root / spec["source"] if "source" in spec else None
        label = spec.get("source")
        if kind == "modules":
            return [ModulesExtractor(source, label)]
        if kind == "sql":
            tables = list(spec.get("tables", []))
            schemas = spec.get("schema", [])
            for pattern in [schemas] if isinstance(schemas, str) else schemas:
                for path in sorted(self.root.glob(pattern)):
                    tables += tables_in_schema(path.read_text(encoding="utf-8"))
            return [SqlExtractor(source, tables, label)]
        if kind == "routes":
            spec_file = self.root / spec["spec"] if "spec" in spec else None
            return [
                RoutesExtractor(
                    source,
                    package=spec.get("package"),
                    spec=spec_file,
                    quiet=tuple(spec.get("quiet", ())),
                )
            ]
        if kind == "plugin":
            module_name, _, attribute = spec["factory"].partition(":")
            if str(self.root) not in sys.path:
                sys.path.insert(0, str(self.root))
            factory = getattr(importlib.import_module(module_name), attribute or "extractors")
            return list(factory())
        raise SystemExit(f"unknown extractor type {kind!r} in {CONFIG}")
