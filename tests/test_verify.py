from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from jobpilot.verify import (
    Code,
    FakeMailReader,
    find_code,
    match_receipt,
    receipt_sweep,
    reader_from_config,
    unconfirmed_rate,
)

from . import synthetic as s

SUBMITTED_AT = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
ROW = {
    "job_id": "a",
    "status": "submitted",
    "url": "https://job-boards.greenhouse.io/acme-robotics/jobs/4001",
    "submit_proof_at": SUBMITTED_AT.isoformat(),
}
ME = "sam@example.test"


def look(inbox, **kwargs):
    defaults = dict(row=ROW, submitted_at=SUBMITTED_AT, reader=FakeMailReader(inbox), recipient=ME)
    defaults.update(kwargs)
    return match_receipt(**defaults)


def test_a_matching_confirmation_is_a_receipt():
    receipt = look([s.mail(submitted_at=SUBMITTED_AT)])
    assert receipt is not None
    assert receipt.mail_id == "mail-1"
    assert "sender domain" in receipt.basis and "10 minutes" in receipt.basis


def test_a_message_from_somewhere_else_is_not_a_receipt():
    other = s.mail(submitted_at=SUBMITTED_AT, sender="Someone <hello@unrelated.example>")
    assert look([other]) is None


def test_a_message_to_another_address_is_not_a_receipt():
    assert look([s.mail(submitted_at=SUBMITTED_AT, recipient="someone.else@example.test")]) is None


def test_a_message_outside_the_window_is_not_a_receipt():
    assert look([s.mail(submitted_at=SUBMITTED_AT, minutes_after=30)]) is None
    assert look([s.mail(submitted_at=SUBMITTED_AT, minutes_after=-5)]) is None


def test_the_window_is_configurable():
    late = s.mail(submitted_at=SUBMITTED_AT, minutes_after=20)
    assert look([late]) is None
    assert look([late], window_minutes=30) is not None


def test_the_newest_match_wins():
    inbox = [
        s.mail(submitted_at=SUBMITTED_AT, minutes_after=1, message_id="first"),
        s.mail(submitted_at=SUBMITTED_AT, minutes_after=5, message_id="second"),
    ]
    assert look(inbox).mail_id == "second"


def test_a_password_reset_email_is_never_evidence_of_anything():
    reset = s.mail(
        submitted_at=SUBMITTED_AT,
        subject="Reset your password",
        body="Click here to reset your password. Thank you for applying.",
    )
    assert look([reset]) is None


def test_a_verification_email_is_not_a_receipt():
    verify_mail = s.mail(
        submitted_at=SUBMITTED_AT,
        subject="Your verification code",
        body="Your security code is ABC12345.",
    )
    assert look([verify_mail]) is None


def test_a_message_with_no_confirmation_wording_is_not_a_receipt():
    chatty = s.mail(submitted_at=SUBMITTED_AT, subject="Hello", body="Just saying hi.")
    assert look([chatty]) is None


def test_an_employers_own_domain_also_counts():
    row = {**ROW, "url": "https://careers.acme-robotics.example/jobs/4001"}
    mail = s.mail(submitted_at=SUBMITTED_AT, sender="Careers <no-reply@careers.acme-robotics.example>")
    assert match_receipt(
        row=row, submitted_at=SUBMITTED_AT, reader=FakeMailReader([mail]), recipient=ME
    ) is not None


def test_no_match_leaves_the_application_where_it_was():
    """Fail closed: a missing receipt is never a downgrade and never a retry."""
    assert look([]) is None


def test_a_sweep_finds_receipts_for_everything_still_waiting():
    rows = [ROW, {**ROW, "job_id": "b", "status": "applied"}]
    found = receipt_sweep(
        rows=rows, reader=FakeMailReader([s.mail(submitted_at=SUBMITTED_AT)]), recipient=ME
    )
    assert [job_id for job_id, _ in found] == ["a"]


# -- verification codes --------------------------------------------------


def _mailbox(inbox, *, minutes: int = 60):
    """A fake mailbox whose header vouches for the window the reader asks about."""
    return FakeMailReader.covering(
        inbox,
        mailbox=ME,
        since=SUBMITTED_AT,
        until=SUBMITTED_AT + timedelta(minutes=minutes),
        query="security code",
    )


def test_a_code_is_found_inside_the_window():
    inbox = [
        s.mail(
            submitted_at=SUBMITTED_AT,
            subject="Your security code",
            body="Your code is AB12CD34 and expires soon.",
            sender="no-reply@greenhouse.io",
        )
    ]
    code = find_code(
        reader=_mailbox(inbox),
        sender_domains=["greenhouse.io"],
        recipient=ME,
        submitted_at=SUBMITTED_AT,
    )
    assert code is not None and code.reveal() == "AB12CD34"


def test_a_code_refuses_to_be_printed():
    code = Code("AB12CD34", "mail-9")
    assert str(code) == "[REDACTED-EMAIL-VERIFY]"
    assert repr(code) == "[REDACTED-EMAIL-VERIFY]"
    assert f"the code is {code}" == "the code is [REDACTED-EMAIL-VERIFY]"
    assert "AB12CD34" not in f"{code!r} {code!s} {code:>20}"


def test_a_reset_email_never_yields_a_code():
    inbox = [
        s.mail(
            submitted_at=SUBMITTED_AT,
            subject="Reset your password",
            body="Use ZZ99YY88 to reset your password.",
            sender="no-reply@greenhouse.io",
        )
    ]
    assert (
        find_code(
            reader=_mailbox(inbox),
            sender_domains=["greenhouse.io"],
            recipient=ME,
            submitted_at=SUBMITTED_AT,
        )
        is None
    )


def test_a_code_from_the_wrong_sender_or_too_late_is_ignored():
    late = s.mail(
        submitted_at=SUBMITTED_AT,
        minutes_after=45,
        subject="Your security code",
        body="Code AB12CD34",
        sender="no-reply@greenhouse.io",
    )
    assert (
        find_code(
            reader=_mailbox([late]),
            sender_domains=["greenhouse.io"],
            recipient=ME,
            submitted_at=SUBMITTED_AT,
        )
        is None
    )
    wrong_sender = s.mail(
        submitted_at=SUBMITTED_AT,
        subject="Your security code",
        body="Code AB12CD34",
        sender="no-reply@phishing.example",
    )
    assert (
        find_code(
            reader=_mailbox([wrong_sender]),
            sender_domains=["greenhouse.io"],
            recipient=ME,
            submitted_at=SUBMITTED_AT,
        )
        is None
    )


# -- the metric ----------------------------------------------------------


def test_the_unconfirmed_rate_ignores_confirmed_and_in_progress_and_duplicates():
    rows = [
        {"status": "submitted"},
        {"status": "submitted"},
        {"status": "applied"},
        {"status": "interview"},
        {"status": "pipeline"},
        {"status": "new"},
        {"status": "submitted", "duplicate_of": "x"},
    ]
    rate, unconfirmed, considered = unconfirmed_rate(rows)
    assert (unconfirmed, considered) == (2, 4)
    assert rate == 0.5


def test_a_receipt_on_the_row_counts_as_confirmed():
    rows = [{"status": "submitted", "receipt": {"mail_id": "m", "basis": "matched"}}]
    assert unconfirmed_rate(rows) == (0.0, 0, 1)


def test_nothing_sent_means_no_rate_at_all():
    assert unconfirmed_rate([{"status": "pipeline"}]) == (0.0, 0, 0)


def test_no_mailbox_configured_is_a_valid_choice(config):
    assert reader_from_config(config) is None


# -- the export header guard ---------------------------------------------


def test_a_mailbox_with_no_record_of_what_it_searched_is_refused():
    """Otherwise "no code found" and "nobody looked" are the same answer."""
    from jobpilot.verify import ExportRefused

    with pytest.raises(ExportRefused) as caught:
        find_code(
            reader=FakeMailReader([]),
            sender_domains=["greenhouse.io"],
            recipient=ME,
            submitted_at=SUBMITTED_AT,
        )
    assert caught.value.code == "no_header"
    assert "nothing arrived" in str(caught.value)


def test_an_export_of_a_different_mailbox_is_refused():
    from jobpilot.verify import ExportRefused

    reader = FakeMailReader.covering(
        [], mailbox="someone-else@example.test", since=SUBMITTED_AT, until=SUBMITTED_AT + timedelta(hours=1)
    )
    with pytest.raises(ExportRefused) as caught:
        find_code(
            reader=reader, sender_domains=["greenhouse.io"], recipient=ME, submitted_at=SUBMITTED_AT
        )
    assert caught.value.code == "wrong_mailbox"


def test_an_unfinished_export_fails_closed():
    from jobpilot.verify import ExportRefused

    reader = _mailbox([])
    reader.header["complete"] = False
    with pytest.raises(ExportRefused) as caught:
        find_code(
            reader=reader, sender_domains=["greenhouse.io"], recipient=ME, submitted_at=SUBMITTED_AT
        )
    assert caught.value.code == "incomplete_scan"
    assert "wait" in str(caught.value)


def test_an_export_that_stops_before_the_window_does_is_refused():
    from jobpilot.verify import ExportRefused

    reader = FakeMailReader.covering(
        [], mailbox=ME, since=SUBMITTED_AT, until=SUBMITTED_AT + timedelta(minutes=2)
    )
    with pytest.raises(ExportRefused) as caught:
        find_code(
            reader=reader,
            sender_domains=["greenhouse.io"],
            recipient=ME,
            submitted_at=SUBMITTED_AT,
            window_minutes=10,
        )
    assert caught.value.code == "window_too_small"


def test_an_export_missing_half_its_header_is_refused():
    from jobpilot.verify import ExportRefused

    reader = FakeMailReader([], header={"mailbox": ME})
    with pytest.raises(ExportRefused) as caught:
        find_code(
            reader=reader, sender_domains=["greenhouse.io"], recipient=ME, submitted_at=SUBMITTED_AT
        )
    assert caught.value.code == "incomplete_header"


# -- the code provider ---------------------------------------------------


def _code_mailbox(inbox):
    return FakeMailReader.covering(
        inbox, mailbox=ME, since=SUBMITTED_AT, until=SUBMITTED_AT + timedelta(hours=1)
    )


def test_code_reading_is_off_for_every_system_until_it_is_switched_on(make_config):
    from jobpilot.verify import MailboxCodeProvider

    inbox = [
        s.mail(
            submitted_at=SUBMITTED_AT,
            subject="Your security code",
            body="Your code is AB12CD34.",
            sender="no-reply@greenhouse.io",
        )
    ]
    config = make_config()
    provider = MailboxCodeProvider.from_config(config, _code_mailbox(inbox))
    assert provider.find_code(ats="greenhouse", recipient=ME, submitted_at=SUBMITTED_AT) is None


def test_a_system_switched_on_reads_its_own_codes(make_config):
    from jobpilot.verify import MailboxCodeProvider

    inbox = [
        s.mail(
            submitted_at=SUBMITTED_AT,
            subject="Your security code",
            body="Your code is AB12CD34.",
            sender="no-reply@greenhouse.io",
        )
    ]
    config = make_config(verify={"email_codes": {"greenhouse": True}})
    provider = MailboxCodeProvider.from_config(config, _code_mailbox(inbox))
    code = provider.find_code(ats="greenhouse", recipient=ME, submitted_at=SUBMITTED_AT)
    assert code is not None and code.reveal() == "AB12CD34"
    # Switching one system on does not switch on the rest.
    assert provider.find_code(ats="workday", recipient=ME, submitted_at=SUBMITTED_AT) is None


def test_a_system_nobody_has_mail_domains_for_is_simply_skipped(make_config):
    from jobpilot.verify import MailboxCodeProvider

    config = make_config(verify={"email_codes": {"greenhouse": True}})
    provider = MailboxCodeProvider(reader=_code_mailbox([]), enabled_for=frozenset({"mystery-ats"}))
    assert provider.find_code(ats="mystery-ats", recipient=ME, submitted_at=SUBMITTED_AT) is None
