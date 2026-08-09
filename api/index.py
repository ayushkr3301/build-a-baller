"""Vercel serverless entry point.

Vercel treats every file under /api as a function and looks for a module-level
ASGI callable named `app`. The real application lives in backend/app so that the
project still runs as a normal uvicorn server locally; this module only puts that
package on the import path and re-exports it.

`backend/**` has to be listed under `functions.includeFiles` in vercel.json,
otherwise the bundler won't ship it alongside this file.
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.main import app  # noqa: E402

__all__ = ["app"]
