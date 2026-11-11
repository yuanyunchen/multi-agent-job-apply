"""Deterministic rules. They FLAG; they do not drop.

This split is the backbone of the system: code that pattern-matches text only
ever *annotates* a job, and a model (``screen``) makes the call while quoting
the posting. Flags are what the model is told to pay attention to, and what a
human sees next to a decision.

:func:`hard_exclude` is the only exception, and it is deliberately tiny — the
three automatic drops:

1. a company the user named on their never-apply list (no quote needed);
2. an explicit, **quoted** sentence from the employer's own description that
   rules the user out entirely (no sponsorship at all, citizen/green-card only,
   clearance required, ITAR/US-person);
3. a posting proven closed by a structured liveness receipt
   (``{"http_code": 404, "url": ..., "checked_at": ...}``) — free text that
   merely contains "404" is not a receipt.

Nothing else drops. A posting that accepts OPT/CPT/STEM-OPT/EAD or an existing
visa but will not sponsor a new one is a normal role, not a disqualifier.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Iterable

from .config import Config
from .domain import Flag, HardExclude, Job, RuleResult, normalize_name, squeeze

# -- sentence families ---------------------------------------------------

#: Phrases that, on their own, mean "we will not sponsor at all".
NO_SPONSORSHIP = (
    "will not sponsor",
    "do not sponsor",
    "does not sponsor",
    "unable to sponsor",
    "cannot sponsor",
    "no visa sponsorship",
    "without the need for sponsorship",
    "without the need for visa sponsorship",
    "without requiring sponsorship",
    "without sponsorship",
    "not eligible for visa sponsorship",
    "not eligible for sponsorship",
    "sponsorship is not available",
    "sponsorship not available",
    "we are not able to sponsor",
    "no sponsorship",
)

#: Phrases that mean the user's own status is fine — these cancel the family.
SPONSORSHIP_ALLOWANCES = (
    "opt",
    "cpt",
    "stem opt",
    "ead",
    "f-1",
    "f1 visa",
    "existing visa",
    "current work authorization",
    "already authorized",
    "transfer an existing",
    "will sponsor",
    "do sponsor",
    "sponsorship available",
    "we sponsor",
)

CITIZEN_ONLY = (
    "u.s. citizenship is required",
    "us citizenship is required",
    "must be a u.s. citizen",
    "must be a us citizen",
    "u.s. citizens only",
    "us citizens only",
    "citizenship required",
    "green card holders only",
    "citizen or green card",
    "permanent resident only",
)

CLEARANCE = (
    "security clearance",
    "active clearance",
    "ts/sci",
    "top secret",
    "secret clearance",
    "public trust clearance",
)

ITAR = ("itar", "u.s. person", "us person", "export control")

PHD_ONLY = ("phd required", "ph.d. required", "phd is required", "requires a phd", "doctorate required")

YOE_PATTERN = re.compile(
    r"(?P<low>\d{1,2})\s*(?:\+|or more|plus)?\s*(?:-|to|–)?\s*(?P<high>\d{1,2})?\s*"
    r"(?:\+)?\s*years?(?:\s+of)?(?:\s+\w+){0,4}?\s*experience",
    re.IGNORECASE,
)

#: "preferred" / "nice to have" years never drop a row, and a ceiling
#: ("up to 3 years", "0-2 years") is not a minimum.
YOE_SOFT = ("preferred", "nice to have", "a plus", "ideally", "desired", "bonus")
YOE_CEILING = ("up to", "at most", "less than", "fewer than", "no more than")

REMOTE_WORDS = ("remote", "work from home", "distributed", "anywhere")

US_HINTS = (
    "united states",
    "usa",
    "u.s.",
    " us ",
    "remote",
    "new york",
    "san francisco",
    "seattle",
    "boston",
    "austin",
    "chicago",
    "los angeles",
)

MUST_WORK_ABROAD = (
    "must be based in",
    "must reside in",
    "must be located in",
    "requires residence in",
    "eligible to work in the uk",
    "eligible to work in canada",
    "eligible to work in india",
    "work permit for",
)


#: Something that ends in a period but not in a sentence: "U.S.", "Inc.", "e.g.".
ABBREVIATION_END = re.compile(
    r"(?:\b[A-Z]\.|\b(?:U\.S|Inc|Ltd|Co|No|vs|e\.g|i\.e|Mr|Ms|Dr|Ph\.D)\.)$"
)


def sentences(text: str) -> list[str]:
    """Split a description into sentences, keeping bullet lines whole.

    "Applicants must be a U.S. citizen" is one sentence, not two: a quote has to
    read the way the employer wrote it.
    """
    out: list[str] = []
    for line in (text or "").splitlines():
        pieces: list[str] = []
        for piece in re.split(r"(?<=[.!?;])\s+", line):
            if pieces and ABBREVIATION_END.search(pieces[-1]):
                pieces[-1] = f"{pieces[-1]} {piece}"
            else:
                pieces.append(piece)
        out.extend(cleaned for cleaned in (squeeze(p) for p in pieces) if cleaned)
    return out


@lru_cache(maxsize=512)
def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Whole-phrase, whole-word matching: 'opt' must not match 'optimize'."""
    body = r"\s+".join(re.escape(word) for word in phrase.split())
    left = r"\b" if phrase[:1].isalnum() else ""
    right = r"\b" if phrase[-1:].isalnum() else ""
    return re.compile(left + body + right, re.IGNORECASE)


def mentions(text: str, phrases: Iterable[str]) -> bool:
    return any(_phrase_pattern(phrase).search(text or "") for phrase in phrases)


def find_sentence(text: str, phrases: Iterable[str]) -> str:
    """The first sentence containing any phrase, verbatim as written."""
    for sentence in sentences(text):
        if mentions(sentence, phrases):
            return sentence
    return ""


def denies_sponsorship(sentence: str) -> bool:
    """True only when the sentence rules out sponsorship *entirely*.

    This is the one place that decision is made. A sentence that also mentions
    an allowance (OPT, an existing visa, …) is not a denial, and a sentence that
    never says "sponsor"/"visa" is not about sponsorship at all.
    """
    if not mentions(sentence, NO_SPONSORSHIP):
        return False
    if not mentions(sentence, ("sponsor", "sponsorship", "visa")):
        return False
    return not mentions(sentence, SPONSORSHIP_ALLOWANCES)


def required_years(text: str) -> tuple[int | None, str]:
    """The highest explicitly *required* minimum, and the sentence it came from."""
    best: int | None = None
    quote = ""
    for sentence in sentences(text):
        low = sentence.lower()
        if any(word in low for word in YOE_SOFT) or any(word in low for word in YOE_CEILING):
            continue
        for match in YOE_PATTERN.finditer(sentence):
            low_bound = int(match.group("low"))
            if low_bound == 0:
                continue
            if best is None or low_bound > best:
                best, quote = low_bound, sentence
    return best, quote


# -- the flag layer ------------------------------------------------------


def evaluate(job: Job, config: Config, *, liveness: dict[str, Any] | None = None) -> RuleResult:
    """Flag everything worth knowing about ``job``; drop almost nothing."""
    flags: list[Flag] = []
    jd = job.description or ""
    auth = config.section("work_authorization").get("hard_exclude_on", {})
    title_low = (job.title or "").lower()

    # --- sponsorship / eligibility family
    sponsor_sentence = find_sentence(jd, NO_SPONSORSHIP)
    if sponsor_sentence:
        if denies_sponsorship(sponsor_sentence):
            flags.append(Flag("no_sponsorship", "says it will not sponsor", sponsor_sentence))
        else:
            flags.append(
                Flag("sponsorship_mentioned", "mentions sponsorship but allows your status", sponsor_sentence)
            )

    citizen_sentence = find_sentence(jd, CITIZEN_ONLY)
    if citizen_sentence:
        flags.append(Flag("citizen_only", "asks for citizenship or a green card", citizen_sentence))

    clearance_sentence = find_sentence(jd, CLEARANCE)
    if clearance_sentence:
        flags.append(Flag("clearance", "mentions a security clearance", clearance_sentence))

    itar_sentence = find_sentence(jd, ITAR)
    if itar_sentence:
        flags.append(Flag("itar_us_person", "mentions export control or US-person status", itar_sentence))

    # --- location
    abroad_sentence = find_sentence(jd, MUST_WORK_ABROAD)
    haystack = f"{job.location} {job.title}"
    looks_us = mentions(haystack, US_HINTS) or job.remote is True
    countries = [str(c).upper() for c in config.get("search.locations.countries", ["US"])]
    if "US" in countries and job.location and not looks_us:
        flags.append(Flag("location_outside_preference", f"location reads {job.location!r}"))
    if abroad_sentence:
        flags.append(Flag("must_work_abroad", "requires living somewhere else", abroad_sentence))
    if mentions(haystack, REMOTE_WORDS) or job.remote is True:
        flags.append(Flag("remote", "remote or remote-friendly"))

    # --- experience and degree
    threshold = int(config.get("search.max_required_years_experience", 2))
    years, years_quote = required_years(jd)
    if years is not None and years > threshold:
        flags.append(Flag("years_experience", f"requires {years} years, you set {threshold}", years_quote))

    phd_sentence = find_sentence(jd, PHD_ONLY)
    if phd_sentence:
        flags.append(Flag("phd_only", "requires a doctorate", phd_sentence))

    # --- title
    for word in config.get("search.seniority_excludes", []):
        if re.search(rf"\b{re.escape(str(word).lower())}\b", title_low):
            flags.append(Flag("senior_title", f"the title says {word!r}"))
            break
    for term in config.get("search.categories.excluded", []):
        if str(term).lower() in title_low:
            flags.append(Flag("excluded_category", f"the title matches your excluded list ({term})"))
            break

    # --- companies
    company = normalize_name(job.company)
    if company in {normalize_name(c) for c in config.get("search.company_rules.hold_pending_user", [])}:
        flags.append(Flag("hold_pending_user", "a company you asked me to hold for your decision"))

    # --- freshness
    if job.posted_at:
        flags.append(Flag("fresh", "posted recently") if _within(job.posted_at, 3) else Flag("aging"))
    else:
        flags.append(Flag("freshness_unknown", "no posting date"))

    return RuleResult(tuple(flags), hard_exclude(job, config, liveness=liveness, flags=flags, auth=auth))


def _within(posted_at: str, days: int) -> bool:
    try:
        moment = datetime.fromisoformat(str(posted_at).replace("Z", "+00:00"))
    except ValueError:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment >= datetime.now(timezone.utc) - timedelta(days=days)


def hard_exclude(
    job: Job,
    config: Config,
    *,
    liveness: dict[str, Any] | None = None,
    flags: list[Flag] | None = None,
    auth: dict[str, Any] | None = None,
) -> HardExclude | None:
    """The only three automatic drops. Everything else is the model's call."""
    auth = auth if auth is not None else config.section("work_authorization").get("hard_exclude_on", {})

    # 1. a company the user named.
    excluded = {normalize_name(c) for c in config.get("search.company_rules.hard_exclude", [])}
    if normalize_name(job.company) in excluded:
        return HardExclude("company_excluded", f"{job.company} is on your never-apply list")

    # 2. a quoted, disqualifying sentence from the employer's own description.
    by_code = {flag.code: flag for flag in (flags or [])}
    families = (
        ("no_sponsorship", "no_sponsorship_at_all", "says it will not sponsor a work visa at all"),
        ("citizen_only", "citizen_or_gc_only", "asks for US citizenship or a green card"),
        ("clearance", "clearance_required", "requires a security clearance"),
        ("itar_us_person", "itar_us_person", "is restricted to US persons"),
    )
    for code, setting, reason in families:
        flag = by_code.get(code)
        if flag and auth.get(setting) and flag.quote and squeeze(flag.quote) in squeeze(job.description):
            return HardExclude(code, reason, quote=flag.quote, quote_url=job.url)

    # 3. a structured liveness receipt. Free text containing "404" is not one.
    if liveness and _is_receipt(liveness):
        return HardExclude("posting_closed", "the posting is no longer open", quote_url=str(liveness["url"]))
    return None


def _is_receipt(receipt: dict[str, Any]) -> bool:
    code = receipt.get("http_code")
    return (
        isinstance(receipt, dict)
        and isinstance(code, int)
        and code in (404, 410, 301, 302, 403)
        and bool(receipt.get("url"))
        and bool(receipt.get("checked_at"))
    )
