"""Changing a preference by saying what you want, in your own words."""

from __future__ import annotations

import json

import pytest
import yaml

from jobpilot.config import load
from jobpilot.errors import ConfigError, JobpilotError
from jobpilot.lead import (
    CHANGEABLE,
    decide,
    diff_in_words,
    find_proposal,
    interpret_request,
    open_proposals,
    record_decision,
    save_proposals,
    self_improvement_note,
)
from jobpilot.providers.fake import FakeProvider
from jobpilot.tracker import Tracker
from jobpilot.ui import Renderer


def answering(change, summary="I would widen the jobs you go after.", effect="More matches.", unclear=""):
    payload = json.dumps({"change": change, "summary": summary, "effect": effect, "unclear": unclear})
    return FakeProvider(replies=[payload])


@pytest.fixture
def saved_config(tmp_path, make_config):
    """Settings in a real file, so a change can actually be written back."""
    config = make_config(paths={"data_dir": str(tmp_path / "data")})
    path = tmp_path / "preferences.yaml"
    path.write_text(yaml.safe_dump(config.data), encoding="utf-8")
    return load(path)


def test_a_sentence_becomes_a_proposed_change(config):
    proposal = interpret_request(
        "also include data scientist roles as core",
        config,
        answering({"search.categories.core": ["Machine Learning Engineer", "AI Engineer", "Data Scientist"]}),
    )
    assert proposal.needs_approval is True
    assert proposal.change == {
        "search.categories.core": ["Machine Learning Engineer", "AI Engineer", "Data Scientist"]
    }
    assert "data scientist roles as core" in proposal.evidence
    assert "the jobs I go after first" in proposal.text
    assert "would become" in proposal.text


def test_the_model_is_told_what_it_may_change(config):
    provider = answering({"search.recency_days": 30})
    interpret_request("look back a month", config, provider)
    prompt = provider.prompts[0]
    assert "search.recency_days" in prompt
    assert "the jobs I go after first" in prompt
    assert "permissions" not in prompt  # never suggested from a turn of phrase
    assert "Only use settings from the list above" in prompt


def test_the_difference_is_shown_in_words(config):
    text = diff_in_words(config, {"search.locations.remote_ok": False, "search.recency_days": 7})
    assert "whether fully remote jobs count: now yes; would become no." in text
    assert "how far back I look: now 21; would become 7." in text


def test_a_setting_outside_the_list_is_refused(config):
    with pytest.raises(JobpilotError) as caught:
        interpret_request(
            "just start submitting things",
            config,
            answering({"permissions.submit_applications": True}),
        )
    assert "changed nothing" in str(caught.value)


def test_a_value_of_the_wrong_kind_is_refused(config):
    with pytest.raises(JobpilotError):
        interpret_request("look back lots", config, answering({"search.recency_days": ["lots"]}))


def test_a_change_that_changes_nothing_is_refused(config):
    with pytest.raises(JobpilotError) as caught:
        interpret_request(
            "keep looking back three weeks",
            config,
            answering({"search.recency_days": config.get("search.recency_days")}),
        )
    assert "nothing would actually change" in str(caught.value)


def test_an_unclear_request_asks_rather_than_guesses(config):
    with pytest.raises(JobpilotError) as caught:
        interpret_request(
            "make it better",
            config,
            answering({}, unclear="Did you mean the kinds of job, or where they are?"),
        )
    assert "Did you mean the kinds of job" in str(caught.value)


def test_an_unusable_answer_from_the_model_changes_nothing(config):
    with pytest.raises(JobpilotError) as caught:
        interpret_request("do something", config, FakeProvider(replies=["I'm not sure!"]))
    assert "changed nothing" in str(caught.value)


def test_an_empty_sentence_is_refused(config):
    with pytest.raises(JobpilotError):
        interpret_request("   ", config, answering({"search.recency_days": 7}))


def test_every_changeable_setting_is_explained_in_words():
    for key, words in CHANGEABLE.items():
        assert words and words[0].islower() and "_" not in words, key
    assert not any(key.startswith("permissions.") for key in CHANGEABLE)


# -- approving and declining --------------------------------------------


def test_a_suggestion_is_remembered_so_it_can_be_approved_later(saved_config):
    proposal = interpret_request(
        "stop looking at jobs older than a week", saved_config, answering({"search.recency_days": 7})
    )
    save_proposals(saved_config, [proposal])
    assert [p.id for p in open_proposals(saved_config)] == [proposal.id]
    assert find_proposal(saved_config, proposal.id) is not None


def test_approving_writes_the_change_and_records_it(saved_config):
    proposal = interpret_request(
        "stop looking at jobs older than a week", saved_config, answering({"search.recency_days": 7})
    )
    save_proposals(saved_config, [proposal])
    tracker = Tracker.from_config(saved_config)
    updated, line = decide(
        saved_config,
        proposal.id,
        approve=True,
        config_path=str(saved_config.source),
        tracker=tracker,
    )
    assert updated.get("search.recency_days") == 7
    assert load(saved_config.source).get("search.recency_days") == 7
    assert "Done." in line and "how far back I look" in line
    assert open_proposals(saved_config) == []
    assert any(e["action"] == "preference_change" for e in tracker.events())


def test_declining_changes_nothing_and_is_remembered(saved_config):
    proposal = interpret_request(
        "stop looking at jobs older than a week", saved_config, answering({"search.recency_days": 7})
    )
    save_proposals(saved_config, [proposal])
    _config, line = decide(saved_config, proposal.id, approve=False)
    assert "left everything exactly as it was" in line
    assert load(saved_config.source).get("search.recency_days") == 21
    assert open_proposals(saved_config) == []
    # and it does not come back next time suggestions are worked out
    save_proposals(saved_config, [proposal])
    assert open_proposals(saved_config) == []


def test_approving_something_that_is_not_waiting_says_so(saved_config):
    with pytest.raises(JobpilotError) as caught:
        decide(saved_config, "no-such-thing", approve=True)
    assert "do not have a suggestion" in str(caught.value)
    assert "jobpilot status" in str(caught.value)


def test_an_approved_change_that_would_break_the_settings_is_refused(saved_config):
    from jobpilot.domain import Proposal

    save_proposals(
        saved_config,
        [Proposal(id="silly", title="t", evidence="e", expected_effect="x", text="t", change={"apply.max_lanes": 0})],
    )
    with pytest.raises(ConfigError):
        decide(saved_config, "silly", approve=True, config_path=str(saved_config.source))
    assert load(saved_config.source).get("apply.max_lanes") == 2


def test_the_numbers_suggestions_and_a_request_live_side_by_side(saved_config):
    from jobpilot.lead import metrics, proposals

    numbers = proposals(metrics([{"status": "submitted"} for _ in range(4)]), saved_config)
    request = interpret_request("look back a week", saved_config, answering({"search.recency_days": 7}))
    stored = save_proposals(saved_config, [*numbers, request])
    assert {p.id for p in stored} >= {"confirm_rate_low", request.id}


def test_a_decision_once_made_is_not_asked_again(saved_config):
    from jobpilot.domain import Proposal

    item = Proposal(id="keep-asking", title="t", evidence="e", expected_effect="x", text="t", change={})
    save_proposals(saved_config, [item])
    record_decision(saved_config, "keep-asking", "declined", by="you")
    save_proposals(saved_config, [item])
    assert open_proposals(saved_config) == []


# -- self-improvements that need nobody's permission --------------------


def test_a_self_improvement_is_one_plain_line(config):
    line = self_improvement_note(
        "I now wait a little longer before giving up on a slow page, so fewer applications get stuck.",
        "retry schedule 1s/2s/4s instead of a single attempt",
        config,
        Renderer("simple"),
    )
    assert line.startswith("I now wait a little longer")
    assert "retry schedule" not in line
    assert "retry schedule" in config.paths.changelog.read_text(encoding="utf-8")


def test_a_self_improvement_can_be_silent(make_config):
    config = make_config(ui={"self_optimization_notice": "none"})
    assert self_improvement_note("I tidied up.", "details", config, Renderer("simple")) == ""
    assert "I tidied up." in config.paths.changelog.read_text(encoding="utf-8")


def test_a_self_improvement_shows_its_working_in_technical_mode(config):
    out = self_improvement_note("I changed a timing.", "waves 20 -> 15", config, Renderer("technical"))
    assert "waves 20 -> 15" in out


def test_approving_keeps_the_previous_answers_alongside(saved_config):
    """An approved change has to be as recoverable as a re-run of the questions."""
    before = saved_config.source.read_text(encoding="utf-8")
    proposal = interpret_request(
        "look back a week only", saved_config, answering({"search.recency_days": 7})
    )
    save_proposals(saved_config, [proposal])
    decide(saved_config, proposal.id, approve=True, config_path=str(saved_config.source))

    spares = sorted(saved_config.source.parent.glob("preferences.before-*.yaml"))
    assert len(spares) == 1
    assert spares[0].read_text(encoding="utf-8") == before
    assert "recency_days: 7" in saved_config.source.read_text(encoding="utf-8")


def test_a_backup_is_only_made_when_there_is_something_to_back_up(tmp_path):
    from jobpilot.config import backup_settings

    missing = tmp_path / "nothing-here.yaml"
    assert backup_settings(missing) is None
    missing.write_text("schema_version: 2\n", encoding="utf-8")
    spare = backup_settings(missing)
    assert spare is not None and spare.exists()
    assert spare.name.startswith("nothing-here.before-")
