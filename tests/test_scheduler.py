from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from jobpilot.routines import Routine
from jobpilot.scheduler import ACTIONS, State, due, is_due, run_due

MONDAY_8AM = datetime(2026, 11, 9, 8, 0, tzinfo=timezone.utc)
SATURDAY_8AM = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)


def at(time_text="08:00", days="mon-fri", name="daily_email", what="report.digest"):
    return Routine(name=name, schedule={"at": time_text, "days": days}, what=what, description="")


def window(text="09:30-18:00", days="mon-fri", every_minutes=None, name="apply"):
    schedule = {"window": text, "days": days}
    if every_minutes:
        schedule["every_minutes"] = every_minutes
    return Routine(name=name, schedule=schedule, what="apply.pass", description="")


def every(text="2 hours", name="mail"):
    return Routine(name=name, schedule={"every": text, "days": "daily"}, what="verify.receipt_sweep", description="")


# -- when is something due ----------------------------------------------


def test_a_daily_time_is_due_once_that_day():
    assert is_due(at(), None, MONDAY_8AM) is True
    assert is_due(at(), MONDAY_8AM, MONDAY_8AM + timedelta(minutes=5)) is False
    assert is_due(at(), MONDAY_8AM, MONDAY_8AM + timedelta(days=1)) is True


def test_a_daily_time_is_not_due_before_it():
    assert is_due(at("08:00"), None, MONDAY_8AM - timedelta(minutes=1)) is False


def test_a_late_start_still_runs_that_day():
    assert is_due(at("08:00"), None, MONDAY_8AM + timedelta(hours=6)) is True


def test_days_are_respected():
    assert is_due(at(days="mon-fri"), None, SATURDAY_8AM) is False
    assert is_due(at(days="daily"), None, SATURDAY_8AM) is True
    assert is_due(at(days="sat-sun"), None, SATURDAY_8AM) is True
    assert is_due(at(days="mon"), None, MONDAY_8AM) is True
    assert is_due(at(days="tue,wed"), None, MONDAY_8AM) is False


def test_a_window_repeats_while_it_is_open():
    inside = MONDAY_8AM.replace(hour=10)
    assert is_due(window(), None, inside) is True
    assert is_due(window(), inside, inside + timedelta(minutes=10)) is False
    assert is_due(window(), inside, inside + timedelta(minutes=61)) is True
    assert is_due(window(), None, MONDAY_8AM.replace(hour=19)) is False


def test_a_window_can_choose_its_own_spacing():
    inside = MONDAY_8AM.replace(hour=10)
    assert is_due(window(every_minutes=15), inside, inside + timedelta(minutes=16)) is True
    assert is_due(window(every_minutes=15), inside, inside + timedelta(minutes=5)) is False


def test_a_window_may_cross_midnight():
    overnight = window("22:00-07:00", days="daily")
    assert is_due(overnight, None, MONDAY_8AM.replace(hour=23)) is True
    assert is_due(overnight, None, MONDAY_8AM.replace(hour=3)) is True
    assert is_due(overnight, None, MONDAY_8AM.replace(hour=12)) is False


def test_an_interval_waits_out_its_interval():
    assert is_due(every("2 hours"), None, MONDAY_8AM) is True
    assert is_due(every("2 hours"), MONDAY_8AM, MONDAY_8AM + timedelta(hours=1)) is False
    assert is_due(every("2 hours"), MONDAY_8AM, MONDAY_8AM + timedelta(hours=2)) is True
    assert is_due(every("30 minutes"), MONDAY_8AM, MONDAY_8AM + timedelta(minutes=31)) is True


@pytest.mark.parametrize(
    "schedule",
    [{"at": "nonsense"}, {"at": "25:00"}, {"window": "bad"}, {"every": "soonish"}, {}],
)
def test_a_schedule_i_cannot_read_never_runs(schedule):
    assert is_due(Routine("x", schedule, "report.digest", ""), None, MONDAY_8AM) is False


# -- running what is due -------------------------------------------------


def fake_actions(log: list[str]):
    def make(name):
        def action(config, renderer):
            log.append(name)
            return f"I did {name}."

        return action

    return {what: make(what) for what in ACTIONS}


def test_run_due_runs_the_due_things_and_nothing_else(config, capsys):
    log: list[str] = []
    report = run_due(config, now=MONDAY_8AM, actions=fake_actions(log))
    assert "daily_email" in report.ran
    assert "find_jobs" in report.ran  # 07:30, so it is late but still today's
    assert "weekly_review" not in report.ran  # Monday 10:00, not yet
    assert log


def test_running_twice_in_a_row_does_nothing_the_second_time(config):
    log: list[str] = []
    first = run_due(config, now=MONDAY_8AM, actions=fake_actions(log))
    second = run_due(config, now=MONDAY_8AM + timedelta(minutes=1), actions=fake_actions(log))
    assert first.ran
    assert second.ran == []
    assert second.words() == "Nothing was due just now."


def test_the_next_day_it_runs_again(config):
    log: list[str] = []
    run_due(config, now=MONDAY_8AM, actions=fake_actions(log))
    later = run_due(config, now=MONDAY_8AM + timedelta(days=1), actions=fake_actions(log))
    assert "daily_email" in later.ran


def test_what_it_tells_the_user_is_plain(config):
    from jobpilot.ui import lint_plain

    report = run_due(config, now=MONDAY_8AM, actions=fake_actions([]))
    for line in report.words().splitlines():
        assert lint_plain(line) == [], line


def test_a_practice_run_changes_nothing(config):
    log: list[str] = []
    report = run_due(config, now=MONDAY_8AM, actions=fake_actions(log), dry_run=True)
    assert report.ran and log == []
    assert "(practice)" in report.words()
    # nothing was recorded, so it is still due
    assert run_due(config, now=MONDAY_8AM, actions=fake_actions(log), dry_run=True).ran


def test_one_broken_routine_does_not_stop_the_others(config):
    def angry(config, renderer):
        raise RuntimeError("the kettle exploded")

    actions = {**fake_actions([]), "report.digest": angry}
    report = run_due(config, now=MONDAY_8AM, actions=actions)
    assert ("daily_email", "the kettle exploded") in report.failed
    assert "find_jobs" in report.ran
    assert "did not finish" in report.words()


def test_a_routine_with_nothing_wired_up_is_reported(config):
    report = run_due(config, now=MONDAY_8AM, actions={})
    assert all("nothing is wired up" in why for _name, why in report.failed)
    assert report.ran == []


def test_every_routine_in_the_shipped_timetable_has_something_to_do(config):
    from jobpilot.routines import all_routines

    for routine in all_routines(config):
        assert routine.what in ACTIONS, routine.name


def test_the_record_of_last_runs_survives_a_restart(config):
    log: list[str] = []
    run_due(config, now=MONDAY_8AM, actions=fake_actions(log))
    reloaded = State.load(config)
    assert reloaded.when("daily_email") is not None
    assert due(config, now=MONDAY_8AM + timedelta(minutes=1), state=reloaded) == []


def test_a_damaged_record_of_last_runs_is_simply_ignored(config):
    path = config.paths.ensure().state / "routines.json"
    path.write_text("{not json", encoding="utf-8")
    assert State.load(config).last_run == {}


def test_the_time_the_user_chose_wins_over_the_timetable_file(make_config):
    from jobpilot.routines import all_routines

    config = make_config(notifications={"digest_time": "17:45"})
    digest = next(r for r in all_routines(config) if r.name == "daily_email")
    assert digest.schedule["at"] == "17:45"
    assert "5:45pm" in digest.explain()
    assert is_due(digest, None, MONDAY_8AM.replace(hour=18)) is True
    assert is_due(digest, None, MONDAY_8AM.replace(hour=9)) is False
