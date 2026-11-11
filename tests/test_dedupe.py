from __future__ import annotations

import pytest

from jobpilot.search.dedupe import ats_key, canonical_url, dedupe, identities, is_known, row_identities

from .synthetic import job


@pytest.mark.parametrize(
    "raw, expected",
    [
        (
            "https://JOB-boards.greenhouse.io/acme-robotics/jobs/4001?utm_source=x&gh_src=y",
            "https://job-boards.greenhouse.io/acme-robotics/jobs/4001",
        ),
        (
            "https://www.jobs.lever.co/globex-systems/abc/?ref=mail#apply",
            "https://jobs.lever.co/globex-systems/abc",
        ),
        (
            "https://jobs.ashbyhq.com/northwind/nw-1?gh_jid=55",
            "https://jobs.ashbyhq.com/northwind/nw-1?gh_jid=55",
        ),
        ("job-boards.greenhouse.io/acme/jobs/1", "https://job-boards.greenhouse.io/acme/jobs/1"),
        ("", ""),
    ],
)
def test_urls_are_canonicalised(raw, expected):
    assert canonical_url(raw) == expected


def test_the_same_url_in_two_shapes_is_one_job():
    rows = dedupe(
        [
            job(url="https://job-boards.greenhouse.io/acme-robotics/jobs/4001"),
            job(url="https://JOB-boards.greenhouse.io/acme-robotics/jobs/4001?utm_campaign=z"),
        ]
    )
    assert len(rows) == 1


def test_the_same_ats_id_with_a_different_url_and_an_older_title_is_one_job():
    """URL-only de-duplication misses exactly this case, which is why we key on both."""
    rows = dedupe(
        [
            job(
                title="Machine Learning Engineer",
                url="https://job-boards.greenhouse.io/acme-robotics/jobs/4001",
                ats_job_id="4001",
            ),
            job(
                title="ML Engineer (old title)",
                url="https://boards.greenhouse.io/acmerobotics/jobs/4001",
                ats_job_id="4001",
                description="",
            ),
        ]
    )
    assert len(rows) == 1
    kept = rows[0]
    assert kept.title == "Machine Learning Engineer"  # the first, richer row wins
    assert "https://boards.greenhouse.io/acmerobotics/jobs/4001" in kept.alternate_urls


def test_different_companies_sharing_an_id_stay_separate():
    rows = dedupe(
        [
            job(company="Acme Robotics", url="https://a.example/1", ats_job_id="42"),
            job(company="Globex Systems", url="https://b.example/1", ats_job_id="42"),
        ]
    )
    assert len(rows) == 2


def test_a_job_without_an_id_falls_back_to_the_url_only():
    rows = dedupe(
        [
            job(url="https://careers.example/role-a", ats_job_id=""),
            job(url="https://careers.example/role-b", ats_job_id=""),
        ]
    )
    assert len(rows) == 2
    assert ats_key(rows[0]) == ""


def test_merging_never_loses_a_description_or_a_date():
    rows = dedupe(
        [
            job(url="https://x.example/1", ats_job_id="9", description="", posted_at=""),
            job(url="https://x.example/1", ats_job_id="9", description="Full text", posted_at="2026-11-09"),
        ]
    )
    assert rows[0].description == "Full text"
    assert rows[0].posted_at == "2026-11-09"


def test_known_keys_recognise_either_identity():
    first = job()
    assert is_known(first, set(identities(first))) is True
    other_shape = job(url="https://boards.greenhouse.io/acmerobotics/jobs/4001")
    assert is_known(other_shape, {f"ats:{ats_key(first)}"}) is True


def test_tracker_rows_produce_the_same_identities():
    first = job()
    row = first.to_row()
    assert set(identities(first)) <= set(row_identities(row))


def test_a_jobs_local_id_is_stable_and_identity_based():
    assert job().job_id == job(title="Different title").job_id
    assert job().job_id != job(ats_job_id="4002").job_id


def test_a_job_read_back_from_the_record_keeps_its_own_id():
    """Two rows with no link must not look like the same job."""
    from jobpilot.domain import Job

    first = Job(company="Acme Robotics", title="A", url="", source="hand", id_hint="row-1")
    second = Job(company="Acme Robotics", title="B", url="", source="hand", id_hint="row-2")
    assert first.job_id == "row-1"
    assert first.job_id != second.job_id


# -- company and title: the weak identity --------------------------------


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Machine Learning Engineer", "machine learning engineer"),
        ("Machine Learning Engineer (Remote)", "machine learning engineer"),
        ("Machine Learning Engineer - Remote", "machine learning engineer"),
        ("Machine Learning Engineer, New York", "machine learning engineer"),
        ("Machine Learning Engineer, Platform", "machine learning engineer, platform"),
    ],
)
def test_a_title_is_compared_without_where_it_is(title, expected):
    from jobpilot.search.dedupe import title_norm

    assert title_norm(title) == expected


def test_the_weak_key_ignores_company_suffixes_and_location(config):
    from jobpilot.search.dedupe import company_title_key

    first = company_title_key("Acme Robotics, Inc.", "Machine Learning Engineer (Remote)")
    second = company_title_key("Acme Robotics", "Machine Learning Engineer, New York")
    assert first == second


def test_no_company_or_no_title_means_no_weak_key():
    from jobpilot.search.dedupe import company_title_key

    assert company_title_key("", "Machine Learning Engineer") == ""
    assert company_title_key("Acme Robotics", "") == ""


@pytest.mark.parametrize(
    "first,second,differ",
    [
        ("Perception Engineer", "Forecasting Engineer", True),
        ("Perception Engineer", "Perception Engineer II", False),
        ("Software Engineer", "Engineer, New Grad", False),  # all generic: no evidence
        ("Software Engineer R12345", "Software Engineer R99999", False),  # ids are not words
    ],
)
def test_whether_two_titles_describe_different_openings(first, second, differ):
    from jobpilot.search.dedupe import titles_differ_materially

    assert titles_differ_materially(first, second) is differ


def test_the_same_posting_from_two_sources_is_flagged_not_dropped():
    """Company and title matched loosely once removed good rows silently."""
    from jobpilot.search.dedupe import possible_duplicates

    mine = {
        "job_id": "a",
        "company": "Acme Robotics",
        "title": "Machine Learning Engineer (Remote)",
        "url": "https://acme-robotics.example/jobs/1",
    }
    theirs = {
        "job_id": "b",
        "company": "Acme Robotics, Inc.",
        "title": "Machine Learning Engineer",
        "url": "https://aggregator.example/listing/99",
    }
    assert possible_duplicates(mine, [theirs]) == [theirs]


def test_two_genuinely_different_openings_at_one_company_are_not_duplicates():
    from jobpilot.search.dedupe import possible_duplicates

    perception = {"job_id": "a", "company": "Acme Robotics", "title": "Perception Engineer"}
    forecasting = {"job_id": "b", "company": "Acme Robotics", "title": "Forecasting Engineer"}
    assert possible_duplicates(perception, [forecasting]) == []


def test_a_row_is_never_its_own_duplicate():
    from jobpilot.search.dedupe import possible_duplicates

    row = {"job_id": "a", "company": "Acme Robotics", "title": "Machine Learning Engineer"}
    assert possible_duplicates(row, [row, dict(row)]) == []


def test_a_strong_match_is_not_reported_as_a_weak_one():
    """The URL already settled it; saying "maybe" afterwards is just noise."""
    from jobpilot.search.dedupe import possible_duplicates

    mine = {
        "job_id": "a",
        "company": "Acme Robotics",
        "title": "Machine Learning Engineer",
        "url": "https://acme-robotics.example/jobs/1",
    }
    same = {**mine, "job_id": "b"}
    assert possible_duplicates(mine, [same]) == []
