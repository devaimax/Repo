"""Simple JSON cache helpers for metric fallbacks."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PRIMARY_CACHE_ROOT = Path("logs") / "cache"
FALLBACK_CACHE_ROOT = Path.home() / ".docker-swarm-project" / "logs" / "cache"

try:  # pandas is optional during runtime
    from pandas import Timestamp as PandasTimestamp  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    PandasTimestamp = None  # type: ignore

try:  # numpy is optional during runtime
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    np = None  # type: ignore


def _json_default(obj: Any) -> Any:
    """Best-effort serializer for pandas/numpy objects."""

    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            obj = obj.replace(tzinfo=timezone.utc)
        return obj.isoformat()

    if isinstance(obj, date):
        return obj.isoformat()

    if PandasTimestamp is not None and isinstance(obj, PandasTimestamp):  # type: ignore[arg-type]
        return obj.isoformat()

    if np is not None:
        if isinstance(obj, np.integer):  # type: ignore[arg-type]
            return int(obj)
        if isinstance(obj, np.floating):  # type: ignore[arg-type]
            return float(obj)
        if isinstance(obj, np.ndarray):  # type: ignore[arg-type]
            return obj.tolist()

    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def _payload(data: Any) -> dict[str, Any]:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


def store_json(data: Any, path: Path) -> None:
    payload = json.dumps(_payload(data), indent=2, default=_json_default)

    primary_path = PRIMARY_CACHE_ROOT / path
    try:
        primary_path.parent.mkdir(parents=True, exist_ok=True)
        primary_path.write_text(payload, encoding="utf-8")
        return
    except (OSError, PermissionError) as exc:
        fallback_path = FALLBACK_CACHE_ROOT / path
        print(
            f"⚠️ Cache path {primary_path} not writable ({exc}); "
            f"using {fallback_path}"
        )
        fallback_path.parent.mkdir(parents=True, exist_ok=True)
        fallback_path.write_text(payload, encoding="utf-8")


def load_json(path: Path) -> Any | None:
    for root in (PRIMARY_CACHE_ROOT, FALLBACK_CACHE_ROOT):
        candidate = root / path
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, PermissionError, OSError):
            continue
        return payload.get("data")
    return None
