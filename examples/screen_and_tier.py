#!/usr/bin/env python3
"""Reading descriptions, and the one rule that matters most.

A job may be ruled out **only** by quoting the posting, word for word, and the
quote is checked against the posting afterwards. This example shows that rule
working in both directions: a quoted drop is accepted, and an invented one is
thrown away while the job survives.

Offline: the "model" is a stand-in whose answers are written here in full, so
you can see exactly what is and is not accepted.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobpilot.tiering import classify, summarize  # noqa: E402

from _shared import heading, jobs, settings  # noqa: E402


class Model:
    """A stand-in. ``answers`` maps a company to what it would say about it."""

    name = "a-stand-in-model"

    def __init__(self, answers: dict[str, dict]) -> None:
        self.answers = answers

    def rank(self, batch, flags):
        return {
            job.job_id: self.answers[job.company]
            for job in batch
            if job.company in self.answers
        }


def show(decisions, batch) -> None:
    by_id = {job.job_id: job for job in batch}
    for decision in decisions:
        job = by_id[decision.job_id]
        verdict = {"core": "apply first", "non_core": "apply later", "irrelevant": "skip"}[decision.tier]
        print(f"  {job.company} — {job.title}: {verdict}")
        print(f"      because: {decision.reason}")
        if decision.quote:
            print(f'      quoting the posting: "{decision.quote}"')
        if decision.model_pending:
            print("      (no clear answer from the model, so the rule answer stands)")


def main() -> int:
    config = settings("screen")
    batch = jobs()

    heading("Rules only — no model, no cost, no network")
    show(classify(batch, config), batch)

    heading("With a model that quotes the posting properly")
    honest = Model(
        {
            "Northwind Analytics": {
                "tier": "irrelevant",
                "quote": "8 years of experience in production machine learning is required.",
                "reason": "it requires far more experience than you have",
            }
        }
    )
    decisions = classify(batch, config, hook=honest)
    show(decisions, batch)

    heading("With a model that makes its reason up")
    liar = Model(
        {
            "Acme Robotics": {
                "tier": "irrelevant",
                "quote": "We only consider candidates with a doctorate from a top-five school.",
                "reason": "they want a doctorate",
            }
        }
    )
    decisions = classify(batch, config, hook=liar)
    show(decisions, batch)
    print("\n  Note what happened to Acme Robotics: that sentence is not in the posting,")
    print("  so the skip was thrown away and the job is still going out.")

    heading("The tally")
    counts = summarize(classify(batch, config, hook=honest))
    print(f"  apply first: {counts.core}")
    print(f"  apply later: {counts.non_core}")
    print(f"  skipped: {counts.irrelevant}")
    print(f"  kept because nothing could back up a skip: {counts.unverified_quotes}")
    print("\nNothing was written down.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
