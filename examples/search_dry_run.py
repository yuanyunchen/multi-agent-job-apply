#!/usr/bin/env python3
"""One search pass, offline, over fixture job pages.

Shows the funnel the lead watches: how many postings each source returned, how
many survived de-duplication, and how many are new. Nothing is written to any
record and nothing goes over the network — the fetcher is a fixture reader.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobpilot.search import canonical_url, dedupe, run_search  # noqa: E402
from jobpilot.search.base import FixtureFetcher  # noqa: E402

from _shared import heading, jobs, settings  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

BOARDS = {
    "https://boards-api.greenhouse.io/v1/boards/acme-robotics/jobs?content=true": "greenhouse_acme.json",
    "https://api.lever.co/v0/postings/globex-systems?mode=json": "lever_globex.json",
    "https://api.ashbyhq.com/posting-api/job-board/northwind-analytics?includeCompensation=false": "ashby_northwind.json",
}


def main() -> int:
    config = settings(
        "search",
        search={
            "sources": {
                "greenhouse": {"enabled": True, "boards": ["acme-robotics"]},
                "lever": {"enabled": True, "boards": ["globex-systems"]},
                "ashby": {"enabled": True, "boards": ["northwind-analytics"]},
            }
        },
    )

    heading("Looking at three companies' own job pages")
    report = run_search(config, FixtureFetcher.from_dir(FIXTURES, BOARDS))
    for source, count in sorted(report.per_source.items()):
        print(f"  {source}: {count} posting(s)")
    print(f"\nFound {report.fetched}, {report.unique} of them distinct, {report.new} new to me.")
    if report.dead_sources:
        print(f"Returned nothing at all: {', '.join(report.dead_sources)}")
    for error in report.errors:
        print(f"  trouble: {error}")

    heading("What one posting looks like once it is read")
    first = report.jobs[0]
    print(f"  {first.company} — {first.title}")
    print(f"  where: {first.location or 'not stated'}")
    print(f"  posted: {first.posted_at or 'no date given'}")
    print(f"  link as the site gave it: {first.url}")
    print(f"  link once the tracking is stripped: {canonical_url(first.url)}")

    heading("The same posting arriving twice, from two places")
    original = jobs()[0]
    # Same job, a completely different link, and only the site's own identifier
    # in common. Matching on the link alone would miss this one.
    elsewhere = replace(
        original,
        url="https://an-aggregator.example/listing/55512?utm_campaign=weekly",
        source="an-aggregator",
        description="",
        posted_at="",
        location="",
    )
    collapsed = dedupe([original, elsewhere])
    print(f"  two rows in, {len(collapsed)} row out")
    print("  matched on: the company's own identifier, not the link")
    print(f"  the other link is remembered too: {collapsed[0].alternate_urls[0]}")
    print("  and the fuller description survived the merge:", bool(collapsed[0].description))

    print("\nNothing was written down and nothing left this computer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
