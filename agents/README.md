# agents/ — the role prompts

One file per role. Each is a prompt you can paste into an agent session, or that
an orchestrating agent can load when it plays that role. They describe
behaviour, not implementation: the code enforces the guards, and these files
tell the agent what the guards are and how to behave around them.

| file | role | talks to |
|---|---|---|
| [bootstrap.md](bootstrap.md) | sets the system up with the user, first contact | the user |
| [lead.md](lead.md) | coordinates everything, and is the **only** role that talks to the user | the user, all roles |
| [search.md](search.md) | finds openings and hands them on | the lead |
| [apply.md](apply.md) | fills in application forms | the lead |
| [mail.md](mail.md) | reads the application mailbox, read-only | the lead |

Browser prompts for the optional helpers ship with the helpers themselves, so a
helper and its prompt can never drift apart:

- `src/jobpilot/plugins/linkedin/agent.md`
- `src/jobpilot/plugins/handshake/agent.md`
- `src/jobpilot/plugins/yc/agent.md`

## Rules every role shares

1. **Evidence or nothing.** A job may be skipped only with a sentence quoted
   word for word from the posting. The code re-checks the quote; an invented one
   is thrown away and the job is kept.
2. **Never invent an answer** to a form question. No answer on file means the
   application stops and the user is asked.
3. **Never twice.** A job that was submitted is never submitted again.
4. **Nothing leaves the machine** unless the matching permission is on and the
   outbound check passes. A blocked message is dropped, never reworded.
5. **No password resets, ever.** No reset links, no new codes, no sign-outs.
6. **Only the user signs in.** Never ask for a password; never type one.
7. **One writer.** Only the application record's own code writes to it.
8. **Plain words to the user.** No file names, settings keys, model names, ids
   or error codes unless they asked for the technical view.
9. **Only the lead talks to the user.** Everyone else reports to the lead.
10. **Say what you did not do.** A skipped step, a missing login or a paused
    helper is reported, never silently dropped.
