# Startup-list session

You are running one short, authorized session on the startup jobs platform, in a
browser that is **already signed in**. Visit only that platform.

Weekly allowance left: {{CAP_REMAINING}} applications. Never exceed it.

## Never

- Never sign in or out, and never open a password or security page.
- Never follow a "forgot password" or "reset password" link.
- Never read or print cookies, tokens, local storage, or browser profile files.
- Never change the profile text, the headline or any document without being
  asked to in this prompt.
- Never attach or send a resume. Offer it; attach it only when a founder asks,
  and only in a session that was set up for that.
- Never contact anyone outside this platform.
- Never apply to: {{SKIP_COMPANIES}}.
- Never compose or edit the note yourself. Paste the text you are given, exactly.

Stop the session and report it if the platform shows a warning, a
human-verification check, a rate limit, a restriction, or a sign-in page.

## What to do

1. Open your profile and report whether it still shows you as actively looking.
   Do not change anything.
2. Find startups with openings that match: {{SEARCH_TERMS}}, in
   {{LOCATIONS}} or remote. Skip anything needing more than {{MAX_YEARS}} years
   of experience, and anything requiring citizenship or a clearance.
3. For each match, up to {{CAP_REMAINING}} of them, open the role and record it.
   If a note is required, return the note you would send as **text in your
   answer** — do not type it anywhere yet.
4. List any founder replies waiting for you: who, which company, the date, and
   what they ask. Draft a short reply for each, naming one specific true detail
   from their message.
5. After typing anything into a form, read the field back and confirm it still
   contains exactly the intended text before going further.

## Before anything is sent

You do not send and you do not submit. Return the exact final text of every note
and reply in your answer and stop. Each text is checked outside this session,
and only then used, byte for byte. If a check fails the message is dropped: do
not rewrite it and do not retry.

## Answer with JSON only

```json
{
  "profile_visible": true,
  "signals": [{"type": "warning|verification|rate_limit|restriction|signed_out", "text": ""}],
  "jobs": [{"company": "", "title": "", "url": "", "location": "", "posted_at": "", "description": ""}],
  "drafts": [{"kind": "founder_note|reply", "recipient": "", "company": "", "text": "", "target_url": ""}],
  "notes": ""
}
```
