---
name: apply-method
description: >-
  Use when working a batch of applications: the frozen list and its
  fingerprint, the guards that run before anything is typed, batches across
  sessions under the memory gate, the gated submit, the four outcomes, and what
  to do when a batch dies.
---

# Apply method

## The four rules everything else serves

1. **A duplicate is worse than a miss.** Applying twice is embarrassing and
   cannot be undone; missing one costs a day.
2. **Never invent an answer.** No answer on file means stop and ask. There is
   no "probably".
3. **Every job picked up is put down.** One outcome each, always.
4. **Nothing leaves the machine without a permission and a check.** The
   permission is the owner's decision; the check is the code's.

## The frozen list

The Lead hands over a list written once and fingerprinted over its contents.

- **Check the fingerprint before starting.** If the contents no longer match,
  stop and tell the Lead. A queue that changed under a running batch is how a
  job ends up in two batches.
- **Never edit it.** It is a work order, not a copy of the record.
- **Flags must be real true/false values.** The word `"False"` is a true
  string, and a row once bypassed a guard exactly that way. Refuse the whole
  list rather than guess.

## Before anything is typed

In this order - cheapest and most certain first.

| step | what it checks | if it fails |
|---|---|---|
| **already applied** | by identifier *and* by posting identity, across the whole record, including anything later rejected | skip; record why |
| **was it skipped** | re-opening a job the owner skipped needs their recorded approval | skip |
| **claimed elsewhere** | one session at a time, with a claim that expires so a crash cannot hold a job for ever | skip this pass |
| **needs an account** | ask the registry; sign-up by email confirmation only | hand back to the owner |
| **every question answerable** | from the answer bank only | **park**, with the question word for word |
| **the outbound check** | the permission is on *and* the check passes | **blocked**; final, never retried |

A failure at any step is an **outcome**, not an error. Record it, report it,
move on to the next job.

## Batches and sessions

- Roughly **twenty jobs per batch**: large enough that the setup cost pays off,
  small enough that a crash loses little and a watchdog notices quickly.
- A few **sessions in parallel**, as many as the gate allows. No new session
  starts below the memory floor, and the floor is checked as a projection over
  the sessions that would then be running.
- Each session gets its own working directory and its own temporary space.
  Never share one, and never put working files somewhere a cleaner will remove
  them mid-run.
- **A running batch always finishes.** No new batch starts once a stop is asked
  for, or in the half hour before the session window changes.

## Filling and submitting

- **Answers come only from the answer bank.** A short written answer may be
  composed from recorded background facts, and never beyond them.
- **Read the live form back** and compare it with what you meant to type -
  name, contact, location, work-authorisation answers, the document attached. A
  mismatch is a **block**, not a retry.
- **Submit only through the gated path**, never by clicking a submit control
  directly. The gate re-reads the form, compares it with the read-back, and
  clicks only on a match.
- **A submit with no record of the read-back** is written down as sent-but-
  unverified, never as confirmed.
- **Verify the confirmation screen** and keep its link and its text as the
  evidence.

### Per-system settings

Each application system has its own quirks: how many steps it takes, whether an
autofill helper helps or hurts, whether it needs an account. Keep those in
**settings, one entry per system** - never in this skill and never in a prompt.

Two settings every system needs: a **step budget** (stop and park rather than
wandering for ever) and whether an **autofill helper** is on. Treat an
autofill helper's output as a draft: check every field against the answer bank
and overwrite it before submitting.

## The four outcomes

| outcome | means | what is recorded |
|---|---|---|
| **submitted** | a submit happened | the confirmation link and text, and when |
| **parked** | a required fact is missing and only the owner can supply it | the exact question |
| **blocked** | a wall we could not pass | what the wall was, so a pattern shows up per system |
| **skipped** | the apply step decided against it | the reason |

`submitted` is not `confirmed`. Confirmation needs mailbox evidence and is
somebody else's job.

## When a batch dies

It will: a crash, a restart, the machine running out of memory mid-batch.

1. **Notice** - a batch with jobs outstanding and no movement for a while, or
   jobs still claimed past their lease.
2. **Hand back only what was never reached.** Anything mid-flight is re-checked
   against the record, the submit evidence **and the mailbox** first.
3. **Only then** may a job be picked up again. A first submit recorded as
   blocked but which actually went through is exactly how the same posting gets
   two applications - so consult the mailbox, not just the record.

## Reporting the batch

One report when the list is done: counts per outcome, every parked job with its
question, every blocked job with its wall, and the evidence paths. Then
insights - which system blocked repeatedly, which question parks the most
applications - and one or two suggestions.

Stay silent until then, except for an urgent blocker.

## Never

- Never apply to the same posting twice.
- Never invent, guess or approximate an answer.
- Never submit without both the permission and the check.
- Never reset a password, follow a reset link, or ask for a second verification
  code - not as a fallback, not to recover.
- Never create an account where sign-up needs more than an email confirmation.
- Never leave a job claimed.
- Never take the form over by hand when a worker fails: dispose of the job and
  continue.
