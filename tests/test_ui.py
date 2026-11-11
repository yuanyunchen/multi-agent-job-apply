from __future__ import annotations

from jobpilot.domain import Message
from jobpilot.ui import Renderer, lint_plain, plural, renderer_for


def test_simple_mode_is_the_default(config):
    assert renderer_for(config).mode == "simple"


def test_simple_mode_shows_only_the_plain_sentence():
    renderer = Renderer("simple")
    message = Message("x", "I applied to 12 jobs today.", technical="queue=/tmp/queue.json lane=2")
    assert renderer.render(message) == "I applied to 12 jobs today."


def test_technical_mode_adds_the_details():
    renderer = Renderer("technical")
    message = Message("x", "I applied to 12 jobs today.", technical="unconfirmed rate 10%")
    assert renderer.render(message) == "I applied to 12 jobs today.\nunconfirmed rate 10%"


def test_jargon_is_caught():
    assert lint_plain("see /home/someone/run.log for details")
    assert lint_plain("the tracker write failed with exit 14")
    assert lint_plain("claude-haiku answered")
    assert lint_plain("lane 2 finished wave 3")
    assert lint_plain("commit a1b2c3d4e5")
    assert lint_plain("job 2f1c8b0e-1111-4222-8333-444455556666 failed")
    assert lint_plain("I applied to 12 jobs today, 3 need your answer.") == []
    assert lint_plain("Two applications are waiting for a confirmation email.") == []


def test_a_message_that_slips_through_is_replaced_not_shown():
    renderer = Renderer("simple")
    message = Message(
        "x",
        "tracker write failed with exit 14",
        fallback="Something went wrong on my side; I will try again.",
    )
    assert renderer.render(message) == "Something went wrong on my side; I will try again."
    assert renderer.violations and renderer.violations[0][0] == "x"


def test_self_optimization_is_one_plain_line():
    renderer = Renderer("simple")
    line = renderer.self_optimization(
        "I now retry the email-code step automatically, so fewer applications get stuck.",
        details="changed the retry budget in the apply driver from 1 to 3",
    )
    assert line == "I now retry the email-code step automatically, so fewer applications get stuck."
    assert "retry budget" not in line


def test_self_optimization_can_be_silent():
    assert Renderer("simple").self_optimization("I tuned something.", notice="none") == ""


def test_self_optimization_in_technical_mode_includes_the_details():
    out = Renderer("technical").self_optimization("I changed a setting.", details="max_lanes 2 -> 3")
    assert "max_lanes 2 -> 3" in out


def test_self_optimization_never_leaks_jargon():
    renderer = Renderer("simple")
    line = renderer.self_optimization("rewrote tracker_write.py to retry on exit 12")
    assert line == "I made a small improvement to how I work."
    assert renderer.violations


def test_several_messages_render_together():
    renderer = Renderer("simple")
    out = renderer.render_all([Message("a", "First thing."), Message("b", "Second thing.")])
    assert out == "First thing.\nSecond thing."


def test_counting_reads_naturally():
    assert plural(1, "application") == "1 application"
    assert plural(2, "application") == "2 applications"
    assert plural(1, "needs", "need") == "1 needs"
    assert plural(3, "needs", "need") == "3 need"
