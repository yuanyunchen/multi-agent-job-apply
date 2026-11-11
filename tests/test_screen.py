from __future__ import annotations

import json

from jobpilot.providers.fake import FakeProvider
from jobpilot.screen import (
    MIN_QUOTE_CHARS,
    decision_to_update,
    lexical_tier,
    parse_model_reply,
    quote_is_verbatim,
    screen,
)

from . import synthetic as s


def reply(job, **fields):
    row = {"job_id": job.job_id, "verdict": "keep", "tier": "core", "quote": "", "reason": "ok"}
    row.update(fields)
    return FakeProvider(replies=[json.dumps([row])])


def test_a_quote_must_really_be_in_the_description():
    jd = s.JD_NOT_ELIGIBLE
    assert quote_is_verbatim("This position is not eligible for visa sponsorship.", jd) is True
    # whitespace and capitalisation may differ; words may not
    assert quote_is_verbatim("this  position is not\neligible for visa sponsorship.", jd) is True
    assert quote_is_verbatim("This position is not eligible for sponsorship of visas.", jd) is False


def test_a_quote_too_short_to_mean_anything_is_not_evidence():
    assert quote_is_verbatim("a" * (MIN_QUOTE_CHARS - 1), "a" * 100) is False


def test_a_drop_with_a_real_quote_is_accepted(config):
    job = s.job(description=s.JD_NO_SPONSORSHIP, title="Data Analyst")
    quote = "Candidates must be authorized to work in the United States without sponsorship now or in the future."
    outcome = screen([job], config, reply(job, verdict="drop", tier="irrelevant", quote=quote))
    decision = outcome.decisions[0]
    assert decision.verdict == "drop"
    assert decision.quote_verified is True
    assert decision.quote in job.description.replace("\n", " ")


def test_a_drop_with_an_invented_quote_is_rejected_and_the_job_is_kept(config):
    job = s.job(description=s.JD_PLAIN, title="Data Analyst")
    outcome = screen(
        [job],
        config,
        reply(job, verdict="drop", tier="irrelevant", quote="We only hire citizens of Mars, sorry."),
    )
    decision = outcome.decisions[0]
    assert decision.verdict == "review"
    assert decision.quote == ""
    assert outcome.unverified_quotes == 1
    assert "could not back it up" in decision.reason


def test_a_drop_with_no_quote_at_all_is_rejected(config):
    job = s.job(description=s.JD_PLAIN)
    outcome = screen([job], config, reply(job, verdict="drop", quote=""))
    assert outcome.decisions[0].verdict == "review"
    assert outcome.unverified_quotes == 1


def test_a_keep_needs_no_quote(config):
    job = s.job()
    outcome = screen([job], config, reply(job, verdict="keep", tier="core"))
    assert outcome.decisions[0].verdict == "keep"
    assert outcome.decisions[0].tier == "core"
    assert outcome.unverified_quotes == 0


def test_no_usable_answer_keeps_the_job_for_review(config):
    job = s.job()
    outcome = screen([job], config, FakeProvider(replies=["I am afraid I cannot do that."]))
    decision = outcome.decisions[0]
    assert decision.verdict == "review"
    assert decision.tier == "core"  # the tier we worked out from the title
    assert outcome.model_pending == 1


def test_a_hard_exclude_is_decided_by_code_without_asking_a_model(make_config):
    config = make_config(search={"company_rules": {"hard_exclude": ["Umbrella Logistics"]}})
    job = s.job(company="Umbrella Logistics")
    provider = FakeProvider(replies=["[]"])
    outcome = screen([job], config, provider)
    assert provider.prompts == []  # no model call at all
    decision = outcome.decisions[0]
    assert decision.verdict == "drop" and decision.source == "rule:company_excluded"


def test_tiers_come_from_the_users_own_categories(config):
    assert lexical_tier(s.job(title="Machine Learning Engineer"), config) == "core"
    assert lexical_tier(s.job(title="Software Engineer, Backend"), config) == "non_core"
    assert lexical_tier(s.job(title="Sales Development Representative"), config) == "irrelevant"
    assert lexical_tier(s.job(title="Something Nobody Listed"), config) == "non_core"


def test_a_kept_job_is_never_filed_as_irrelevant(config):
    job = s.job()
    outcome = screen([job], config, reply(job, verdict="keep", tier="irrelevant"))
    assert outcome.decisions[0].tier == "non_core"


def test_jobs_are_screened_in_batches(config):
    jobs = [s.job(url=f"https://x.example/{n}", ats_job_id=str(n)) for n in range(5)]
    provider = FakeProvider(answer=lambda prompt: "[]")
    screen(jobs, config, provider, batch_size=2)
    assert len(provider.prompts) == 3


def test_the_prompt_tells_the_model_the_quote_will_be_checked(config):
    provider = FakeProvider(replies=["[]"])
    screen([s.job()], config, provider)
    prompt = provider.prompts[0]
    assert "word for word" in prompt
    assert "Machine Learning Engineer" in prompt  # the user's own categories
    assert "If you are unsure" in prompt


def test_model_output_wrapped_in_prose_is_still_read():
    parsed = parse_model_reply('Sure! Here you go:\n[{"job_id": "abc", "verdict": "keep"}]\nHope that helps.')
    assert parsed["abc"]["verdict"] == "keep"
    assert parse_model_reply("no json here") == {}


def test_a_decision_turns_into_tracker_fields_with_its_evidence(config):
    job = s.job(description=s.JD_NOT_ELIGIBLE)
    quote = "This position is not eligible for visa sponsorship."
    outcome = screen([job], config, reply(job, verdict="drop", quote=quote))
    update = decision_to_update(job, outcome.decisions[0])
    assert update["status"] == "skipped"
    assert update["skip_quote"] == quote
    assert update["skip_quote_url"] == job.url
    assert update["review_verdict"] == "drop"


def test_a_kept_decision_becomes_a_pipeline_row(config):
    job = s.job()
    outcome = screen([job], config, reply(job, verdict="keep"))
    update = decision_to_update(job, outcome.decisions[0])
    assert update["status"] == "pipeline" and update["apply_tier"] == "core"


def test_the_description_survives_the_trip_through_the_record(config):
    """Without the employer's own words on the row, no later step can quote them."""
    from jobpilot.tracker import Tracker

    job = s.job(description=s.JD_NO_SPONSORSHIP)
    tracker = Tracker.from_config(config)
    tracker.upsert([job.to_row()], caller="search")
    row = tracker.by_id()[job.job_id]
    assert row["description"] == job.description
    assert "without sponsorship now or in the future" in row["description"]
