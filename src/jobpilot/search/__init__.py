"""Finding postings.

A :class:`~jobpilot.search.base.Source` fetches rows through an injectable
:class:`~jobpilot.search.base.Fetcher`, so tests run against fixtures and never
touch the network. Built-in sources read public job-board APIs that need no
login and no account.
"""

from .base import Fetcher, FixtureFetcher, Source, UrllibFetcher
from .dedupe import (
    POSSIBLE_DUP,
    ats_key,
    canonical_url,
    company_title_key,
    dedupe,
    possible_duplicates,
    title_norm,
    titles_differ_materially,
)
from .pipeline import SearchReport, built_in_sources, run_search

__all__ = [
    "Fetcher",
    "FixtureFetcher",
    "POSSIBLE_DUP",
    "Source",
    "UrllibFetcher",
    "SearchReport",
    "ats_key",
    "built_in_sources",
    "canonical_url",
    "company_title_key",
    "dedupe",
    "possible_duplicates",
    "run_search",
    "title_norm",
    "titles_differ_materially",
]
