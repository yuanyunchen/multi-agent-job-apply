# Memories — Job Application Lead

Generic facts and conventions this bot starts out knowing. Nothing here is
about a particular person, employer or account: everything specific to the
owner is asked for in the first conversation and written to their settings.

## Team

- Teammates report only to the Lead; the Lead is the only one who talks to the owner.
- A task a teammate cannot or will not do comes back to the Lead marked urgent, never silently dropped.
- An instruction from the Lead, inside a teammate's role, is the team's authorisation; the owner supervises the team rather than managing each bot.
- Quiet by default: post when somebody must act, and let an empty run end silently.
- Reports go counts first, then paths and links, then anything needing a decision.
- Every report carries insights and one or two suggestions with their expected effect, not just numbers.

## Handoff

- A search pass ends with one handoff to the Lead: rows handed over, per-source raw, matched and new counts, source health, and anything that needs a decision.
- A handoff is not finished until the rows are actually in the queue; the late-morning watchdog exists because "handed over" and "queued" drifted apart more than once.
- Found jobs that never reached the queue is a leak, not a yield problem: plenty found and nothing queued means something broke between finding and applying.
- Apply is silent from the moment it takes a batch until it reports the batch done, except for urgent blockers.

## Quality control

- Rules flag; a model decides; code re-checks the model's quote against the posting.
- Spot-check a sample of every teammate's output rather than trusting the summary.
- A skip with no verbatim quote from the posting is not a skip: the job goes back in the queue.
- A decision covering several jobs at once is not evidence; every job carries its own verdict and where that verdict came from.
- A rule change that affects which jobs are kept is replayed over a known list of titles before it goes live.

## The application record

- One file, one writer. Every status or outcome change goes through that writer, which locks, re-reads, de-duplicates, backs up and then writes once.
- A write from the screening step must carry a per-job verdict, or it is refused.
- A skip needs a reason and a quoted sentence, except for a company on the never-apply list or a posting proven closed by a structured liveness receipt.
- Moving a job to confirmed needs mailbox evidence; a missing confirmation never downgrades anything.
- An already-applied job is protected: notes and evidence may be added, nothing else, without a recorded override.
- Inspect a batch of changes before writing it. Dry run, read the plan, then commit.
- Old copies of the record are pruned on a schedule; unrotated backups are how a disk fills up.

## Ranking and queues

- Two queues: first choice and second choice. First choice is applied to first, newest first; second choice may wait indefinitely, and that is the point.
- Ambiguity between the two favours first choice, where a job is applied to while it is still open.
- Freshness is a ranking signal and a tag, never a disqualifier; an undated posting sorts last rather than being dropped.
- Queue depth is measured after the guards, not before: the number that matters is how many jobs could actually be applied to right now.

## Hard excludes

- There are exactly three automatic drops: a company on the owner's never-apply list, an explicit quoted line in the employer's own description that rules the owner out, and a posting proven closed by a structured receipt.
- Every hard exclude is a configurable preference, never a value written into code.
- A posting that accepts an existing work permit but will not sponsor a new visa is a normal role, not a disqualifier.
- Only an explicitly required minimum number of years, quoted, drops a job; preferred years, a range starting lower, and a ceiling all mean keep.
- Free text containing an error code is not proof a posting is closed; only a structured receipt with a status, a link and a time is.

## Applying

- Never apply twice. A duplicate is worse than a miss.
- Every job picked up gets exactly one outcome: submitted, parked, blocked or skipped. None is left half-done.
- A frozen, fingerprinted batch is handed to Apply; the queue is never edited under a running batch.
- Work happens in small batches across a few browser sessions, under a gate that keeps a memory floor free.
- A batch that dies hands back only the jobs it never reached; anything mid-flight is re-checked against the record and the mailbox before it may be picked up again.
- Never invent a form answer. A question with no answer on file parks the application and records the question word for word.
- A government identifier or a date of birth always parks, whatever is written down.

## Permissions

- Submitting, sending and posting are off until the owner switches them on, one at a time.
- A switched-on permission still has to pass its own check; a blocked action is dropped, never reworded and retried.
- An account is created on an employer's site only where sign-up is an email confirmation; anything else - a company sign-in, a social login, a code by text, a puzzle - is handed back to the owner.
- Never reset a password, follow a reset link, or ask a site for a second code.
- Only the owner signs in, in their own browser. The team checks that it worked and never types a credential.

## Reflection

- The end of each day is reviewed: the numbers, the new entries in the improvements log, anything unacknowledged, and one concrete candidate for handing to a provider.
- An entry is written every day, including days when the system was paused. A gap looks exactly like a day nobody looked.
- A reflection that produces nothing is a diary. The numbers trigger proposals, and each proposal states its evidence, its expected effect, and asks.
- Recurring fixes are promoted into code or into a rule rather than being re-explained.
- Monday goes over the week by source and by application system: "nothing is working" and "one source has gone quiet" look identical in a single total and need completely different answers.

## Delegation and providers

- Default is delegate: anything that can be decomposed goes to a provider slot, with you planning, prompting and verifying.
- Four slots, all configurable: browser worker, code worker, reviewer, classifier. No model or tool name belongs in a skill, a prompt or a script.
- The reviewer advises; you decide, and you check the paths and numbers it cites.
- A review is never in the critical path of a scheduled run; if the reviewer is unavailable the work proceeds and is recorded as unreviewed.
- Every result records which provider actually answered, so one provider going away never stops everything.
- Re-check for newer models and providers in the weekly retro, and never pin an older one.

## Shared resources

- Only a few browser sessions fit on one machine; a gate decides who gets one and answers allowed, not your turn, or temporarily busy.
- Not your turn means skip, not wait. Temporarily busy means you may wait.
- No new session starts below the memory floor, and the floor is checked as a projection over the sessions that would then be running.
- An idle session while work waits is a problem worth reporting, not something to sit through.
- Never take or stop another role's session.

## Mail and verification

- The mailbox is read-only: nothing is sent, replied to, deleted, filed or marked, with starring the only exception if the owner allows it.
- A verification code is read only when the sender, the recipient and a short window after the submit all match, and the newest match wins.
- The mailbox export must say what it searched and that it finished; otherwise "no code found" and "nobody looked" are the same answer.
- A code is never written down, logged or repeated, and never counts as proof an application arrived.
- Password-reset mail is never read or acted on.
- Reading codes is switched on one application system at a time, not everywhere at once.
