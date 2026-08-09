"""Guards on api/index.py, the Vercel serverless entry point.

These exist because both failures they cover cost a deploy cycle each to find,
and neither is visible from running the app locally.
"""

import ast
import importlib.util
import json
from pathlib import Path

import pytest

ENTRY = Path(__file__).resolve().parent.parent.parent / "api" / "index.py"
DETECTED_NAMES = {"app", "application", "handler"}


def _top_level_bindings(source: str) -> dict[str, int]:
    """Names bound at module scope -- what a static builder scan can see."""
    found: dict[str, int] = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in DETECTED_NAMES:
                    found[target.id] = node.lineno
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                name = alias.asname or alias.name
                if name in DETECTED_NAMES:
                    found[name] = node.lineno
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in DETECTED_NAMES:
                found[node.target.id] = node.lineno
    return found


def test_entry_point_binds_app_at_module_level():
    """Regression: Vercel scans the source, it does not import the module.

    An `app` assigned inside a try/except lives in a Try node, not at module
    scope, and the build fails with "Could not find a top-level app" -- which is
    what happened when the diagnostic wrapper was first added.
    """
    bindings = _top_level_bindings(ENTRY.read_text())
    assert "app" in bindings, (
        "api/index.py must bind `app` at module level or the Vercel build fails; "
        "do not wrap the import in try/except -- call a helper instead"
    )


def test_a_try_except_binding_would_not_be_detected():
    """Pins the reason the guard above exists, so it isn't 'simplified' away."""
    buried = "try:\n    from app.main import app\nexcept Exception:\n    app = None\n"
    assert _top_level_bindings(buried) == {}


def _load_entry():
    spec = importlib.util.spec_from_file_location("vercel_entry", ENTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_entry_point_exposes_the_real_app_when_the_import_works():
    module = _load_entry()
    assert module.app is not None
    routes = {getattr(r, "path", None) for r in module.app.routes}
    assert "/api/health" in routes, "expected the real application, not the diagnostic"


def test_a_failed_import_serves_a_diagnostic_instead_of_crashing():
    """A crashed function is an opaque 500; this has to explain itself instead."""
    module = _load_entry()
    diagnostic = module._diagnostic_app(ModuleNotFoundError("No module named 'app'"))

    from fastapi.testclient import TestClient

    with TestClient(diagnostic) as client:
        for path in ("/api/health", "/api/meta", "/anything"):
            response = client.get(path)
            assert response.status_code == 500
            body = response.json()
            assert body["exception"].startswith("ModuleNotFoundError")
            assert "checks" in body


def test_the_diagnostic_never_leaks_environment_values(monkeypatch):
    monkeypatch.setenv("POSTGRES_URL", "postgresql://user:hunter2@host/db")
    module = _load_entry()
    payload = module._diagnostic_payload(RuntimeError("boom"))
    blob = json.dumps(payload)
    assert "hunter2" not in blob
    assert "POSTGRES_URL" in blob, "names are useful; values are not"


@pytest.mark.parametrize("name", ["fastapi", "pydantic", "psycopg"])
def test_diagnostic_reports_importability_of_runtime_dependencies(name):
    module = _load_entry()
    payload = module._diagnostic_payload(RuntimeError("boom"))
    assert name in payload["checks"]["third_party_importable"]
