"""Reading the mailbox for outcomes: tests, interviews, offers, rejections.

Read-only, like everything else that touches mail. Nothing is sent, replied to,
deleted, filed or marked — the only thing that happens here is *reading*, and
the only thing that comes out is a classification with the sentence that
justified it.

Three jobs:

* :func:`classify` — what one message is about, with the line that says so;
* :func:`triage` — turn a mailbox window into tracker updates and a list of
  dates the user has to know about;
* :func:`reminders` — the morning and evening reminder text for whatever is
  coming up.

Rules in the code rather than in a document:

* an outcome is only written when the message can be tied to a job on the
  record (the posting's own site, or the company name in the subject);
* a verification code is never an outcome, and never written down anywhere;
* password-reset mail is ignored entirely;
* a rejection is recorded but not reported, unless the user asked for that.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from .config import Config
from .domain import normalize_name
from .gates import is_password_reset
from .verify import MailMessage, MailReader, VERIFICATION_PHRASES, _domain_of, _same_site

#: What a message can be about, strongest first: the first family that matches
#: wins, because "we would like to schedule an interview" in a message that
#: also says "take-home test" is an interview.
OUTCOME_PHRASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "offer",
        ("we are pleased to offer", "offer of employment", "your offer letter", "we would like to offer you"),
    ),
    (
        "interview",
        (
            "schedule an interview",
            "schedule a call",
            "invite you to interview",
            "interview invitation",
            "phone screen",
            "technical interview",
            "onsite interview",
            "meet with the team",
        ),
    ),
    (
        "online_assessment",
        (
            "online assessment",
            "coding assessment",
            "coding challenge",
            "take-home",
            "take home test",
            "hackerrank",
            "codesignal",
            "complete the assessment",
        ),
    ),
    (
        "rejected",
        (
            "not moving forward",
            "we have decided to move forward with other candidates",
            "will not be moving forward",
            "decided not to proceed",
            "unfortunately",
            "no longer under consideration",
        ),
    ),
    (
        "recruiter_reply",
        ("i wanted to reach out", "are you still interested", "a quick question about your application"),
    ),
)

#: Outcomes worth telling the user about the moment they arrive.
URGENT = ("offer", "interview", "online_assessment", "recruiter_reply")

#: "Tuesday, 3 December at 2:30pm", "2026-12-03 14:30", "Dec 3 at 2pm" …
_DATE_PATTERNS = (
    re.compile(r"\b(\d{4}-\d{2}-\d{2})(?:(?:[ T]|\s+at\s+)(\d{1,2}):(\d{2}))?"),
    re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})"
        r"(?:,?\s+(\d{4}))?(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?)?",
        re.IGNORECASE,
    ),
)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


@dataclass(frozen=True, slots=True)
class Classification:
    """What a message is about, and the sentence that says so."""

    outcome: str  # one of OUTCOME_PHRASES, or "" for nothing of interest
    quote: str = ""
    mail_id: str = ""

    @property
    def urgent(self) -> bool:
        return self.outcome in URGENT


def _sentences(text: str) -> list[str]:
    from .rules import sentences

    return sentences(text)


def classify(message: MailMessage) -> Classification:
    """What this message is about. Codes without evidence are not returned."""
    body = f"{message.subject}\n{message.body}"
    if is_password_reset(body):
        return Classification("", mail_id=message.message_id)
    low = body.lower()
    if any(phrase in low for phrase in VERIFICATION_PHRASES) and not any(
        phrase in low for family in OUTCOME_PHRASES[:3] for phrase in family[1]
    ):
        # Identity mail. It is not an outcome, and its contents are never kept.
        return Classification("", mail_id=message.message_id)

    for outcome, phrases in OUTCOME_PHRASES:
        for sentence in _sentences(body):
            lowered = sentence.lower()
            if any(phrase in lowered for phrase in phrases):
                return Classification(outcome, quote=sentence, mail_id=message.message_id)
    return Classification("", mail_id=message.message_id)


def find_date(text: str, *, today: date | None = None) -> str:
    """The first date (and time, if given) in the text, as an ISO string.

    A date with no year is read as the next one to come, so "3 December" in
    January means this year and in December means next year.
    """
    reference = today or date.today()
    for pattern in _DATE_PATTERNS:
        match = pattern.search(text or "")
        if not match:
            continue
        if pattern is _DATE_PATTERNS[0]:
            day = date.fromisoformat(match.group(1))
            hour = int(match.group(2) or 0)
            minute = int(match.group(3) or 0)
            return datetime(day.year, day.month, day.day, hour, minute).isoformat()
        month_word = match.group(0)[:3].lower()
        month = _MONTHS.get(month_word)
        if month is None:
            continue
        day_number = int(match.group(1))
        year = int(match.group(2)) if match.group(2) else reference.year
        hour = int(match.group(3) or 0)
        minute = int(match.group(4) or 0)
        if (match.group(5) or "").lower() == "pm" and hour < 12:
            hour += 12
        if (match.group(5) or "").lower() == "am" and hour == 12:
            hour = 0
        try:
            when = datetime(year, month, day_number, hour, minute)
        except ValueError:
            continue
        if not match.group(2) and when.date() < reference:
            when = when.replace(year=year + 1)
        return when.isoformat()
    return ""


def _matches_row(message: MailMessage, row: dict) -> str:
    """How this message ties to this job, or ``""`` if it does not.

    Either the sender belongs to the posting's own site, or the company name is
    in the subject. Without one of those the outcome is not written: a message
    on the record against the wrong job is worse than one that is missed.
    """
    posting = _domain_of(str(row.get("url", "")))
    if posting and _same_site(message.sender_domain, posting):
        return f"sender belongs to the posting's own site ({message.sender_domain})"
    company = normalize_name(str(row.get("company", "")))
    if company and company in normalize_name(message.subject):
        return "the company is named in the subject"
    return ""


@dataclass
class Appointment:
    """Something with a date the user has to turn up to."""

    job_id: str
    company: str
    title: str
    kind: str  # interview | online_assessment
    when: str  # ISO, possibly date-only
    note: str = ""

    @property
    def words(self) -> str:
        what = "interview" if self.kind == "interview" else "take-home test"
        when = self.when.replace("T", " at ") if self.when else "a date you have been sent"
        line = f"{self.company} — {self.title}: {what}, {when}"
        return f"{line} ({self.note})" if self.note else line


@dataclass
class TriageResult:
    updates: list[dict] = field(default_factory=list)  # tracker updates, ready to write
    appointments: list[Appointment] = field(default_factory=list)
    urgent: list[str] = field(default_factory=list)  # plain lines worth telling the user now
    unmatched: int = 0  # messages that looked like an outcome but matched no job
    read: int = 0


def triage(
    *,
    rows: Iterable[dict],
    reader: MailReader,
    recipient: str,
    since: datetime,
    until: datetime | None = None,
    today: date | None = None,
) -> TriageResult:
    """Read the mailbox window and work out what it means for the record."""
    rows = list(rows)
    result = TriageResult()
    end = until or datetime.now(timezone.utc)
    for message in reader.messages(since=since, until=end, recipient=recipient):
        result.read += 1
        found = classify(message)
        if not found.outcome:
            continue
        row = next((r for r in rows if _matches_row(message, r)), None)
        if row is None:
            result.unmatched += 1
            continue
        basis = _matches_row(message, row)
        job_id = str(row.get("job_id") or "")
        update: dict = {
            "job_id": job_id,
            "outcome": found.outcome,
            "outcome_evidence": {
                "mail_id": found.mail_id,
                "basis": basis,
                "quote": found.quote,
            },
            "notes": f'A message about this said: "{found.quote}"',
        }
        if found.outcome in ("online_assessment", "interview", "offer", "rejected"):
            update["status"] = found.outcome
        result.updates.append(update)

        if found.outcome in ("interview", "online_assessment"):
            when = find_date(f"{message.subject}\n{message.body}", today=today)
            result.appointments.append(
                Appointment(
                    job_id=job_id,
                    company=str(row.get("company", "a company")),
                    title=str(row.get("title", "a role")),
                    kind=found.outcome,
                    when=when,
                    note=str(row.get("interview_note", "")),
                )
            )
        if found.urgent:
            label = f"{row.get('company', 'a company')} — {row.get('title', 'a role')}"
            words = {
                "offer": "has made you an offer",
                "interview": "wants to interview you",
                "online_assessment": "has sent you a take-home test",
                "recruiter_reply": "has replied to you",
            }[found.outcome]
            result.urgent.append(f"{label} {words}.")
    return result


# -- reminders ------------------------------------------------------------


def upcoming(
    appointments: Iterable[Appointment],
    *,
    within_days: int = 7,
    moment: datetime | None = None,
) -> list[Appointment]:
    """Appointments in the next few days, soonest first. Undated ones come last."""
    at = moment or datetime.now()
    horizon = at + timedelta(days=within_days)

    def when(item: Appointment) -> datetime:
        if not item.when:
            return datetime.max
        try:
            parsed = datetime.fromisoformat(item.when)
        except ValueError:
            return datetime.max
        return parsed.replace(tzinfo=None)

    chosen = [a for a in appointments if not a.when or at.replace(tzinfo=None) <= when(a) <= horizon]
    return sorted(chosen, key=when)


def reminders(
    appointments: Iterable[Appointment],
    *,
    moment: datetime | None = None,
    within_days: int = 7,
) -> str:
    """The reminder the user reads, morning and evening. Empty when there is nothing."""
    soon = upcoming(appointments, within_days=within_days, moment=moment)
    if not soon:
        return ""
    lines = ["Coming up:"]
    lines += [f"  - {item.words}" for item in soon]
    lines.append("Tell me if you would like me to stop reminding you about any of these.")
    return "\n".join(lines)


def reminder_times(config: Config) -> tuple[str, str]:
    """When the reminders go out: morning and evening, both configurable."""
    morning = str(config.get("notifications.reminder_times.morning", "09:30"))
    evening = str(config.get("notifications.reminder_times.evening", "20:00"))
    return morning, evening
