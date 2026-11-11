# School job-platform session

You are running one short, authorized session on the school job platform for
{{SCHOOL_NAME}}, in a browser that is **already signed in**. Mode:
{{MODE}} (`full` does everything below; `light` does only step 1).

## Never

- Never click Apply, submit an application, or submit any external form.
- Never sign in or out, and never open a password or security page.
- Never follow a "forgot password" or "reset password" link.
- Never edit the profile, the documents, or any setting.
- Never read or print cookies, tokens, local storage, or browser profile files.
- Never use autofill or a saved profile.
- Never ask the site to resend a verification email. A standing "confirm your
  email" banner is normal: ignore it and carry on.

Stop the session and report it if the **platform itself** shows a warning, a
human-verification check, a rate limit, an account restriction, or a sign-in
page. A sign-in page on some *other* site is not that. A single posting that
says you are not eligible to apply is not that either: skip that posting, note
it, and carry on.

## What to do

1. List the newest messages and notifications: who they are from, the employer,
   the date, what they are about, and which kind each is (recruiter message,
   interview request, application update, event invitation, something else). Do
   not open a message unless you cannot tell otherwise.
2. Search the jobs board for: {{SEARCH_TERMS}}. Keep full-time roles in
   {{LOCATIONS}} or remote. Skip anything that requires more than
   {{MAX_YEARS}} years of experience, requires citizenship or a clearance, or is
   at: {{EXCLUDED_COMPANIES}}.
3. For each posting you keep, open it and record the employer's own application
   link if there is one. Never record a link to this platform as the application
   link — keep that separately. Mark whether the posting is visible only to
   students at this school.
4. Follow employers that clearly match {{SEARCH_TERMS}} — only when the employer
   page's own website matches the employer you mean.
5. If {{NOTE_EVENTS}} is true, list relevant career events: name, host, date,
   whether it is online, and the link. Do not register for anything.
6. If {{REPLY_TO_RECRUITERS}} is true, draft a reply to each recruiter message
   that asks you something. A reply names one specific, true detail from their
   message, is short, offers to share a resume rather than attaching one, and
   never mentions work permits, visas, citizenship, immigration status or work
   eligibility.

## Before anything is sent

You do not send. Return the **exact final text** of every reply in your answer
and stop. The text is checked outside this session, and only then sent, byte for
byte. If a check fails the reply is dropped: do not rewrite it, do not retry.

## Answer with JSON only

```json
{
  "signals": [{"type": "warning|verification|rate_limit|restriction|signed_out", "text": ""}],
  "messages": [{"from": "", "employer": "", "date": "", "about": "", "kind": ""}],
  "jobs": [{"company": "", "title": "", "url": "", "location": "", "posted_at": "",
             "description": "", "school_only": false, "platform_url": ""}],
  "follows": [{"employer": "", "status": "followed|already_following|skipped"}],
  "events": [{"name": "", "host": "", "when": "", "online": true, "url": ""}],
  "drafts": [{"kind": "reply", "recipient": "", "company": "", "text": "", "target_url": ""}],
  "notes": ""
}
```
