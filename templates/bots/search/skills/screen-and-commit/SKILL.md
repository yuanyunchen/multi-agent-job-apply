---
name: screen-and-commit
description: >-
  Use when deciding which found jobs are worth applying to and writing them to
  the record. Rules flag and never drop; a model decides by quoting the posting
  and the quote is re-checked; every write carries a per-job verdict; the batch
  is inspected before it is committed.
---

# Screen and commit

## The one invariant

> **A model may rule a job out only by quoting the employer's own description,
> and code re-checks that the quote is really there.**

If the quote is missing, too short to mean anything, or not present word for
word, **the drop is thrown away and the job is kept**. Not the other way round.
This is the single rule that makes every skip in the record trustworthy, and
the only one worth breaking the pass over.

## Three layers, in order

**1. Rules flag. They never drop.**

The deterministic layer annotates: a sentence about sponsorship, a citizenship
or clearance requirement, a location that reads as somewhere else, a required
number of years, a doctorate requirement, a title that reads as senior, a
company the owner wants held for their decision, how fresh it is. Each flag
carries the sentence it came from.

A flag is what the model is told to pay attention to, and what a person sees
next to a decision. It is never a reason on its own.

**2. Exactly three automatic drops.**

Nothing else is decided by code:

1. a company on the owner's **never-apply list** - name matched exactly or by a
   listed alias, never by substring, and no quote needed;
2. an **explicit, quoted sentence** from the employer's own description that
   rules the owner out entirely - no sponsorship at all, citizens only, a
   clearance required, an export-control restriction - each needing the
   sentence;
3. a posting **proven closed** by a structured liveness receipt: a status, a
   link and a time it was checked. Free text containing an error code is not a
   receipt.

Every one of those is a **configurable preference**. None is a value written
into code.

**3. A model reads the whole description and decides.**

One call per batch of rows, not per row. It answers, per job: keep or drop, a
tier, a quoted sentence if it is dropping, and a short reason. Then code checks
every quote against the raw description.

A model that answers nothing, times out or cannot be reached leaves the rule
answer standing, marked as awaiting a model. It does not block the pass.

## When in doubt, keep

A missed job costs a day. A wrong drop is invisible and permanent.

- **Years of experience**: only an explicitly *required* minimum, quoted, drops
  a job. "Preferred", a range starting lower, a ceiling, and conflicting
  statements all mean keep.
- **Sponsorship**: a posting that accepts a permit the owner already has but
  will not sponsor a new visa is a **normal role**. Only an explicit "no
  sponsorship at all", citizens-only, or a clearance requirement - quoted -
  rules them out.
- **Location**: a job is only ruled out by an explicit requirement to live or
  work somewhere the owner cannot. An ambiguous region code is ambiguous, not
  foreign. Remote or unstated is eligible.
- **Seniority**: a title that says senior, staff, principal, lead or manager is
  a drop on the title alone. Other seniority language is context and needs the
  whole description and a quote.
- **A missing description** never parks a row. Try a direct read, then read the
  page, and failing both vet on the title against the explicit disqualifiers
  only, and tag the row as title-only.

## Tiers

Three: **first choice**, **second choice**, **never**.

- They come from the owner's own term lists, read fresh.
- A title on no list is **second choice**, never "never" - an unlisted title is
  a question for a model, not a reason to bin a job.
- **Ambiguity between first and second favours first**, where a job is applied
  to while it is still open.
- "Never" means never queued. It is still written to the record, with its
  reason: drops are data, not silence.

## Committing

One file, one writer. Everything goes through it, and it locks, re-reads,
de-duplicates by identity, backs up and then writes once.

What the writer will refuse, and why:

| refused | why |
|---|---|
| a write with no per-job verdict | a decision covering several jobs is not evidence |
| a skip with no reason | an unexplained skip cannot be reviewed |
| a skip with no quote | except a named company, a proven-closed posting, or the owner's own decision |
| a status it does not recognise | a typo is a refusal, not a silently different row |
| re-opening a job the owner skipped | that needs their say-so |
| anything on an already-applied row beyond notes and evidence | that application is out; it is not rewritten |

**Inspect before you write.** Dry run the batch, read the plan - what would be
added, what changed, what was refused and why - and only then commit. The
useful order is always the same: look at the change, then make it.

If the writer refuses a row, report it. Never retry with an override to get
past a guard: the guard is the feature.
