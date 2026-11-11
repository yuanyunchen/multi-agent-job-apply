# Memories — Job Apply Bot

Generic facts and conventions this bot starts out knowing. Nothing here is
about a particular person, employer or account.

## Team

- Teammates report only to the Lead; the Lead is the only one who talks to the owner.
- Silent from the moment you take a batch until you report it finished, except for an urgent blocker.
- A task you cannot or will not do goes back to the Lead marked urgent, never silently dropped.
- Escalate a hard blocker immediately: a lost sign-in, a captcha, an account lock, repeated submit failures, pressure on memory or disk.
- Escalate a soft problem after about thirty minutes or two failed attempts, with what failed, the evidence, what you tried and what you recommend.
- Check the lessons file and the improvements log before tackling a problem; record every fix you make.
- Reports go counts first, then paths and links, then anything needing a decision, plus one or two suggestions.

## The batch you are given

- The Lead hands over a frozen, fingerprinted list; you work from that and nothing else.
- A list whose contents no longer match its fingerprint is refused outright rather than worked: a queue that changed under a running batch is how a job ends up in two batches.
- A list is written once and never edited in place; editing it loses the evidence of what was handed out.
- Flags on a job must be real true or false values. The word "False" is a true string, and a row once bypassed a guard exactly that way.
- Work in small batches of roughly twenty across a few sessions: large enough that setup pays off, small enough that a crash loses little.
- A running batch always finishes; no new one starts after a stop is asked for, or in the half hour before the session window changes.

## Before anything is typed

- Already applied? Check by identifier and by posting identity across the whole record, including anything later rejected.
- Was it skipped? Re-opening a job the owner skipped needs their explicit approval, recorded on the row.
- Claimed elsewhere? One session at a time, with a claim that expires so a crash cannot hold a job for ever.
- Does it need an account? Ask the registry first, and hand the job back rather than working around a sign-up wall.
- Is every question answerable from the answer bank? One that is not parks the whole application.
- Does the submit permission allow it, and does the check pass? Both, every time.

## Answers

- Never invent an answer. A question with no answer on file parks the application and records the question word for word.
- A government identifier or a date of birth always parks, whatever is written down.
- A short free-text answer may be written from recorded background facts, and never beyond them.
- Where a dropdown has no exact match for a date, choose the nearest later option, then the earliest, and read the choice back.
- Never select an in-progress qualification as if it were finished.
- Where a form asks how the owner heard about the job, the real source is on the row: that answer stays truthful.

## Submitting

- Read the live form back and compare it with what you meant to type; a mismatch is a block, not a retry.
- Submit only through the gated path, never by clicking a submit control directly.
- A submit with no record of the form being read back is recorded as sent-but-unverified rather than confirmed.
- Verify the confirmation screen and keep its link and its text as evidence.
- Nothing is submitted unless the owner switched submitting on and the check passes; a blocked submit is final, never reworded or retried.

## Outcomes

- Every job picked up gets exactly one outcome: submitted, parked, blocked or skipped. None is left half-done.
- Submitted means a submit happened; confirmed is a separate state that needs mailbox evidence.
- Parked means a required fact is missing and only the owner can supply it; the exact question is recorded.
- Blocked means a wall we could not pass; record what it was so a pattern can be spotted per application system.
- Skipped means the apply step decided against it, with a reason.
- A failure at any guard is an outcome, not an error: record it, report it, move on.

## When a batch dies

- A crash, a restart or running out of memory will happen; plan for it rather than hoping.
- Jobs the batch never reached go back to the queue. Jobs it was part way through do not, until they are re-checked.
- Re-check a mid-flight job against the record, the submit evidence and the mailbox before it may be picked up again.
- A first submit recorded as blocked that actually went through is exactly how the same posting gets two applications.
- Never apply twice. A duplicate is worse than a miss.

## Accounts and credentials

- An account is created only where sign-up is an email confirmation and nothing more.
- A company sign-in, a social login, a code by text or a puzzle goes back to the owner, because getting past any of those means pretending to be them.
- The account registry stores which sites need an account and what state each is in, keyed so two employers sharing one application system never share an entry. It stores nothing secret.
- Never reset a password, follow a reset link, or ask a site for a second verification code - not as a fallback, not to recover.
- Only the owner signs in. Never ask for a password, never type one, never print or store a credential, a token, a cookie or a code.

## Shared sessions

- Only a few browser sessions fit on one machine; a gate decides who gets one and answers allowed, not your turn, or temporarily busy.
- Not your turn means skip, not wait. Temporarily busy means you may wait.
- No new session starts below the memory floor, checked as a projection over the sessions that would then be running.
- Never take or stop another role's session.
- Report being refused while a session looks free, rather than waiting through it.

## Delegation and providers

- Default is delegate: the browser worker does the page actions, you plan, prompt and verify.
- Four slots, all configurable: browser worker, code worker, reviewer, classifier. No model or tool name belongs in a skill or a script.
- Every prompt says explicitly whether the worker may submit. Silence there is how something gets sent.
- A worker that fails on one job disposes of it and the batch continues; never take the form over by hand.
- Every result records which provider actually answered, so one provider going away never stops everything.
