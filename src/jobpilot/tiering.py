"""Which queue does a job go in: first choice, second choice, or neither?

This is the one place that answer is given, and it is given in two layers that
never mix:

1. **Rules.** Configurable title terms decide ``core`` / ``non_core`` /
   ``excluded``, and a tiny set of hard excludes (:mod:`jobpilot.rules`) drops a
   job outright — a named company, a quoted disqualifying sentence, a posting
   proven closed. Rules are offline, repeatable and cost nothing.
2. **A model, optionally.** If a :class:`TierHook` is supplied, it may change
   the tier and may drop a job — but only by quoting the posting, and the quote
   is re-checked here against the employer's own text. A hook that returns
   nothing, times out or quotes something that is not in the posting leaves the
   rule answer standing and marks the job ``model_pending``.

Two rules that exist because the alternative lost good jobs:

* **Ambiguity favours core.** A job that could be either goes in the first
  queue, where it is applied to while it is still open.
* **A hook may never promote a drop over a keep without evidence.** The rules
  flag; only a quote drops.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol, runtime_checkable

from .config import Config
from .domain import Flag, HardExclude, Job, Tier, squeeze
from .rules import evaluate

#: ``excluded`` is the user's own "never this" list; ``irrelevant`` is what the
#: tracker records for anything that will never be queued, whatever the reason.
TIERS: tuple[Tier, ...] = ("core", "non_core", "irrelevant")

#: A quote shorter than this proves nothing. Shared with :mod:`jobpilot.screen`.
MIN_QUOTE_CHARS = 25


@dataclass(frozen=True, slots=True)
class TierDecision:
    """One job's tier, with where it came from and why."""

    job_id: str
    tier: Tier
    #: ``rules`` · ``rules:<hard exclude code>`` · a model name · ``model_pending``
    source: str
    reason: str = ""
    quote: str = ""
    quote_verified: bool = False
    flags: tuple[str, ...] = ()
    hard_exclude: HardExclude | None = None
    model_pending: bool = False

    @property
    def queued(self) -> bool:
        """Will this job ever reach the apply queue?"""
        return self.tier in ("core", "non_core")


@runtime_checkable
class TierHook(Protocol):
    """An optional model step. Everything about it is allowed to fail.

    It is handed the jobs the rules did not already settle, together with the
    rule flags, and answers with one entry per ``job_id``:

    ``{"job_id": str, "tier": "core"|"non_core"|"irrelevant", "quote": str, "reason": str}``

    A ``tier`` of ``irrelevant`` is a drop and needs a verbatim ``quote``.
    """

    name: str

    def rank(self, jobs: list[Job], flags: dict[str, tuple[str, ...]]) -> dict[str, dict[str, Any]]: ...


@dataclass
class NoHook:
    """The default: rules only. Offline, free, and perfectly usable."""

    name: str = "rules"

    def rank(self, jobs: list[Job], flags: dict[str, tuple[str, ...]]) -> dict[str, dict[str, Any]]:
        return {}


# -- the rule layer -------------------------------------------------------


def _terms(config: Config, key: str) -> list[str]:
    values = config.get(f"search.categories.{key}", []) or []
    return [str(term).strip() for term in values if str(term).strip()]


def _matches(title: str, terms: Iterable[str]) -> str:
    """The first term that appears in the title, or ``""``.

    Substring matching is right here and wrong for company names: a user who
    lists "Data Engineer" means titles containing it, but a user who excludes
    "Acme" does not mean "Acme Robotics Holdings".
    """
    low = (title or "").lower()
    return next((term for term in terms if term.lower() in low), "")


def rule_tier(job: Job, config: Config) -> tuple[Tier, str]:
    """``(tier, why)`` from the title and the user's own term lists.

    An unknown title is ``non_core``, not ``irrelevant``: a title nobody listed
    is a question for a model, not a reason to throw a job away.
    """
    excluded = _matches(job.title, _terms(config, "excluded"))
    if excluded:
        return "irrelevant", f"the title matches your never-apply list ({excluded})"
    core = _matches(job.title, _terms(config, "core"))
    if core:
        return "core", f"the title matches one of the jobs you want most ({core})"
    non_core = _matches(job.title, _terms(config, "non_core"))
    if non_core:
        return "non_core", f"the title matches a job you would still take ({non_core})"
    return "non_core", "the title is not on any of your lists, so I kept it for a closer look"


# -- the whole classifier -------------------------------------------------


def classify(
    jobs: list[Job],
    config: Config,
    *,
    hook: TierHook | None = None,
    liveness: dict[str, dict[str, Any]] | None = None,
) -> list[TierDecision]:
    """Tier every job. Rules first, then the hook for whatever is left."""
    liveness = liveness or {}
    rules: dict[str, tuple[Tier, str, tuple[Flag, ...], HardExclude | None]] = {}
    decided: dict[str, TierDecision] = {}
    undecided: list[Job] = []

    for job in jobs:
        result = evaluate(job, config, liveness=liveness.get(job.job_id))
        tier, why = rule_tier(job, config)
        rules[job.job_id] = (tier, why, result.flags, result.hard_exclude)

        if result.hard_exclude is not None:
            # Decided by code, with its own evidence. No model call, no cost.
            decided[job.job_id] = TierDecision(
                job_id=job.job_id,
                tier="irrelevant",
                source=f"rules:{result.hard_exclude.code}",
                reason=result.hard_exclude.detail,
                quote=result.hard_exclude.quote,
                quote_verified=True,
                flags=result.codes,
                hard_exclude=result.hard_exclude,
            )
            continue
        if tier == "irrelevant":
            decided[job.job_id] = TierDecision(
                job_id=job.job_id,
                tier="irrelevant",
                source="rules",
                reason=why,
                quote_verified=True,  # the user's own list needs no quote
                flags=result.codes,
            )
            continue
        undecided.append(job)

    answers: dict[str, dict[str, Any]] = {}
    hook_name = ""
    if hook is not None and undecided:
        hook_name = getattr(hook, "name", "model")
        hints = {job.job_id: tuple(f.code for f in rules[job.job_id][2]) for job in undecided}
        try:
            answers = hook.rank(undecided, hints) or {}
        except Exception:  # a hook that breaks must never stop the pass
            answers = {}
        if not isinstance(answers, dict):
            answers = {}

    for job in undecided:
        tier, why, flags, _ = rules[job.job_id]
        codes = tuple(f.code for f in flags)
        reply = answers.get(job.job_id)
        if hook is None:
            decided[job.job_id] = TierDecision(
                job_id=job.job_id, tier=tier, source="rules", reason=why, flags=codes
            )
            continue
        if not isinstance(reply, dict) or reply.get("tier") not in TIERS:
            decided[job.job_id] = TierDecision(
                job_id=job.job_id,
                tier=tier,
                source="model_pending",
                reason="I could not get a clear read on this one, so I kept the rule answer.",
                flags=codes,
                model_pending=True,
            )
            continue

        wanted: Tier = reply["tier"]
        quote = squeeze(str(reply.get("quote") or ""))
        reason = str(reply.get("reason") or "").strip() or why
        if wanted == "irrelevant":
            if not quote_is_verbatim(quote, job.description):
                # A drop with no evidence is thrown away, not the job.
                decided[job.job_id] = TierDecision(
                    job_id=job.job_id,
                    tier=tier,
                    source=f"{hook_name}:unverified_quote",
                    reason="I wanted to rule this out but could not back it up, so I kept it.",
                    flags=codes,
                )
                continue
            decided[job.job_id] = TierDecision(
                job_id=job.job_id,
                tier="irrelevant",
                source=hook_name,
                reason=reason,
                quote=quote,
                quote_verified=True,
                flags=codes,
            )
            continue

        decided[job.job_id] = TierDecision(
            job_id=job.job_id, tier=wanted, source=hook_name, reason=reason, flags=codes
        )

    return [decided[job.job_id] for job in jobs if job.job_id in decided]


def quote_is_verbatim(quote: str, description: str) -> bool:
    """Is ``quote`` really in ``description``, word for word?

    Whitespace is collapsed on both sides (job boards wrap lines wherever they
    like) and case is ignored, but no word may differ.
    """
    needle = squeeze(quote)
    if len(needle) < MIN_QUOTE_CHARS:
        return False
    return needle.casefold() in squeeze(description).casefold()


@dataclass
class TierCounts:
    core: int = 0
    non_core: int = 0
    irrelevant: int = 0
    model_pending: int = 0
    unverified_quotes: int = 0
    by_source: dict[str, int] = field(default_factory=dict)


def summarize(decisions: Iterable[TierDecision]) -> TierCounts:
    counts = TierCounts()
    for decision in decisions:
        setattr(counts, decision.tier, getattr(counts, decision.tier) + 1)
        if decision.model_pending:
            counts.model_pending += 1
        if decision.source.endswith(":unverified_quote"):
            counts.unverified_quotes += 1
        head = decision.source.split(":")[0]
        counts.by_source[head] = counts.by_source.get(head, 0) + 1
    return counts
