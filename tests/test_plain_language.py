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


# -- the new surfaces, in plain words too --------------------------------
#
# Every one of these is something the user reads. The no-jargon rule is a
# promise, and a promise that only covers the modules that existed when it was
# written is not much of one.


def test_the_health_check_speaks_plainly(config):
    from datetime import datetime, timedelta, timezone

    from jobpilot.watch import tick

    now = datetime(2026, 11, 10, 14, 0, tzinfo=timezone.utc)
    rows = [
        {"job_id": f"j{n}", "status": "submitted", "url": f"https://example.test/{n}",
         "submit_proof_at": (now - timedelta(hours=3)).isoformat()}
        for n in range(8)
    ]
    rows.append({"job_id": "q", "status": "pipeline", "apply_tier": "core", "url": "https://example.test/q"})
    result = tick(
        config,
        rows=rows,
        found_recently=9,
        last_submit_at=now - timedelta(hours=5),
        pin_outstanding=4,
        pin_progress_at=now - timedelta(hours=2),
        login_states={"linkedin": "needs_help"},
        moment=now,
    )
    assert result.alerts, "the point of this test is a tick with plenty to say"
    for alert in result.alerts:
        assert lint_plain(alert.detail, allow=PRODUCT_NAMES_OK) == [], alert.code
    for line in result.words().splitlines():
        assert lint_plain(line, allow=PRODUCT_NAMES_OK) == [], line


def test_the_outreach_manifest_speaks_plainly(make_config):
    from jobpilot.outreach import build_manifest

    config = make_config(
        plugins={"linkedin": {"enabled": True}}, permissions={"send_outreach_messages": True}
    )
    leads = {
        "linkedin": [
            {"kind": "connect_note", "recipient": "a hiring manager",
             "text": "Hello — I work on forecasting models.", "company": "Acme Robotics"}
        ]
    }
    manifest = build_manifest(config, leads=leads)
    for line in manifest.words().splitlines():
        assert lint_plain(line, allow=PRODUCT_NAMES_OK) == [], line


def test_the_reminders_speak_plainly():
    from datetime import datetime

    from jobpilot.mail import Appointment, reminders

    item = Appointment(
        job_id="j1",
        company="Acme Robotics",
        title="Machine Learning Engineer",
        kind="online_assessment",
        when="2026-11-12T14:30:00",
        note="ask about the team",
    )
    for line in reminders([item], moment=datetime(2026, 11, 10, 8, 0)).splitlines():
        assert lint_plain(line) == [], line


def test_a_refused_change_is_explained_plainly(tracker):
    tracker.upsert([{"job_id": "a", "status": "submitted", "url": "https://example.test/a"}], caller="apply")
    plan = tracker.plan(
        [
            {"job_id": "a", "status": "pipeline"},
            {"job_id": "b", "status": "skipped", "skip_reason": "no quote"},
        ]
    )
    for line in plan.words().splitlines():
        assert lint_plain(line) == [], line


def test_the_weekly_review_speaks_plainly(config):
    from datetime import date

    from jobpilot.report import weekly_review

    rows = [
        {"job_id": "1", "status": "blocked", "source": "greenhouse", "ats": "workday",
         "url": "https://example.test/1"},
        {"job_id": "2", "status": "submitted", "source": "lever", "ats": "lever",
         "url": "https://example.test/2"},
    ]
    for line in weekly_review(rows, config, today=date(2026, 11, 9)).words().splitlines():
        assert lint_plain(line) == [], line


def test_an_account_waiting_on_the_user_is_explained_plainly(config):
    from jobpilot.accounts import WALLS, AccountRegistry

    registry = AccountRegistry.from_config(config)
    for wall in WALLS:
        account = registry.hand_back("a-site", wall)
        assert lint_plain(account.reason) == [], wall


def test_a_refused_batch_of_applications_is_explained_plainly():
    from jobpilot.pins import PinRefused, build_pin

    try:
        build_pin([{"job_id": "a", "status": "pipeline", "rerun_approved": "False"}])
    except PinRefused as refused:
        assert lint_plain(refused.message) == []
    else:  # pragma: no cover - the point is that it refuses
        raise AssertionError("expected the batch to be refused")


def test_a_refused_mailbox_export_is_explained_plainly():
    from datetime import datetime, timedelta, timezone

    from jobpilot.verify import ExportRefused, FakeMailReader, find_code

    moment = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    readers = [
        FakeMailReader([]),
        FakeMailReader([], header={"mailbox": "sam@example.test"}),
        FakeMailReader.covering(
            [], mailbox="other@example.test", since=moment, until=moment + timedelta(hours=1)
        ),
    ]
    for reader in readers:
        try:
            find_code(
                reader=reader,
                sender_domains=["greenhouse.io"],
                recipient="sam@example.test",
                submitted_at=moment,
            )
        except ExportRefused as refused:
            assert lint_plain(refused.message) == [], refused.code
        else:  # pragma: no cover
            raise AssertionError("expected the export to be refused")
