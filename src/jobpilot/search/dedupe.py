"""De-duplication.

Two independent identities, because either one alone leaks:

* the **canonical URL** (tracking parameters stripped, host lower-cased); and
* the **ATS job id**, scoped to the company and the ATS family.

Lesson learned the hard way: de-duplicating on the URL alone misses the same
posting when a second source reports it with a different URL shape or an older
title; de-duplicating on the id alone misses postings from sources that do not
expose one.
"""

from __future__ import annotations

from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..domain import Job, normalize_name

#: Query parameters that never identify a posting.
TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "fbclid",
        "gclid",
        "msclkid",
        "ref",
        "referrer",
        "source",
        "src",
        "trk",
        "trackingid",
        "gh_src",
        "gh_jid_src",
        "lever-source",
        "lever-origin",
    }
)


def canonical_url(url: str) -> str:
    """A stable form of a posting URL. Empty input stays empty."""
    raw = (url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw.lstrip("/")
    parts = urlsplit(raw)
    host = (parts.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=False)
        if key.lower() not in TRACKING_PARAMS
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


def ats_key(job: Job) -> str:
    """``company|ats|id`` — only when the posting really carries an id."""
    if not job.ats_job_id:
        return ""
    family = (job.ats or "").strip().lower()
    return f"{normalize_name(job.company)}|{family}|{str(job.ats_job_id).strip().lower()}"


def identities(job: Job) -> list[str]:
    """Every key this job should be remembered under."""
    keys = [f"url:{canonical_url(url)}" for url in (job.url, *job.alternate_urls) if url]
    key = ats_key(job)
    if key:
        keys.append(f"ats:{key}")
    return keys


def _merge(kept: Job, other: Job) -> Job:
    """Keep the richer row; remember the other URL; never lose a description."""
    from dataclasses import replace

    extra = {canonical_url(u) for u in (other.url, *other.alternate_urls) if u}
    extra -= {canonical_url(u) for u in (kept.url, *kept.alternate_urls) if u}
    return replace(
        kept,
        description=kept.description or other.description,
        posted_at=kept.posted_at or other.posted_at,
        location=kept.location or other.location,
        ats=kept.ats or other.ats,
        ats_job_id=kept.ats_job_id or other.ats_job_id,
        alternate_urls=tuple(sorted({*kept.alternate_urls, *extra})),
        tags=tuple(sorted({*kept.tags, *other.tags})),
    )


def dedupe(jobs: Iterable[Job]) -> list[Job]:
    """Collapse duplicates, keeping the first-seen row and merging the rest."""
    order: list[int] = []
    rows: dict[int, Job] = {}
    index: dict[str, int] = {}
    for job in jobs:
        hit = next((index[key] for key in identities(job) if key in index), None)
        if hit is None:
            slot = len(rows)
            rows[slot] = job
            order.append(slot)
        else:
            slot = hit
            rows[slot] = _merge(rows[slot], job)
        for key in identities(rows[slot]):
            index[key] = slot
    return [rows[slot] for slot in order]


def is_known(job: Job, known_keys: set[str]) -> bool:
    """Has this posting been seen before? ``known_keys`` comes from the tracker."""
    return any(key in known_keys for key in identities(job))


def row_identities(row: dict) -> list[str]:
    """The same keys, for a tracker row rather than a freshly found job."""
    keys = [
        f"url:{canonical_url(url)}"
        for url in [row.get("url", ""), row.get("source_url", ""), *(row.get("alternate_urls") or [])]
        if url
    ]
    if row.get("ats_job_id"):
        family = str(row.get("ats", "")).strip().lower()
        keys.append(
            f"ats:{normalize_name(str(row.get('company', '')))}|{family}|"
            f"{str(row['ats_job_id']).strip().lower()}"
        )
    return keys
