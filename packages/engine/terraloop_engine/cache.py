"""Tiny JSON disk cache for external API calls.

Keeps demos fast and resilient to API outages. Cache dir defaults to
``<repo>/data/cache`` and can be overridden with TERRALOOP_CACHE_DIR.
"""

from __future__ import annotations

import functools
import hashlib
import io
import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import pandas as pd

T = TypeVar("T")

_DEFAULT = Path(__file__).resolve().parents[3] / "data" / "cache"


def cache_dir() -> Path:
    p = Path(os.environ.get("TERRALOOP_CACHE_DIR", _DEFAULT))
    try:
        p.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Read-only deployment filesystems (e.g. Vercel Functions) only allow writes under the temp dir.
        p = Path(tempfile.gettempdir()) / "terraloop-cache"
        p.mkdir(parents=True, exist_ok=True)
    return p


def _serialize(obj: Any) -> Any:
    if isinstance(obj, pd.DataFrame):
        return {
            "__pd_type__": "DataFrame",
            "data": json.loads(obj.to_json(orient="split", date_format="iso")),
        }
    if isinstance(obj, pd.Series):
        return {
            "__pd_type__": "Series",
            "name": str(obj.name) if obj.name is not None else None,
            "data": json.loads(obj.to_json(orient="split", date_format="iso")),
        }
    if isinstance(obj, tuple):
        return {
            "__pd_type__": "tuple",
            "items": [_serialize(x) for x in obj],
        }
    return obj


def _deserialize(obj: Any) -> Any:
    if isinstance(obj, dict) and "__pd_type__" in obj:
        t = obj["__pd_type__"]
        if t == "DataFrame":
            return pd.read_json(io.StringIO(json.dumps(obj["data"])), orient="split")
        if t == "Series":
            s = pd.read_json(io.StringIO(json.dumps(obj["data"])), typ="series", orient="split")
            if obj.get("name"):
                s.name = obj["name"]
            return s
        if t == "tuple":
            return tuple(_deserialize(x) for x in obj["items"])
    return obj


def disk_cache(namespace: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = json.dumps([args, sorted(kwargs.items())], default=str)
            digest = hashlib.sha1(key.encode()).hexdigest()[:16]
            path = cache_dir() / namespace / f"{digest}.json"
            if path.exists():
                raw = json.loads(path.read_text(encoding="utf-8"))
                return _deserialize(raw)
            result = fn(*args, **kwargs)
            path.parent.mkdir(parents=True, exist_ok=True)
            serializable = _serialize(result)
            path.write_text(json.dumps(serializable), encoding="utf-8")
            return result

        return wrapper

    return decorator
