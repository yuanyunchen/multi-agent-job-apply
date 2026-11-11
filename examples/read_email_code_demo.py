#!/usr/bin/env python3
"""Reading a verification code from a fake mailbox — and every refusal.

Some application forms email a short code part way through. Reading it is the
most delicate thing this system does, so the rules are strict and all of them
are shown here working:

1. the sender must belong to the application system that asked;
2. the recipient must be the address used on that form;
3. the message must have arrived inside the few minutes after the submit;
4. the newest match wins;
5. password-reset mail is never used, and a new code is never requested;
6. the mailbox must say what it searched — otherwise "no code found" and
   "nobody looked" are the same answer, and they must never be confused;
7. the code itself cannot be printed. Try it and you get a redaction marker.

Everything is read-only and in memory. No mailbox is contacted.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobpilot.verify import (  # noqa: E402
    ExportRefused,
    FakeMailReader,
    MailboxCodeProvider,
    MailMessage,
    find_code,
)

from _shared import heading, settings  # noqa: E402

SUBMITTED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
ME = "sam@example.test"
WINDOW = timedelta(minutes=10)


def mail(
    *,
    subject: str,
    body: str,
    sender: str = "no-reply@greenhouse.io",
    recipient: str = ME,
    minutes_after: float = 2,
    message_id: str = "m-1",
) -> MailMessage:
    return MailMessage(
        message_id=message_id,
        sender=sender,
        recipient=recipient,
        subject=subject,
        received_at=SUBMITTED_AT + timedelta(minutes=minutes_after),
        body=body,
    )


def mailbox(inbox: list[MailMessage], **header_overrides) -> FakeMailReader:
    """A fake mailbox that says what it searched, as a real export must."""
    reader = FakeMailReader.covering(
        inbox, mailbox=ME, since=SUBMITTED_AT, until=SUBMITTED_AT + timedelta(hours=1)
    )
    reader.header.update(header_overrides)
    return reader


def look(label: str, reader: FakeMailReader, **kwargs) -> None:
    try:
        code = find_code(
            reader=reader,
            sender_domains=["greenhouse.io", "greenhouse-mail.io"],
            recipient=ME,
            submitted_at=SUBMITTED_AT,
            **kwargs,
        )
    except ExportRefused as refused:
        print(f"  {label}: refused — {refused.message}")
        return
    if code is None:
        print(f"  {label}: no code, so the application waits for you")
    else:
        print(f"  {label}: found one (and it prints as {code})")


GOOD = mail(subject="Your security code", body="Your code is AB12CD34 and expires soon.")


def main() -> int:
    config = settings("codes")

    heading("The code is there, and everything checks out")
    look("a proper code", mailbox([GOOD]))

    heading("Each rule, refusing in turn")
    look("the wrong sender", mailbox([mail(subject="Your code", body="Code AB12CD34",
                                          sender="no-reply@not-the-system.example")]))
    look("the wrong recipient", mailbox([mail(subject="Your code", body="Code AB12CD34",
                                             recipient="someone-else@example.test")]))
    look("too late", mailbox([mail(subject="Your code", body="Code AB12CD34", minutes_after=45)]))
    look("a password reset", mailbox([mail(subject="Reset your password",
                                          body="Use ZZ99YY88 to reset your password.")]))
    look("an empty mailbox", mailbox([]))

    heading("The newest one wins")
    older = mail(subject="Your security code", body="Code AAAAAA11", minutes_after=1, message_id="m-old")
    newer = mail(subject="Your security code", body="Code BBBBBB22", minutes_after=4, message_id="m-new")
    code = find_code(
        reader=mailbox([older, newer]),
        sender_domains=["greenhouse.io"],
        recipient=ME,
        submitted_at=SUBMITTED_AT,
    )
    print(f"  came from the newer message: {code.source_id == 'm-new'}")

    heading("A mailbox that cannot say what it searched")
    look("no record of the search", FakeMailReader([GOOD]))
    look("an unfinished search", mailbox([GOOD], complete=False))
    look("a search of someone else's mailbox", mailbox([GOOD], mailbox="other@example.test"))

    heading("The code refuses to be printed, however you ask")
    code = find_code(
        reader=mailbox([GOOD]),
        sender_domains=["greenhouse.io"],
        recipient=ME,
        submitted_at=SUBMITTED_AT,
    )
    print(f"  as text:        {code}")
    print(f"  repeated:       {code!r}")
    print(f"  in a wide field:{code:>20}")
    print(f"  the real value is only reachable on purpose: {len(code.reveal())} characters long")

    heading("And it is switched off for every system until you say otherwise")
    provider = MailboxCodeProvider.from_config(config, mailbox([GOOD]))
    print(f"  switched on for: {sorted(provider.enabled_for) or 'nothing'}")
    print(f"  asking anyway gives: {provider.find_code(ats='greenhouse', recipient=ME, submitted_at=SUBMITTED_AT)}")

    switched_on = settings("codes-on", verify={"email_codes": {"greenhouse": True}})
    provider = MailboxCodeProvider.from_config(switched_on, mailbox([GOOD]))
    found = provider.find_code(ats="greenhouse", recipient=ME, submitted_at=SUBMITTED_AT)
    print(f"  with that one system on: {'a code' if found else 'nothing'}")
    print(f"  but still not for the others: {provider.find_code(ats='workday', recipient=ME, submitted_at=SUBMITTED_AT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
