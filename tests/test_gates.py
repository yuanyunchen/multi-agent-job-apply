from __future__ import annotations

import pytest

from jobpilot.errors import GateBlocked, NeedsUser
from jobpilot.gates import AnswerBank, LaneGuard, OutboundGate, is_password_reset

ANSWERS = """
answers:
  - id: work_authorization
    match: ["authorized to work"]
    answer: "Yes"
  - id: start_date
    match: ["earliest start"]
    answer: "2027-06-01"
always_ask:
  - "social security"
"""


@pytest.fixture
def bank(tmp_path):
    path = tmp_path / "answers.yaml"
    path.write_text(ANSWERS, encoding="utf-8")
    return AnswerBank.from_file(path)


def test_an_answer_comes_from_the_users_own_file(bank):
    assert bank.answer_or_ask("Are you authorized to work in the United States?") == "Yes"
    assert bank.answer_or_ask("What is your earliest start date?") == "2027-06-01"


def test_an_unknown_question_stops_and_asks_rather_than_guessing(bank):
    with pytest.raises(NeedsUser) as caught:
        bank.answer_or_ask("How did you hear about this role?")
    assert caught.value.question == "How did you hear about this role?"
    assert "I need your answer" in str(caught.value)


def test_personal_identifiers_always_wait_for_the_user(bank):
    assert bank.lookup("Please provide your social security number") is None


def test_a_missing_answer_file_is_not_an_error(tmp_path):
    empty = AnswerBank.from_file(tmp_path / "nope.yaml")
    assert empty.lookup("anything") is None


def test_a_whole_form_is_answered_in_one_go(bank):
    answers, unknown = bank.answer_all(
        ["Are you authorized to work here?", "What is your earliest start date?", "Favourite colour?"]
    )
    assert answers == {
        "Are you authorized to work here?": "Yes",
        "What is your earliest start date?": "2027-06-01",
    }
    assert unknown == ["Favourite colour?"]


def test_the_example_answer_file_in_the_repository_loads():
    from jobpilot.config import repo_root

    bank = AnswerBank.from_file(repo_root() / "config" / "answers.example.yaml")
    assert bank.lookup("Are you authorized to work in the US?") is not None
    assert bank.lookup("Please enter your date of birth") is None


# -- the outbound gate ---------------------------------------------------


def test_nothing_goes_out_without_permission(config):
    gate = OutboundGate(config)
    result = gate.check("submit_applications")
    assert result.allowed is False and result.code == "not_permitted"
    assert "permission" in result.reason


def test_permission_alone_is_enough_for_an_ordinary_submit(make_config):
    config = make_config(permissions={"submit_applications": True})
    assert OutboundGate(config).check("submit_applications").allowed is True


def test_a_pause_file_stops_everything(make_config, tmp_path):
    config = make_config(permissions={"submit_applications": True})
    pause = tmp_path / "PAUSED"
    pause.write_text("", encoding="utf-8")
    gate = OutboundGate(config, pause_file=pause)
    assert gate.check("submit_applications").code == "paused"


def test_a_password_reset_is_refused_outright(make_config):
    config = make_config(permissions={"submit_applications": True})
    gate = OutboundGate(config)
    result = gate.check("submit_applications", context={"page_text": "Forgot password? Reset it here."})
    assert result.code == "password_reset"
    assert is_password_reset("Please reset your password") is True


def test_a_public_comment_may_not_mention_work_permits(make_config):
    config = make_config(permissions={"post_public_comments": True})
    gate = OutboundGate(config)
    blocked = gate.check("post_public_comments", text="Great post! I need visa sponsorship though.")
    assert blocked.code == "banned_phrase"
    allowed = gate.check("post_public_comments", text="Great post — the part about forecasting is spot on.")
    assert allowed.allowed is True


def test_wording_changed_after_approval_is_not_sent(make_config):
    config = make_config(permissions={"send_outreach_messages": True})
    gate = OutboundGate(config)
    result = gate.check(
        "send_outreach_messages", text="Hello there", context={"approved_text": "Hello there!"}
    )
    assert result.code == "text_changed"


def test_an_over_long_message_is_refused(make_config):
    config = make_config(permissions={"send_outreach_messages": True})
    gate = OutboundGate(config, max_chars=10)
    assert gate.check("send_outreach_messages", text="x" * 11).code == "too_long"


def test_a_plugin_can_add_its_own_check(make_config):
    from jobpilot.gates import GateResult

    config = make_config(permissions={"send_outreach_messages": True})
    gate = OutboundGate(
        config,
        checks={"send_outreach_messages": lambda text, ctx: GateResult(False, "weekly_cap", "That is enough for this week.")},
    )
    assert gate.check("send_outreach_messages", text="hi").code == "weekly_cap"


def test_a_blocked_result_can_be_turned_into_a_stop(config):
    with pytest.raises(GateBlocked) as caught:
        OutboundGate(config).check("submit_applications").raise_if_blocked()
    assert caught.value.code == "not_permitted"


# -- lanes ---------------------------------------------------------------


def test_only_as_many_at_once_as_the_settings_allow(make_config):
    config = make_config(apply={"max_lanes": 2, "min_free_memory_mb": 0})
    guard = LaneGuard.from_config(config, probe=lambda: 100_000)
    assert guard.admit(running=0).allowed is True
    assert guard.admit(running=2).code == "at_capacity"


def test_memory_is_checked_as_a_projection_not_as_what_is_free_now(make_config):
    config = make_config(
        apply={"max_lanes": 3, "min_free_memory_mb": 1500, "projected_memory_per_lane_mb": 1200}
    )
    guard = LaneGuard.from_config(config, probe=lambda: 2800)
    assert guard.admit(running=0).allowed is True  # 2800 - 1200 >= 1500
    assert guard.admit(running=1).code == "low_memory"  # 2800 - 2400 < 1500
    assert "low on memory" in guard.admit(running=1).reason


def test_the_number_of_lanes_available_is_reported(make_config):
    config = make_config(
        apply={"max_lanes": 3, "min_free_memory_mb": 500, "projected_memory_per_lane_mb": 1000}
    )
    guard = LaneGuard.from_config(config, probe=lambda: 2600)
    assert guard.lanes_available() == 2


def test_memory_can_be_read_from_this_machine_without_crashing():
    from jobpilot.gates import memory_available_mb

    assert memory_available_mb() > 0
