from __future__ import annotations

from jobpilot.rules import denies_sponsorship, evaluate, hard_exclude, required_years

from . import synthetic as s


def codes(job, config, **kwargs):
    return evaluate(job, config, **kwargs).codes


def test_rules_flag_but_never_drop(config):
    """Every family below is a flag. Only three things are automatic drops."""
    for description in (
        s.JD_YOE,
        s.JD_PHD,
        s.JD_NOT_ELIGIBLE,
        s.JD_CLEARANCE,
        s.JD_CITIZEN_ONLY,
    ):
        result = evaluate(s.job(description=description), config)
        assert result.flags, "a disqualifying sentence should at least be flagged"


def test_no_sponsorship_is_flagged(config):
    assert "no_sponsorship" in codes(s.job(description=s.JD_NO_SPONSORSHIP), config)


def test_not_eligible_for_visa_sponsorship_is_part_of_the_same_family(config):
    result = evaluate(s.job(description=s.JD_NOT_ELIGIBLE), config)
    assert "no_sponsorship" in result.codes
    quote = next(f.quote for f in result.flags if f.code == "no_sponsorship")
    assert quote == "This position is not eligible for visa sponsorship."


def test_accepting_opt_or_an_existing_visa_is_not_a_disqualifier(config):
    result = evaluate(s.job(description=s.JD_OPT_FRIENDLY), config)
    assert "no_sponsorship" not in result.codes
    assert "sponsorship_mentioned" in result.codes
    assert result.hard_exclude is None


def test_a_sentence_that_never_mentions_sponsorship_is_not_about_sponsorship():
    assert denies_sponsorship("You will work without the need for supervision.") is False
    assert denies_sponsorship("We will not sponsor a work visa for this role.") is True
    assert denies_sponsorship("We do not sponsor new visas but welcome candidates on OPT.") is False


def test_citizenship_and_clearance_are_flagged_with_their_sentence(config):
    citizen = evaluate(s.job(description=s.JD_CITIZEN_ONLY), config)
    assert "citizen_only" in citizen.codes
    clearance = evaluate(s.job(description=s.JD_CLEARANCE), config)
    assert "clearance" in clearance.codes
    assert "clearance is required" in next(f.quote for f in clearance.flags if f.code == "clearance")


def test_years_of_experience_only_counts_an_explicit_requirement():
    assert required_years(s.JD_YOE)[0] == 5
    assert required_years(s.JD_YOE_CEILING)[0] is None
    assert required_years("0-2 years of experience required")[0] is None
    assert required_years("We ask for 3+ years of experience")[0] == 3


def test_years_over_the_threshold_is_flagged_with_the_threshold(config):
    result = evaluate(s.job(description=s.JD_YOE), config)
    flag = next(f for f in result.flags if f.code == "years_experience")
    assert "requires 5 years" in flag.detail and "you set 2" in flag.detail


def test_a_ceiling_or_a_preference_is_not_flagged(config):
    assert "years_experience" not in codes(s.job(description=s.JD_YOE_CEILING), config)


def test_a_doctorate_requirement_is_flagged(config):
    assert "phd_only" in codes(s.job(description=s.JD_PHD), config)


def test_a_senior_title_is_flagged(config):
    assert "senior_title" in codes(s.job(title="Senior Machine Learning Engineer"), config)
    assert "senior_title" not in codes(s.job(title="Machine Learning Engineer II"), config)


def test_an_excluded_category_is_flagged(config):
    assert "excluded_category" in codes(s.job(title="Technician, Field Operations"), config)


def test_somewhere_else_in_the_world_is_flagged_not_dropped(config):
    job = s.job(location="Dublin, Ireland", description="Applicants must reside in Ireland.")
    result = evaluate(job, config)
    assert "location_outside_preference" in result.codes
    assert "must_work_abroad" in result.codes
    assert result.hard_exclude is None


def test_remote_and_us_locations_are_not_flagged_as_foreign(config):
    assert "location_outside_preference" not in codes(s.job(location="Remote (US)"), config)
    assert "location_outside_preference" not in codes(s.job(location="Austin, TX"), config)


def test_a_company_on_hold_is_flagged_for_the_user(make_config):
    config = make_config(search={"company_rules": {"hold_pending_user": ["Umbrella Logistics"]}})
    assert "hold_pending_user" in codes(s.job(company="Umbrella Logistics"), config)


def test_freshness_is_a_tag_never_a_disqualifier(config):
    assert "fresh" in codes(s.job(posted_at=s.iso_days_ago(1)), config)
    assert "aging" in codes(s.job(posted_at=s.iso_days_ago(30)), config)
    assert "freshness_unknown" in codes(s.job(posted_at=""), config)


# -- the three automatic drops ------------------------------------------


def test_a_company_the_user_excluded_is_dropped_without_a_quote(make_config):
    config = make_config(search={"company_rules": {"hard_exclude": ["Umbrella Logistics, Inc."]}})
    excluded = hard_exclude(s.job(company="Umbrella Logistics"), config)
    assert excluded is not None and excluded.code == "company_excluded"
    assert excluded.quote == ""


def test_a_quoted_no_sponsorship_line_is_a_drop_and_keeps_its_quote(config):
    job = s.job(description=s.JD_NOT_ELIGIBLE)
    result = evaluate(job, config)
    assert result.hard_exclude is not None
    assert result.hard_exclude.code == "no_sponsorship"
    assert result.hard_exclude.quote in job.description
    assert result.hard_exclude.quote_url == job.url


def test_that_family_can_be_switched_off_by_the_user(make_config):
    config = make_config(work_authorization={"hard_exclude_on": {"no_sponsorship_at_all": False}})
    assert evaluate(s.job(description=s.JD_NOT_ELIGIBLE), config).hard_exclude is None


def test_a_closed_posting_needs_a_structured_receipt(config):
    job = s.job()
    free_text = {"note": "the page said 404 when I looked"}
    assert hard_exclude(job, config, liveness=free_text) is None
    receipt = {"http_code": 404, "url": job.url, "checked_at": "2026-11-10T10:00:00+00:00"}
    excluded = hard_exclude(job, config, liveness=receipt)
    assert excluded is not None and excluded.code == "posting_closed"


def test_an_ordinary_posting_is_never_dropped_by_the_rules(config):
    assert evaluate(s.job(description=s.JD_PLAIN), config).hard_exclude is None
    assert evaluate(s.job(description=s.JD_YOE), config).hard_exclude is None
    assert evaluate(s.job(description=s.JD_PHD), config).hard_exclude is None
