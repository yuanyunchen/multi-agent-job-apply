from __future__ import annotations

from jobpilot.queue import build_queue, depth, eligible, next_wave

from .synthetic import iso_days_ago


def row(job_id: str, *, tier: str = "core", days_old: float = 1, status: str = "pipeline", **fields):
    out = {
        "job_id": job_id,
        "status": status,
        "apply_tier": tier,
        "posted_at": iso_days_ago(days_old),
    }
    out.update(fields)
    return out


def test_core_comes_first_then_everything_else():
    rows = [row("a", tier="non_core"), row("b", tier="core")]
    assert [r["job_id"] for r in build_queue(rows)] == ["b", "a"]


def test_newest_first_inside_each_group():
    rows = [
        row("old-core", days_old=10),
        row("new-core", days_old=1),
        row("new-other", tier="non_core", days_old=0.5),
        row("old-other", tier="non_core", days_old=20),
    ]
    assert [r["job_id"] for r in build_queue(rows)] == ["new-core", "old-core", "new-other", "old-other"]


def test_jobs_without_a_date_sort_last_but_are_not_dropped():
    rows = [row("undated", posted_at=""), row("dated", days_old=30)]
    assert [r["job_id"] for r in build_queue(rows)] == ["dated", "undated"]


def test_the_other_queue_waits_until_the_first_one_is_empty():
    rows = [row("core-1"), row("other-1", tier="non_core")]
    assert [r["job_id"] for r in next_wave(rows, 10)] == ["core-1"]


def test_the_other_queue_runs_once_there_is_no_core_work():
    rows = [row("other-1", tier="non_core"), row("other-2", tier="non_core", days_old=5)]
    assert [r["job_id"] for r in next_wave(rows, 10)] == ["other-1", "other-2"]


def test_a_wave_is_capped():
    rows = [row(f"j{n}", days_old=n) for n in range(30)]
    assert len(next_wave(rows, 20)) == 20


def test_only_screened_jobs_are_eligible():
    rows = [
        row("new", status="new"),
        row("ready"),
        row("already-out", status="submitted"),
        row("skipped", status="skipped"),
        row("held", status="hold_pending_user"),
        row("parked", status="parked"),
    ]
    assert [r["job_id"] for r in eligible(rows)] == ["ready"]


def test_rows_the_user_asked_to_hold_never_reach_the_queue():
    rows = [row("held", flags=["hold_pending_user"]), row("ready")]
    assert [r["job_id"] for r in build_queue(rows)] == ["ready"]


def test_duplicates_and_unapplyable_rows_are_left_out():
    rows = [row("dup", duplicate_of="other"), row("blocked-site", applyable=False), row("ready")]
    assert [r["job_id"] for r in build_queue(rows)] == ["ready"]


def test_depth_is_reported_per_queue():
    rows = [row("a"), row("b"), row("c", tier="non_core")]
    assert depth(rows) == {"core": 2, "non_core": 1, "total": 3}


def test_an_empty_list_is_not_an_error():
    assert build_queue([]) == [] and next_wave([], 20) == []
    assert depth([]) == {"core": 0, "non_core": 0, "total": 0}
