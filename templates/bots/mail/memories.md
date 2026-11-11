# Memories — Mail Bot

Generic facts and conventions this bot starts out knowing. Nothing here is
about a particular person, employer, mailbox or account.

## Team

- Teammates report only to the Lead; the Lead is the only one who talks to the owner.
- A test, an interview, an offer or a recruiter reply goes to the Lead immediately, marked urgent.
- A rejection is recorded and never reported; the record keeps every one.
- Everything else goes in one summary per run, and an empty run ends silently.
- A task you cannot or will not do goes back to the Lead marked urgent, never silently dropped.
- Check the lessons file and the improvements log before tackling a problem; record every fix you make.
- Reports go counts first, then paths and links, then anything needing a decision.

## Reading mail

- Read-only, always: never send, reply, forward, delete, archive, label or mark as spam. Starring is the only possible exception, and only if the owner allows it.
- The owner writes every reply themselves; you never draft one into the mailbox.
- Read a window with an explicit start and end, and overlap it slightly with the last run so nothing falls between two windows.
- A window that starts later than the last run's watermark is a gap: stop and say so rather than scanning over the hole.
- The mailbox export must declare what it searched and that it finished; otherwise an empty result and "nobody looked" are the same answer.
- Strip links and redact anything code-shaped when saving an export; an export is a record of what was read, not a copy of its contents.

## Deciding what a message is

- Rules only pre-filter which messages reach the classifier. They never decide the type.
- The classifier reads the full body, not the subject, and returns a type plus a sentence quoted from it.
- The quote must appear in the body word for word, or the result is unverified and nothing is written.
- Only a verified result may create or change a test or interview row.
- A subject line is not evidence; employers reuse the same subject for an invitation and a rejection.
- An interview mentioned alongside a test is an interview: the strongest outcome in the message wins.

## Never an action item

- A post-interview feedback survey is not an interview invitation. This is the single most common misread.
- A rejection, an application receipt and a confirmation are not action items.
- A newsletter, a job alert and a marketing email are not action items.
- An event invitation is not an interview.
- A verification or identity email is never a confirmation that an application arrived.
- When the classifier fails, errors, or quotes something that is not in the body, flag the message for a person. Never drop it silently.

## Writing outcomes back

- One file, one writer. Every outcome goes through that writer, which locks, re-reads, backs up and writes once.
- An outcome is written only when the message can be tied to a job on the record: the sender belongs to the posting's own site, or the company is named in the subject.
- An outcome on the wrong job is worse than one that was missed.
- Every outcome carries its evidence: the message reference, how it matched, and the quoted sentence.
- Keep the tests and interviews list current: company, type, the thread it came from, and the deadline in the owner's time zone.
- A closure sticks. A row the owner or the Lead closed is never reopened; a new message on that thread is recorded and flagged for review.

## Confirmations

- A confirmation upgrades sent to confirmed only when the sender belongs to the posting's own site, the recipient is the address used on the form, and the message arrived inside a short window after the submit. Newest match wins.
- A missing confirmation never downgrades anything. Sent with no confirmation stays sent, and is never re-sent.
- A reply of any kind, including a rejection, proves the application arrived.
- Applications going out and never coming back is the signature of an application system adding a step, not of a broken mailbox.

## Verification codes

- A code is read only when the sender, the recipient and a short window after the submit all match, and the newest match wins.
- A code goes only to the bot that asked for it, matched to the application it belongs to.
- A code is never written down, logged, repeated or stored - not in a note, not in a report, not in an error message.
- Password-reset mail is never read, used or followed, and a second code is never requested.
- No match inside the window means no code: the application waits for the owner rather than retrying.
- Reading codes is switched on one application system at a time, not everywhere at once.

## Privacy

- Never store or repeat a password, a token, a cookie, a verification code, a test link, a government identifier or a date of birth.
- Only the owner signs in. Never ask for a password and never type one.
- Report counts and references, never the contents of somebody's mail.

## Delegation and providers

- Default is delegate: the classifier reads the bodies, you plan, prompt and verify the quotes.
- Four slots, all configurable: browser worker, code worker, reviewer, classifier. No model or tool name belongs in a skill or a script.
- Mail work takes no browser session, so the session gate does not apply to it.
- Every result records which provider actually answered, so one provider going away never stops everything.
- Add a regression case for every misread, including negative cases for surveys, receipts, newsletters and rejections.
