"""The hourly health check. Nothing here changes anything; it only notices."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jobpilot.watch import (
    freshly_found,
    in_quiet_hours,
    last_submit_from_rows,
    last_tick,
    login_states_from_disk,
    record,
    tick,
)

NOW = datetime(2026, 11, 10, 14, 0, tzinfo=timezone.utc)


def queued(job_id: str = "job-1") -> dict:
    return {
        "job_id": job_id,
        "status": "pipeline",
        "apply_tier": "core",
        "url": f"https://example.test/{job_id}",
    }


def sent(job_id: str, *, minutes_ago: int = 5, receipt: bool = False) -> dict:
    row = {
        "job_id": job_id,
        "status": "submitted",
        "url": f"https://example.test/{job_id}",
        "submit_proof_at": (NOW - timedelta(minutes=minutes_ago)).isoformat(),
    }
    if receipt:
        row["receipt"] = {"mail_id": "m-1", "basis": "sender", "matched_at": NOW.isoformat()}
    return row


def codes(result) -> list[str]:
    return [alert.code for alert in result.alerts]


# -- a healthy system -----------------------------------------------------


def test_a_healthy_system_says_so_and_raises_nothing(config):
    result = tick(config, rows=[queued()], found_recently=3, moment=NOW)
    assert result.healthy
    assert result.words() == "Everything is moving as it should."
    assert len(result.checked) == 5, "every check runs, healthy or not"


# -- the five checks ------------------------------------------------------


def test_jobs_found_that_never_reached_the_list(config):
    result = tick(config, rows=[], found_recently=42, moment=NOW)
    assert codes(result) == ["queue_leak"]
    assert "42" in result.alerts[0].detail


def test_a_batch_that_stopped_moving(config):
    result = tick(
        config,
        rows=[queued()],
        pin_outstanding=5,
        pin_progress_at=NOW - timedelta(hours=2),
        moment=NOW,
    )
    assert "batch_stuck" in codes(result)


def test_a_batch_that_is_still_moving_is_left_alone(config):
    result = tick(
        config,
        rows=[queued()],
        pin_outstanding=5,
        pin_progress_at=NOW - timedelta(minutes=2),
        moment=NOW,
    )
    assert "batch_stuck" not in codes(result)


def test_sitting_idle_while_jobs_wait(config):
    result = tick(config, rows=[queued()], last_submit_at=NOW - timedelta(hours=4), moment=NOW)
    assert "idle_with_work" in codes(result)


def test_sitting_idle_with_nothing_to_do_is_fine(config):
    result = tick(config, rows=[], last_submit_at=NOW - timedelta(hours=4), moment=NOW)
    assert "idle_with_work" not in codes(result)


def test_a_sign_in_that_stopped_working_is_the_users_to_fix(config):
    result = tick(config, rows=[queued()], login_states={"linkedin": "needs_help"}, moment=NOW)
    alert = next(a for a in result.alerts if a.code == "login:linkedin")
    assert alert.needs_user
    assert "sign in again" in alert.detail
    assert "everything else keeps running" in alert.detail
    assert "cannot sort out myself" in result.words()


def test_a_sign_in_left_for_later_is_not_a_problem(config):
    result = tick(config, rows=[queued()], login_states={"linkedin": "skipped"}, moment=NOW)
    assert result.healthy


def test_confirmations_drying_up_is_noticed(config):
    rows = [sent(f"job-{n}") for n in range(8)]
    result = tick(config, rows=rows, last_submit_at=NOW, moment=NOW)
    alert = next(a for a in result.alerts if a.code == "confirmations_low")
    assert "added a step" in alert.detail


def test_a_couple_of_unconfirmed_applications_is_not_a_pattern(config):
    result = tick(config, rows=[sent("job-1"), sent("job-2")], last_submit_at=NOW, moment=NOW)
    assert "confirmations_low" not in codes(result)


def test_confirmed_applications_do_not_count_against_the_rate(config):
    rows = [sent(f"job-{n}", receipt=True) for n in range(8)]
    result = tick(config, rows=rows, last_submit_at=NOW, moment=NOW)
    assert "confirmations_low" not in codes(result)


# -- quiet hours ----------------------------------------------------------


def test_nothing_is_raised_during_quiet_hours(make_config):
    config = make_config(watch={"quiet_hours_start": "13:00", "quiet_hours_end": "15:00"})
    result = tick(config, rows=[], found_recently=42, moment=NOW)
    assert result.healthy
    assert "quiet hours" in result.checked[0]


def test_quiet_hours_may_cross_midnight(make_config):
    config = make_config(watch={"quiet_hours_start": "22:00", "quiet_hours_end": "07:00"})
    assert in_quiet_hours(config, NOW.replace(hour=23)) is True
    assert in_quiet_hours(config, NOW.replace(hour=3)) is True
    assert in_quiet_hours(config, NOW.replace(hour=14)) is False


def test_no_quiet_hours_configured_means_always_awake(config):
    assert in_quiet_hours(config, NOW) is False


# -- the thresholds are the user's ---------------------------------------


def test_the_idle_threshold_is_configurable(make_config):
    patient = make_config(watch={"idle_minutes": 600})
    result = tick(patient, rows=[queued()], last_submit_at=NOW - timedelta(hours=4), moment=NOW)
    assert "idle_with_work" not in codes(result)


# -- reading the surroundings --------------------------------------------


def test_a_tick_is_written_to_the_health_log_and_read_back(config):
    result = tick(config, rows=[], found_recently=9, moment=NOW)
    path = record(config, result)
    assert path.exists()
    again = last_tick(config)
    assert again is not None
    assert codes(again) == ["queue_leak"]


def test_the_health_log_does_not_grow_without_limit(config):
    for _ in range(12):
        record(config, tick(config, rows=[], moment=NOW), keep=5)
    path = config.paths.logs / "health.jsonl"
    assert len([line for line in path.read_text(encoding="utf-8").splitlines() if line]) == 5


def test_no_health_log_yet_is_not_an_error(config):
    assert last_tick(config) is None


def test_the_last_sign_in_walk_is_read_from_disk(config):
    from jobpilot.logins import Checklist, Result

    checklist = Checklist(config)
    checklist.results = [Result("linkedin", "needs_help", "it signed you out")]
    checklist.save()
    assert login_states_from_disk(config) == {"linkedin": "needs_help"}


def test_no_sign_in_walk_yet_means_nothing_to_report(config):
    assert login_states_from_disk(config) == {}


def test_when_something_last_went_out(config):
    rows = [sent("job-1", minutes_ago=90), sent("job-2", minutes_ago=5)]
    assert last_submit_from_rows(rows) == NOW - timedelta(minutes=5)
    assert last_submit_from_rows([queued()]) is None


def test_how_many_jobs_arrived_recently(config):
    from jobpilot.domain import iso, now

    rows = [
        {**queued("a"), "added_at": iso(now())},
        {**queued("b"), "added_at": iso(now() - timedelta(days=9))},
        {**queued("c")},  # no date at all
    ]
    assert freshly_found(rows) == 1
