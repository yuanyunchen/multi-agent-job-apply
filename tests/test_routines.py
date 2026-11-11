from __future__ import annotations

import pytest

from jobpilot.config import DEFAULT_ROUTINES_PATH, repo_root
from jobpilot.errors import ConfigError
from jobpilot.routines import Routine, all_routines, clock, load_routines, timetable

ROUTINES = """
routines:
  - name: daily_email
    schedule: { at: "08:00", days: mon-fri }
    what: report.digest
    description: "Every weekday at 8am you get one email."
  - name: apply
    schedule: { window: "09:30-18:00", days: mon-fri }
    what: apply.waves
  - name: mail_check
    schedule: { every: "2 hours", days: daily }
    what: verify.receipt_sweep
"""


@pytest.fixture
def routines(tmp_path):
    path = tmp_path / "routines.yaml"
    path.write_text(ROUTINES, encoding="utf-8")
    return load_routines(path)


def test_routines_are_declarative(routines):
    assert [r.name for r in routines] == ["daily_email", "apply", "mail_check"]
    assert routines[0].what == "report.digest"


def test_a_time_is_read_back_the_way_a_person_says_it():
    assert clock("08:00") == "8am"
    assert clock("18:30") == "6:30pm"
    assert clock("00:00") == "12am"
    assert clock("12:00") == "12pm"
    assert clock("nonsense") == "nonsense"


def test_a_schedule_becomes_a_sentence(routines):
    assert routines[0].when_in_words == "every weekday at 8am"
    assert routines[1].when_in_words == "every weekday between 9:30am and 6pm"
    assert routines[2].when_in_words == "every 2 hours"


def test_the_users_own_words_win_when_they_wrote_some(routines):
    assert routines[0].explain() == "Every weekday at 8am you get one email."


def test_without_a_description_one_is_built_from_the_schedule(routines):
    assert routines[1].explain() == "Every weekday between 9:30am and 6pm I run apply."


def test_the_whole_timetable_reads_as_a_list(routines, config):
    text = timetable(routines, config)
    assert text.startswith("- Every weekday at 8am you get one email.")
    assert "All times are" in text


def test_an_empty_timetable_says_so():
    assert timetable([]) == "Nothing is scheduled yet."


def test_a_routine_with_no_time_is_a_friendly_error(tmp_path):
    path = tmp_path / "routines.yaml"
    path.write_text("routines:\n  - name: mystery\n    what: something\n", encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        load_routines(path)
    assert "needs a time" in str(caught.value)


def test_a_missing_file_is_simply_an_empty_timetable(tmp_path):
    assert load_routines(tmp_path / "nope.yaml") == []


def test_the_timetable_shipped_with_the_repository_loads():
    routines = load_routines(repo_root() / DEFAULT_ROUTINES_PATH)
    assert {"find_jobs", "daily_email", "apply"} <= {r.name for r in routines}
    for routine in routines:
        assert routine.description, f"{routine.name} should be explained in the user's words"


def test_plugins_add_their_own_routines_only_when_switched_on(make_config):
    off = all_routines(make_config())
    on = all_routines(make_config(plugins={"linkedin": {"enabled": True}}))
    assert len(on) == len(off) + 1
    added = next(r for r in on if r.name.startswith("linkedin"))
    assert "evening" in added.explain()


def test_a_routine_is_comparable_and_immutable():
    one = Routine("a", {"at": "08:00"}, "x", "")
    with pytest.raises(AttributeError):
        one.name = "b"  # type: ignore[misc]
