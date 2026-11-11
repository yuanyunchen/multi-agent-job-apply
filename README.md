# jobpilot

**A small team of assistants that applies to jobs for you.** It looks for
openings you would actually want, reads each job description properly, fills in
the applications, checks which ones really arrived, and sends you one short
summary a day.

You do not need to be technical to use it, and you do not need to edit any
files. You answer about twenty short questions once, in plain language — what
you are looking for, where your CV is, and what to put in the boxes forms
always ask about.

```
             ┌─────────────────────────────────────────────────────────┐
  job pages  │  finds openings  →  reads each description  →  applies  │ →  one email a day
  you name   │                      (and quotes its reasons)          │     with anything
             └─────────────────────────────────────────────────────────┘     that needs you
                        nothing is sent until you say it may
```

## Quick start

**Give your AI agent this repository and one sentence.** Any agent with a
terminal (Claude Code, Codex, Cursor, a bot, …) can set everything up for you —
paste exactly this:

```
Read AGENTS.md in https://github.com/yuanyunchen/multi-agent-job-apply and set up my job-application team.
```

It will clone the project, set up the workspace, build the team, walk you
through your preferences and your sign-ins, and explain everything in plain
language. **Nothing is submitted or sent until you switch it on.** (If you are in
a chat assistant without its own shell, paste [`START_HERE.md`](START_HERE.md)
instead.)

**Rather do it yourself in a terminal?**

```bash
git clone https://github.com/yuanyunchen/multi-agent-job-apply
cd multi-agent-job-apply
python3 -m venv .venv && . .venv/bin/activate   # Python 3.10 or newer
pip install -e .
jobpilot setup            # answer the questions
jobpilot logins           # sign in to anything you switched on, in your browser
```

## 5-minute start

`jobpilot start` rolls the introduction, the questions and the sign-ins into one
conversation:

```bash
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

To let it run by itself, add one line to your scheduler. Ask for the line
instead of copying one, because it has to name the folder *you* downloaded
into:

```bash
jobpilot routines list --technical    # prints the line, ready to paste
crontab -e                            # paste it at the end
```

The line looks like this, with your own folder in place of the one shown:

```cron
*/10 * * * * cd ~/your-folder && jobpilot routines run-due >> ~/.jobpilot/logs/cron.log 2>&1
```

`jobpilot routines run-due` works out what is due, does it, and remembers that
it did, so calling it every ten minutes is safe: nothing happens twice. The
timetable itself is in `routines/routines.yaml`, written in the same plain words it
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
to the setup questions, and the answers it puts in form boxes, live in two
files next to each other (`config/preferences.yaml` and `config/answers.yaml`),
neither of which is part of this project. Your CV is not copied anywhere — it
only remembers where you keep it. Nothing is uploaded anywhere except the job
applications themselves, and whatever your chosen model sees in order to read a
job description.

**What about privacy?** Verification codes are never written down. Passwords,
tokens and cookies are never read. Anything that looks like a key is scrubbed
out of what a model returns before it is stored.

**Can I see what it decided and why?** Yes — every skip keeps the sentence that
caused it, and `jobpilot status --technical` shows the numbers behind everything.

## Documentation

**If you just want to use it**

- [`AGENTS.md`](AGENTS.md) — the entry point for an agent given only the repo
  link: how it installs, builds the team and runs setup itself.
- [`START_HERE.md`](START_HERE.md) — the prompt to paste into an assistant.
- [`docs/sample-session.md`](docs/sample-session.md) — a complete practice run,
  start to finish, recorded from an actual run.
- [`examples/`](examples/) — eight short scripts you can run right now. They
  work offline, on made-up jobs, and send nothing.
- [`docs/ROUTINES.md`](docs/ROUTINES.md) — everything that happens by itself.

**If you want to know how it works**

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — how it works, and why.
- [`docs/APPLY-METHOD.md`](docs/APPLY-METHOD.md) — how one application gets from
  "found" to "confirmed", and every place it is allowed to stop.
- [`docs/CAPABILITY-MATRIX.md`](docs/CAPABILITY-MATRIX.md) — what it does, what
  it does not, and why not.
- [`docs/MIGRATION.md`](docs/MIGRATION.md) — moving in, moving your things, and
  the portability checks.
- [`agents/`](agents/) — the prompt for each role.
- [`templates/`](templates/) — the same seven roles as bot templates you can
  import somewhere else, one folder each.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — development, tests, writing a plugin.
- [`CHANGELOG.md`](CHANGELOG.md) — what changed, and what to do about it.

## Licence

MIT — see [LICENSE](LICENSE).
