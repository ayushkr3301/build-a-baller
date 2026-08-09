"""Vercel serverless entry point.

Vercel treats every file under /api as a function and looks for a module-level
ASGI callable named `app`. The real application lives in backend/app so that the
project still runs as a normal uvicorn server locally; this module only puts that
package on the import path and re-exports it.

`backend/**` has to be listed under `functions.includeFiles` in vercel.json,
otherwise the bundler won't ship it alongside this file.

If that import fails, a bare-ASGI diagnostic app is served instead. A crashed
Python function on Vercel is otherwise an opaque 500 whose traceback only exists
in the dashboard logs -- and deployment protection can put those out of reach of
anyone helping you debug. The diagnostic reports environment variable *names*
only, never values.
"""

import json
import os
import sys
import traceback
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _diagnostic_app(exc: BaseException):
    """A zero-dependency ASGI app that explains why the real one didn't load."""
    payload = {
        "error": "The backend failed to import, so the API never started.",
        "exception": f"{type(exc).__name__}: {exc}",
        "traceback": traceback.format_exc().splitlines()[-20:],
        "checks": {
            "python_version": sys.version.split()[0],
            "backend_dir_shipped": BACKEND.is_dir(),
            "backend_contents": sorted(p.name for p in BACKEND.iterdir())[:30]
            if BACKEND.is_dir()
            else "backend/ is missing -- check functions.includeFiles in vercel.json",
            "app_package_shipped": (BACKEND / "app" / "main.py").is_file(),
            "database_env_vars_present": sorted(
                k for k in os.environ if "POSTGRES" in k or "DATABASE" in k
            )
            or "none -- attach a Postgres database and redeploy",
            "third_party_importable": {
                name: _importable(name) for name in ("fastapi", "pydantic", "psycopg")
            },
        },
    }
    body = json.dumps(payload, indent=2, default=str).encode()

    async def diagnostic(scope, receive, send):
        if scope["type"] != "http":
            return
        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

    return diagnostic


def _importable(module: str) -> bool:
    try:
        __import__(module)
        return True
    except Exception:
        return False


try:
    from app.main import app
except Exception as exc:  # noqa: BLE001 -- any failure here must still serve a reply
    app = _diagnostic_app(exc)

__all__ = ["app"]
