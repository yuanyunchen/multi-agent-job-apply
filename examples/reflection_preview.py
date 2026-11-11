#!/usr/bin/env python3
"""The end-of-day look back, and the suggestions that come out of it.

The important part is the last step. A reflection nobody acts on is a diary, so
the look-back is what *triggers* the suggestions: the numbers are read, anything
worth asking about becomes a proposal, and the proposal waits.

**No setting is ever changed here.** Each suggestion states its evidence, says
what the person would notice, and asks. Approving one is a separate, deliberate
act, and declining it is remembered too.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobpilot.lead import (  # noqa: E402
    diff_in_words,
    metrics,
    open_proposals,
    proposals,
    render_proposals,
)
from jobpilot.report import reflection, weekly_review  # noqa: E402
from jobpilot.scheduler import action_reflection  # noqa: E402
from jobpilot.tracker import Tracker  # noqa: E402
from jobpilot.ui import Renderer  # noqa: E402

from _shared import days_ago, heading, settings  # noqa: E402


def rows() -> list[dict]:
    """A day that went badly in a way the system should notice by itself."""
    out = []
    # Five applications went out and none came back: that is the signature of an
    # application system quietly adding a step.
    for number in range(5):
        out.append(
            {
                "job_id": f"sent-{number}",
                "company": "Acme Robotics",
                "title": "ML Engineer",
                "status": "submitted",
                "ats": "greenhouse",
                "source": "greenhouse",
                "url": f"https://example.test/sent-{number}",
                "submit_proof_at": days_ago(1),
            }
        )
    # And three forms asked something nobody had written an answer to.
    for number in range(3):
        out.append(
            {
                "job_id": f"parked-{number}",
                "company": "Globex Systems",
                "title": "ML Engineer",
                "status": "parked",
                "ats": "workday",
                "source": "lever",
                "url": f"https://example.test/parked-{number}",
                "pending_questions": ["What is your expected salary for this role?"],
            }
        )
    return out


def main() -> int:
    config = settings("reflection")
    data = rows()
    Tracker.from_config(config).upsert(data, caller="example")

    heading("The note it writes for itself, every day, even a quiet one")
    print(reflection(data, today=__import__("datetime").date(2026, 11, 10)))

    heading("What it noticed, and what it would like to ask")
    print(render_proposals(proposals(metrics(data), config)))

    heading("The look back is what sets the asking off")
    spoken = action_reflection(config, Renderer("simple"))
    print(spoken or "(nothing worth asking about today)")

    heading("The suggestions are remembered, so they can be answered later")
    waiting = open_proposals(config)
    for item in waiting:
        print(f"  {item.id}")
        if item.change:
            print("      it would change:")
            print("      " + diff_in_words(config, item.change).replace("\n", "\n      "))
        else:
            print("      it needs a decision from you, not a setting change")
    print("\n  Nothing has changed. 'jobpilot approve <name>' is the only thing that changes a setting.")

    heading("The Monday version, over the whole week")
    print(weekly_review(data, config, today=__import__("datetime").date(2026, 11, 9)).words())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
