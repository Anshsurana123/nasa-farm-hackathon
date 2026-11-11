"""Vercel Serverless Function entrypoint for TerraLoop FastAPI backend."""

import sys
from pathlib import Path

# Ensure workspace packages (schemas, engine, api) are importable across all runtimes
_ROOT = Path(__file__).resolve().parent.parent
for _pkg in [
    _ROOT / "packages" / "schemas",
    _ROOT / "packages" / "engine",
    _ROOT / "apps" / "api",
]:
    if _pkg.is_dir() and str(_pkg) not in sys.path:
        sys.path.insert(0, str(_pkg))

from terraloop_api.main import app

__all__ = ["app"]
