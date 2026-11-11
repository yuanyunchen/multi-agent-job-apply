"""Finding postings.

A :class:`~jobpilot.search.base.Source` fetches rows through an injectable
:class:`~jobpilot.search.base.Fetcher`, so tests run against fixtures and never
touch the network. Built-in sources read public job-board APIs that need no
login and no account.
"""

from .base import Fetcher, FixtureFetcher, Source, UrllibFetcher
from .dedupe import ats_key, canonical_url, dedupe
from .pipeline import SearchReport, built_in_sources, run_search

__all__ = [
    "Fetcher",
    "FixtureFetcher",
    "Source",
    "UrllibFetcher",
    "SearchReport",
    "ats_key",
    "built_in_sources",
    "canonical_url",
    "dedupe",
    "run_search",
]
