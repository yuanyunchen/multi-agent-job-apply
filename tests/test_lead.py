from __future__ import annotations

import pytest
import yaml

from jobpilot.config import load
from jobpilot.errors import JobpilotError
from jobpilot.lead import apply_proposal, metrics, proposals, render_proposals
from jobpilot.tracker import Tracker


def submitted(n: int) -> list[dict]:
    return [{"job_id": f"s{i}", "status": "submitted"} for i in range(n)]


def test_metrics_come_from_the_record():
    rows = [
        *submitted(3),
        {"job_id": "a", "status": "applied", "receipt": {"mail_id": "m", "basis": "b"}},
        {"job_id": "b", "status": "blocked", "ats": "workday"},
        {"job_id": "c", "status": "parked", "pending_questions": ["Referral code?"]},
        {"job_id": "d", "status": "pipeline", "apply_tier": "core"},
    ]
    numbers = metrics(rows, dead_sources=["lever"], empty_queue_days=3, idle_lane_minutes=90)
    assert numbers.confirmed == 1
    assert numbers.sent_waiting == 3
    assert numbers.unconfirmed_rate == 0.75
    assert numbers.queue_core == 1
    assert numbers.blocks_by_host == {"workday": 1}
    assert numbers.parked_questions == ["Referral code?"]
    assert numbers.dead_sources == ["lever"]


def test_a_low_confirmation_rate_becomes_a_suggestion(config):
    items = proposals(metrics(submitted(4)), config)
    confirm = next(p for p in items if p.id == "confirm_rate_low")
    assert confirm.needs_approval is True
    assert "never came back" in confirm.evidence
    assert confirm.expected_effect
    assert "May I" in confirm.text


def test_an_empty_queue_becomes_a_suggestion_to_widen(config):
    items = proposals(metrics([], empty_queue_days=3), config)
    empty = next(p for p in items if p.id == "queue_empty")
    assert empty.change == {"search.recency_days": config.get("search.recency_days") + 14}


def test_a_source_with_nothing_in_it_becomes_a_suggestion(config):
    items = proposals(metrics([], dead_sources=["lever"]), config)
    dead = next(p for p in items if p.id == "dead_source:lever")
    assert dead.change == {"search.sources.lever.enabled": False}


def test_repeated_blocks_on_one_site_become_a_suggestion(config):
    rows = [{"job_id": str(n), "status": "blocked", "ats": "workday"} for n in range(3)]
    items = proposals(metrics(rows), config)
    assert any(p.id == "repeated_block:workday" for p in items)


def test_idle_capacity_becomes_a_suggestion(config):
    rows = [{"job_id": "a", "status": "pipeline", "apply_tier": "core"}]
    items = proposals(metrics(rows, idle_lane_minutes=120), config)
    idle = next(p for p in items if p.id == "idle_capacity")
    assert idle.change == {"apply.max_lanes": config.get("apply.max_lanes") + 1}


def test_missing_answers_become_a_suggestion(config):
    rows = [
        {"job_id": str(n), "status": "parked", "pending_questions": [f"Question {n}?"]}
        for n in range(3)
    ]
    items = proposals(metrics(rows), config)
    assert any(p.id == "answers_missing" for p in items)


def test_a_healthy_week_suggests_nothing(config):
    rows = [{"job_id": "a", "status": "applied", "receipt": {"mail_id": "m", "basis": "b"}}]
    assert proposals(metrics(rows), config) == []
    assert "Nothing to suggest" in render_proposals([])


def test_suggestions_read_as_questions(config):
    text = render_proposals(proposals(metrics(submitted(4)), config))
    assert text.startswith("One suggestion:")
    assert "Why I am asking:" in text
    assert "What changes:" in text


def test_nothing_changes_without_approval(config):
    proposal = proposals(metrics([], empty_queue_days=3), config)[0]
    with pytest.raises(JobpilotError) as caught:
        apply_proposal(proposal, config, approved=False, approved_by="you")
    assert "needs your say-so" in str(caught.value)


def test_with_approval_the_setting_is_written_and_recorded(make_config, tmp_path):
    path = tmp_path / "preferences.yaml"
    config = make_config(paths={"data_dir": str(tmp_path / "data")})
    path.write_text(yaml.safe_dump(config.data), encoding="utf-8")
    config = load(path)
    tracker = Tracker.from_config(config)

    proposal = proposals(metrics([], empty_queue_days=3), config)[0]
    updated = apply_proposal(
        proposal, config, approved=True, approved_by="you", config_path=str(path), tracker=tracker
    )
    assert updated.get("search.recency_days") == config.get("search.recency_days") + 14
    assert load(path).get("search.recency_days") == updated.get("search.recency_days")
    assert any(event["action"] == "preference_change" for event in tracker.events())
    assert proposal.title in config.paths.changelog.read_text(encoding="utf-8")


def test_a_suggestion_with_nothing_to_change_says_so(config):
    rows = [{"job_id": str(n), "status": "blocked", "ats": "workday"} for n in range(3)]
    proposal = next(p for p in proposals(metrics(rows), config) if p.id == "repeated_block:workday")
    with pytest.raises(JobpilotError) as caught:
        apply_proposal(proposal, config, approved=True, approved_by="you")
    assert "needs a decision from you" in str(caught.value)


def test_an_approved_change_that_would_break_the_settings_is_refused(config):
    from jobpilot.domain import Proposal
    from jobpilot.errors import ConfigError

    broken = Proposal(
        id="silly",
        title="Set an impossible number",
        evidence="none",
        expected_effect="none",
        text="?",
        change={"apply.max_lanes": 0},
    )
    with pytest.raises(ConfigError):
        apply_proposal(broken, config, approved=True, approved_by="you")
