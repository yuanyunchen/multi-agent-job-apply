"""The model screen: a job may only be dropped by quoting the posting.

The single most important invariant in the system:

    A model may drop a job only by quoting the employer's own description, and
    this module re-checks that the quote really is in the description.

If the quote is missing, too short to mean anything, or not present verbatim,
the drop is **rejected**: the job is kept and sent to review instead. A model
that returns nothing usable leaves the job on its lexical tier, marked for
review. Keeps never need a quote — only drops do.

Tiering uses the user's own categories: ``core`` is applied to first,
``non_core`` waits, ``irrelevant`` is never queued. Ambiguity favours core.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Iterable

from .config import Config
from .domain import Decision, Job, Tier, squeeze
from .rules import evaluate
from .providers.base import ModelProvider

#: A quote shorter than this proves nothing ("a", "and", "US").
MIN_QUOTE_CHARS = 25

SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["job_id", "verdict", "tier"],
        "properties": {
            "job_id": {"type": "string"},
            "verdict": {"enum": ["keep", "drop"]},
            "tier": {"enum": ["core", "non_core", "irrelevant"]},
            "quote": {"type": "string"},
            "reason": {"type": "string"},
        },
    },
}

PROMPT = """You are screening job postings for one candidate.

Decide, for each posting below, whether it is worth applying to.

Rules you must follow:
- You may answer "drop" ONLY if you copy a sentence from that posting's own
  description, word for word, into "quote". The quote is checked against the
  description; an invented or paraphrased quote invalidates your answer.
- If you are unsure, answer "keep". A missed job is cheaper than a wrong drop.
- "tier" is "core" for the candidate's primary targets, "non_core" for roles
  they would still take, "irrelevant" for roles they would never take.
  If a posting could be either core or non_core, answer "core".

The candidate wants, first of all: {core}
They would also consider: {non_core}
They never want: {excluded}
They need no more than {years} years of required experience.

Answer with JSON only: a list of objects
{{"job_id": "...", "verdict": "keep"|"drop", "tier": "core"|"non_core"|"irrelevant",
  "quote": "...", "reason": "short plain sentence"}}

Postings:
{postings}
"""


def quote_is_verbatim(quote: str, description: str) -> bool:
    """Is ``quote`` really in ``description``?

    Whitespace is collapsed on both sides (job boards wrap lines wherever they
    like) and the comparison is case-insensitive, but no word may differ.
    """
    needle = squeeze(quote)
    if len(needle) < MIN_QUOTE_CHARS:
        return False
    return needle.casefold() in squeeze(description).casefold()


def lexical_tier(job: Job, config: Config) -> Tier:
    """The tier we can work out from the title alone, before any model runs."""
    title = (job.title or "").lower()

    def hit(terms: Iterable[str]) -> bool:
        return any(str(term).lower() in title for term in terms if str(term).strip())

    if hit(config.get("search.categories.excluded", [])):
        return "irrelevant"
    if hit(config.get("search.categories.core", [])):
        return "core"
    if hit(config.get("search.categories.non_core", [])):
        return "non_core"
    return "non_core"  # unknown titles stay in the pipeline; the model decides


@dataclass
class ScreenOutcome:
    decisions: list[Decision]
    unverified_quotes: int = 0
    model_pending: int = 0
    answered_by: str = ""


def _postings_block(jobs: list[Job], jd_chars: int) -> str:
    blocks = []
    for job in jobs:
        blocks.append(
            f"--- job_id: {job.job_id}\n"
            f"company: {job.company}\ntitle: {job.title}\nlocation: {job.location}\n"
            f"description:\n{(job.description or '(no description available)')[:jd_chars]}"
        )
    return "\n".join(blocks)


def build_prompt(jobs: list[Job], config: Config, *, jd_chars: int = 6000) -> str:
    def listing(key: str) -> str:
        return ", ".join(str(t) for t in config.get(f"search.categories.{key}", [])) or "(nothing listed)"

    return PROMPT.format(
        core=listing("core"),
        non_core=listing("non_core"),
        excluded=listing("excluded"),
        years=config.get("search.max_required_years_experience", 2),
        postings=_postings_block(jobs, jd_chars),
    )


def parse_model_reply(text: str) -> dict[str, dict]:
    """Tolerant JSON parsing: models like to wrap their answer in prose."""
    payload = text.strip()
    if not payload:
        return {}
    if not payload.startswith(("[", "{")):
        match = re.search(r"(\[.*\]|\{.*\})", payload, re.DOTALL)
        payload = match.group(1) if match else ""
    try:
        parsed = json.loads(payload)
    except ValueError:
        return {}
    rows = parsed.get("decisions", []) if isinstance(parsed, dict) else parsed
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("job_id")): row
        for row in rows
        if isinstance(row, dict) and row.get("job_id") is not None
    }


def screen(
    jobs: list[Job],
    config: Config,
    provider: ModelProvider,
    *,
    batch_size: int = 10,
) -> ScreenOutcome:
    """Screen jobs in batches. Rules run first and only ever add flags."""
    decisions: list[Decision] = []
    unverified = 0
    pending = 0
    answered_by = ""

    for start in range(0, len(jobs), batch_size):
        batch = jobs[start : start + batch_size]
        rules = {job.job_id: evaluate(job, config) for job in batch}

        # A hard exclude is decided by code, with its own evidence: no model call.
        for job in list(batch):
            excluded = rules[job.job_id].hard_exclude
            if excluded:
                decisions.append(
                    Decision(
                        job_id=job.job_id,
                        verdict="drop",
                        tier="irrelevant",
                        reason=excluded.detail,
                        quote=excluded.quote,
                        # rules.hard_exclude already checked the quote, and a
                        # named company or a liveness receipt needs none.
                        quote_verified=True,
                        source=f"rule:{excluded.code}",
                        flags=rules[job.job_id].codes,
                    )
                )
                batch = [j for j in batch if j.job_id != job.job_id]
        if not batch:
            continue

        result = provider.complete(build_prompt(batch, config), schema=SCHEMA)
        answered_by = result.answered_by or provider.name
        replies = parse_model_reply(result.text)

        for job in batch:
            flags = rules[job.job_id].codes
            fallback_tier = lexical_tier(job, config)
            reply = replies.get(job.job_id)
            if not reply or reply.get("verdict") not in ("keep", "drop"):
                pending += 1
                decisions.append(
                    Decision(
                        job_id=job.job_id,
                        verdict="review",
                        tier=fallback_tier,
                        reason="I could not get a clear read on this one, so I kept it for you to look at.",
                        source=f"{answered_by}:no_answer",
                        flags=flags,
                    )
                )
                continue

            tier = reply.get("tier") if reply.get("tier") in ("core", "non_core", "irrelevant") else fallback_tier
            quote = str(reply.get("quote") or "")
            reason = str(reply.get("reason") or "").strip()

            if reply["verdict"] == "drop":
                if quote_is_verbatim(quote, job.description):
                    decisions.append(
                        Decision(
                            job_id=job.job_id,
                            verdict="drop",
                            tier="irrelevant",
                            reason=reason or "the posting rules this out",
                            quote=squeeze(quote),
                            quote_verified=True,
                            source=answered_by,
                            flags=flags,
                        )
                    )
                else:
                    # The drop is rejected: no evidence, so we keep the job.
                    unverified += 1
                    decisions.append(
                        Decision(
                            job_id=job.job_id,
                            verdict="review",
                            tier=fallback_tier,
                            reason="I wanted to skip this one but could not back it up, so I kept it.",
                            source=f"{answered_by}:unverified_quote",
                            flags=flags,
                        )
                    )
                continue

            decisions.append(
                Decision(
                    job_id=job.job_id,
                    verdict="keep",
                    tier="non_core" if tier == "irrelevant" else tier,
                    reason=reason or "looks like a fit",
                    source=answered_by,
                    flags=flags,
                )
            )

    return ScreenOutcome(decisions, unverified, pending, answered_by)


def decision_to_update(job: Job, decision: Decision) -> dict:
    """The tracker fields one screening decision writes."""
    status = {"keep": "pipeline", "drop": "skipped", "review": "review"}[decision.verdict]
    update = {
        "job_id": job.job_id,
        "status": status,
        "apply_tier": decision.tier,
        "review_verdict": decision.verdict,
        "review_verdict_source": decision.source,
        "flags": list(decision.flags),
    }
    if decision.verdict == "drop":
        update.update(
            skip_reason=decision.reason,
            skip_quote=decision.quote,
            skip_quote_url=job.url,
        )
    else:
        update["notes"] = decision.reason
    return update
