"""De-duplication.

Three identities, because no one of them is enough on its own:

* the **canonical URL** (tracking parameters stripped, host lower-cased);
* the **ATS job id**, scoped to the company and the ATS family; and
* **company + title**, normalised, which catches the same posting arriving
  from two sources that share neither a URL shape nor an id.

Lesson learned the hard way: de-duplicating on the URL alone misses the same
posting when a second source reports it with a different URL shape or an older
title; de-duplicating on the id alone misses postings from sources that do not
expose one.

The third identity is deliberately **weaker than the other two**. Company and
title matched loosely once removed good rows silently — two genuinely different
openings at one company often share a title. So:

* a URL or id match is a **merge**: one posting, seen twice;
* a company+title match is a **flag** (``possible_dup``) unless the titles are
  materially the same, and it never silently removes the row.
"""

from __future__ import annotations

import re
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


# -- company + title, the weak identity -----------------------------------

#: Words that say where a job is, not which job it is. A title ending in one of
#: these after a dash or a comma is the same title without it.
TRAILING_LOCATIONS = frozenset(
    {
        "remote",
        "hybrid",
        "onsite",
        "on site",
        "us",
        "usa",
        "united states",
        "north america",
        "emea",
        "apac",
        "canada",
        "new york",
        "nyc",
        "san francisco",
        "sf",
        "bay area",
        "seattle",
        "boston",
        "austin",
        "chicago",
        "london",
        "east coast",
        "west coast",
    }
)

#: Title words so common they say nothing about *which* opening this is. Two
#: titles built only out of these are not evidence of anything.
GENERIC_TITLE_WORDS = frozenset(
    {
        "a", "an", "and", "at", "associate", "campus", "career", "college", "date", "dates",
        "developer", "early", "engineer", "engineering", "engineers", "entry", "for", "full",
        "fulltime", "grad", "graduate", "graduates", "hybrid", "in", "junior", "jr", "level",
        "member", "mid", "new", "of", "onsite", "or", "position", "principal", "program",
        "remote", "role", "senior", "software", "sr", "staff", "start", "starts", "technical",
        "the", "time", "to", "university", "us", "usa", "with",
    }
)

#: "II" and "2" distinguish a level, not a different opening.
LEVEL_WORDS = frozenset({"i", "ii", "iii", "iv", "1", "2", "3", "4"})

POSSIBLE_DUP = "possible_dup"


def title_norm(title: str) -> str:
    """A comparable form of a job title.

    Parentheses go, and so does a trailing location after a dash or a comma:
    "Software Engineer, New York" and "Software Engineer (Remote)" and
    "Software Engineer" are one title.
    """
    text = re.sub(r"\([^()]*\)", " ", (title or "").lower())
    text = " ".join(text.split())
    while True:
        cut = max(text.rfind(" - "), text.rfind(", "))
        if cut < 0:
            break
        width = 3 if text[cut : cut + 3] == " - " else 2
        suffix = re.sub(r"^\W+|\W+$", "", text[cut + width :].strip())
        if suffix not in TRAILING_LOCATIONS:
            break
        text = text[:cut].rstrip()
    return re.sub(r"^\W+|\W+$", "", text).strip()


def _distinctive_words(title: str) -> set[str]:
    """The words in a title that actually identify the opening."""
    out = set()
    for word in re.findall(r"[a-z0-9]+", title_norm(title)):
        if word in GENERIC_TITLE_WORDS or word in LEVEL_WORDS:
            continue
        if re.search(r"[0-9]{4,}", word):  # a requisition number, not a word
            continue
        if re.search(r"[a-z]", word) and re.search(r"[0-9]", word):
            continue
        out.add(word)
    return out


def titles_differ_materially(first: str, second: str) -> bool:
    """Do two titles describe clearly different openings?

    True only when both titles have identifying words and share none of them.
    Two titles made purely of generic words ("Software Engineer" and "Engineer,
    New Grad") are *not* materially different — they are simply not evidence.
    """
    left, right = _distinctive_words(first), _distinctive_words(second)
    return bool(left and right and left.isdisjoint(right))


def company_title_key(company: str, title: str) -> str:
    """The weak identity: ``company|title``, or empty when either is missing."""
    name, role = normalize_name(company), title_norm(title)
    return f"{name}|{role}" if name and role else ""


def possible_duplicates(row: dict, others: Iterable[dict]) -> list[dict]:
    """Rows that may be the same posting as ``row`` by company and title.

    Used to *flag*, never to drop: the caller writes ``possible_dup`` and the
    row stays in the queue. Rows whose titles differ materially are excluded,
    and so is the row itself.
    """
    key = company_title_key(str(row.get("company", "")), str(row.get("title", "")))
    if not key:
        return []
    own_ids = set(row_identities(row))
    out = []
    for other in others:
        if other is row:
            continue
        if str(other.get("job_id") or "~") == str(row.get("job_id") or "!"):
            continue
        if own_ids & set(row_identities(other)):
            continue  # already the same posting by a strong identity
        if company_title_key(str(other.get("company", "")), str(other.get("title", ""))) != key:
            continue
        if titles_differ_materially(str(row.get("title", "")), str(other.get("title", ""))):
            continue
        out.append(other)
    return out


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
