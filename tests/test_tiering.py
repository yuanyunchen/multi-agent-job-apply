"""Which queue a job lands in, and who decided."""

from __future__ import annotations

import pytest

from jobpilot.tiering import (
    NoHook,
    TierDecision,
    classify,
    quote_is_verbatim,
    rule_tier,
    summarize,
)

from . import synthetic as s


def tier_of(decisions: list[TierDecision], job_id: str) -> TierDecision:
    return next(d for d in decisions if d.job_id == job_id)


# -- the rule layer -------------------------------------------------------


def test_a_title_on_the_first_choice_list_is_core(config):
    tier, why = rule_tier(s.job(title="Machine Learning Engineer"), config)
    assert tier == "core"
    assert "want most" in why


def test_a_title_on_the_second_list_waits(config):
    tier, _ = rule_tier(s.job(title="Software Engineer, Platform"), config)
    assert tier == "non_core"


def test_a_title_on_the_never_list_is_dropped_by_rules_alone(config):
    tier, why = rule_tier(s.job(title="Sales Engineer"), config)
    assert tier == "irrelevant"
    assert "never-apply" in why


def test_an_unknown_title_is_kept_for_a_closer_look(config):
    """A title nobody listed is a question for a model, not a reason to bin it."""
    tier, why = rule_tier(s.job(title="Perception Wizard"), config)
    assert tier == "non_core"
    assert "closer look" in why


def test_rules_alone_tier_everything_with_no_model(config):
    jobs = [
        s.job(title="Machine Learning Engineer", url="https://example.test/1", ats_job_id="1"),
        s.job(title="Software Engineer", url="https://example.test/2", ats_job_id="2"),
        s.job(title="Sales Engineer", url="https://example.test/3", ats_job_id="3"),
    ]
    decisions = classify(jobs, config)
    assert [d.tier for d in decisions] == ["core", "non_core", "irrelevant"]
    assert {d.source for d in decisions} == {"rules"}


def test_a_hard_exclude_is_decided_by_code_with_its_own_evidence(config):
    job = s.job(description=s.JD_NOT_ELIGIBLE, title="AI Engineer")
    decision = classify([job], config)[0]
    assert decision.tier == "irrelevant"
    assert decision.source.startswith("rules:")
    assert decision.quote_verified
    assert "not eligible for visa sponsorship" in decision.quote.lower()


def test_a_company_on_the_never_list_needs_no_quote(make_config):
    config = make_config(search={"company_rules": {"hard_exclude": ["Acme Robotics"]}})
    decision = classify([s.job()], config)[0]
    assert decision.tier == "irrelevant"
    assert decision.source == "rules:company_excluded"
    assert decision.quote == ""


# -- the optional model hook ---------------------------------------------


class Hook:
    """A stand-in model. ``answers`` is keyed by job id."""

    name = "pretend-model"

    def __init__(self, answers: dict | None = None, explode: bool = False) -> None:
        self.answers = answers or {}
        self.explode = explode
        self.seen: list[str] = []

    def rank(self, jobs, flags):
        if self.explode:
            raise RuntimeError("the model fell over")
        self.seen = [job.job_id for job in jobs]
        assert set(flags) == set(self.seen), "the hook must be told the rule flags"
        return {job.job_id: self.answers[job.job_id] for job in jobs if job.job_id in self.answers}


def test_the_hook_may_move_a_job_between_queues(config):
    job = s.job(title="Perception Wizard")
    hook = Hook({job.job_id: {"tier": "core", "reason": "this is the work you asked for"}})
    decision = classify([job], config, hook=hook)[0]
    assert decision.tier == "core"
    assert decision.source == "pretend-model"


def test_the_hook_may_drop_a_job_only_by_quoting_the_posting(config):
    job = s.job(title="Perception Wizard", description=s.JD_YOE)
    quote = "5 years of experience in production machine learning is required."
    hook = Hook({job.job_id: {"tier": "irrelevant", "quote": quote, "reason": "too much experience"}})
    decision = classify([job], config, hook=hook)[0]
    assert decision.tier == "irrelevant"
    assert decision.quote_verified
    assert decision.quote == quote


def test_a_drop_with_an_invented_quote_is_thrown_away_and_the_job_kept(config):
    job = s.job(title="Perception Wizard", description=s.JD_PLAIN)
    hook = Hook(
        {job.job_id: {"tier": "irrelevant", "quote": "We only hire people from Mars, obviously."}}
    )
    decision = classify([job], config, hook=hook)[0]
    assert decision.tier == "non_core", "the job survives an unprovable drop"
    assert decision.source.endswith(":unverified_quote")
    assert not decision.quote_verified


def test_a_drop_with_too_short_a_quote_is_no_evidence(config):
    job = s.job(title="Perception Wizard", description=s.JD_PLAIN)
    hook = Hook({job.job_id: {"tier": "irrelevant", "quote": "Boston"}})
    assert classify([job], config, hook=hook)[0].tier == "non_core"


def test_a_hook_that_says_nothing_leaves_the_rule_answer_and_is_marked(config):
    job = s.job(title="Machine Learning Engineer")
    decision = classify([job], config, hook=Hook({}))[0]
    assert decision.tier == "core"
    assert decision.model_pending
    assert decision.source == "model_pending"


def test_a_hook_that_falls_over_never_stops_the_pass(config):
    jobs = [s.job(title="Machine Learning Engineer")]
    decisions = classify(jobs, config, hook=Hook(explode=True))
    assert decisions[0].tier == "core"
    assert decisions[0].model_pending


def test_the_hook_is_never_asked_about_a_job_the_rules_already_settled(config):
    jobs = [
        s.job(title="Sales Engineer", url="https://example.test/1", ats_job_id="1"),
        s.job(title="Machine Learning Engineer", url="https://example.test/2", ats_job_id="2"),
    ]
    hook = Hook({})
    classify(jobs, config, hook=hook)
    assert hook.seen == [jobs[1].job_id], "a job already ruled out costs nothing"


def test_the_default_hook_is_rules_only(config):
    job = s.job(title="Machine Learning Engineer")
    decision = classify([job], config, hook=NoHook())[0]
    assert decision.tier == "core"
    assert decision.model_pending  # nothing answered, so the rule answer stands


# -- odds and ends --------------------------------------------------------


def test_a_closed_posting_is_dropped_only_on_a_structured_receipt(config):
    job = s.job()
    receipt = {"http_code": 404, "url": job.url, "checked_at": "2026-11-10T12:00:00+00:00"}
    assert classify([job], config, liveness={job.job_id: receipt})[0].tier == "irrelevant"
    # Free text that merely mentions 404 is not a receipt.
    assert classify([job], config, liveness={job.job_id: {"note": "page said 404"}})[0].tier == "core"


@pytest.mark.parametrize(
    "quote,expected",
    [
        ("We review applications weekly.", True),
        ("we   review\napplications weekly.", True),  # whitespace is collapsed
        ("WE REVIEW APPLICATIONS WEEKLY.", True),  # case is ignored
        ("We review applications monthly.", False),  # one word differs
        ("Boston", False),  # too short to mean anything
    ],
)
def test_quote_checking(quote, expected):
    assert quote_is_verbatim(quote, s.JD_PLAIN) is expected


def test_the_summary_counts_what_happened(config):
    jobs = [
        s.job(title="Machine Learning Engineer", url="https://example.test/1", ats_job_id="1"),
        s.job(title="Sales Engineer", url="https://example.test/2", ats_job_id="2"),
    ]
    counts = summarize(classify(jobs, config))
    assert counts.core == 1
    assert counts.irrelevant == 1
    assert counts.by_source["rules"] == 2
