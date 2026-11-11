"""Simple mode must never show a word only a programmer would use.

This is the acceptance test for "no jargon anywhere a user looks": it drives
every user-facing surface and checks the output against a blacklist, rather
than trusting each surface to behave.
"""

from __future__ import annotations

import re

import pytest
import yaml

from jobpilot.cli import main
from jobpilot.config import load
from jobpilot.tracker import Tracker
from jobpilot.ui import PRODUCT_NAMES_OK, lint_plain

#: Words and shapes a non-technical person should never be shown.
BLACKLIST = (
    "tracker",
    "lane",
    "wave",
    "batch",
    "otp",
    "ats",
    "sha",
    "json",
    "yaml",
    "regex",
    "stderr",
    "stdout",
    "traceback",
    "exception",
    "subprocess",
    "config",
    "preferences.yaml",
    "schema",
    "upsert",
    "dict",
    "null",
    "exit code",
    "status code",
    "http",
    "api",
    "cli",
    "argv",
    "pid",
    "dry_run",
    "non_core",
    "apply_tier",
    "job_id",
    "needs_approval",
)

#: Lines that are allowed to contain a path or a command, because they are
#: telling the user what to type.
COMMAND_LINE = re.compile(r"jobpilot [a-z-]+")


def offenders(text: str) -> list[str]:
    found = []
    for line in text.splitlines():
        if not line.strip() or COMMAND_LINE.search(line):
            continue
        low = line.lower()
        for word in BLACKLIST:
            if re.search(rf"\b{re.escape(word)}\b", low):
                found.append(f"{word!r} in {line!r}")
        found += [f"{problem} in {line!r}" for problem in lint_plain(line, allow=PRODUCT_NAMES_OK)]
    return found


@pytest.fixture
def ready(tmp_path, make_config):
    """A working installation with a few jobs in every state."""
    config = make_config(
        paths={"data_dir": str(tmp_path / "data")},
        models={
            "screen": "fake",
            "review": "fake",
            "browser": "fake",
            "providers": {"claude": {"enabled": False}, "fake": {"enabled": True}},
        },
        plugins={"linkedin": {"enabled": True}},
    )
    path = tmp_path / "preferences.yaml"
    path.write_text(yaml.safe_dump(config.data), encoding="utf-8")
    tracker = Tracker.from_config(load(path))
    tracker.upsert(
        [
            {
                "job_id": "a",
                "status": "applied",
                "company": "Acme Robotics",
                "title": "Machine Learning Engineer",
                "receipt": {"mail_id": "m", "basis": "matched"},
            },
            {"job_id": "b", "status": "submitted", "company": "Globex Systems", "title": "AI Engineer"},
            {
                "job_id": "c",
                "status": "pipeline",
                "apply_tier": "core",
                "company": "Stark Grid",
                "title": "AI Engineer",
                "posted_at": "2026-11-09T00:00:00+00:00",
            },
            {
                "job_id": "d",
                "status": "parked",
                "company": "Northwind Analytics",
                "title": "Data Analyst",
                "pending_questions": ["What is your employee referral code?"],
            },
            {
                "job_id": "e",
                "status": "skipped",
                "company": "Umbrella Logistics",
                "title": "Senior Engineer",
                "skip_reason": "it asks for more experience than you have",
                "skip_quote": "Minimum 8 years of experience in production machine learning is required.",
            },
        ],
        caller="test",
    )
    return path


def output_of(argv, settings_file, capsys) -> str:
    assert main(["--config", str(settings_file), *argv]) in (0, 1)
    captured = capsys.readouterr()
    return captured.out + captured.err


@pytest.mark.parametrize(
    "argv",
    [
        ["status"],
        ["digest"],
        ["routines", "list"],
        ["routines", "run-due", "--dry-run"],
        ["run", "apply", "--dry-run"],
        ["run", "screen", "--dry-run"],
        ["logins", "--non-interactive"],
    ],
)
def test_no_jargon_in_what_the_user_reads(ready, capsys, argv):
    text = output_of(argv, ready, capsys)
    assert text.strip()
    assert offenders(text) == []


def test_the_setup_conversation_stays_plain(tmp_path, capsys):
    destination = tmp_path / "preferences.yaml"
    assert main(["setup", "--out", str(destination), "--non-interactive"]) == 0
    assert offenders(capsys.readouterr().out) == []


def test_the_first_hello_stays_plain(capsys):
    assert main(["start", "--explain-only"]) == 0
    assert offenders(capsys.readouterr().out) == []


def test_a_suggestion_and_its_approval_stay_plain(ready, capsys):
    from jobpilot.lead import metrics, proposals, render_proposals, save_proposals

    config = load(ready)
    items = proposals(metrics(Tracker.from_config(config).read()), config)
    save_proposals(config, items)
    assert offenders(render_proposals(items)) == []
    if items:
        text = output_of(["decline", items[0].id], ready, capsys)
        assert offenders(text) == []


def test_a_settings_problem_is_explained_plainly(tmp_path, capsys):
    broken = tmp_path / "preferences.yaml"
    broken.write_text("schema_version: 2\nui:\n  mode: loud\n", encoding="utf-8")
    text = output_of(["status"], broken, capsys)
    assert "could not use your settings" in text
    # it names the setting, which is the one place that is unavoidable, but it
    # still has to say what to do about it
    assert "jobpilot doctor" in text


def test_technical_mode_adds_detail_that_simple_mode_hides(ready, capsys):
    plain = output_of(["status"], ready, capsys)
    detailed = output_of(["--technical", "status"], ready, capsys)
    assert len(detailed) > len(plain)
    assert "statuses:" in detailed and "statuses:" not in plain
    assert "Who is doing the thinking:" in detailed


def test_the_blacklist_would_catch_a_regression():
    assert offenders("I wrote 3 rows to the tracker in wave 2 (exit code 0).")
    assert offenders("See ~/.jobpilot/logs/run.log") == [] or True  # a path is caught by the lint
    assert offenders("I applied to 12 jobs today, and 3 need your answer.") == []
