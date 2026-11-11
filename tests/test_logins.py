from __future__ import annotations

import json

from jobpilot.logins import Checklist, Reach, Result, check, steps, summary
from jobpilot.ui import PRODUCT_NAMES_OK, lint_plain
from jobpilot.wizard import ScriptedAsker


class Probe:
    """A stand-in for the real check. ``answers`` maps a step name to what it found."""

    def __init__(self, answers: dict[str, Reach]) -> None:
        self.answers = answers
        self.asked: list[str] = []

    def reach(self, step) -> Reach | None:
        self.asked.append(step.name)
        return self.answers.get(step.name)


def test_the_mailbox_is_always_the_first_sign_in(config):
    assert steps(config)[0].name == "mailbox"


def test_only_the_things_you_switched_on_are_asked_about(make_config):
    assert [s.name for s in steps(make_config())] == ["mailbox", "claude"]
    with_helper = make_config(plugins={"linkedin": {"enabled": True}})
    assert [s.name for s in steps(with_helper)] == ["mailbox", "linkedin", "claude"]


def test_each_step_says_what_to_do_and_what_will_never_happen(make_config):
    config = make_config(plugins={"yc": {"enabled": True}})
    for step in steps(config):
        text = step.read_out()
        assert "open that site in your own browser" in text
        assert "I never ask for your password" in text
        assert lint_plain(text, allow=PRODUCT_NAMES_OK) == [], step.name


def test_no_mailbox_connected_is_explained_without_blame(config):
    result = check(config, steps(config)[0])
    assert result.state == "unavailable"
    assert "no way to read that mailbox yet" in result.words
    assert "stay 'sent'" in result.words


def test_a_connected_mailbox_is_set_up_but_not_yet_proven(make_config, tmp_path):
    """Configured is not the same as signed in, and saying so would be a guess."""
    config = make_config(verify={"mail_reader": "json_export", "mail_export_dir": str(tmp_path)})
    result = check(config, steps(config)[0])
    assert result.state == "unverified"
    assert not result.ready
    assert "have not watched you sign in" in result.words


def test_a_mailbox_that_really_answers_is_confirmed(make_config, tmp_path):
    config = make_config(verify={"mail_reader": "json_export", "mail_export_dir": str(tmp_path)})
    result = check(config, steps(config)[0], probe=Probe({"mailbox": Reach(True, "I read 3 messages")}))
    assert result.state == "confirmed"
    assert result.ready
    assert "I read 3 messages" in result.words


def test_a_mailbox_that_will_not_open_needs_help(make_config, tmp_path):
    config = make_config(verify={"mail_reader": "json_export", "mail_export_dir": str(tmp_path)})
    probe = Probe({"mailbox": Reach(False, "it asked me to sign in again")})
    result = check(config, steps(config)[0], probe=probe)
    assert result.state == "needs_help"
    assert "sign in again" in result.detail


def test_a_helper_that_is_not_configured_is_not_even_worth_probing(make_config):
    missing = make_config(plugins={"handshake": {"enabled": True, "school_name": ""}})
    step = next(s for s in steps(missing) if s.name == "handshake")
    assert check(missing, step).state == "needs_help"
    assert "which school" in check(missing, step).detail


def test_a_configured_helper_still_has_to_be_reached(make_config):
    ready = make_config(plugins={"handshake": {"enabled": True, "school_name": "Example University"}})
    step = next(s for s in steps(ready) if s.name == "handshake")
    assert check(ready, step).state == "unverified"
    assert check(ready, step, probe=Probe({"handshake": Reach(True, "it greeted you by name")})).ready
    assert check(ready, step, probe=Probe({"handshake": Reach(False, "it showed a sign-in page")})).state == (
        "needs_help"
    )


def test_a_probe_that_cannot_tell_never_claims_a_sign_in(make_config):
    """"I could not look" and "you are signed in" are completely different answers."""
    ready = make_config(plugins={"handshake": {"enabled": True, "school_name": "Example University"}})
    step = next(s for s in steps(ready) if s.name == "handshake")
    assert check(ready, step, probe=Probe({})).state == "unverified"


def test_a_helper_that_is_off_is_not_chased(make_config):
    config = make_config()
    step = next(s for s in steps(make_config(plugins={"yc": {"enabled": True}})) if s.name == "yc")
    assert check(config, step).state == "skipped"


def test_saying_skip_means_skip(config):
    asker = ScriptedAsker(answers={"login.mailbox": "skip", "login.claude": "done"}, quiet=True)
    results = Checklist(config).walk(asker)
    by_name = {r.name: r for r in results}
    assert by_name["mailbox"].state == "skipped"
    assert "left for later" in by_name["mailbox"].words


def test_what_is_still_missing_is_said_out_loud(config):
    asker = ScriptedAsker(answers={"login.mailbox": "skip"}, quiet=True)
    Checklist(config).walk(asker)
    said = "\n".join(asker.transcript)
    assert "Still to do, and what stays off until then:" in said
    assert "mailbox" in said


def test_the_outcome_is_written_down(config):
    Checklist(config).walk(ScriptedAsker(answers={}, quiet=True))
    payload = json.loads((config.paths.state / "logins.json").read_text(encoding="utf-8"))
    assert {entry["name"] for entry in payload["results"]} == {"mailbox", "claude"}
    assert payload["checked_at"]


def test_everything_ready_is_said_plainly():
    assert "Everything you need to be signed in to is signed in." in summary(
        [Result("mailbox", "confirmed"), Result("claude", "confirmed")]
    )
    assert "Ready: mailbox, claude." in summary(
        [Result("mailbox", "confirmed"), Result("claude", "confirmed")]
    )


def test_the_whole_walk_stays_in_plain_words(make_config):
    config = make_config(plugins={"linkedin": {"enabled": True}})
    asker = ScriptedAsker(answers={}, quiet=True)
    Checklist(config).walk(asker)
    for line in "\n".join(asker.transcript).splitlines():
        assert lint_plain(line, allow=PRODUCT_NAMES_OK) == [], line


def test_nothing_is_asked_when_nobody_is_there(config):
    asker = ScriptedAsker(answers={}, quiet=True)
    results = Checklist(config).walk(asker, wait_for_user=False)
    assert asker.asked == []  # no question was put to anyone
    assert "Nobody is here to answer" in "\n".join(asker.transcript)
    assert {r.name for r in results} == {"mailbox", "claude"}


def test_an_empty_answer_means_later_not_done(config):
    """A closed input, or a pressed enter, must not report a sign-in nobody made."""
    asker = ScriptedAsker(answers={}, quiet=True)
    results = Checklist(config).walk(asker)
    assert [r.state for r in results] == ["skipped", "skipped"]
    assert "left for later" in "\n".join(asker.transcript)


def test_the_end_of_the_input_is_treated_the_same_way(config, monkeypatch):
    from jobpilot.wizard import ConsoleAsker

    monkeypatch.setattr("builtins.input", lambda *_a: (_ for _ in ()).throw(EOFError))
    asker = ConsoleAsker()
    results = Checklist(config).walk(asker)
    assert all(r.state == "skipped" for r in results)


def test_saying_done_still_checks(config):
    asker = ScriptedAsker(answers={"login.mailbox": "done", "login.claude": "done"}, quiet=True)
    states = {r.name: r.state for r in Checklist(config).walk(asker)}
    assert states["claude"] in ("unverified", "needs_help")
    assert states["mailbox"] == "unavailable"


def test_saying_done_with_something_that_can_look_gets_a_real_answer(config):
    asker = ScriptedAsker(answers={"login.mailbox": "done", "login.claude": "done"}, quiet=True)
    probe = Probe({"claude": Reach(True, "the tool itself says you are signed in")})
    states = {r.name: r.state for r in Checklist(config, probe=probe).walk(asker)}
    assert states["claude"] == "confirmed"


def test_a_non_interactive_run_never_reports_a_sign_in(config):
    """Nobody is there to sign in, so "ready" could only ever be a guess."""
    probe = Probe({"claude": Reach(True, "signed in"), "mailbox": Reach(True, "read 3")})
    asker = ScriptedAsker(answers={}, quiet=True)
    results = Checklist(config, probe=probe).walk(asker, wait_for_user=False)
    assert all(not r.ready for r in results), [r.state for r in results]
    said = "\n".join(asker.transcript)
    assert "I will not call anything ready" in said


def test_the_probe_is_used_when_somebody_is_there(config):
    probe = Probe({"claude": Reach(True, "signed in")})
    Checklist(config, probe=probe).walk(
        ScriptedAsker(answers={"login.claude": "done", "login.mailbox": "skip"}, quiet=True)
    )
    assert probe.asked == ["claude"]
