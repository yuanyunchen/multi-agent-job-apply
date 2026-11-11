"""What to apply to next.

Core first, newest first. Non-core only when there is no core work left — it is
allowed to starve, and that is the point: the jobs the user cares about most go
out while they are still fresh.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .domain import SUBMITTED_STATUSES
from .tracker import normalize_status

#: Only these statuses are eligible to be applied to.
QUEUEABLE = frozenset({"pipeline"})


def _posted_at(row: dict) -> datetime:
    raw = str(row.get("posted_at") or "")
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)  # undated rows sort last
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def eligible(rows: Iterable[dict]) -> list[dict]:
    """Rows that may be applied to: screened, not held, not already out."""
    out = []
    for row in rows:
        status = normalize_status(row.get("status"))
        if status not in QUEUEABLE or status in SUBMITTED_STATUSES:
            continue
        if row.get("hold") or row.get("duplicate_of"):
            continue
        if "hold_pending_user" in (row.get("flags") or []) or "hold_pending_user" in (row.get("tags") or []):
            continue
        if row.get("applyable") is False:
            continue
        out.append(row)
    return out


def build_queue(rows: Iterable[dict]) -> list[dict]:
    """Order the eligible rows: core newest-first, then non-core newest-first."""
    rows = eligible(rows)
    core = [row for row in rows if row.get("apply_tier") == "core"]
    non_core = [row for row in rows if row.get("apply_tier") != "core"]
    core.sort(key=_posted_at, reverse=True)
    non_core.sort(key=_posted_at, reverse=True)
    return core + non_core


def next_wave(rows: Iterable[dict], size: int) -> list[dict]:
    """The next batch to work through. Non-core waits until core is empty."""
    queue = build_queue(rows)
    core = [row for row in queue if row.get("apply_tier") == "core"]
    chosen = core if core else queue
    return chosen[: max(0, size)]


def depth(rows: Iterable[dict]) -> dict[str, int]:
    queue = build_queue(rows)
    core = sum(1 for row in queue if row.get("apply_tier") == "core")
    return {"core": core, "non_core": len(queue) - core, "total": len(queue)}
