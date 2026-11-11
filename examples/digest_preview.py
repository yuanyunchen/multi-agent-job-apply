#!/usr/bin/env python3
"""The one summary a day, exactly as the person would read it.

Two things to notice:

* **no jargon.** The summary goes through a renderer with a lint that rejects
  file names, model names, identifiers, error codes and internal words. If a
  message somehow fails the lint, a safe line is shown instead and the problem
  is recorded — the person never sees the jargon.
* **only once.** The same day never produces two summaries, however many times
  the timetable or a person asks for one.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobpilot.report import digest  # noqa: E402
from jobpilot.scheduler import action_digest  # noqa: E402
from jobpilot.tracker import Tracker  # noqa: E402
from jobpilot.ui import Renderer  # noqa: E402

from _shared import days_ago, heading, settings  # noqa: E402

ROWS = [
    {"job_id": "1", "company": "Acme Robotics", "title": "ML Engineer", "status": "applied",
     "url": "https://example.test/1",
     "receipt": {"mail_id": "m-1", "basis": "the company's own mail server", "matched_at": days_ago(0)}},
    {"job_id": "2", "company": "Globex Systems", "title": "ML Engineer", "status": "submitted",
     "url": "https://example.test/2", "submit_proof_at": days_ago(0)},
    {"job_id": "3", "company": "Northwind Analytics", "title": "AI Engineer", "status": "interview",
     "url": "https://example.test/3"},
    {"job_id": "4", "company": "Initech Defense", "title": "ML Engineer", "status": "online_assessment",
     "url": "https://example.test/4"},
    {"job_id": "5", "company": "Umbrella Logistics", "title": "ML Engineer", "status": "parked",
     "url": "https://example.test/5",
     "pending_questions": ["What is your expected salary?", "Which campus did you attend?"]},
    {"job_id": "6", "company": "Stark Grid", "title": "ML Engineer", "status": "pipeline",
     "apply_tier": "core", "url": "https://example.test/6", "posted_at": days_ago(1)},
    {"job_id": "7", "company": "Wayne Freight", "title": "ML Engineer", "status": "rejected",
     "url": "https://example.test/7"},
]


def main() -> int:
    config = settings("digest")
    Tracker.from_config(config).upsert(ROWS, caller="example", force=True, force_reason="example data")

    heading("What the person reads")
    print(digest(ROWS, config, Renderer("simple"), today=date(2026, 11, 10)))

    heading("The same day, with the detail switched on")
    print(digest(ROWS, config, Renderer("technical"), today=date(2026, 11, 10)))

    heading("Rejections are only mentioned if they asked for them")
    talkative = settings("digest-rejections", notifications={"report_rejections": True})
    text = digest(ROWS, talkative, Renderer("simple"), today=date(2026, 11, 10))
    print([line for line in text.splitlines() if "came back" in line][0])

    heading("Asking twice on one day")
    first = action_digest(config, Renderer("simple"))
    second = action_digest(config, Renderer("simple"))
    print(f"  first time: {first}")
    print(f"  second time: {second or '(nothing — today is already done)'}")

    heading("No jargon reaches the person")
    from jobpilot.ui import lint_plain

    offenders = [
        line
        for line in digest(ROWS, config, Renderer("simple"), today=date(2026, 11, 10)).splitlines()
        if lint_plain(line)
    ]
    print(f"  lines that would have leaked something internal: {len(offenders)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
