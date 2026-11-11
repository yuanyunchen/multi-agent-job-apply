"""What the user reads: one daily summary, plus the assistant's own notes.

The digest is about features, progress and outcomes. No internal names, no
counts of internal objects, no identifiers — the renderer's lint enforces that.
Rejections are only mentioned if the user asked for them.

The reflection log is for the assistant, not the user: it is where "what went
badly today and what I would change" goes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from .config import Config
from .domain import Message
from .queue import depth
from .tracker import normalize_status
from .ui import Renderer, plural
from .verify import unconfirmed_rate


@dataclass
class DailyNumbers:
    applied: int = 0
    sent_waiting: int = 0
    needs_you: list[str] = field(default_factory=list)
    new_matches: int = 0
    interviews: int = 0
    assessments: int = 0
    replies: int = 0
    rejections: int = 0
    queue_core: int = 0
    queue_non_core: int = 0
    unconfirmed_rate: float = 0.0


def summarize(rows: Iterable[dict]) -> DailyNumbers:
    rows = list(rows)
    numbers = DailyNumbers()
    for row in rows:
        status = normalize_status(row.get("status"))
        if status == "applied":
            numbers.applied += 1
        elif status == "submitted":
            numbers.sent_waiting += 1
        elif status == "interview":
            numbers.interviews += 1
        elif status == "online_assessment":
            numbers.assessments += 1
        elif status == "rejected":
            numbers.rejections += 1
        elif status in ("new", "pipeline"):
            numbers.new_matches += 1
        if status == "parked":
            for question in row.get("pending_questions") or []:
                if question not in numbers.needs_you:
                    numbers.needs_you.append(str(question))
        if status in ("hold_pending_user", "review"):
            label = f"{row.get('company', 'a company')} — {row.get('title', 'a role')}"
            if label not in numbers.needs_you:
                numbers.needs_you.append(label)
    sizes = depth(rows)
    numbers.queue_core = sizes["core"]
    numbers.queue_non_core = sizes["non_core"]
    numbers.unconfirmed_rate = unconfirmed_rate(rows)[0]
    return numbers


def digest(
    rows: Iterable[dict],
    config: Config,
    renderer: Renderer,
    *,
    today: date | None = None,
    max_needs_you: int = 3,
) -> str:
    """The one message a day. Plain language, at most a short page."""
    numbers = summarize(rows)
    day = (today or date.today()).strftime("%A %d %B")
    lines: list[str] = [f"Your job search — {day}", ""]

    headline = []
    if numbers.applied:
        headline.append(f"{plural(numbers.applied, 'application')} confirmed")
    if numbers.sent_waiting:
        headline.append(f"{numbers.sent_waiting} sent and waiting for a confirmation")
    if numbers.new_matches:
        headline.append(f"{plural(numbers.new_matches, 'new match', 'new matches')} found")
    lines.append(
        renderer.render(
            Message(
                "digest.headline",
                "Today: " + (", ".join(headline) if headline else "a quiet day, nothing went out."),
                technical=f"queue core={numbers.queue_core} non_core={numbers.queue_non_core}",
            )
        )
    )

    if numbers.needs_you:
        lines += ["", "Needs you:"]
        for item in numbers.needs_you[:max_needs_you]:
            lines.append(f"  - {item}")
        if len(numbers.needs_you) > max_needs_you:
            lines.append(f"  - and {len(numbers.needs_you) - max_needs_you} more when you have a minute")

    good_news = []
    if numbers.interviews:
        good_news.append(f"{plural(numbers.interviews, 'interview')}")
    if numbers.assessments:
        good_news.append(f"{plural(numbers.assessments, 'take-home test')}")
    if numbers.replies:
        good_news.append(f"{plural(numbers.replies, 'reply', 'replies')} from a recruiter")
    if good_news:
        lines += ["", "Good news: " + ", ".join(good_news) + "."]

    if config.get("notifications.report_rejections", False) and numbers.rejections:
        lines += ["", f"Also: {plural(numbers.rejections, 'no')} came back."]

    waiting = numbers.queue_core + numbers.queue_non_core
    lines += [
        "",
        renderer.render(
            Message(
                "digest.next",
                f"Still on my list: {plural(waiting, 'job')} to apply to."
                if waiting
                else "My list is empty, so I will look harder for new matches tomorrow.",
                technical=f"unconfirmed rate {numbers.unconfirmed_rate:.0%}",
            )
        ),
    ]
    return "\n".join(line for line in lines if line is not None)


def reflection(rows: Iterable[dict], *, notes: str = "", today: date | None = None) -> str:
    """One entry a day, even on days when nothing happened."""
    numbers = summarize(rows)
    day = (today or date.today()).isoformat()
    rate, unconfirmed, considered = unconfirmed_rate(rows)
    body = [
        f"## {day}",
        f"- confirmed: {numbers.applied}; sent and waiting: {numbers.sent_waiting}",
        f"- waiting to be applied to: {numbers.queue_core} first-choice, {numbers.queue_non_core} other",
        f"- unconfirmed: {unconfirmed} of {considered} ({rate:.0%})",
        f"- needs the user: {len(numbers.needs_you)}",
    ]
    if notes:
        body.append(f"- note: {notes}")
    return "\n".join(body) + "\n"


def append_reflection(config: Config, text: str) -> None:
    path = config.paths.ensure().reflections
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text + "\n")
