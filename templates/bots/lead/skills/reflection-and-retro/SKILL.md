---
name: reflection-and-retro
description: >-
  Use for the end-of-day look back and the Monday retro. The reflection reads
  the day's numbers, logs one candidate for handing to a provider and raises
  suggestions for approval; the retro goes over the week by source and by
  application system and re-checks the provider slots. Neither ever changes a
  setting.
---

# Reflection and retro

## Why these exist

A system that does not look at itself gets worse quietly. Nothing crashes, no
error appears, and a month later the confirmation rate has halved.

The reflection is **not a diary**. Its output is proposals. A note nobody acts
on is a cost with no benefit.

## Daily reflection

Read, in this order:

1. **The day's aggregate numbers** - found, screened, queued, submitted,
   confirmed, parked, blocked, skipped. Compare with the last few days, not
   with zero.
2. **New entries in the improvements log** - what broke today and what fixed
   it. Anything appearing for the third time is not an incident, it is a
   missing feature.
3. **Unacknowledged assignments** - a teammate that did not acknowledge is a
   teammate that is not working.

Then write the entry, and write it **every day, including days when the system
was paused and nothing happened**. A gap in this record is indistinguishable
from a day nobody looked.

Log **one concrete agent-ification candidate**: something done by hand today, a
provider slot that could have done it, and the saving you expect. One, not a
list - a list is a wish, one is a plan.

## Turning numbers into proposals

Each of these is worth asking about. Each proposal states its **evidence**, its
**expected effect**, and then **asks**.

| what you see | what to propose |
|---|---|
| applications going out and not coming back | a site has probably added a step; propose switching on code reading for that one system |
| the queue empty for days | propose looking further back, or widening the roles considered |
| a source producing nothing for a week | propose retiring it, and say what that frees up |
| the same application system blocking repeatedly | propose the owner finishing those by hand, or skipping that system for now |
| several forms asking the same unanswered question | propose adding it to the answer bank, with the wording |
| a session idle while the queue is deep | propose working on one more at a time |
| a role the owner liked appearing again and again | propose adding it to their first-choice list |

**You never change a setting.** Not a small one, not an obvious one. Propose it,
show what it would change in plain words, and wait. Approving is a separate,
deliberate act; declining is recorded too, so the same proposal does not come
back tomorrow.

## Monday retro

The week, split so the answer is actionable:

- **by source** - which found jobs that became applications, and which found
  nothing;
- **by application system** - where submissions succeeded, where they blocked;
- **confirmation rate** - of what went out, how much arrived;
- **where replies actually came from** - the only number that matters in the
  end.

Splitting matters: "nothing is working" and "one source has gone quiet" look
identical in a single total and need completely different answers.

Then **re-check the provider slots**. Ask what is available now for the browser
worker, the code worker, the reviewer and the classifier. Models improve, and a
slot pinned to an older one is slower and more expensive for no reason. Propose
updating the settings; never pin an older version, and never write a model name
into a skill or a script.

Finish with the handful of preference changes the week's evidence justifies -
three or four, not twenty - each with what it would change and what the owner
would notice.

## Promote, do not re-explain

A fix that worked becomes a rule or code, in the same turn:

- a reusable fix goes in the lessons file as a dated one-line rule;
- a recurring manual step becomes a script or a routine;
- a rule the owner states is written down immediately and applied to every
  similar case without asking again.

A rule kept in two places will disagree with itself. Keep one copy and point
everything else at it.
