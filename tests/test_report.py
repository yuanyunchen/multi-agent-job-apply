from __future__ import annotations

from datetime import date

from jobpilot.report import append_reflection, digest, reflection, summarize
from jobpilot.ui import Renderer, lint_plain

from .synthetic import iso_days_ago

TODAY = date(2026, 11, 10)


def rows():
    return [
        {"job_id": "1", "status": "applied", "company": "Acme Robotics", "title": "ML Engineer"},
        {"job_id": "2", "status": "applied", "company": "Globex Systems", "title": "ML Engineer"},
        {"job_id": "3", "status": "submitted", "company": "Stark Grid", "title": "AI Engineer"},
        {
            "job_id": "4",
            "status": "parked",
            "company": "Northwind Analytics",
            "title": "Applied Scientist",
            "pending_questions": ["What is your employee referral code?"],
        },
        {"job_id": "5", "status": "pipeline", "apply_tier": "core", "posted_at": iso_days_ago(1)},
        {"job_id": "6", "status": "pipeline", "apply_tier": "non_core", "posted_at": iso_days_ago(2)},
        {"job_id": "7", "status": "interview", "company": "Acme Robotics", "title": "ML Engineer"},
        {"job_id": "8", "status": "rejected", "company": "Umbrella Logistics", "title": "ML Engineer"},
    ]


def test_the_numbers_are_counted_from_the_record():
    numbers = summarize(rows())
    assert numbers.applied == 2
    assert numbers.sent_waiting == 1
    assert numbers.interviews == 1
    assert numbers.rejections == 1
    assert numbers.queue_core == 1 and numbers.queue_non_core == 1
    assert numbers.needs_you == ["What is your employee referral code?"]


def test_the_digest_is_plain_language(config):
    renderer = Renderer("simple")
    text = digest(rows(), config, renderer, today=TODAY)
    assert "Your job search — Tuesday 10 November" in text
    assert "2 applications confirmed" in text
    assert "Needs you:" in text
    assert "1 interview" in text
    for line in text.splitlines():
        assert lint_plain(line) == [], line


def test_the_digest_never_mentions_rejections_unless_asked(config, make_config):
    quiet = digest(rows(), config, Renderer("simple"), today=TODAY)
    assert "came back" not in quiet
    loud = digest(
        rows(),
        make_config(notifications={"report_rejections": True}),
        Renderer("simple"),
        today=TODAY,
    )
    assert "came back" in loud


def test_the_digest_limits_what_it_asks_of_the_user(config):
    many = [
        {
            "job_id": str(n),
            "status": "parked",
            "pending_questions": [f"Question number {n}?"],
        }
        for n in range(6)
    ]
    text = digest(many, config, Renderer("simple"), today=TODAY, max_needs_you=2)
    assert "and 4 more when you have a minute" in text


def test_a_quiet_day_is_still_a_digest(config):
    text = digest([], config, Renderer("simple"), today=TODAY)
    assert "a quiet day" in text
    assert "look harder for new matches" in text


def test_technical_mode_adds_numbers_a_user_would_not_want(config):
    text = digest(rows(), config, Renderer("technical"), today=TODAY)
    assert "queue core=" in text


def test_a_reflection_is_written_even_on_an_empty_day(tmp_path, config):
    text = reflection([], today=TODAY)
    assert "## 2026-11-10" in text
    assert "confirmed: 0" in text
    append_reflection(config, text)
    assert "## 2026-11-10" in config.paths.reflections.read_text(encoding="utf-8")


def test_a_reflection_records_the_unconfirmed_share():
    text = reflection(rows(), notes="one site kept stopping me", today=TODAY)
    assert "unconfirmed: 1 of 5" in text
    assert "one site kept stopping me" in text
