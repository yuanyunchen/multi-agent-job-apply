# jobpilot

**A small team of assistants that applies to jobs for you.** It looks for
openings you would actually want, reads each job description properly, fills in
the applications, checks which ones really arrived, and sends you one short
summary a day.

You do not need to be technical to use it, and you do not need to edit any
files. You answer about fifteen questions once, in plain language.

```
             ┌─────────────────────────────────────────────────────────┐
  job pages  │  finds openings  →  reads each description  →  applies  │ →  one email a day
  you name   │                      (and quotes its reasons)          │     with anything
             └─────────────────────────────────────────────────────────┘     that needs you
                        nothing is sent until you say it may
```

## 5-minute start

**If you use a coding assistant** (Claude Code, Codex, Cursor, …) — the easiest
way: open [`START_HERE.md`](START_HERE.md), copy the block of text it shows you,
and paste it into your assistant. It will install, set up and explain everything,
and talk to you in plain language.

**If you are happy in a terminal:**

```bash
pip install -e .          # Python 3.11 or newer
jobpilot start            # meet the team, then answer the questions
```

That writes your answers down, walks you through any sign-ins, and leaves
everything ready. Then, whenever you like:

```bash
jobpilot status                   # how is it going? what needs you?
jobpilot digest                   # today's summary
jobpilot run apply --dry-run      # a practice run: nothing is sent
jobpilot ask "stop applying outside New York"   # change anything, in your words
```

To let it run by itself, add one line to your scheduler — `crontab -e`, then:

```cron
*/10 * * * * cd ~/jobpilot && jobpilot routines run-due >> ~/.jobpilot/logs/cron.log 2>&1
```

`jobpilot routines run-due` works out what is due, does it, and remembers that
it did, so calling it every ten minutes is safe: nothing happens twice. The
timetable itself is in `config/routines.yaml`, written in the same plain words it
reads back to you, and `jobpilot routines list` shows it.

## What you can switch on

Everything that needs an account is **off** until you say otherwise. The first
three are helpers; the rest are the engines that do the thinking.

| switch | what it adds | sign-in needed | default |
|---|---|---|---|
| `linkedin` | more jobs to apply to, and messages on your behalf — only with your permission | LinkedIn | off |
| `handshake` | school-only postings, and replies to recruiters — only with your permission | your school's job platform | off |
| `yc` | startup openings, and a short note with each application | a startup jobs platform account | off |
| `claude` | the engine that reads job descriptions, reviews its own work and can work in a browser | your Claude account, in the Claude Code tool | on |
| `codex` | a second engine, so one being unavailable does not stop everything | your account in the Codex tool | off |
| `openai_compatible` | the option of using a model of your own instead of the ones above | a key from that service, kept outside your settings | off |
| `fake` | a practice mode that works end to end without a real model | none | off |

Three jobs are shared out between whichever engines are on: reading job
descriptions, reviewing and planning, and working inside a web page (which only
the helpers above need). `jobpilot status --technical` shows who is doing what.

The job pages you name are read directly and need no account at all.

## What it will never do

- **Never apply to the same job twice.** Every application is recorded, and the
  record is checked before anything is sent.
- **Never make up an answer** on a form. If a question has no answer on file,
  that application stops and you are asked. Social security numbers, dates of
  birth and similar always stop.
- **Never send, post or submit anything** unless you switched that permission
  on *and* the action passes a separate check. All of those start off.
- **Never reset a password**, follow a password-reset link, or ask a site for
  another verification code.
- **Never ask you for a password**, and never sign in as you. You sign in, in
  your own browser; it only ever checks that it worked.
- **Never change one of your settings on its own.** It proposes, shows the
  difference in plain words, and waits for a yes.
- **Never skip a job without evidence.** A skip always quotes the sentence from
  the posting that caused it, and the quote is checked against the posting — an
  invented one is thrown away and the job is kept.

## Questions people ask

**What does it cost?** The software is free. The thinking is done by a model you
provide, so you pay whatever that model costs you. Most of the reading is done
by the cheapest model available, and you can see which model does which job.

**Which AI models can it use?** Claude through the Claude Code tool (Haiku,
Sonnet or Opus), Codex through its tool, or any other service you host or pay
for. You can run several, and if one is unavailable the rest carry on.

**Is this allowed by the job sites?** That is between you and each site. Some
sites' terms restrict automated access, and **you are responsible for following
the terms of any site you point this at.** It reads public job pages directly
and uses your own browser session for anything else; it never creates accounts
where a site forbids it, never sends messages without your permission, and stops
as soon as a site shows a warning or asks it to prove it is a person.

**How do I stop it?** Remove the line from your scheduler, or just stop running
it. Nothing runs in the background on its own. To pause the messaging helpers
immediately, switch their permission off.

**Where does my data live?** On your computer, in a folder you choose
(`~/.jobpilot` by default): the record of your applications, backups of it, a
log of what happened, and the suggestions waiting for your answer. Your answers
to the setup questions live in `config/preferences.yaml`, which is not committed
to this repository. Nothing is uploaded anywhere except the job applications
themselves, and whatever your chosen model sees in order to read a job
description.

**What about privacy?** Verification codes are never written down. Passwords,
tokens and cookies are never read. Anything that looks like a key is scrubbed
out of what a model returns before it is stored.

**Can I see what it decided and why?** Yes — every skip keeps the sentence that
caused it, and `jobpilot status --technical` shows the numbers behind everything.

## Documentation

- [`START_HERE.md`](START_HERE.md) — the prompt to paste into an assistant.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — how it works, and why.
- [`docs/sample-session.md`](docs/sample-session.md) — a complete practice run,
  start to finish, recorded from an actual run.
- [`agents/`](agents/) — the prompt for each role.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — development, tests, writing a plugin.

## Licence

MIT — see [LICENSE](LICENSE).
