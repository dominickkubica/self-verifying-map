"""c15: /api/gaps takes an optional integer max_symbols query parameter."""

from optscan.api.app import create_app
from optscan.config import Settings


def test_gaps_documents_max_symbols(tmp_path) -> None:
    app = create_app(Settings(_env_file=None, data_dir=tmp_path))
    params = app.openapi()["paths"]["/api/gaps"]["get"].get("parameters", [])
    found = [p for p in params if p["name"] == "max_symbols"]
    assert found, "no max_symbols parameter on /api/gaps"
    assert not found[0].get("required", False)
    schema = found[0]["schema"]
    kinds = {schema.get("type")} | {s.get("type") for s in schema.get("anyOf", [])}
    assert "integer" in kinds
