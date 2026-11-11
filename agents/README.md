# agents/ — the role prompts

One file per role. Each is a prompt you can paste into an agent session, or that
an orchestrating agent can load when it plays that role. They describe
behaviour, not implementation: the code enforces the guards, and these files
tell the agent what the guards are and how to behave around them.

## Every role

### Always on

| file | role | talks to |
|---|---|---|
| [bootstrap.md](bootstrap.md) | sets the system up with the user, first contact | the user |
| [lead.md](lead.md) | coordinates everything, and is the **only** role that talks to the user | the user, all roles |
| [search.md](search.md) | finds openings and hands them on — **two lanes**, wide and deep | the lead |
| [apply.md](apply.md) | fills in application forms | the lead |
| [mail.md](mail.md) | reads the application mailbox, read-only | the lead |

Search is one role with two lanes rather than two roles, on purpose: two roles
means two copies of the title and eligibility rules, and those copies drift.
[search.md](search.md) describes both lanes.

### Optional helpers

Each helper's browser prompt ships **with the helper**, so a helper and its
prompt cannot drift apart. All three are off until the user switches them on,
and none of them can send anything by itself.

| role | prompt | what it does | talks to |
|---|---|---|---|
| **LinkedIn** | [`../src/jobpilot/plugins/linkedin/agent.md`](../src/jobpilot/plugins/linkedin/agent.md) | makes the user more visible: connection notes and comments, under a weekly cap. No direct messages, no inbox reading. | the lead |
| **School platform** | [`../src/jobpilot/plugins/handshake/agent.md`](../src/jobpilot/plugins/handshake/agent.md) | postings only the user's school can see, career events, and replies to recruiters if that is switched on | the lead |
| **Startup list** | [`../src/jobpilot/plugins/yc/agent.md`](../src/jobpilot/plugins/yc/agent.md) | startup openings and in-platform applications with a short note, under a weekly cap | the lead |

### Not an agent

The hourly health check (`jobpilot/watch.py`) is plain code, not a role: it
reads, notices and writes an alert the lead picks up. It costs no model calls
and changes nothing.

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
