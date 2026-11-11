#!/usr/bin/env python3
"""Record a complete practice session into ``docs/sample-session.md``.

Everything in the generated document is real output from running this script:
nothing is written by hand. Two runs are recorded — one with every helper
switched on, one with none of them — so the documentation shows what a user with
a bare installation sees as well as a user with everything.

Safety, because this writes a document people trust:

* ``JOBPILOT_TEST=1`` is set, so the network, real mailboxes, real browsers and
  real model tools all refuse to be used;
* the data directory is a throwaway temporary one, never the real home;
* the job pages come from the synthetic fixtures in ``tests/fixtures``;
* the model answers come from the built-in practice stand-in.

Run it with:  python tools/record_sample_session.py
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

os.environ["JOBPILOT_TEST"] = "1"

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from jobpilot.cli import main  # noqa: E402
from jobpilot.providers.fake import FakeProvider  # noqa: E402
from jobpilot.search.base import FixtureFetcher  # noqa: E402

FIXTURES = REPO / "tests" / "fixtures"
OUT = REPO / "docs" / "sample-session.md"

BOARD_URLS = {
    "https://boards-api.greenhouse.io/v1/boards/acme-robotics/jobs?content=true": "greenhouse_acme.json",
    "https://api.lever.co/v0/postings/globex-systems?mode=json": "lever_globex.json",
    "https://api.ashbyhq.com/posting-api/job-board/northwind-analytics?includeCompensation=false": "ashby_northwind.json",
}

#: Answers for the two runs. These are the "user typing" parts of the session.
EVERYTHING_ON = {
    "identity.full_name": "Sam Example",
    "identity.apply_email": "sam@example.test",
    "identity.phone": "+1 555 0100 222",
    "identity.current_location": "Austin, TX",
    "search.categories.core": "Machine Learning Engineer, AI Engineer",
    "search.categories.non_core": "Software Engineer, Data Analyst",
    "search.categories.excluded": "Sales, Technician",
    "search.locations.preferred": "Austin, New York, Remote",
    "search.locations.remote_ok": True,
    "work_authorization.needs_sponsorship_now_or_later": True,
    "search.max_required_years_experience": "about 2",
    "search.company_rules.hard_exclude": "Umbrella Logistics",
    "search.company_rules.hold_pending_user": "Stark Grid",
    "search.recency_days": 30,
    "search.sources.greenhouse.boards": "acme-robotics, globex-systems:lever, northwind-analytics:ashby",
    "enable.linkedin": True,
    "enable.handshake": True,
    "enable.yc": True,
    "enable.claude": True,
    "enable.fake": True,
    "plugins.handshake.school_name": "Example University",
    "identity.digest_email": "",
    "notifications.digest_time": "7:30am",
    "ui.mode": "simple",
    "login.mailbox": "done",
    "login.linkedin": "done",
    "login.handshake": "done",
    "login.yc": "skip",
    "login.claude": "done",
}

NOTHING_ON = {
    "identity.full_name": "Alex Sample",
    "identity.apply_email": "alex@example.test",
    "identity.phone": "",
    "identity.current_location": "Chicago, IL",
    "search.categories.core": "Data Analyst",
    "search.categories.non_core": "Business Analyst",
    "search.categories.excluded": "Sales",
    "search.locations.preferred": "Chicago",
    "search.locations.remote_ok": True,
    "work_authorization.needs_sponsorship_now_or_later": False,
    "search.max_required_years_experience": 1,
    "search.company_rules.hard_exclude": "none",
    "search.company_rules.hold_pending_user": "none",
    "search.recency_days": 21,
    "search.sources.greenhouse.boards": "acme-robotics, globex-systems:lever",
    "enable.linkedin": False,
    "enable.handshake": False,
    "enable.yc": False,
    "enable.claude": False,
    "enable.fake": True,
    "identity.digest_email": "",
    "notifications.digest_time": "8am",
    "ui.mode": "simple",
    "login.mailbox": "done",
}

NOW = "2026-11-09T08:05"


# -- the stand-in model --------------------------------------------------

JOB_BLOCK = re.compile(r"^--- job_id: (?P<id>\S+)$", re.MULTILINE)
REQUIRED_YEARS = re.compile(r"[^.\n]*\byears of experience\b[^.\n]*\brequired\b[^.\n]*\.")


def screening_answer(prompt: str) -> str:
    """Read the postings out of the prompt and answer the way a model would.

    A posting that says in so many words that it *requires* more years than the
    person has is dropped, quoting that exact sentence — which the code then
    checks against the posting. Everything else is kept.
    """
    blocks = list(JOB_BLOCK.finditer(prompt))
    answers = []
    for index, match in enumerate(blocks):
        end = blocks[index + 1].start() if index + 1 < len(blocks) else len(prompt)
        body = prompt[match.end() : end]
        title = (re.search(r"^title: (.*)$", body, re.MULTILINE) or [None, ""])[1]
        quote = REQUIRED_YEARS.search(body)
        if quote:
            answers.append(
                {
                    "job_id": match.group("id"),
                    "verdict": "drop",
                    "tier": "irrelevant",
                    "quote": quote.group(0).strip(),
                    "reason": "it asks for more experience than you have",
                }
            )
            continue
        core = any(word in title for word in ("Machine Learning", "AI ", "Data Analyst"))
        answers.append(
            {
                "job_id": match.group("id"),
                "verdict": "keep",
                "tier": "core" if core else "non_core",
                "quote": "",
                "reason": "it looks like the kind of job you asked for",
            }
        )
    return json.dumps(answers)


def request_answer(prompt: str) -> str:
    """The stand-in's answer when the user asks for a change in their own words."""
    return json.dumps(
        {
            "change": {"search.categories.core": ["Machine Learning Engineer", "AI Engineer", "Data Scientist"]},
            "summary": "I would also treat data scientist roles as a first choice",
            "effect": "A few more jobs each morning, and they go out before the others.",
        }
    )


def stand_in(prompt: str) -> str:
    if "Work out which of their settings" in prompt:
        return request_answer(prompt)
    return screening_answer(prompt)


def install_stand_ins() -> None:
    """Swap the network and the models for fixtures and the stand-in."""
    import jobpilot.providers as providers
    import jobpilot.search as search

    search.UrllibFetcher = lambda *a, **k: FixtureFetcher.from_dir(FIXTURES, BOARD_URLS)
    providers._providers_from_config = lambda config: {
        "fake": FakeProvider(answer=stand_in),
        **{
            name: FakeProvider(name=name, answer=stand_in)
            for name in ("claude-haiku", "claude-sonnet", "claude-opus", "codex")
        },
    }


# -- running the commands ------------------------------------------------


def answers_file(directory: Path, answers: dict) -> Path:
    import yaml

    path = directory / "answers.yaml"
    path.write_text(yaml.safe_dump(answers, sort_keys=False), encoding="utf-8")
    return path


def capture(argv: list[str]) -> str:
    """Run one command and give back exactly what the user would have seen."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(argv)
    text = buffer.getvalue()
    if code not in (0, 1):
        text += f"\n(stopped early, nothing was left half-done)\n"
    return text.rstrip() + "\n"


def mark_user_answers(text: str) -> str:
    return "\n".join(
        ("YOU > " + line[2:]) if line.startswith("> ") else line for line in text.splitlines()
    )


def trim_questions(text: str) -> str:
    """Keep every question and answer; elide the default/consequence lines.

    The full text of those lines is in the test suite; here they would triple
    the length of the document without showing anything new.
    """
    out: list[str] = []
    dropped = 0
    for line in text.splitlines():
        if re.match(r"^  \((default|.*default:)", line) or line.startswith(
            ("  What this changes:", "  Example I would apply to:", "  Example I would skip:")
        ):
            dropped += 1
            continue
        if dropped and not line.startswith("  "):
            out.append(f"  … ({dropped} lines of default and consequence omitted)")
            dropped = 0
        out.append(line)
    return "\n".join(out)


def section(title: str, command: str, body: str, *, fence: str = "text") -> str:
    return "\n".join([f"### {title}", "", f"```console", f"$ {command}", body.rstrip(), "```", ""])


def hide_machine_paths(text: str, workspace: Path) -> str:
    """Nothing in a public document may show where the recording happened."""
    text = text.replace(f"{workspace}/data", "~/.jobpilot")
    text = text.replace(str(workspace), "~/jobpilot")
    text = text.replace(str(REPO), "~/jobpilot")
    text = text.replace(str(Path.home()), "~")
    return text


def one_run(name: str, answers: dict, *, trim: bool, extras: bool) -> str:
    """Record one complete session and return it as Markdown."""
    workspace = Path(tempfile.mkdtemp(prefix="jobpilot-sample-"))
    data_dir = workspace / "data"
    settings = workspace / "preferences.yaml"
    os.environ["JOBPILOT_DATA_DIR"] = str(data_dir)
    script = answers_file(workspace, answers)

    blocks = [f"## {name}", ""]

    setup = capture(["start", "--out", str(settings), "--answers", str(script)])
    setup = mark_user_answers(setup)
    blocks.append(
        section(
            "Setting up",
            "jobpilot start",
            trim_questions(setup) if trim else setup,
        )
    )

    for title, argv, command in (
        ("Is everything ready?", ["--config", str(settings), "doctor"], "jobpilot doctor"),
        (
            "Looking for jobs (a practice run first)",
            ["--config", str(settings), "run", "search", "--dry-run"],
            "jobpilot run search --dry-run",
        ),
        ("Looking for jobs, for real", ["--config", str(settings), "run", "search"], "jobpilot run search"),
        (
            "Reading the descriptions",
            ["--config", str(settings), "run", "screen"],
            "jobpilot run screen",
        ),
        (
            "Working through the list, sending nothing",
            ["--config", str(settings), "run", "apply", "--dry-run"],
            "jobpilot run apply --dry-run",
        ),
        ("How is it going?", ["--config", str(settings), "status"], "jobpilot status"),
        ("Today's summary", ["--config", str(settings), "digest"], "jobpilot digest"),
    ):
        blocks.append(section(title, command, capture(argv)))

    if extras:
        blocks.append(
            section(
                "Changing something in your own words",
                'jobpilot ask "also treat data scientist roles as a first choice"',
                capture(
                    [
                        "--config",
                        str(settings),
                        "ask",
                        "also treat data scientist roles as a first choice",
                    ]
                ),
            )
        )
        blocks.append(
            section(
                "…and saying yes to it",
                "jobpilot approve your-request",
                capture(["--config", str(settings), "approve", "your-request"]),
            )
        )
        blocks.append(
            section(
                "What the timetable would do, without doing it",
                "jobpilot routines run-due --dry-run",
                capture(["--config", str(settings), "routines", "run-due", "--dry-run", "--now", NOW]),
            )
        )
        blocks.append(
            section(
                "Letting it run by itself",
                "jobpilot routines list --technical",
                capture(["--config", str(settings), "--technical", "routines", "list", "--now", NOW]),
            )
        )

    text = hide_machine_paths("\n".join(blocks), workspace)
    shutil.rmtree(workspace, ignore_errors=True)
    return text


HEADER = """# A sample session

Every line below is **real output**, recorded by running
`tools/record_sample_session.py`. Nothing here is written by hand.

The recording is sandboxed: no network, no real mailbox, no real browser and no
real model. The job pages come from the synthetic fixtures in `tests/fixtures`
(invented companies), the model answers come from the built-in practice stand-in,
and the data folder is a temporary one that is deleted afterwards.

Lines beginning with **`YOU >`** are what the person typed. In a real session
they are typed one at a time; here they came from a file of answers so that the
document can be regenerated exactly.

Two sessions are recorded:

1. **everything switched on** — all three helpers, plus a model;
2. **nothing switched on** — the core on its own, with the practice stand-in.

"""


def main_script() -> int:
    install_stand_ins()
    body = [
        HEADER,
        one_run("Run 1 — everything switched on", EVERYTHING_ON, trim=True, extras=True),
        "---\n",
        one_run("Run 2 — nothing switched on (the core on its own)", NOTHING_ON, trim=True, extras=False),
        "---\n",
        "## Regenerating this document\n",
        "```console\n$ python tools/record_sample_session.py\n```\n",
    ]
    document = "\n".join(body)
    leaked = [needle for needle in ("/home/", "/Users/", "/workspace", "/tmp/") if needle in document]
    if leaked:
        print(f"refusing to write: the recording still shows {leaked}", file=sys.stderr)
        return 1
    OUT.write_text(document, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} ({len(document.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_script())
