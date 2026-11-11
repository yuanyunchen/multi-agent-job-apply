"""Pins and waves: the frozen list, and what happens when a wave dies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from jobpilot.gates import LaneGuard
from jobpilot.pins import (
    Driver,
    Pin,
    PinRefused,
    PinStore,
    build_pin,
    fingerprint,
    watch_handoff,
)

from . import synthetic as s


def row(job_id: str, *, tier: str = "core", days_ago: float = 1, **extra) -> dict:
    return {
        "job_id": job_id,
        "url": f"https://example.test/{job_id}",
        "company": "Acme Robotics",
        "title": "Machine Learning Engineer",
        "status": "pipeline",
        "apply_tier": tier,
        "posted_at": s.iso_days_ago(days_ago),
        **extra,
    }


def lanes(count: int = 2) -> LaneGuard:
    return LaneGuard(
        max_lanes=count, min_free_memory_mb=0, projected_per_lane_mb=0, probe=lambda: 1_000_000
    )


# -- building a pin -------------------------------------------------------


def test_a_pin_freezes_the_queue_in_the_order_it_will_be_worked(config):
    rows = [row("b", tier="non_core"), row("a", days_ago=5), row("c", days_ago=1)]
    pin = build_pin(rows)
    # Core first, newest first; the second-choice job waits.
    assert pin.job_ids == ["c", "a", "b"]


def test_a_pin_is_fingerprinted_over_its_contents(config):
    pin = build_pin([row("a")])
    assert pin.digest == fingerprint(list(pin.rows))
    assert pin.digest[:8] in pin.pin_id


def test_a_pin_whose_contents_changed_refuses_to_be_used(config):
    pin = build_pin([row("a")])
    tampered = Pin(
        pin_id=pin.pin_id,
        created_at=pin.created_at,
        rows=({**pin.rows[0], "job_id": "somebody-else"},),
        digest=pin.digest,
    )
    with pytest.raises(PinRefused) as caught:
        tampered.verify()
    assert caught.value.code == "pin_changed"
    assert "twice" in str(caught.value)


def test_a_pin_carries_only_the_work_order_not_the_whole_record(config):
    rows = [row("a", description="a very long job description", notes=["private"])]
    pin = build_pin(rows)
    assert "description" not in pin.rows[0]
    assert "notes" not in pin.rows[0]
    assert pin.rows[0]["company"] == "Acme Robotics"


def test_a_flag_that_is_the_word_false_is_refused(config):
    """"False" is a true string. A row once got past a guard exactly this way."""
    with pytest.raises(PinRefused) as caught:
        build_pin([row("a", rerun_approved="False")])
    assert caught.value.code == "bad_flags"
    assert "not the shape I expect" in str(caught.value)


def test_a_real_boolean_flag_is_fine(config):
    pin = build_pin([row("a", rerun_approved=True)])
    assert pin.rows[0]["rerun_approved"] is True


def test_a_pin_is_cut_into_waves(config):
    pin = build_pin([row(str(n)) for n in range(5)], wave_size=2)
    assert [len(wave) for wave in pin.waves()] == [2, 2, 1]


# -- storing pins ---------------------------------------------------------


def test_a_pin_is_written_once_and_never_changed(config):
    store = PinStore.from_config(config)
    pin = build_pin([row("a")])
    store.write(pin)
    with pytest.raises(PinRefused) as caught:
        store.write(pin)
    assert caught.value.code == "already_written"


def test_a_stored_pin_comes_back_the_same(config):
    store = PinStore.from_config(config)
    pin = build_pin([row("a"), row("b")])
    store.write(pin)
    assert store.read(pin.pin_id).job_ids == pin.job_ids
    assert store.latest().pin_id == pin.pin_id


def test_reading_a_pin_someone_edited_is_refused(config):
    store = PinStore.from_config(config)
    pin = build_pin([row("a")])
    path = store.write(pin)
    path.write_text(path.read_text().replace('"a"', '"z"'), encoding="utf-8")
    with pytest.raises(PinRefused):
        store.read(pin.pin_id)


# -- handing waves out ----------------------------------------------------


def test_the_driver_hands_every_wave_out_and_records_what_came_back(config):
    pin = build_pin([row(str(n)) for n in range(5)], wave_size=2)
    handled: list[tuple[str, str, int]] = []

    def run_wave(wave, lane, rows):
        handled.append((wave, lane, len(rows)))
        return {str(r["job_id"]): "submitted" for r in rows}

    report = Driver(pin=pin, lanes=lanes(2), run_wave=run_wave).run()
    assert len(handled) == 3
    assert report.disposed == 5
    assert report.counts() == {"submitted": 5}
    assert report.requeued == []


def test_waves_are_spread_across_the_lanes_that_are_free(config):
    pin = build_pin([row(str(n)) for n in range(4)], wave_size=1)
    seen: list[str] = []
    Driver(
        pin=pin,
        lanes=lanes(2),
        run_wave=lambda wave, lane, rows: seen.append(lane) or {},
    ).run()
    assert seen == ["lane-1", "lane-2", "lane-1", "lane-2"]


def test_a_wave_that_dies_hands_its_jobs_back_rather_than_losing_them(config):
    pin = build_pin([row("a"), row("b")], wave_size=2)

    def run_wave(wave, lane, rows):
        raise RuntimeError("the browser went away")

    report = Driver(pin=pin, lanes=lanes(1), run_wave=run_wave).run()
    assert sorted(report.requeued) == ["a", "b"]
    assert report.waves[0].stopped_because


def test_a_wave_that_only_half_finished_hands_back_only_what_it_did_not_reach(config):
    pin = build_pin([row("a"), row("b"), row("c")], wave_size=3)
    report = Driver(
        pin=pin, lanes=lanes(1), run_wave=lambda w, l, rows: {"a": "submitted", "b": "parked"}
    ).run()
    assert report.requeued == ["c"]
    assert report.counts() == {"submitted": 1, "parked": 1}


def test_nothing_new_starts_when_there_is_no_room(config):
    pin = build_pin([row("a")], wave_size=1)
    full = LaneGuard(max_lanes=1, min_free_memory_mb=4000, projected_per_lane_mb=4000, probe=lambda: 100)
    report = Driver(pin=pin, lanes=full, run_wave=lambda w, l, rows: {}).run()
    assert report.stopped_because == "low_memory"
    assert report.requeued == ["a"]
    assert report.disposed == 0


def test_a_stop_file_lets_the_wave_in_flight_finish_and_starts_no_more(config, tmp_path):
    stop = tmp_path / "STOP"
    # Explicit ages, so the order the waves come out in is not a coincidence.
    pin = build_pin([row("a", days_ago=1), row("b", days_ago=2)], wave_size=1)

    def run_wave(wave, lane, rows):
        stop.touch()  # asked to stop while the first wave is running
        return {str(r["job_id"]): "submitted" for r in rows}

    report = Driver(pin=pin, lanes=lanes(1), run_wave=run_wave, stop_file=stop).run()
    assert report.disposed == 1, "the wave that was running finished"
    assert report.requeued == ["b"], "the next one never started"
    assert report.stopped_because == "asked_to_stop"


def test_progress_is_written_so_a_watchdog_can_see_movement(config, tmp_path):
    progress = tmp_path / "progress.jsonl"
    pin = build_pin([row("a")], wave_size=1)
    Driver(
        pin=pin, lanes=lanes(1), run_wave=lambda w, l, rows: {"a": "submitted"}, progress=progress
    ).run()
    assert "\"disposed\": 1" in progress.read_text(encoding="utf-8")


# -- the watchdog ---------------------------------------------------------


def test_a_queue_leak_is_noticed(config):
    problems = watch_handoff([], found_recently=42)
    assert [p.code for p in problems] == ["queue_leak"]
    assert "42" in problems[0].detail


def test_a_full_queue_is_not_a_leak(config):
    assert watch_handoff([row("a")], found_recently=42) == []


def test_a_pin_that_stopped_moving_is_noticed(config):
    pin = build_pin([row("a")])
    long_ago = datetime.now(timezone.utc) - timedelta(hours=3)
    problems = watch_handoff([row("a")], pin=pin, progress_at=long_ago)
    assert [p.code for p in problems] == ["pin_stuck"]


def test_a_pin_that_is_moving_is_left_alone(config):
    pin = build_pin([row("a")])
    assert watch_handoff([row("a")], pin=pin, progress_at=datetime.now(timezone.utc)) == []


def test_jobs_left_half_started_are_noticed(config):
    stale = row("a", status="claimed", claimed_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat())
    problems = watch_handoff([stale])
    assert [p.code for p in problems] == ["claims_expired"]
    assert "half-started" in problems[0].detail


def test_a_job_claimed_a_moment_ago_is_not_abandoned(config):
    fresh = row("a", status="claimed", claimed_at=datetime.now(timezone.utc).isoformat())
    assert watch_handoff([fresh]) == []
