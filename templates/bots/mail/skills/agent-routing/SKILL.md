---
name: agent-routing
description: >-
  Use for any task that can be broken into steps. Delegate by default to a
  configured provider slot - browser worker for page actions, code worker for
  code, data, files and lookups, reviewer for judgment, classifier for bulk
  reading - then verify the result. Do a step by hand only when it is a
  one-liner or needs the owner's own identity. Provider slots are settings, so
  no model or tool name is written into this skill.
---

# Agent routing

## The rule

**Default is delegate.** Any task that can be decomposed - a fixed pipeline or
something that came up five minutes ago - goes to a provider. You plan, write
one self-contained prompt, run it, and verify. You are a manager of workers,
not one of the workers.

Doing it by hand is the exception, and there are exactly two: a trivial
one-liner (a single read, a count, a status check), and an action that needs
the owner's own identity or their approval.

## The four slots

Slots, not products. Which model or tool fills a slot is a setting the owner
controls, so this skill never names one. Ask the configuration what is in each
slot; if a slot is empty, say which work is paused rather than guessing.

| slot | what goes to it |
|---|---|
| **browser worker** | anything on a page: reading a posting, filling a form, checking a link or a title, working inside a signed-in session |
| **code worker** | code, scripts, data processing, tidying files and records, lookups and investigations, keeping notes up to date |
| **reviewer** | review, audit, planning, design, analysis, judgment calls, second opinions, cross-review of important output |
| **classifier** | bulk reading where the answer is a label plus a quote: screening descriptions, sorting mail |

Two slot rules worth stating:

- **The reviewer advises; you decide.** Check the paths and numbers it cites.
  Anything needing approval goes to the Lead, and from the Lead to the owner.
- **A review is never in the critical path of a scheduled run.** If the
  reviewer is unavailable or over budget, carry on and record the work as
  unreviewed. A routine that waits on a review is a routine that stalls.

## Writing the prompt

The provider sees none of your context. Every prompt carries all five:

1. The goal, and what counts as done.
2. The inputs: exact paths, links, data, and which account or identity to use.
3. The limits: what it may and may not do. Say **explicitly** whether it may
   submit, send, post or buy. Silence here is how something gets sent.
4. The output shape: a file at a given path, plus a short summary.
5. For bulk work, one chunk per run (roughly 20 to 50 items) with a status for
   every item, so a failure is partial rather than total.

## Verify, do not redo

Run the tests. Spot-check a page or a few rows. Diff the output against what
you expected. If it is wrong, **re-run with a sharper prompt** - taking over by
hand hides the fact that the prompt was the problem, and you will write the
same prompt again next week.

## Budgets and limits

- Only a few browser sessions fit on one machine. Browser work goes through the
  lane gate, which answers: allowed, not your turn (skip, do not wait), or
  temporarily busy (you may wait). Never take another role's session.
- The reviewer is the expensive slot and is shared by the whole team. Batch
  related questions into one well-scoped call. Never call it in a loop or from
  a frequent routine. Plain lookups go to the code worker.
- Back off on rate limits rather than retrying hard.

## Keep the slots current

Models improve. A slot pinned to last season's model is a slow, expensive slot.
The Lead re-checks for newer models and providers in the weekly retro and
updates the settings; nobody else pins a version, and nobody writes a model
name into a skill, a prompt or a script.

If a provider goes down or logs out, the fallback chain in the settings takes
over, every result records which provider actually answered, and the owner is
told plainly which work is paused. One provider going away must never stop
everything.

## Never

- Never print, copy or log an authentication file, token, cookie or password.
- Never sign a provider or a browser profile in or out, and never change the
  global configuration of a tool.
- Never stop a process you did not start.
- If a provider is not signed in, stop and ask the owner to sign in. You never
  sign in on their behalf.
