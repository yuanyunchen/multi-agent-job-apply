"""Did it arrive? Reading the mailbox, read-only.

Two jobs, both evidence-driven:

* **Receipts.** A message upgrades "sent" to "confirmed" only when it matches on
  sender domain **and** recipient address **and** a time window just after the
  submit. The newest match wins. A missing receipt never downgrades anything.
* **Verification codes.** Some application forms mail a short code. It is read
  the same way, and the value is wrapped in a :class:`Code` object that cannot
  be printed, logged or formatted into a message.

Hard rules, in code rather than in a document:

* Read-only. Nothing is ever sent, replied to, deleted or archived.
* Password-reset mail is never used, and a reset link is never followed.
* Fail closed. No match inside the window means no receipt and no code — never
  a retry loop, and never a request for another code.
* Any mail backend works: it only has to answer :class:`MailReader`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Protocol, runtime_checkable

from .config import Config
from .domain import SUBMITTED_STATUSES, IN_PROGRESS_STATUSES
from .errors import JobpilotError
from .gates import is_password_reset
from .testmode import ensure_live
from .tracker import normalize_status

#: Phrases that mean "your application arrived".
RECEIPT_PHRASES = (
    "thank you for applying",
    "thanks for applying",
    "application received",
    "we received your application",
    "your application to",
    "application confirmation",
    "we have received your application",
)

#: Mail that proves identity, not delivery. Never counts as a receipt.
VERIFICATION_PHRASES = ("verification code", "security code", "verify your email", "one-time code")


@dataclass(frozen=True, slots=True)
class MailMessage:
    message_id: str
    sender: str  # "Careers <no-reply@acme-robotics.example>"
    recipient: str
    subject: str
    received_at: datetime
    body: str = ""

    @property
    def sender_domain(self) -> str:
        address = self.sender.split("<")[-1].strip(" >")
        return address.split("@")[-1].lower()


@runtime_checkable
class MailReader(Protocol):
    """Read-only access to a mailbox. No other verbs exist on purpose."""

    def messages(self, *, since: datetime, until: datetime, recipient: str = "") -> Iterable[MailMessage]: ...


@dataclass
class FakeMailReader:
    """An in-memory mailbox for tests, examples and ``--dry-run``.

    ``header`` is the same declaration a real export carries, so the guard can
    be exercised offline — including the cases where it should refuse.
    """

    inbox: list[MailMessage] = field(default_factory=list)
    header: dict | None = None

    def messages(self, *, since: datetime, until: datetime, recipient: str = "") -> list[MailMessage]:
        return [
            message
            for message in self.inbox
            if since <= message.received_at <= until
            and (not recipient or message.recipient.lower() == recipient.lower())
        ]

    def export_header(self) -> dict | None:
        return self.header

    @classmethod
    def covering(
        cls,
        inbox: list[MailMessage],
        *,
        mailbox: str,
        since: datetime,
        until: datetime,
        query: str = "application mail",
    ) -> "FakeMailReader":
        """A fake mailbox with a header that vouches for the whole window."""
        return cls(
            inbox=list(inbox),
            header={
                "mailbox": mailbox,
                "query": query,
                "since": since.isoformat(),
                "until": until.isoformat(),
                "complete": True,
            },
        )


class ExportRefused(JobpilotError):
    """An export was refused. The message never contains anything from the mail."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


#: An export's header declares what it is. Without it there is no way to tell a
#: scoped, finished export of the right mailbox from a file somebody happened
#: to leave in the folder.
REQUIRED_HEADER_FIELDS = ("mailbox", "query", "since", "until", "complete")


def check_export_header(
    header: object,
    *,
    recipient: str,
    since: datetime,
    until: datetime,
) -> dict:
    """Refuse an export whose own header does not vouch for it.

    This guard is what makes "read-only export" mean something. A dropped,
    half-written or differently scoped file would otherwise be read as though
    the mail agent had produced it on purpose, and the matching rules would be
    applied to the wrong mail — or worse, an empty result would be read as "no
    code arrived" when the truth is "nobody looked".

    All of these must hold:

    1. the header exists and declares every required field;
    2. its mailbox is the address the application was sent from;
    3. it is marked finished — a partial scan fails closed;
    4. its window covers the window being asked about.
    """
    if not isinstance(header, dict):
        raise ExportRefused("no_header", "That mailbox export does not say what it contains.")
    if [name for name in REQUIRED_HEADER_FIELDS if name not in header]:
        raise ExportRefused(
            "incomplete_header",
            "That mailbox export does not say what it contains, so I did not read it.",
        )
    if str(header.get("mailbox", "")).strip().lower() != (recipient or "").strip().lower():
        raise ExportRefused(
            "wrong_mailbox",
            "That mailbox export is for a different address than the one on the application.",
        )
    if not header.get("complete"):
        raise ExportRefused(
            "incomplete_scan",
            "That mailbox export was not finished, so I will wait rather than assume nothing arrived.",
        )
    try:
        covered_from = _as_utc(datetime.fromisoformat(str(header["since"])))
        covered_to = _as_utc(datetime.fromisoformat(str(header["until"])))
    except (TypeError, ValueError) as exc:
        raise ExportRefused(
            "bad_window", "That mailbox export does not say which period it covers."
        ) from exc
    if covered_from > _as_utc(since) or covered_to < _as_utc(until):
        raise ExportRefused(
            "window_too_small",
            "That mailbox export does not cover the minutes after the application was sent.",
        )
    return dict(header)


def _as_utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


@dataclass
class JsonExportMailReader:
    """Reads a read-only export written by the mail agent: one JSON per message.

    The system never speaks to a mail API itself — that keeps credentials out of
    this package entirely. Blocked while the tests are running, because the
    export is real mail.
    """

    export_dir: Path

    def __post_init__(self) -> None:
        ensure_live("mailbox")

    def messages(self, *, since: datetime, until: datetime, recipient: str = "") -> list[MailMessage]:
        import json

        out: list[MailMessage] = []
        for path in sorted(Path(self.export_dir).glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            received = datetime.fromisoformat(str(payload["received_at"]))
            if received.tzinfo is None:
                received = received.replace(tzinfo=timezone.utc)
            if not (since <= received <= until):
                continue
            if recipient and str(payload.get("recipient", "")).lower() != recipient.lower():
                continue
            out.append(
                MailMessage(
                    message_id=str(payload.get("message_id") or path.stem),
                    sender=str(payload.get("sender", "")),
                    recipient=str(payload.get("recipient", "")),
                    subject=str(payload.get("subject", "")),
                    received_at=received,
                    body=str(payload.get("body", "")),
                )
            )
        return out


def reader_from_config(config: Config) -> MailReader | None:
    """``none`` means no mailbox is connected; receipts simply stay pending."""
    kind = str(config.get("verify.mail_reader", "none"))
    if kind == "json_export":
        return JsonExportMailReader(Path(str(config.get("verify.mail_export_dir"))))
    return None


# -- receipts ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Receipt:
    mail_id: str
    basis: str  # how it matched, for the record
    matched_at: str

    def as_row_field(self) -> dict:
        return {"mail_id": self.mail_id, "basis": self.basis, "matched_at": self.matched_at}


def _domain_of(url_or_domain: str) -> str:
    text = (url_or_domain or "").lower()
    if "://" in text:
        text = text.split("://", 1)[1]
    return text.split("/")[0].removeprefix("www.")


def _same_site(sender: str, allowed: str) -> bool:
    """Do two host names belong to the same site?

    ``no-reply@greenhouse.io`` is the right sender for a posting hosted at
    ``job-boards.greenhouse.io``, and ``careers.acme.example`` is the right
    sender for ``acme.example``. Anything further apart than a shared last two
    labels is a different site.
    """
    if not sender or not allowed:
        return False
    if sender == allowed or sender.endswith("." + allowed) or allowed.endswith("." + sender):
        return True
    return sender.split(".")[-2:] == allowed.split(".")[-2:]


def match_receipt(
    *,
    row: dict,
    submitted_at: datetime,
    reader: MailReader,
    recipient: str,
    window_minutes: int = 10,
    extra_domains: Iterable[str] = (),
) -> Receipt | None:
    """The newest message that proves this application arrived, or ``None``.

    All of these must hold: the sender's domain belongs to the posting's host or
    an allowed ATS domain, the recipient is the address used on the form, and
    the message landed inside the window after the submit.
    """
    until = submitted_at + timedelta(minutes=window_minutes)
    candidates = [
        message
        for message in reader.messages(since=submitted_at, until=until, recipient=recipient)
        if message.recipient.lower() == recipient.lower()
    ]
    allowed = {_domain_of(row.get("url", "")), *{d.lower() for d in extra_domains}}
    allowed.discard("")

    best: MailMessage | None = None
    for message in sorted(candidates, key=lambda m: m.received_at, reverse=True):
        text = f"{message.subject}\n{message.body}"
        if is_password_reset(text):
            continue  # a reset mail is never evidence of anything
        if any(phrase in text.lower() for phrase in VERIFICATION_PHRASES) and not any(
            phrase in text.lower() for phrase in RECEIPT_PHRASES
        ):
            continue  # identity mail is not a receipt
        if not any(_same_site(message.sender_domain, domain) for domain in allowed):
            continue
        if not any(phrase in text.lower() for phrase in RECEIPT_PHRASES):
            continue
        best = message
        break

    if best is None:
        return None  # fail closed: still "sent", never downgraded
    return Receipt(
        mail_id=best.message_id,
        basis=f"sender domain {best.sender_domain}, sent to the address on the form, inside {window_minutes} minutes",
        matched_at=best.received_at.isoformat(),
    )


# -- verification codes --------------------------------------------------


class Code:
    """A verification code that refuses to be printed.

    ``str()``, ``repr()`` and f-strings all give ``[REDACTED-EMAIL-VERIFY]``.
    The only way to the value is :meth:`reveal`, and the only caller allowed to
    use it is the step that types it into the form.
    """

    __slots__ = ("_value", "source_id")

    REDACTED = "[REDACTED-EMAIL-VERIFY]"

    def __init__(self, value: str, source_id: str) -> None:
        self._value = value
        self.source_id = source_id

    def reveal(self) -> str:
        return self._value

    def __str__(self) -> str:
        return self.REDACTED

    __repr__ = __str__

    def __format__(self, _spec: str) -> str:
        return self.REDACTED


CODE_PATTERN = r"\b([A-Z0-9]{6,8})\b"

#: Which sender domains belong to which application system. Used to check a
#: code really came from the system that asked for it.
ATS_MAIL_DOMAINS: dict[str, tuple[str, ...]] = {
    "greenhouse": ("greenhouse.io", "greenhouse-mail.io"),
    "lever": ("lever.co", "hire.lever.co"),
    "ashby": ("ashbyhq.com",),
    "workday": ("myworkday.com", "workday.com", "myworkdayjobs.com"),
    "smartrecruiters": ("smartrecruiters.com",),
    "workable": ("workable.com",),
}


def find_code(
    *,
    reader: MailReader,
    sender_domains: Iterable[str],
    recipient: str,
    submitted_at: datetime,
    window_minutes: int = 10,
    require_header: bool = True,
) -> Code | None:
    """The newest verification code inside the window, or ``None``.

    Four rules, all of which must hold: the sender belongs to the application
    system, the recipient is the address used on the form, the message landed
    inside the window after the submit, and the newest match wins.

    Before any of that, the export's own header is checked
    (:func:`check_export_header`) unless ``require_header`` is off. Without it,
    "no code found" and "nobody looked" are the same answer, and the second one
    must never be treated as the first.

    Reset mail is skipped. No match means no code: the application waits for the
    user rather than asking the site for another one.
    """
    import re

    until = submitted_at + timedelta(minutes=window_minutes)
    header_of = getattr(reader, "export_header", None)
    header = header_of() if callable(header_of) else None
    if header is not None:
        check_export_header(header, recipient=recipient, since=submitted_at, until=until)
    elif require_header:
        raise ExportRefused(
            "no_header",
            "That mailbox gave me no record of what it searched, so I will not treat an empty "
            "result as proof that nothing arrived.",
        )

    domains = {d.lower() for d in sender_domains}
    messages = sorted(
        reader.messages(since=submitted_at, until=until, recipient=recipient),
        key=lambda m: m.received_at,
        reverse=True,
    )
    for message in messages:
        if message.recipient.lower() != recipient.lower():
            continue
        if not any(_same_site(message.sender_domain, domain) for domain in domains):
            continue
        text = f"{message.subject}\n{message.body}"
        if is_password_reset(text):
            continue
        match = re.search(CODE_PATTERN, text)
        if match:
            return Code(match.group(1), message.message_id)
    return None


@runtime_checkable
class EmailCodeProvider(Protocol):
    """Where a verification code comes from. One per mailbox backend."""

    name: str

    def find_code(
        self, *, ats: str, recipient: str, submitted_at: datetime, window_minutes: int = 10
    ) -> Code | None: ...


@dataclass
class MailboxCodeProvider:
    """A code provider over any :class:`MailReader`.

    Each application system is switched on separately
    (``verify.email_codes.<system>``, all **off** by default). That is how a
    risky path is rolled out one system at a time instead of everywhere at once.
    """

    reader: MailReader
    enabled_for: frozenset[str] = frozenset()
    name: str = "mailbox"
    require_header: bool = True

    @classmethod
    def from_config(cls, config: Config, reader: MailReader) -> "MailboxCodeProvider":
        switched_on = {
            name
            for name, value in (config.section("verify.email_codes") or {}).items()
            if bool(value)
        }
        return cls(reader=reader, enabled_for=frozenset(switched_on))

    def find_code(
        self, *, ats: str, recipient: str, submitted_at: datetime, window_minutes: int = 10
    ) -> Code | None:
        family = (ats or "").strip().lower()
        if family not in self.enabled_for:
            return None  # switched off: the application waits for the user
        domains = ATS_MAIL_DOMAINS.get(family)
        if not domains:
            return None
        return find_code(
            reader=self.reader,
            sender_domains=domains,
            recipient=recipient,
            submitted_at=submitted_at,
            window_minutes=window_minutes,
            require_header=self.require_header,
        )


# -- the metric ----------------------------------------------------------


def unconfirmed_rate(rows: Iterable[dict]) -> tuple[float, int, int]:
    """``(rate, unconfirmed, considered)`` over applications that should have landed.

    Rows still in progress, rows already confirmed and known duplicates are all
    excluded, so the number means "went out but never came back".
    """
    considered = 0
    unconfirmed = 0
    for row in rows:
        status = normalize_status(row.get("status"))
        if row.get("duplicate_of"):
            continue
        if status in IN_PROGRESS_STATUSES:
            continue
        if status not in SUBMITTED_STATUSES:
            continue
        considered += 1
        # A reply of any kind — including a rejection — proves it arrived.
        confirmed = bool(row.get("receipt")) or status in (
            "applied",
            "online_assessment",
            "interview",
            "offer",
            "rejected",
        )
        if not confirmed:
            unconfirmed += 1
    rate = (unconfirmed / considered) if considered else 0.0
    return round(rate, 4), unconfirmed, considered


def receipt_sweep(
    *,
    rows: Iterable[dict],
    reader: MailReader,
    recipient: str,
    window_minutes: int = 10,
) -> list[tuple[str, Receipt]]:
    """Find receipts for everything still unconfirmed. Writes nothing itself."""
    found: list[tuple[str, Receipt]] = []
    for row in rows:
        if normalize_status(row.get("status")) != "submitted" or row.get("receipt"):
            continue
        stamp = row.get("submit_proof_at") or row.get("status_changed_at")
        if not stamp:
            continue
        try:
            submitted_at = datetime.fromisoformat(str(stamp))
        except ValueError:
            continue
        if submitted_at.tzinfo is None:
            submitted_at = submitted_at.replace(tzinfo=timezone.utc)
        receipt = match_receipt(
            row=row,
            submitted_at=submitted_at,
            reader=reader,
            recipient=recipient,
            window_minutes=window_minutes,
        )
        if receipt:
            found.append((str(row.get("job_id")), receipt))
    return found
