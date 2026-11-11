---
name: inbox-triage
description: >-
  Use when reading the application mailbox. Read-only; rules only pre-filter;
  the classifier reads the full body and quotes it; the quote is re-checked; an
  outcome is written only when the message ties to a job on the record; the list
  of things that are never action items.
---

# Inbox triage

## Read-only means read-only

Never send, reply, forward, delete, archive, label or mark as spam. The owner
writes every reply themselves.

The one possible exception is **starring** a message, if the owner has allowed
it, and only after checking it is not already starred. Nothing else.

## The window

Read a window with an explicit start and end:

- **start**: the watermark from your last run, minus a few minutes so a message
  that arrived while you were running is not missed;
- **end**: now.

If the window would start *later* than your watermark, that is a **gap**. Stop
and report it rather than scanning over the hole - the messages in the gap are
exactly the ones nobody will ever look at again.

When saving an export of what you read, strip links and redact anything
code-shaped. An export is a record of what was read, not a second copy of its
contents.

## Three layers, in order

**1. Rules narrow it down. They never decide.**

Rules choose which messages are worth a full read. They may be as crude as you
like - a sender domain, a word in a subject. They never assign a type.

**2. The classifier reads the full body and quotes it.**

For each candidate, it returns:

- a **type**: test, interview, recruiter reply, offer, rejection, or nothing;
- a **status** and a **deadline**, if the message gives one;
- **one sentence quoted from the body** as its evidence.

A subject line is not evidence. Employers reuse the same subject for an
invitation and for a rejection, and the difference is in the body.

**3. Code checks the quote.**

The quoted sentence must appear in the body **word for word**. If it does not,
the result is **unverified** and nothing is written. Only a verified result may
create or change a test or interview row.

Where a message mentions several things, the **strongest outcome wins**: an
interview mentioned alongside a test is an interview.

## Never an action item

This list exists because each one has been got wrong, and each one cost
somebody an hour of confusion:

- **a post-interview feedback survey** - "how did we do", "rate your
  experience", "your interview experience with". This is the most common
  misread of all;
- **a rejection**;
- **an application receipt or confirmation**;
- **a newsletter, a job alert, a marketing email**;
- **an event invitation** - a careers fair is not an interview;
- **a verification or identity email** - and it is never proof an application
  arrived either.

## Tying a message to a job

An outcome is written **only** when the message can be tied to a job on the
record, by one of:

- the **sender belongs to the posting's own site**; or
- the **company is named in the subject**.

Without one of those, count it as unmatched and report the count. **An outcome
recorded against the wrong job is worse than one that was missed** - it makes
the record say something untrue, and nobody will check it again.

## Writing it back

Through the record's single writer, which locks, re-reads, backs up and writes
once. Every outcome carries its evidence: the message reference, how it
matched, and the quoted sentence.

Keep the tests-and-interviews list current: company, type, the thread it came
from, and the deadline in the **owner's own time zone**. A deadline in the
wrong time zone is worse than no deadline.

**A closure sticks.** A row the owner or the Lead has closed, or marked as not
an invitation, is never reopened. A new message on that thread is recorded
separately and flagged for review.

## When it fails

If the classifier errors, cannot be reached, or returns a quote that is not in
the body, **flag that message for a person to look at**. Never drop it, and
never fall back to guessing from the subject.

If a whole run fails, retry once and then tell the Lead. Do not hand-fix the
record.

## Reporting

- **Immediately, marked urgent**: tests, interviews, offers, recruiter replies.
- **Recorded, never reported**: rejections.
- **One summary per run**: everything else, with counts.
- **Silently**: nothing at all, when there is nothing.

Never put the contents of somebody's mail in a report. Counts, companies,
roles, deadlines and references - not bodies.
