"""Reading the mailbox for outcomes, and the reminders that come out of it."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from jobpilot.mail import (
    Appointment,
    classify,
    find_date,
    reminder_times,
    reminders,
    triage,
    upcoming,
)
from jobpilot.verify import FakeMailReader

from . import synthetic as s

SUBMITTED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
ME = "sam@example.test"

ROW = {
    "job_id": "job-1",
    "company": "Acme Robotics",
    "title": "Machine Learning Engineer",
    "url": "https://job-boards.greenhouse.io/acme-robotics/jobs/4001",
    "status": "submitted",
}


def message(subject: str, body: str = "", **kwargs):
    return s.mail(subject=subject, body=body, submitted_at=SUBMITTED_AT, recipient=ME, **kwargs)


# -- classifying one message ---------------------------------------------


@pytest.mark.parametrize(
    "subject,body,expected",
    [
        ("Your application", "We would like to schedule an interview next week.", "interview"),
        ("Next step", "Please complete the online assessment by Friday.", "online_assessment"),
        ("Good news", "We are pleased to offer you the role.", "offer"),
        ("Your application", "Unfortunately we are not moving forward.", "rejected"),
        ("Hello", "I wanted to reach out about your application.", "recruiter_reply"),
        ("Newsletter", "Here are this week's engineering blog posts.", ""),
    ],
)
def test_what_a_message_is_about(subject, body, expected):
    assert classify(message(subject, body)).outcome == expected


def test_a_classification_always_carries_the_sentence_that_justified_it():
    found = classify(message("Your application", "We would like to schedule an interview next week."))
    assert found.quote == "We would like to schedule an interview next week."


def test_an_interview_beats_a_test_mentioned_in_the_same_message():
    found = classify(
        message(
            "Next steps",
            "First an online assessment. Then we would like to schedule an interview.",
        )
    )
    assert found.outcome == "interview"


def test_a_verification_code_is_never_an_outcome():
    found = classify(message("Your security code", "Your verification code is AB12CD34."))
    assert found.outcome == ""
    assert found.quote == ""


def test_password_reset_mail_is_ignored_entirely():
    assert classify(message("Reset your password", "Click to reset your password.")).outcome == ""


# -- dates ----------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Your interview is on 2026-12-03 at 14:30.", "2026-12-03T14:30:00"),
        ("Interview on 2026-12-03.", "2026-12-03T00:00:00"),
        ("Dec 3, 2026 at 2pm works for us.", "2026-12-03T14:00:00"),
        ("Dec 3 at 9:30am works.", "2026-12-03T09:30:00"),
        ("Soon, we promise.", ""),
    ],
)
def test_finding_the_date_in_a_message(text, expected):
    assert find_date(text, today=date(2026, 11, 10)) == expected


def test_a_date_with_no_year_means_the_next_one_to_come():
    assert find_date("Interview on Jan 5 at 10am.", today=date(2026, 11, 10)).startswith("2027-01-05")


# -- triage ---------------------------------------------------------------


def test_an_interview_becomes_a_tracker_update_and_an_appointment():
    inbox = [
        message(
            "Interview — Acme Robotics",
            "We would like to schedule an interview on 2026-12-03 at 14:30.",
        )
    ]
    result = triage(
        rows=[ROW],
        reader=FakeMailReader(inbox),
        recipient=ME,
        since=SUBMITTED_AT,
        until=SUBMITTED_AT + timedelta(days=1),
        today=date(2026, 11, 10),
    )
    assert len(result.updates) == 1
    update = result.updates[0]
    assert update["job_id"] == "job-1"
    assert update["status"] == "interview"
    assert update["outcome_evidence"]["quote"].startswith("We would like to schedule")
    assert update["outcome_evidence"]["mail_id"]
    assert result.appointments[0].when == "2026-12-03T14:30:00"
    assert "wants to interview you" in result.urgent[0]


def test_an_outcome_that_matches_no_job_is_counted_and_never_written():
    """A message on the record against the wrong job is worse than a missed one."""
    inbox = [
        message(
            "Interview",
            "We would like to schedule an interview.",
            sender="recruiting@somewhere-else.example",
        )
    ]
    result = triage(rows=[ROW], reader=FakeMailReader(inbox), recipient=ME, since=SUBMITTED_AT)
    assert result.updates == []
    assert result.unmatched == 1


def test_the_company_named_in_the_subject_is_enough_to_match():
    inbox = [
        message(
            "Acme Robotics — your application",
            "We would like to schedule an interview.",
            sender="people@talent-partner.example",
        )
    ]
    result = triage(rows=[ROW], reader=FakeMailReader(inbox), recipient=ME, since=SUBMITTED_AT)
    assert result.updates[0]["outcome"] == "interview"
    assert "named in the subject" in result.updates[0]["outcome_evidence"]["basis"]


def test_a_rejection_is_recorded_but_is_not_urgent():
    inbox = [message("Your application", "Unfortunately we are not moving forward.")]
    result = triage(rows=[ROW], reader=FakeMailReader(inbox), recipient=ME, since=SUBMITTED_AT)
    assert result.updates[0]["status"] == "rejected"
    assert result.urgent == []


def test_a_recruiter_reply_is_urgent_but_changes_no_status():
    inbox = [message("Hello", "I wanted to reach out about the role.")]
    result = triage(rows=[ROW], reader=FakeMailReader(inbox), recipient=ME, since=SUBMITTED_AT)
    assert "status" not in result.updates[0]
    assert result.updates[0]["outcome"] == "recruiter_reply"
    assert result.urgent


def test_nothing_interesting_means_nothing_written():
    inbox = [message("Newsletter", "This week in robotics.")]
    result = triage(rows=[ROW], reader=FakeMailReader(inbox), recipient=ME, since=SUBMITTED_AT)
    assert result.read == 1
    assert result.updates == []


# -- reminders ------------------------------------------------------------


def appointment(days: float, kind: str = "interview", note: str = "") -> Appointment:
    when = (datetime(2026, 11, 10, 9, 0) + timedelta(days=days)).isoformat()
    return Appointment(
        job_id="job-1", company="Acme Robotics", title="ML Engineer", kind=kind, when=when, note=note
    )


def test_only_what_is_coming_up_is_reminded_about():
    soon, later = appointment(2), appointment(30)
    chosen = upcoming([later, soon], moment=datetime(2026, 11, 10, 8, 0))
    assert chosen == [soon]


def test_the_soonest_comes_first():
    second, first = appointment(5), appointment(1)
    assert upcoming([second, first], moment=datetime(2026, 11, 10, 8, 0)) == [first, second]


def test_an_appointment_with_no_date_is_still_reminded_about():
    undated = Appointment("job-1", "Acme Robotics", "ML Engineer", "online_assessment", when="")
    text = reminders([undated], moment=datetime(2026, 11, 10, 8, 0))
    assert "a date you have been sent" in text


def test_a_private_note_is_surfaced_in_the_reminder():
    text = reminders([appointment(1, note="ask about the team")], moment=datetime(2026, 11, 10, 8, 0))
    assert "ask about the team" in text


def test_nothing_coming_up_means_no_reminder_at_all():
    assert reminders([], moment=datetime(2026, 11, 10, 8, 0)) == ""


def test_the_reminder_times_come_from_the_settings(make_config):
    config = make_config()
    assert reminder_times(config) == ("09:30", "20:00")
    changed = make_config(notifications={"reminder_times": {"morning": "08:45", "evening": "21:15"}})
    assert reminder_times(changed) == ("08:45", "21:15")
