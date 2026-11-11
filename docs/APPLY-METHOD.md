# The apply method — a runbook

How one application gets from "found" to "confirmed", and every place it is
allowed to stop. This is the operational document: if you are writing an apply
driver, debugging a stuck batch, or deciding whether a behaviour is a bug, this
is the order of events it has to fit into.

Written generically. No employer, no application system and no account is named,
because the method does not depend on any of them.

---

## 0. The four rules the whole method exists to enforce

1. **A duplicate is worse than a miss.** Applying twice is embarrassing and
   unfixable; missing one costs a day. Every guard is tuned that way.
2. **Never invent an answer.** No answer on file means the application stops and
   the person is asked. There is no "probably".
3. **Every job that is picked up is put down.** Applied, parked, blocked or
   skipped. A job left in limbo blocks everything behind it.
4. **Nothing leaves the machine without a permission *and* a check.** The
   permission is the person's decision; the check is the code's.

## 1. The journey

```
   found ──► read ──► queued ──► frozen into a batch ──► picked up
                                                            │
                        ┌───────────────────────────────────┤
                        ▼                                   ▼
                     answers?                         no answer on file
                        │                                   │
                        ▼                                   ▼
                  outbound check                     PARKED, with the
                        │                            exact question
          ┌─────────────┴─────────────┐
          ▼                           ▼
     filled and sent              BLOCKED, with what stopped it
          │
          ▼
       "sent"  ──► mailbox receipt inside the window ──► "confirmed"
          │
          └── no receipt: stays "sent". Never re-sent, never downgraded.
```

## 2. Before a batch starts

| step | what it checks | if it fails |
|---|---|---|
| **Queue** | screened, eligible, not held, not already out, not a known duplicate | the job is simply not in this batch |
| **Order** | first choices first, newest first; undated last | — |
| **Freeze** | the list is written once, fingerprinted, never edited | a changed list is refused outright |
| **Flags** | every flag is a real boolean | the batch is refused: `"False"` is a true string, and a row once bypassed a guard exactly that way |
| **Room** | free memory minus *(lanes + 1) × per-lane estimate* still clears the floor | no new lane starts; the jobs wait |
| **Stop file** | present? | the batch in flight finishes; no new one starts |

A batch is cut into waves of about twenty, spread across the lanes that are
free. Twenty is a compromise: large enough that the setup cost amortises, small
enough that a crash loses little and a watchdog notices quickly.

## 3. Per job, before anything is typed

Run in this order, cheapest and most certain first.

1. **Already applied?** By identifier *and* by posting identity, across the
   whole record. A job that was submitted — including one that was later
   rejected — is never submitted again.
2. **Was it skipped?** Re-opening something the person skipped needs their
   explicit approval, recorded on the row.
3. **Claimed elsewhere?** One lane at a time, with a claim that expires after
   40 minutes so a crash cannot hold a job for ever.
4. **An account needed?** Ask the registry. If sign-up is anything other than
   an email confirmation — a company sign-in, a social login, a code by text, a
   puzzle to prove you are human — the job is **handed back to the person**,
   not worked around.
5. **Every question answerable?** From the answer bank only. One unanswerable
   question parks the whole application, with the question recorded verbatim.
   Personal identifiers always park.
6. **The outbound check.** The submit permission must be on, and the check must
   pass. A failure is a **hard stop**: never reworded, never retried.

A failure at any step is a **disposition**, not an error. The job gets its
outcome, the reason is recorded, and the wave moves on.

## 4. Submitting

The core ships a driver that opens nothing. A real driver is a plugin, and the
interface is deliberately narrow so the core cannot tell the difference:

```python
class ApplyDriver(Protocol):
    name: str
    def questions(self, row: dict) -> list[str]: ...
    def apply(self, request: ApplyRequest) -> ApplyOutcome: ...
```

A driver **must**:

- honour `request.dry_run` absolutely — it may look at a page, and must not
  type, click or change anything anywhere;
- answer only from `request.answers`, and raise rather than invent;
- read the form back before submitting and compare it with what it meant to
  type. A mismatch is a block, not a retry;
- return exactly one of `submitted` / `parked` / `blocked` / `skipped`, with
  evidence: the confirmation page's URL and its text for a submit, the exact
  question for a park, what stopped it for a block;
- never click a "forgot password" link, request a second verification code, or
  sign anything in or out. Not once, not as a fallback, not to recover.

## 5. After submitting

| state | what it means | what happens next |
|---|---|---|
| `submitted` | a submit happened; no confirmation yet | the receipt sweep looks for one |
| `applied` | a mailbox message proved it arrived | nothing; the row is protected |
| `parked` | a question only the person can answer | it appears in the daily summary |
| `blocked` | a wall we could not pass | counted per application system; a pattern becomes a proposal |
| `skipped` | the apply step decided against it | recorded with its reason |

A receipt counts only if **all** of these hold: the sender belongs to the
posting's own site, the recipient is the address used on the form, and the
message arrived inside the window after the submit. Newest match wins.

**A missing receipt never downgrades anything.** "Sent" with no confirmation
stays "sent" and is never re-sent. A silence is not evidence.

## 6. When an application system asks for a code mid-form

Some forms email a short code part way through. This is the most delicate thing
the system does, so:

- it is **off for every application system** until switched on individually
  (`verify.email_codes.<system>`), which is how a risky path is rolled out one
  system at a time instead of everywhere at once;
- the mailbox must declare what it searched — an export header naming the
  mailbox, the query and the window, marked finished. Without it, "no code
  found" and "nobody looked" are the same answer, and they must never be
  confused;
- the four matching rules are the receipt rules: sender, recipient, window,
  newest wins;
- the code is wrapped in a type that **cannot be printed**. `str()`, `repr()`
  and f-strings all give a redaction marker; only the step that types it into
  the form calls `reveal()`;
- password-reset mail is never read, and a second code is never requested. No
  match inside the window means the application waits for the person.

## 7. When a batch dies

It will: a crash, a restart, a machine running out of memory mid-wave.

1. The **watchdog** notices — a batch with jobs outstanding and no movement for
   40 minutes, or jobs still claimed past their lease.
2. Jobs the wave **never reached** are handed back to the queue. Jobs it was
   mid-way through are **not**: they are re-checked against the record, the
   submit evidence and the mailbox first.
3. Only then may a job be picked up again. A job whose first submit was
   recorded as *blocked* but which actually went through is exactly how the
   same posting gets two applications — so the mailbox is consulted, not just
   the record.

## 8. Reading a stuck batch

```bash
jobpilot doctor                     # settings, record, models, room, health
jobpilot status --technical         # counts per state, queue depth
jobpilot run apply --dry-run        # what the next batch would do
```

| symptom | most likely cause | where to look |
|---|---|---|
| "nothing waiting to be applied to" with plenty found | the jobs never reached the queue | the handoff check; `watch.tick` raises `queue_leak` |
| nothing goes out and nothing is reported | no room: the memory floor | `doctor` says "Room to work" |
| everything parks | the answer bank is thin | `doctor` counts the answers; the summary lists the questions |
| everything blocks on one system | the form changed, or an account is needed | blocked-by-system in the weekly review |
| sent, never confirmed | the system added a step, or the mailbox is not connected | `watch.tick` raises `confirmations_low` |
| a batch that will not move | a dead wave holding claims | `watch.tick` raises `batch_stuck`; claims expire after 40 minutes |

## 9. What this method never does

- apply to the same posting twice;
- invent, guess or approximate an answer on a form;
- submit without both the permission and the check;
- reset a password, follow a reset link, or ask for a second code;
- create an account where the sign-up needs anything more than an email
  confirmation;
- leave a job it picked up without an outcome;
- treat silence as evidence, in either direction.
