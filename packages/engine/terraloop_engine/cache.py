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
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    return obj


def _deserialize(obj: Any) -> Any:
    if isinstance(obj, dict):
        if "__pd_type__" in obj:
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
        return {k: _deserialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deserialize(x) for x in obj]
    return obj


def _normalize_key_val(val: Any) -> Any:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        fval = float(val)
        return int(fval) if fval.is_integer() and abs(fval) < 1e15 else fval
    if isinstance(val, (list, tuple)):
        return [_normalize_key_val(v) for v in val]
    if isinstance(val, dict):
        return {str(k): _normalize_key_val(v) for k, v in sorted(val.items())}
    return val


def disk_cache(namespace: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            norm_args = [_normalize_key_val(a) for a in args]
            norm_kwargs = [[str(k), _normalize_key_val(v)] for k, v in sorted(kwargs.items())]
            key = json.dumps([norm_args, norm_kwargs], default=str)
            digest = hashlib.sha1(key.encode()).hexdigest()[:16]
            path = cache_dir() / namespace / f"{digest}.json"
            if path.exists():
                raw = json.loads(path.read_text(encoding="utf-8"))
                return _deserialize(raw)
            result = fn(*args, **kwargs)
            path.parent.mkdir(parents=True, exist_ok=True)
            serializable = _serialize(result)
            payload = json.dumps(serializable)
            fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=f".{digest}.", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(payload)
                os.replace(tmp_path, path)
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise
            return result

        return wrapper

    return decorator
