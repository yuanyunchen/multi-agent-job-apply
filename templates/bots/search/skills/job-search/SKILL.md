---
name: job-search
description: >-
  Use when running a search pass. Covers the two focus modes, the order of
  steps, where to look, how to keep a row's identity, de-duplication by three
  identities, platform one-click apply when it is switched on, and the single
  handoff to the Lead.
---

# Job search

## The goal

**Maximise relevant recall.** Find everything plausible; let screening decide.
A job you never found cannot be applied to, and nobody will ever know.

## The two focus modes

The Lead names one per pass. Same role, same rules, same screening code.

**Broad.** Read employers' own application systems and public interfaces
directly, plus aggregated lists and index sites. Accept duplicates - that is
what de-duplication is for. Cover as much ground as the time allows.

**Channel.** One platform the Lead names, gone through properly: its own
search, its own ordering, its own filters. This is where you find postings that
never reach a board, and where you read the employer's own words rather than
somebody's copy of them.

Record which focus and which source found each row. Without that, a dead
channel and a dead system look the same.

## The order of a pass

1. **Set up** - read the owner's title list *fresh*. Never a copy; a list that
   lives in two places drifts.
2. **Collect** per source, with per-source counts kept as you go.
3. **Fill in missing descriptions** - try a direct read from the application
   system first, then read the page through the browser slot if the lane gate
   allows. A missing description never parks a row.
4. **De-duplicate** across everything collected, and against the record.
5. **Screen** - rules flag, a model decides with a quote, code checks the quote.
6. **One-click apply**, only if that is switched on (below).
7. **Resolve links** to the employer's own posting where you have an
   aggregator's copy.
8. **Commit** - dry run, read the plan, write once.
9. **Hand over** - one report to the Lead.
10. **Source health** - what each source yielded, including the zeroes.

## Where to look

The sources are the owner's settings, never a list written in here. Typical
shapes:

- **employers' own application systems** - public interfaces that need no
  account, read directly;
- **aggregated and index sites** - broad, noisy, good for coverage;
- **new-graduate and curated lists** - low volume, high relevance;
- **platforms** - a professional network, a school platform, a startup list,
  each needing the owner's own session and read-only access;
- **named employers** - the list the owner cares about, checked every pass.

Use the owner's own sessions where a platform needs one. Never open their
browser profile directly, never touch cookies or tokens, never sign out, never
create an account.

## Keep every row's identity

Carry all of it through: the link, the company, the title, the location, the
date posted, and the site's own identifier. Each of those is the only way to
match the row later:

- the **link** finds it again;
- the **identifier** matches it when the link shape changes;
- the **date** decides the order, and freshness is a signal, never a
  disqualifier;
- the **description** is the evidence. Never summarise it before screening -
  the quoted reason must be a sentence the employer actually wrote.

A posting with no date is recorded as having none. Guessing one puts it in the
wrong place in the queue.

## De-duplication

Three identities, because no one of them is enough:

1. **the cleaned-up link** - tracking parameters stripped, host lower-cased;
2. **the site's own job identifier**, scoped to the company and the system;
3. **company plus title**, normalised.

The first two are a **merge**: one posting, seen twice. Keep the richer row and
remember the other link.

The third is only ever a **flag**. Company and title matched loosely once
removed good rows silently - two genuinely different openings at one employer
often share a title. So flag it as a possible duplicate, keep the row, and let
a person or the Lead look. Two titles sharing only generic words are not
evidence of anything.

Check against the record **before** handing over.

## One-click apply during a pass

Only when the owner has switched it on, and only for a platform's own in-app
apply - never an employer's own site.

- **Answers** come only from the answer bank. A question that cannot be answered
  truthfully **parks** the role. Never fabricate one.
- **Duplicates**: before submitting, check the record has no application for
  this job and the page shows no sign it was already applied to.
- **Verify** the confirmation screen before recording anything.
- **Record** it with the platform it happened on, so the numbers can be split
  by channel later.
- **Pace** like a person. **Stop and report** at any platform warning, a
  captcha you cannot pass, or a daily limit.

## The handoff

One report, marked urgent, when the pass finishes:

- rows handed over, split by tier;
- per source: raw, matched, new against the record;
- counts for anything applied to in-app, per platform;
- source health, including every source that returned nothing;
- insights - patterns, anomalies, what is working;
- one or two suggestions, each with the effect you expect.

A source that found nothing is a fact the Lead needs. Leaving it out of the
report makes a dead source look like a working one.
