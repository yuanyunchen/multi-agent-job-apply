---
name: verification-codes
description: >-
  Use when an application form has emailed a short verification code. Four
  matching rules that must all hold, an export that has to say what it
  searched, a code that cannot be printed, one application system at a time,
  and never a password reset or a second code.
---

# Verification codes

Some application forms email a short code part way through. Reading it is the
most delicate thing the team does, so every rule here is strict and none has
an exception.

## When this applies at all

Only when **both** are true:

1. a bot has asked for a code **for a specific application**, naming the
   application system and the moment it submitted; and
2. the owner has switched code reading on **for that application system**.

Code reading is off for every system until the owner names one. That is how a
risky path gets rolled out one system at a time instead of everywhere at once.

## The four matching rules

All four must hold. Any one failing means no code.

1. **the sender** belongs to the mail domains of the application system that
   asked - not a lookalike, not a forwarder;
2. **the recipient** is the address used on that application;
3. **the time** is inside the short window after the submit - a few minutes,
   not "today";
4. **the newest match wins**, if there is more than one.

## The export has to vouch for itself

Before any matching, check the mailbox export's own header. It must declare:

- **which mailbox** it searched - and it has to be the address on the
  application;
- **what it searched for**;
- **the window it covers** - which must cover the window you are asking about;
- **that it finished**.

Without that header, **refuse to read it**. This is the guard that makes
"read-only export" mean something: an empty result from an export that never
ran looks exactly like "no code arrived", and treating the second as the first
is how an application gets abandoned for no reason.

A half-written export fails closed. So does an export of a different mailbox.

## The code cannot be printed

A code is held in a form that **refuses to be rendered**: turned into text, put
in a message, or formatted into a log line, it produces a redaction marker and
not the value.

- It goes **only to the bot that asked**, matched to its application.
- It is **never** written to a note, a report, a summary, an error message, a
  log, or the record.
- It is never repeated back to the owner, and never kept after the application
  it belongs to is finished.

## Fail closed

No match inside the window means **no code**. Then:

- the application **waits for the owner**;
- you do **not** widen the window;
- you do **not** retry in a loop;
- you do **not** ask the site for another code.

"Nothing arrived in those five minutes" is a complete and correct answer.

## Never, under any circumstances

- **Never read, use or follow password-reset mail.** Not a reset link, not a
  "forgot password" page, not a "set a new password" message. Not as a
  fallback, not to recover, not because it would work.
- **Never ask a site for a second code.** No resend, ever.
- **Never treat a verification or identity email as proof an application
  arrived.** Those are different things, and conflating them makes the
  confirmation numbers lie.
- **Never sign anything in or out.**

## Reporting

Report that a code was found and handed over, or that none was. Never the code,
never the message, never the link. If a system starts asking for codes and it
is not switched on, say so to the Lead as a **proposal** - it is the owner's
decision, and it is usually the right one.
