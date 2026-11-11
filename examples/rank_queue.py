#!/usr/bin/env python3
"""The order applications go out in, and the frozen list handed over to do them.

First choices first, newest first. Second choices wait, and are *allowed* to
wait indefinitely — that is the point: the jobs the person actually wants go out
while they are still open.

Then the list is frozen and fingerprinted, so it cannot change under a running
batch and a job cannot end up in two batches at once.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobpilot.pins import build_pin  # noqa: E402
from jobpilot.queue import build_queue, depth, eligible  # noqa: E402

from _shared import days_ago, heading, settings  # noqa: E402

ROWS = [
    {"job_id": "1", "company": "Acme Robotics", "title": "ML Engineer", "status": "pipeline",
     "apply_tier": "core", "posted_at": days_ago(9), "url": "https://example.test/1"},
    {"job_id": "2", "company": "Globex Systems", "title": "Software Engineer", "status": "pipeline",
     "apply_tier": "non_core", "posted_at": days_ago(1), "url": "https://example.test/2"},
    {"job_id": "3", "company": "Northwind Analytics", "title": "AI Engineer", "status": "pipeline",
     "apply_tier": "core", "posted_at": days_ago(2), "url": "https://example.test/3"},
    {"job_id": "4", "company": "Initech Defense", "title": "ML Engineer", "status": "pipeline",
     "apply_tier": "core", "posted_at": "", "url": "https://example.test/4"},
    # Each of the next three is held back, for a different reason.
    {"job_id": "5", "company": "Umbrella Logistics", "title": "ML Engineer", "status": "pipeline",
     "apply_tier": "core", "tags": ["hold_pending_user"], "url": "https://example.test/5"},
    {"job_id": "6", "company": "Stark Grid", "title": "ML Engineer", "status": "submitted",
     "apply_tier": "core", "url": "https://example.test/6"},
    {"job_id": "7", "company": "Wayne Freight", "title": "ML Engineer", "status": "pipeline",
     "apply_tier": "core", "duplicate_of": "1", "url": "https://example.test/7"},
]


def main() -> int:
    settings("queue")  # a throwaway folder, though this example writes nothing

    heading("Everything on the list")
    for row in ROWS:
        print(f"  {row['job_id']}. {row['company']} — {row['title']} ({row['status']})")

    heading("Which of them may actually be applied to")
    allowed = {row["job_id"] for row in eligible(ROWS)}
    for row in ROWS:
        if row["job_id"] in allowed:
            print(f"  {row['job_id']}. yes")
        else:
            why = (
                "you have not decided about that company yet"
                if "hold_pending_user" in (row.get("tags") or [])
                else "it has already gone out"
                if row["status"] == "submitted"
                else "it is the same job as one already on the list"
            )
            print(f"  {row['job_id']}. no — {why}")

    heading("The order they go out in")
    for position, row in enumerate(build_queue(ROWS), start=1):
        age = row.get("posted_at") or "no date given"
        kind = "first choice" if row.get("apply_tier") == "core" else "second choice"
        print(f"  {position}. {row['company']} — {kind}, posted {age[:10] if age[:1].isdigit() else age}")
    print("\n  Undated postings sort last, and second choices wait for the first choices.")

    heading("How deep the list is")
    sizes = depth(ROWS)
    print(f"  first choices: {sizes['core']}")
    print(f"  second choices: {sizes['non_core']}")
    print(f"  altogether: {sizes['total']}")

    heading("Freezing it, in batches of two")
    pin = build_pin(ROWS, wave_size=2)
    print(f"  fingerprint: {pin.digest}")
    for number, wave in enumerate(pin.waves(), start=1):
        names = ", ".join(str(row["company"]) for row in wave)
        print(f"  batch {number}: {names}")
    print("\n  The list cannot change now: anything that edits it fails the fingerprint check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
