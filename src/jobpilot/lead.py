"""The Lead: watches the numbers, proposes changes, never makes them.

The Lead is the only part of the system that talks to the user, and the only
part allowed to *suggest* a change to their settings. It is deliberately
powerless: :func:`proposals` returns suggestions with ``needs_approval=True``,
and :func:`apply_proposal` refuses unless the caller passes an explicit
approval. A preference is never changed by the assistant on its own.

Three ways a suggestion appears:

* the numbers justify it (:func:`proposals`);
* the user says something in plain words — "also include data scientist roles
  as core" — and :func:`interpret_request` turns it into a proposed change;
* a self-improvement that touches no setting at all, which is reported in one
  plain line and needs nobody's permission (:func:`self_improvement_note`).

Suggestions are stored, so ``approve <id>`` and ``decline <id>`` work in a later
conversation, and every decision is written down.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from .config import Config, backup_settings, write as write_config
from .domain import Proposal, iso
from .errors import JobpilotError
from .queue import depth
from .tracker import Tracker, normalize_status
from .ui import Renderer
from .verify import unconfirmed_rate

#: Thresholds at which a number becomes worth mentioning.
UNCONFIRMED_ALARM = 0.30
EMPTY_QUEUE_DAYS = 2
BLOCK_STREAK = 3
IDLE_LANE_MINUTES = 60


@dataclass
class Metrics:
    confirmed: int = 0
    sent_waiting: int = 0
    unconfirmed_rate: float = 0.0
    queue_core: int = 0
    queue_non_core: int = 0
    empty_queue_days: int = 0
    dead_sources: list[str] = field(default_factory=list)
    blocks_by_host: dict[str, int] = field(default_factory=dict)
    idle_lane_minutes: int = 0
    parked_questions: list[str] = field(default_factory=list)

    @property
    def queue_total(self) -> int:
        return self.queue_core + self.queue_non_core


def metrics(
    rows: Iterable[dict],
    *,
    dead_sources: Iterable[str] = (),
    empty_queue_days: int = 0,
    idle_lane_minutes: int = 0,
) -> Metrics:
    rows = list(rows)
    sizes = depth(rows)
    rate, _unconfirmed, _considered = unconfirmed_rate(rows)
    out = Metrics(
        unconfirmed_rate=rate,
        queue_core=sizes["core"],
        queue_non_core=sizes["non_core"],
        empty_queue_days=empty_queue_days,
        dead_sources=sorted(dead_sources),
        idle_lane_minutes=idle_lane_minutes,
    )
    for row in rows:
        status = normalize_status(row.get("status"))
        if status == "applied":
            out.confirmed += 1
        elif status == "submitted":
            out.sent_waiting += 1
        elif status == "blocked":
            host = str(row.get("ats") or row.get("company") or "somewhere")
            out.blocks_by_host[host] = out.blocks_by_host.get(host, 0) + 1
        elif status == "parked":
            out.parked_questions.extend(str(q) for q in row.get("pending_questions") or [])
    return out


def proposals(numbers: Metrics, config: Config) -> list[Proposal]:
    """Suggestions worth the user's attention, each with its evidence."""
    out: list[Proposal] = []

    if numbers.sent_waiting >= 3 and numbers.unconfirmed_rate >= UNCONFIRMED_ALARM:
        out.append(
            Proposal(
                id="confirm_rate_low",
                title="Some applications are not being confirmed",
                evidence=(
                    f"{numbers.sent_waiting} applications went out but never came back with a confirmation "
                    f"({numbers.unconfirmed_rate:.0%} of the ones I can check)."
                ),
                expected_effect="More of your applications would be confirmed, and fewer would quietly get stuck.",
                text=(
                    "Several applications went out but I never saw a confirmation email. "
                    "May I start reading the short verification codes some employers email, "
                    "so I can finish those applications myself?"
                ),
                change={"verify.mail_reader": "json_export"},
            )
        )

    if numbers.queue_total == 0 and numbers.empty_queue_days >= EMPTY_QUEUE_DAYS:
        out.append(
            Proposal(
                id="queue_empty",
                title="I am running out of jobs to apply to",
                evidence=f"My list has been empty for {numbers.empty_queue_days} days.",
                expected_effect="More matches each morning, at the cost of some slightly older postings.",
                text=(
                    "I have run out of jobs that match what you asked for. "
                    "Shall I look back a bit further in time, or widen the kinds of roles I consider?"
                ),
                change={"search.recency_days": int(config.get("search.recency_days", 21)) + 14},
            )
        )

    for source in numbers.dead_sources:
        out.append(
            Proposal(
                id=f"dead_source:{source}",
                title="One place I look has nothing for you",
                evidence=f"{source} returned nothing the last time I looked.",
                expected_effect="Less time spent looking where there is nothing, and a clearer picture of what works.",
                text=(
                    f"One of the places I check ({source}) has not had anything for you lately. "
                    "Shall I stop checking it for now?"
                ),
                change={f"search.sources.{source}.enabled": False},
            )
        )

    for host, count in sorted(numbers.blocks_by_host.items(), key=lambda kv: -kv[1]):
        if count >= BLOCK_STREAK:
            out.append(
                Proposal(
                    id=f"repeated_block:{host}",
                    title="One application site keeps stopping me",
                    evidence=f"{count} applications on the same kind of site could not be finished.",
                    expected_effect="Either those applications start going through, or we stop spending time on them.",
                    text=(
                        f"{count} applications on one particular site keep stopping before the end. "
                        "Would you like to finish those yourself, or should I skip that site for now?"
                    ),
                    change={},
                )
            )

    if numbers.idle_lane_minutes >= IDLE_LANE_MINUTES and numbers.queue_total > 0:
        out.append(
            Proposal(
                id="idle_capacity",
                title="I could be working on more at once",
                evidence=(
                    f"{numbers.queue_total} jobs were waiting while I was idle for "
                    f"{numbers.idle_lane_minutes} minutes."
                ),
                expected_effect="Applications go out sooner; the computer works a bit harder while they do.",
                text=(
                    "There is a queue building up while I sit idle. "
                    "Shall I work on one more application at a time?"
                ),
                change={"apply.max_lanes": int(config.get("apply.max_lanes", 2)) + 1},
            )
        )

    if len(numbers.parked_questions) >= 3:
        unique = sorted(set(numbers.parked_questions))[:3]
        out.append(
            Proposal(
                id="answers_missing",
                title="A few forms asked something I do not know",
                evidence="Questions I had to stop on: " + "; ".join(unique),
                expected_effect="Those applications finish by themselves next time instead of waiting for you.",
                text=(
                    "A few forms asked me questions I do not have your answer to. "
                    "If you tell me how to answer them, I will remember for next time."
                ),
                change={},
            )
        )

    return out


def render_proposals(items: list[Proposal]) -> str:
    """What the user sees: the suggestion, the evidence, and a question."""
    if not items:
        return "Nothing to suggest today — things are running as you set them up."
    blocks = [
        "\n".join(
            [
                f"- {item.text}",
                f"  Why I am asking: {item.evidence}",
                f"  What changes: {item.expected_effect}",
                f"  Want me to do this? Say 'yes' — or {_approve_words(item.id)}.",
            ]
        )
        for item in items
    ]
    opener = "One suggestion:" if len(items) == 1 else f"{len(items)} suggestions:"
    return opener + "\n" + "\n".join(blocks)


def _approve_words(proposal_id: str) -> str:
    return f"approve {proposal_id}"


def apply_proposal(
    proposal: Proposal,
    config: Config,
    *,
    approved: bool,
    approved_by: str,
    config_path: str | None = None,
    tracker: Tracker | None = None,
) -> Config:
    """Write a proposal's change into the settings — only with approval.

    Returns the new settings. Raises if the approval is missing, so a caller
    cannot forget.
    """
    if not approved:
        raise JobpilotError(
            "I have not changed anything: that needs your say-so first.",
            hint=f"Approve the suggestion '{proposal.id}' and I will apply it.",
        )
    if not proposal.change:
        raise JobpilotError(
            "There is nothing for me to change for that suggestion — it needs a decision from you.",
        )

    data = _deep_copy(config.data)
    for dotted, value in proposal.change.items():
        _assign(data, dotted, value)
    from .config import validate

    updated = validate(data, config.source)
    destination = config_path or config.source
    if destination:
        # Keep the previous answers next to the file, exactly as setup does, so
        # an approved change is as recoverable as a re-run of the questions.
        backup_settings(destination)
        write_config(updated, destination)
    if tracker is not None:
        tracker.record_event(  # the record of changes is append-only
            "preference_change",
            proposal=proposal.id,
            approved_by=approved_by,
            change=proposal.change,
        )
    _append_changelog(updated, proposal, approved_by)
    return updated


# -- changing a preference in plain words --------------------------------

#: The only settings a sentence may propose changing. Permissions are not here
#: on purpose: switching on sending or submitting is always a deliberate act,
#: never something a model suggests from a turn of phrase.
CHANGEABLE: dict[str, str] = {
    "search.categories.core": "the jobs I go after first",
    "search.categories.non_core": "the jobs I apply to after those",
    "search.categories.excluded": "the jobs I never apply to",
    "search.locations.preferred": "the cities you would work in",
    "search.locations.remote_ok": "whether fully remote jobs count",
    "search.max_required_years_experience": "how many years of experience is too many",
    "search.recency_days": "how far back I look",
    "search.seniority_excludes": "the title words that mean too senior",
    "search.company_rules.hard_exclude": "the companies I avoid completely",
    "search.company_rules.hold_pending_user": "the companies I hold for your decision",
    "apply.rows_per_wave": "how many applications I work through at a time",
    "apply.max_lanes": "how many applications I work on at once",
    "ui.mode": "how much detail you see",
    "notifications.digest_time": "the time of your daily summary",
    "notifications.report_rejections": "whether I mention rejections",
}

REQUEST_SCHEMA = {
    "type": "object",
    "required": ["change"],
    "properties": {
        "change": {"type": "object"},
        "summary": {"type": "string"},
        "effect": {"type": "string"},
        "unclear": {"type": "string"},
    },
}

REQUEST_PROMPT = """The person using this job-application assistant said:

"{sentence}"

Work out which of their settings they are asking to change. These are the only
settings you may touch, with what they mean and their current values:

{settings}

Rules:
- Only use settings from the list above, spelled exactly as shown.
- Keep the same kind of value: a list stays a list, a number stays a number,
  true/false stays true/false.
- For a list, give the WHOLE new list, not just the part being added.
- If you cannot tell what they mean, leave "change" empty and put one short
  question in "unclear".

Answer with JSON only:
{{"change": {{"setting.name": new_value}},
  "summary": "one plain sentence describing the change, no jargon",
  "effect": "one plain sentence on what they would notice",
  "unclear": ""}}
"""


def _settings_block(config: Config) -> str:
    lines = []
    for key, words in CHANGEABLE.items():
        lines.append(f"- {key} ({words}); now: {json.dumps(config.get(key))}")
    return "\n".join(lines)


def _same_shape(current: Any, proposed: Any) -> bool:
    if isinstance(current, bool):
        return isinstance(proposed, bool)
    if isinstance(current, int) and not isinstance(current, bool):
        return isinstance(proposed, int) and not isinstance(proposed, bool)
    if isinstance(current, list):
        return isinstance(proposed, list)
    if isinstance(current, str):
        return isinstance(proposed, str)
    return current is None or isinstance(proposed, type(current))


def diff_in_words(config: Config, change: dict[str, Any], *, done: bool = False) -> str:
    """The change as a person would read it: what it was, what it becomes.

    ``done=True`` phrases it in the past, for after the user has said yes.
    """
    lines = []
    for key, value in change.items():
        words = CHANGEABLE.get(key, key)
        before = _value_words(config.get(key))
        after = _value_words(value)
        if done:
            lines.append(f"- {words}: was {before}; now {after}.")
        else:
            lines.append(f"- {words}: now {before}; would become {after}.")
    return "\n".join(lines)


def _value_words(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "nothing"
    if value in (None, ""):
        return "nothing"
    return str(value)


def interpret_request(sentence: str, config: Config, provider: Any, *, proposal_id: str = "") -> Proposal:
    """Turn a sentence into a proposed settings change. Changes nothing itself."""
    said = " ".join(str(sentence or "").split())
    if not said:
        raise JobpilotError("Tell me what you would like to change, in your own words.")

    result = provider.complete(
        REQUEST_PROMPT.format(sentence=said, settings=_settings_block(config)),
        schema=REQUEST_SCHEMA,
    )
    payload = result.data if result.ok else None
    if not isinstance(payload, dict):
        raise JobpilotError(
            "I could not work out which setting you meant, so I have changed nothing.",
            hint="Try naming it the way I do, for example 'the cities you would work in'.",
        )

    unclear = str(payload.get("unclear") or "").strip()
    change = payload.get("change") if isinstance(payload.get("change"), dict) else {}
    cleaned: dict[str, Any] = {}
    refused: list[str] = []
    for key, value in change.items():
        if key not in CHANGEABLE:
            refused.append(str(key))
            continue
        if not _same_shape(config.get(key), value):
            refused.append(str(key))
            continue
        if value == config.get(key):
            continue
        cleaned[str(key)] = value

    if not cleaned:
        detail = unclear or (
            "that setting is not one I can change for you" if refused else "nothing would actually change"
        )
        raise JobpilotError(
            f"I have changed nothing: {detail}",
            hint="You can always say it another way, or ask me what I can change.",
        )

    return Proposal(
        id=proposal_id or "request-1",
        title=str(payload.get("summary") or "A change you asked for"),
        evidence=f'You said: "{said}"',
        expected_effect=str(payload.get("effect") or "You should notice the difference tomorrow morning."),
        text=(
            f"{payload.get('summary') or 'Here is the change you asked for'}:\n"
            + diff_in_words(config, cleaned)
        ),
        change=cleaned,
        needs_approval=True,
    )


# -- self-improvements that touch no setting -----------------------------


def self_improvement_note(what_changed: str, details: str, config: Config, renderer: Renderer) -> str:
    """One plain line, or nothing. The particulars go to the changelog."""
    path = config.paths.ensure().changelog
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"- {iso()} — self-improvement: {what_changed} ({details})\n")
    return renderer.self_optimization(
        what_changed,
        details=details,
        notice=str(config.get("ui.self_optimization_notice", "one_line")),
    )


# -- remembering suggestions across conversations ------------------------


def _store_path(config: Config):
    return config.paths.ensure().state / "proposals.json"


def _read_store(config: Config) -> dict[str, Any]:
    path = _store_path(config)
    if not path.exists():
        return {"items": [], "decisions": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {"items": [], "decisions": {}}
    payload.setdefault("items", [])
    payload.setdefault("decisions", {})
    return payload


def _write_store(config: Config, payload: dict[str, Any]) -> None:
    path = _store_path(config)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def _as_dict(proposal: Proposal) -> dict[str, Any]:
    return {
        "id": proposal.id,
        "title": proposal.title,
        "evidence": proposal.evidence,
        "expected_effect": proposal.expected_effect,
        "text": proposal.text,
        "change": proposal.change,
        "saved_at": iso(),
    }


def _as_proposal(row: dict[str, Any]) -> Proposal:
    return Proposal(
        id=str(row.get("id", "")),
        title=str(row.get("title", "")),
        evidence=str(row.get("evidence", "")),
        expected_effect=str(row.get("expected_effect", "")),
        text=str(row.get("text", "")),
        change=dict(row.get("change") or {}),
    )


def save_proposals(config: Config, items: Iterable[Proposal]) -> list[Proposal]:
    """Remember suggestions so the user can approve one later. Decided ones stay decided."""
    payload = _read_store(config)
    decided = set(payload["decisions"])
    kept = {row["id"]: row for row in payload["items"] if row.get("id") not in decided}
    for proposal in items:
        if proposal.id in decided:
            continue
        kept[proposal.id] = _as_dict(proposal)
    payload["items"] = [kept[key] for key in sorted(kept)]
    _write_store(config, payload)
    return [_as_proposal(row) for row in payload["items"]]


def open_proposals(config: Config) -> list[Proposal]:
    """Suggestions the user has not answered yet."""
    payload = _read_store(config)
    return [_as_proposal(row) for row in payload["items"] if row.get("id") not in payload["decisions"]]


def find_proposal(config: Config, proposal_id: str) -> Proposal | None:
    return next((p for p in open_proposals(config) if p.id == proposal_id), None)


def record_decision(config: Config, proposal_id: str, decision: str, *, by: str) -> None:
    payload = _read_store(config)
    payload["decisions"][proposal_id] = {"decision": decision, "at": iso(), "by": by}
    payload["items"] = [row for row in payload["items"] if row.get("id") != proposal_id]
    _write_store(config, payload)


def decide(
    config: Config,
    proposal_id: str,
    *,
    approve: bool,
    by: str = "you",
    config_path: str | None = None,
    tracker: Tracker | None = None,
) -> tuple[Config, str]:
    """Approve or decline a remembered suggestion. Returns the settings and a line."""
    proposal = find_proposal(config, proposal_id)
    if proposal is None:
        raise JobpilotError(
            f"I do not have a suggestion called '{proposal_id}' waiting.",
            hint="Run 'jobpilot status' to see what is waiting for your answer.",
        )
    if not approve:
        record_decision(config, proposal_id, "declined", by=by)
        return config, "Understood — I have left everything exactly as it was."
    updated = apply_proposal(
        proposal, config, approved=True, approved_by=by, config_path=config_path, tracker=tracker
    )
    record_decision(config, proposal_id, "approved", by=by)
    return updated, "Done. Here is what changed:\n" + diff_in_words(config, proposal.change, done=True)


def _append_changelog(config: Config, proposal: Proposal, approved_by: str) -> None:
    path = config.paths.ensure().changelog
    line = f"- {iso()} — {proposal.title} (approved by {approved_by}): {proposal.change}\n"
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line)


def _deep_copy(value: Any) -> Any:
    import copy

    return copy.deepcopy(value)


def _assign(data: dict, dotted: str, value: Any) -> None:
    node = data
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value
