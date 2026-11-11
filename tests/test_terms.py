"""The two lists people edit most: job titles, and where to look.

Both may live in the settings or in a file of their own beside them. The thing
being proved here is that there is exactly **one reader** for each, and that
each is read fresh rather than baked in — the same list in two places drifted
apart twice in the system this was taken from.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from jobpilot.config import load
from jobpilot.terms import DEFAULT_LEVELS, Sources, Terms

EXAMPLE_TERMS = Path(__file__).resolve().parent.parent / "config" / "search_terms.example.json"
EXAMPLE_SOURCES = Path(__file__).resolve().parent.parent / "config" / "sources.example.yaml"


@pytest.fixture()
def written(tmp_path, make_config):
    """A settings file on disk, so companion files have somewhere to sit."""

    def _write(**overrides):
        from jobpilot.config import write as write_config

        path = tmp_path / "preferences.yaml"
        write_config(make_config(**overrides), path)
        return load(path)

    return _write


# -- job titles -----------------------------------------------------------


def test_the_titles_come_from_the_settings_when_there_is_no_companion_file(config):
    terms = Terms.from_config(config)
    assert "Machine Learning Engineer" in terms.core
    assert "Software Engineer" in terms.non_core
    assert "Sales" in terms.exclude
    assert terms.source is None


def test_a_companion_file_beside_the_settings_wins(written, tmp_path):
    config = written()
    (tmp_path / "search_terms.json").write_text(
        json.dumps({"core": ["Robotics Engineer"], "exclude": ["Driver"]}), encoding="utf-8"
    )
    terms = Terms.from_config(config)
    assert terms.core == ["Robotics Engineer"]
    assert terms.exclude == ["Driver"]
    assert terms.source is not None


def test_a_companion_file_is_read_again_every_time(written, tmp_path):
    """Adding a title changes the next search: no restart, no release."""
    config = written()
    path = tmp_path / "search_terms.json"
    path.write_text(json.dumps({"core": ["Robotics Engineer"]}), encoding="utf-8")
    assert Terms.from_config(config).core == ["Robotics Engineer"]

    path.write_text(json.dumps({"core": ["Robotics Engineer", "Controls Engineer"]}), encoding="utf-8")
    assert Terms.from_config(config).core == ["Robotics Engineer", "Controls Engineer"]


def test_a_group_left_out_of_the_companion_file_falls_back_to_the_settings(written, tmp_path):
    config = written()
    (tmp_path / "search_terms.json").write_text(json.dumps({"core": ["Robotics Engineer"]}), encoding="utf-8")
    assert "Software Engineer" in Terms.from_config(config).non_core


def test_an_unreadable_companion_file_says_so_plainly(written, tmp_path):
    from jobpilot.errors import ConfigError

    config = written()
    (tmp_path / "search_terms.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError, match="search_terms.json"):
        Terms.from_config(config)


def test_every_title_is_searched_bare_and_at_entry_level(config):
    queries = Terms(core=["ML Engineer"], levels=["New Grad", "Junior"]).queries()
    assert queries == ["ML Engineer", "New Grad ML Engineer", "Junior ML Engineer"]


def test_the_same_search_is_never_run_twice(config):
    queries = Terms(core=["ML Engineer"], non_core=["ml engineer"], levels=[]).queries()
    assert queries == ["ML Engineer"]


def test_the_default_entry_level_wording_is_used_when_none_is_given(config):
    assert Terms.from_config(config).levels == list(DEFAULT_LEVELS)


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Machine Learning Engineer", "core"),
        ("Senior Machine Learning Engineer", "core"),  # the title rule drops this, not the tier
        ("Software Engineer II", "non_core"),
        ("Sales Engineer", "irrelevant"),
        ("Perception Wizard", "non_core"),  # unknown is a question, not a refusal
    ],
)
def test_the_tier_a_title_implies(config, title, expected):
    assert Terms.from_config(config).tier_of(title) == expected


def test_the_shipped_example_is_valid_and_complete():
    payload = json.loads(EXAMPLE_TERMS.read_text(encoding="utf-8"))
    for group in ("core", "non_core", "exclude", "levels", "seniority"):
        assert payload[group], group
    assert payload["_README"], "a template nobody can read is not a template"


# -- where to look --------------------------------------------------------


def test_the_pages_to_read_come_from_the_settings(make_config):
    config = make_config(
        search={"sources": {"greenhouse": {"enabled": True, "boards": ["acme-robotics"]}}}
    )
    sources = Sources.from_config(config)
    assert sources.boards == {"greenhouse": ["acme-robotics"]}
    assert sources.families == ["greenhouse"]


def test_a_source_switched_off_is_not_read(make_config):
    config = make_config(
        search={"sources": {"greenhouse": {"enabled": False, "boards": ["acme-robotics"]}}}
    )
    assert Sources.from_config(config).boards == {}


def test_a_companion_sources_file_wins_and_carries_the_limits(written, tmp_path):
    config = written()
    (tmp_path / "sources.yaml").write_text(
        yaml.safe_dump(
            {
                "sources": {"lever": {"enabled": True, "boards": ["globex-systems"]}},
                "limits": {"per_board_max": 50, "seconds_between_requests": 2.5, "timeout_seconds": 9},
                "health": {"quiet_days_before_suggesting": 3},
            }
        ),
        encoding="utf-8",
    )
    sources = Sources.from_config(config)
    assert sources.boards == {"lever": ["globex-systems"]}
    assert sources.per_board_max == 50
    assert sources.seconds_between_requests == 2.5
    assert sources.timeout_seconds == 9
    assert sources.quiet_days_before_suggesting == 3


def test_the_search_pass_uses_whichever_list_exists(written, tmp_path):
    from jobpilot.search import built_in_sources

    config = written()
    (tmp_path / "sources.yaml").write_text(
        yaml.safe_dump({"sources": {"ashby": {"enabled": True, "boards": ["northwind-analytics"]}}}),
        encoding="utf-8",
    )
    names = [source.name for source in built_in_sources(config)]
    assert names == ["ashby"]


def test_what_is_being_watched_reads_like_a_sentence(make_config):
    config = make_config(
        search={"sources": {"greenhouse": {"enabled": True, "boards": ["a", "b"]}}}
    )
    assert "2 company job page(s)" in Sources.from_config(config).words()
    assert Sources().words() == "no company job pages yet"


def test_the_shipped_sources_example_is_valid():
    payload = yaml.safe_load(EXAMPLE_SOURCES.read_text(encoding="utf-8"))
    assert payload["sources"]["greenhouse"]["boards"]
    assert payload["limits"]["per_board_max"] > 0
    assert payload["health"]["quiet_days_before_suggesting"] > 0
