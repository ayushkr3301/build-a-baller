"""Vercel serverless entry point.

Vercel treats every file under /api as a function and looks for a module-level
ASGI callable named `app`. The real application lives in backend/app so that the
project still runs as a normal uvicorn server locally; this module only puts that
package on the import path and re-exports it.

`backend/**` has to be listed in the build's `includeFiles` in vercel.json,
otherwise the bundler won't ship it alongside this file.

Two constraints shape the odd structure below:

1. The builder finds `app` by *statically scanning* the source, so the assignment
   has to sit at module level. Wrapping the import in a try/except directly --
   the obvious way to trap a bad import -- buries it inside a Try node and the
   build fails with "Could not find a top-level app". Hence `app = _build_app()`.
2. If that import does fail, a crashed function is otherwise an opaque 500 whose
   traceback only exists in dashboard logs, which deployment protection can put
   out of reach. So a failure serves a diagnostic app instead. It reports
   environment variable *names* only, never values.
"""

import json
import os
import sys
import traceback
from pathlib import Path

# Bumped whenever this file changes, so /api/health can prove which build is live.
BUILD = "2026-08-09-diagnostic"

BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _importable(module: str) -> bool:
    try:
        __import__(module)
        return True
    except Exception:
        return False


def _diagnostic_payload(exc: BaseException) -> dict:
    return {
        "build": BUILD,
        "error": "The backend failed to import, so the API never started.",
        "exception": f"{type(exc).__name__}: {exc}",
        "traceback": traceback.format_exc().splitlines()[-20:],
        "checks": {
            "python_version": sys.version.split()[0],
            "backend_dir_shipped": BACKEND.is_dir(),
            "backend_contents": sorted(p.name for p in BACKEND.iterdir())[:30]
            if BACKEND.is_dir()
            else "backend/ is missing -- check includeFiles in vercel.json",
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


def _diagnostic_app(exc: BaseException):
    """An app that explains why the real one didn't load.

    Prefers FastAPI so the object is the same shape the platform sees on a healthy
    deploy, and drops to bare ASGI when FastAPI is itself the thing that's missing.
    """
    payload = _diagnostic_payload(exc)
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse

        diagnostic = FastAPI()

        @diagnostic.api_route(
            "/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"]
        )
        async def _report(path: str):  # noqa: ARG001 -- catches every route
            return JSONResponse(status_code=500, content=payload)

        return diagnostic
    except Exception:
        body = json.dumps(payload, indent=2, default=str).encode()

        async def bare_diagnostic(scope, receive, send):
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

        return bare_diagnostic


def _build_app():
    try:
        from app.main import app as real_app
    except Exception as exc:  # noqa: BLE001 -- any failure must still serve a reply
        return _diagnostic_app(exc)
    return real_app


# Must be a module-level assignment -- see note 1 in the docstring.
app = _build_app()

__all__ = ["app"]
