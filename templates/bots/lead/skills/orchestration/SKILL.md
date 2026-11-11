---
name: orchestration
description: >-
  Use when handing work to teammates and checking what comes back: waking the
  search bots once a day with a focus each, building and freezing the apply
  queue, handing it over, watching the handoff reach the queue, and
  spot-checking output rather than trusting a summary.
---

# Orchestration

## Wake once, with a focus

Wake each search bot **once** a day and give it a focus. Waking twice gets you
the same jobs twice and twice the cost.

Two focuses, one role: a **broad** pass over application systems and public
interfaces, and a **channel** pass that goes deep on one platform you name.
Give each bot one, and say which, so neither guesses.

## Build the queue, then freeze it

1. **Build** from the record: screened, eligible, not held for a decision, not
   already out, not a known duplicate.
2. **Order** it: first-choice roles first, newest first; second choice after;
   undated last.
3. **Freeze** it - write it down once, fingerprint it over its contents, and
   never edit it again.
4. **Hand it over** to Apply as that frozen list.

The freeze is the point. A queue rebuilt while a batch is running puts a job in
two batches, and that is how the same posting gets two applications.

## Watch the handoff land

"Handed over" and "queued" are different facts, and they drift. Late each
morning, check:

- **a leak** - plenty found and nothing queued. Something broke between finding
  and applying; this is not a yield problem and widening the search will not
  fix it.
- **a stalled batch** - handed out and not moving for a while.
- **expired claims** - jobs still marked as being worked on by a session that
  has gone.

Anything mid-flight is re-checked against the record **and the mailbox** before
it goes back in the queue. A first submit recorded as blocked but which
actually went through is exactly how a duplicate happens.

## Check, do not trust

Read every teammate's summary, then check a sample of the work properly:

- a few **kept** jobs: do they really match what the owner asked for?
- a few **skipped** jobs: is the quoted sentence actually in the posting, and
  does it actually rule the owner out?
- a few **submitted** jobs: is there evidence, and is the record consistent
  with it?

A quote that is not in the posting invalidates the skip: the job goes back in
the queue, and you tell the teammate what happened.

## Keep the resources moving

Only a few browser sessions exist. Nothing should sit idle while work waits.

- Time of day decides who has first call: searching in the morning, applying
  through the day and overnight, engagement in the evening.
- No new session starts below the memory floor, checked as a projection over
  the sessions that would then be running.
- A session idle for a while may be borrowed by somebody else for one capped
  task, as long as the owner of that window keeps one free.
- A running batch always finishes. No new one starts in the half hour before
  the window changes.
- If a teammate reports being refused while a session looks free, that is a bug
  worth fixing, not something to leave them waiting through.

## Assignments

An assignment says: which jobs, what counts as done, and what it may not do.
Apply goes silent from the moment it takes one until it reports it finished -
except for an urgent blocker.

Track which assignments were acknowledged. An unacknowledged assignment is a
teammate who is not working, and it will not announce itself.
