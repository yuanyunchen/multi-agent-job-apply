from __future__ import annotations

import json

import pytest

from jobpilot.errors import TrackerRefused
from jobpilot.tracker import Tracker, normalize_status

from . import synthetic as s


def seed(tracker: Tracker, **fields) -> str:
    row = {"job_id": "j1", "status": "pipeline", "company": "Acme Robotics", "title": "ML Engineer"}
    row.update(fields)
    tracker.upsert([row], caller="test")
    return str(row["job_id"])


def test_a_new_job_is_added_once(tracker):
    job = s.job()
    first = tracker.upsert([job.to_row()], caller="search")
    second = tracker.upsert([job.to_row()], caller="search")
    assert first.added == 1
    assert second.added == 0 and second.unchanged == 1
    assert len(tracker.read()) == 1


def test_a_second_url_for_the_same_job_updates_the_same_row(tracker):
    first = s.job(url="https://job-boards.greenhouse.io/acme-robotics/jobs/4001")
    tracker.upsert([first.to_row()], caller="search")
    same_job_other_url = s.job(url="https://boards.greenhouse.io/acmerobotics/jobs/4001")
    tracker.upsert([same_job_other_url.to_row()], caller="search")
    assert len(tracker.read()) == 1


def test_the_file_is_written_atomically_and_left_valid(tracker):
    seed(tracker)
    assert json.loads(tracker.path.read_text(encoding="utf-8"))
    assert not list(tracker.path.parent.glob("*.tmp"))


def test_a_backup_is_kept_before_every_write(tracker):
    seed(tracker)
    seed(tracker, status="review", review_verdict="review")
    backups = list(tracker.backups_dir.glob("applications.json.bak-*"))
    assert len(backups) == 1  # the first write had nothing to back up


def test_backups_are_rotated_and_gzipped(config):
    tracker = Tracker.from_config(config)
    tracker.backups_to_keep = 2
    for n in range(5):
        tracker.upsert([{"job_id": f"j{n}", "status": "pipeline"}], caller="test")
    raw = list(tracker.backups_dir.glob("applications.json.bak-*[0-9]"))
    archives = list(tracker.backups_dir.glob("*.gz"))
    assert len(raw) <= 2
    assert len(archives) == 1  # one per calendar day


def test_every_accepted_change_is_also_an_event(tracker):
    seed(tracker)
    seed(tracker, status="review", review_verdict="review")
    events = list(tracker.events())
    assert [event["action"] for event in events] == ["add", "update"]
    assert all("at" in event for event in events)


def test_the_event_log_is_never_rewritten(tracker):
    seed(tracker)
    before = tracker.events_path.read_text(encoding="utf-8")
    seed(tracker, notes="another note")
    after = tracker.events_path.read_text(encoding="utf-8")
    assert after.startswith(before)


def test_an_unknown_status_is_refused_and_nothing_is_written(tracker):
    seed(tracker)
    with pytest.raises(TrackerRefused) as caught:
        tracker.upsert([{"job_id": "j1", "status": "appliedish"}], caller="test")
    assert caught.value.code == "unknown_status"
    assert tracker.by_id()["j1"]["status"] == "pipeline"


def test_statuses_are_normalised_but_never_guessed():
    assert normalize_status(" Applied-Unverified ") == "applied_unverified"
    assert normalize_status("PIPELINE") == "pipeline"


def test_a_verdict_for_a_whole_batch_is_refused(tracker):
    with pytest.raises(TrackerRefused) as caught:
        tracker.upsert([{"verdict": "pass"}], caller="screen")
    assert caught.value.code == "batch_verdict"


def test_screening_writes_need_a_verdict_per_row(tracker):
    result = tracker.upsert([{"job_id": "j9", "status": "pipeline"}], caller="screen", require_verdict=True)
    assert result.refused == [("j9", "verdict_missing")]
    assert tracker.read() == []


def test_a_skip_needs_a_reason_and_a_quote(tracker):
    refused = tracker.upsert([{"job_id": "j2", "status": "skipped"}], caller="screen")
    assert refused.refused == [("j2", "skip_without_reason")]
    no_quote = tracker.upsert(
        [{"job_id": "j2", "status": "skipped", "skip_reason": "felt wrong"}], caller="screen"
    )
    assert no_quote.refused == [("j2", "skip_without_evidence")]
    accepted = tracker.upsert(
        [
            {
                "job_id": "j2",
                "status": "skipped",
                "skip_reason": "says it will not sponsor",
                "skip_quote": "This position is not eligible for visa sponsorship.",
            }
        ],
        caller="screen",
    )
    assert accepted.added == 1


def test_a_named_company_or_a_closed_posting_may_skip_without_a_quote(tracker):
    result = tracker.upsert(
        [
            {
                "job_id": "j3",
                "status": "skipped",
                "skip_reason": "on your never-apply list",
                "skip_basis": "company_excluded",
            }
        ],
        caller="screen",
    )
    assert result.added == 1


def test_confirmed_needs_a_receipt(tracker):
    seed(tracker, status="submitted")
    refused = tracker.upsert([{"job_id": "j1", "status": "applied"}], caller="mail")
    assert refused.refused == [("j1", "receipt_missing")]
    accepted = tracker.upsert(
        [
            {
                "job_id": "j1",
                "status": "applied",
                "receipt": {"mail_id": "mail-1", "basis": "sender and recipient matched"},
            }
        ],
        caller="mail",
    )
    assert accepted.updated == 1
    assert tracker.by_id()["j1"]["status"] == "applied"


def test_a_job_is_never_applied_to_twice(tracker):
    seed(tracker, status="submitted")
    refused = tracker.upsert([{"job_id": "j1", "status": "claimed"}], caller="apply")
    assert refused.refused == [("j1", "already_applied")]
    assert tracker.already_submitted("j1") is True


def test_re_opening_a_skipped_job_needs_the_users_approval(tracker):
    tracker.upsert(
        [
            {
                "job_id": "j4",
                "status": "skipped",
                "skip_reason": "needed a doctorate",
                "skip_quote": "A PhD required in statistics or a related field.",
            }
        ],
        caller="screen",
    )
    refused = tracker.upsert([{"job_id": "j4", "status": "pipeline"}], caller="search")
    assert refused.refused == [("j4", "reapply_needs_approval")]

    approved = tracker.approve_reapply("j4", approved_by="you", reason="you said the posting changed")
    assert approved.updated == 1
    assert tracker.by_id()["j4"]["status"] == "pipeline"
    assert any(event["action"] == "reapply_approved" for event in tracker.events())


def test_one_lane_at_a_time(tracker):
    seed(tracker)
    assert tracker.claim("j1", "lane-1") is True
    assert tracker.claim("j1", "lane-2") is False
    assert tracker.by_id()["j1"]["claimed_by"] == "lane-1"


def test_a_lane_may_reclaim_its_own_row(tracker):
    seed(tracker)
    assert tracker.claim("j1", "lane-1") is True
    assert tracker.claim("j1", "lane-1") is True


def test_a_confirmed_row_is_protected(tracker):
    tracker.upsert(
        [
            {
                "job_id": "j5",
                "status": "applied",
                "receipt": {"mail_id": "m", "basis": "matched"},
                "interview_note": "ask about the team",
            }
        ],
        caller="mail",
    )
    # Nothing may quietly rewrite what a confirmed row says it is.
    refused = tracker.upsert([{"job_id": "j5", "company": "Somebody Else"}], caller="search")
    assert refused.refused == [("j5", "protected_row")]
    # Putting it back in the queue is refused for an even better reason.
    requeued = tracker.upsert([{"job_id": "j5", "status": "pipeline"}], caller="search")
    assert requeued.refused == [("j5", "already_applied")]
    # notes and outcomes are still allowed
    allowed = tracker.upsert([{"job_id": "j5", "notes": "they replied"}], caller="mail")
    assert allowed.updated == 1
    assert tracker.by_id()["j5"]["interview_note"] == "ask about the team"


def test_overriding_a_guard_requires_a_recorded_reason(tracker):
    tracker.upsert(
        [{"job_id": "j6", "status": "applied", "receipt": {"mail_id": "m", "basis": "matched"}}],
        caller="mail",
    )
    with pytest.raises(TrackerRefused) as caught:
        tracker.upsert([{"job_id": "j6", "status": "pipeline"}], caller="test", force=True)
    assert caught.value.code == "force_without_reason"
    forced = tracker.upsert(
        [{"job_id": "j6", "status": "pipeline"}],
        caller="test",
        force=True,
        force_reason="the employer asked us to re-apply",
    )
    assert forced.updated == 1


def test_notes_are_append_only_and_lists_only_grow(tracker):
    seed(tracker, notes="first", tags=["fresh"], flags=["remote"])
    tracker.upsert([{"job_id": "j1", "notes": "second", "tags": ["core"], "flags": []}], caller="test")
    row = tracker.by_id()["j1"]
    assert row["notes"] == ["first", "second"]
    assert row["tags"] == ["core", "fresh"]
    assert row["flags"] == ["remote"]


def test_two_writers_cannot_overlap(tracker):
    seed(tracker)
    with tracker._lock():
        tracker.lock_timeout_seconds = 0
        with pytest.raises(TrackerRefused) as caught:
            tracker.upsert([{"job_id": "j7", "status": "pipeline"}], caller="test")
    assert caught.value.code == "locked"
    assert "nothing was changed" in str(caught.value)


def test_a_stale_lock_is_taken_over(tracker, monkeypatch):
    tracker.lock_path.parent.mkdir(parents=True, exist_ok=True)
    tracker.lock_path.write_text("999999 stale\n", encoding="utf-8")
    monkeypatch.setattr(Tracker, "_lock_is_stale", lambda self, max_age_seconds=300: True)
    assert tracker.upsert([{"job_id": "j8", "status": "pipeline"}], caller="test").added == 1


def test_unreadable_records_stop_everything_rather_than_guess(tracker):
    tracker.path.parent.mkdir(parents=True, exist_ok=True)
    tracker.path.write_text("{not json", encoding="utf-8")
    with pytest.raises(TrackerRefused) as caught:
        tracker.read()
    assert caught.value.code == "unreadable"
    assert "backup" in str(caught.value)


def test_a_record_shaped_as_an_object_is_also_read(tracker):
    tracker.path.parent.mkdir(parents=True, exist_ok=True)
    tracker.path.write_text(json.dumps({"applications": [{"job_id": "x", "status": "applied"}]}))
    assert tracker.counts() == {"applied": 1}


def test_every_claimed_row_can_be_disposed_of(tracker):
    seed(tracker)
    tracker.claim("j1", "lane-1")
    tracker.dispose("j1", "parked", notes="needs your answer")
    row = tracker.by_id()["j1"]
    assert row["status"] == "parked" and row["claimed_by"] == ""
