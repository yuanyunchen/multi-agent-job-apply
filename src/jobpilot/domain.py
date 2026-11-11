"""The handful of values every module passes around."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Literal

Tier = Literal["core", "non_core", "irrelevant"]

#: Statuses the tracker accepts. There is no synonym mapping on purpose: a typo
#: is a refused write, not a silently different row.
STATUSES: frozenset[str] = frozenset(
    {
        "new",  # discovered, not screened yet
        "pipeline",  # screened and eligible, waiting to be applied to
        "review",  # a human should look at this one
        "hold_pending_user",  # kept and tagged, never queued until the user decides
        "claimed",  # one lane owns it right now
        "skipped",  # dropped, with a quoted reason
        "closed",  # proven closed by a liveness receipt
        "parked",  # a required answer we refuse to invent
        "blocked",  # a wall we could not pass
        "submitted",  # a submit happened, no confirmation yet
        "applied",  # confirmed by a receipt
        "online_assessment",
        "interview",
        "offer",
        "rejected",
    }
)

#: Treated as "already applied" by the never-reapply guard.
SUBMITTED_STATUSES: frozenset[str] = frozenset(
    {"submitted", "applied", "online_assessment", "interview", "offer", "rejected"}
)

#: Still moving: not confirmed, but not a failure either.
IN_PROGRESS_STATUSES: frozenset[str] = frozenset({"new", "pipeline", "claimed", "review"})


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime | None = None) -> str:
    return (moment or now()).isoformat()


def normalize_name(name: str) -> str:
    """Company/people name normalization: exact or alias, never substring."""
    text = re.sub(r"[^a-z0-9]+", " ", (name or "").lower())
    text = re.sub(r"\b(inc|llc|ltd|corp|corporation|co|the|company)\b", " ", text)
    return " ".join(text.split())


def squeeze(text: str) -> str:
    """Collapse all whitespace. Used wherever quoted evidence is compared."""
    return " ".join((text or "").split())


@dataclass(frozen=True, slots=True)
class Job:
    """One posting, as a source found it."""

    company: str
    title: str
    url: str
    source: str
    ats: str = ""
    ats_job_id: str = ""
    location: str = ""
    description: str = ""
    posted_at: str = ""
    remote: bool | None = None
    alternate_urls: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    #: The id this job already has on the record, when it came from there.
    #: Without it, a row with no link would be indistinguishable from any other
    #: row with no link.
    id_hint: str = ""

    @property
    def job_id(self) -> str:
        """Stable local id: the one on the record, else the ATS identity, else the URL."""
        from .search.dedupe import ats_key, canonical_url  # local: avoids a cycle

        if self.id_hint:
            return self.id_hint
        basis = ats_key(self) or canonical_url(self.url)
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]

    def with_description(self, description: str) -> "Job":
        return replace(self, description=description)

    def to_row(self) -> dict[str, Any]:
        """The tracker row a freshly found job starts as."""
        from .search.dedupe import canonical_url

        return {
            "job_id": self.job_id,
            "url": canonical_url(self.url),
            "source_url": self.url,
            "alternate_urls": list(self.alternate_urls),
            "company": self.company,
            "title": self.title,
            "location": self.location,
            "ats": self.ats,
            "ats_job_id": self.ats_job_id,
            "source": self.source,
            "posted_at": self.posted_at,
            # The employer's own words are kept on the row: the reading step
            # needs them to quote a reason, and the quote is checked against
            # them again later. Losing the description loses the evidence.
            "description": self.description,
            "status": "new",
            "tags": list(self.tags),
            "flags": [],
        }


@dataclass(frozen=True, slots=True)
class Flag:
    """A deterministic observation. A flag never removes a job from the list."""

    code: str
    detail: str = ""
    quote: str = ""


@dataclass(frozen=True, slots=True)
class HardExclude:
    """The only automatic drops: a named company, a quoted line, a closed page."""

    code: str
    detail: str
    quote: str = ""
    quote_url: str = ""


@dataclass(frozen=True, slots=True)
class RuleResult:
    flags: tuple[Flag, ...] = ()
    hard_exclude: HardExclude | None = None

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(f.code for f in self.flags)


@dataclass(frozen=True, slots=True)
class Decision:
    """The outcome of screening one job."""

    job_id: str
    verdict: Literal["keep", "drop", "review"]
    tier: Tier
    reason: str = ""
    quote: str = ""
    quote_verified: bool = False
    source: str = ""  # which model (or rule) decided
    flags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Proposal:
    """A change the assistant would like to make. The user decides."""

    id: str
    title: str
    evidence: str
    expected_effect: str
    text: str  # what the user reads, in plain words
    change: dict[str, Any] = field(default_factory=dict)
    needs_approval: bool = True


@dataclass(frozen=True, slots=True)
class Message:
    """One thing to tell the user.

    ``simple`` is the only thing a user in simple mode ever sees; ``technical``
    is appended in technical mode. ``fallback`` is used if ``simple`` somehow
    fails the no-jargon lint.
    """

    kind: str
    simple: str
    technical: str = ""
    fallback: str = "I have an update for you."
    data: dict[str, Any] = field(default_factory=dict)
