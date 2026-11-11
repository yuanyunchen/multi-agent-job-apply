#!/usr/bin/env python3
"""A practice run through the list. Nothing is claimed and nothing is sent.

Three things are worth watching here:

* the **answer bank**: a form question with no answer on file stops that
  application and asks the person, rather than being guessed at;
* the **outbound check**: even with everything else in order, nothing is
  submitted until that permission is switched on;
* **disposal**: every job that was picked up gets an outcome. None is left
  half-done.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import yaml  # noqa: E402

from jobpilot.apply import DryRunDriver, WaveRunner, describe  # noqa: E402
from jobpilot.gates import AnswerBank, OutboundGate  # noqa: E402
from jobpilot.tracker import Tracker  # noqa: E402
from jobpilot.ui import Renderer  # noqa: E402

from _shared import days_ago, heading, settings  # noqa: E402

ANSWERS = {
    "answers": [
        {"id": "work_authorization", "match": ["authorized to work"], "answer": "Yes"},
        {"id": "relocate", "match": ["willing to relocate"], "answer": "Yes"},
    ],
    "always_ask": ["social security", "date of birth"],
}

QUESTIONS = {
    "ready": ["Are you authorized to work in the United States?", "Are you willing to relocate?"],
    "needs-you": ["What is your expected salary for this role?"],
    "never-answered": ["Please enter your social security number."],
}


def main() -> int:
    answers_file = Path(tempfile.mkdtemp(prefix="jobpilot-example-answers-")) / "answers.yaml"
    answers_file.write_text(yaml.safe_dump(ANSWERS), encoding="utf-8")

    config = settings("apply", documents={"answers": str(answers_file)})
    tracker = Tracker.from_config(config)
    tracker.upsert(
        [
            {
                "job_id": job_id,
                "company": {"ready": "Acme Robotics", "needs-you": "Globex Systems",
                            "never-answered": "Northwind Analytics"}[job_id],
                "title": "Machine Learning Engineer",
                "url": f"https://example.test/{job_id}",
                "status": "pipeline",
                "apply_tier": "core",
                "posted_at": days_ago(1),
            }
            for job_id in QUESTIONS
        ],
        caller="example",
    )

    heading("What is on the answer bank")
    bank = AnswerBank.from_file(answers_file)
    for question in [q for group in QUESTIONS.values() for q in group]:
        found = bank.lookup(question)
        print(f'  "{question}"')
        print(f"      {'answer on file: ' + found.value if found else 'no answer — this would stop and ask you'}")

    heading("A practice run")
    driver = DryRunDriver(asks=QUESTIONS)
    runner = WaveRunner.build(config, tracker=tracker, driver=driver)
    result = runner.run(dry_run=True)
    print("  " + describe(result, Renderer("simple")))
    if result.questions:
        print("\n  Waiting on you:")
        for question in result.questions:
            print(f"      - {question}")

    heading("Nothing moved")
    print(f"  states on the record: {tracker.counts()}")
    print("  no job was picked up, so none needed an outcome.")

    heading("Why nothing would be sent even for real")
    gate = OutboundGate(config)
    check = gate.check("submit_applications")
    print(f"  {check.reason}")
    print("  Switching that on is a deliberate act, and the check still runs afterwards.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
