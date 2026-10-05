"""Tiny JSON disk cache for external API calls.

Keeps demos fast and resilient to API outages. Cache dir defaults to
``<repo>/data/cache`` and can be overridden with TERRALOOP_CACHE_DIR.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")

_DEFAULT = Path(__file__).resolve().parents[3] / "data" / "cache"


def cache_dir() -> Path:
    p = Path(os.environ.get("TERRALOOP_CACHE_DIR", _DEFAULT))
    p.mkdir(parents=True, exist_ok=True)
    return p


def disk_cache(namespace: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = json.dumps([args, sorted(kwargs.items())], default=str)
            digest = hashlib.sha1(key.encode()).hexdigest()[:16]
            path = cache_dir() / namespace / f"{digest}.json"
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
            result = fn(*args, **kwargs)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result), encoding="utf-8")
            return result

        return wrapper

    return decorator
