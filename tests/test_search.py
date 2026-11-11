from __future__ import annotations

import pytest

from jobpilot.search import built_in_sources, run_search
from jobpilot.search.ats import BoardSource, plain_text
from jobpilot.search.base import FetchError, FixtureFetcher

from .synthetic import ASHBY_URL, GREENHOUSE_URL, LEVER_URL, board_fetcher


def test_a_url_without_a_fixture_raises_rather_than_reaching_the_network():
    with pytest.raises(FetchError):
        FixtureFetcher().get_json("https://example.test/anything")


def test_greenhouse_rows_are_parsed(fixtures_dir):
    source = BoardSource("greenhouse", ["acme-robotics"])
    jobs = list(source.fetch(board_fetcher(fixtures_dir)))
    assert [job.title for job in jobs] == [
        "Machine Learning Engineer",
        "Senior Staff Platform Engineer",
        "AI Engineer, Perception",
    ]
    first = jobs[0]
    assert first.company == "Acme Robotics"
    assert first.ats == "greenhouse" and first.ats_job_id == "4001"
    assert first.location == "New York, NY"
    assert first.posted_at.startswith("2026-11-08")
    # The description keeps the employer's own sentences, so a quote can be checked.
    assert "we do not sponsor new work visas" in first.description


def test_lever_rows_are_parsed_including_their_lists(fixtures_dir):
    jobs = list(BoardSource("lever", ["globex-systems"]).fetch(board_fetcher(fixtures_dir)))
    assert jobs[0].title == "Software Engineer, New Grad"
    assert jobs[0].remote is True
    assert "Up to 2 years of experience" in jobs[0].description
    assert jobs[0].posted_at.startswith("2026-11")


def test_ashby_rows_are_parsed_and_unlisted_ones_are_left_out(fixtures_dir):
    jobs = list(BoardSource("ashby", ["northwind-analytics"]).fetch(board_fetcher(fixtures_dir)))
    assert [job.ats_job_id for job in jobs] == ["nw-9001", "nw-9002"]
    assert "active secret clearance is required" in jobs[1].description


def test_a_board_that_is_down_is_reported_not_raised(fixtures_dir):
    fetcher = board_fetcher(fixtures_dir)
    fetcher.responses[GREENHOUSE_URL] = FetchError("The job board answered with an error (503).")
    source = BoardSource("greenhouse", ["acme-robotics"])
    assert list(source.fetch(fetcher)) == []
    assert source.errors and "acme-robotics" in source.errors[0]


def test_only_switched_on_sources_are_used(make_config):
    config = make_config(
        search={
            "sources": {
                "greenhouse": {"enabled": True, "boards": ["acme-robotics"]},
                "lever": {"enabled": False, "boards": ["globex-systems"]},
            }
        }
    )
    assert [source.name for source in built_in_sources(config)] == ["greenhouse"]


def test_a_whole_pass_reports_its_funnel(make_config, fixtures_dir):
    config = make_config(
        search={
            "sources": {
                "greenhouse": {"enabled": True, "boards": ["acme-robotics"]},
                "lever": {"enabled": True, "boards": ["globex-systems"]},
                "ashby": {"enabled": True, "boards": ["northwind-analytics"]},
            }
        }
    )
    report = run_search(config, board_fetcher(fixtures_dir))
    assert report.fetched == 7
    assert report.unique == 7
    assert report.new == 7
    assert report.per_source == {"greenhouse": 3, "lever": 2, "ashby": 2}
    assert report.errors == []


def test_jobs_already_on_file_are_not_reported_as_new(make_config, fixtures_dir):
    config = make_config(
        search={"sources": {"greenhouse": {"enabled": True, "boards": ["acme-robotics"]}}}
    )
    first = run_search(config, board_fetcher(fixtures_dir))
    known = set()
    from jobpilot.search.dedupe import identities

    for job in first.jobs:
        known.update(identities(job))
    second = run_search(config, board_fetcher(fixtures_dir), known_keys=known)
    assert second.unique == 3 and second.new == 0


def test_a_source_yielding_nothing_is_visible_to_the_lead(make_config, fixtures_dir):
    fetcher = board_fetcher(fixtures_dir)
    fetcher.responses[LEVER_URL] = []
    config = make_config(
        search={
            "sources": {
                "greenhouse": {"enabled": True, "boards": ["acme-robotics"]},
                "lever": {"enabled": True, "boards": ["globex-systems"]},
            }
        }
    )
    report = run_search(config, fetcher)
    assert report.dead_sources == ["lever"]


def test_a_source_that_raises_does_not_stop_the_pass(make_config, fixtures_dir):
    class Angry:
        name = "angry"

        def fetch(self, fetcher):
            raise RuntimeError("boom")

    report = run_search(make_config(), board_fetcher(fixtures_dir), sources=[Angry()])
    assert report.new == 0
    assert "angry" in report.errors[0]


def test_html_becomes_readable_text_even_when_double_escaped():
    assert plain_text("&lt;p&gt;Hello&lt;/p&gt;&lt;p&gt;World&lt;/p&gt;") == "Hello\nWorld"
    assert plain_text("<ul><li>One</li><li>Two</li></ul>") == "One\nTwo"


def test_the_core_runs_with_no_sources_at_all(make_config, fixtures_dir):
    report = run_search(make_config(), board_fetcher(fixtures_dir))
    assert report.fetched == 0 and report.new == 0


def test_ashby_url_is_the_posting_api(fixtures_dir):
    assert BoardSource("ashby", ["northwind-analytics"]).urls() == [ASHBY_URL]
