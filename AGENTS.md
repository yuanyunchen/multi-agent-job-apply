# AGENTS.md — set up jobpilot from scratch

**You are a coding/assistant agent (Claude Code, Codex, Cursor, a bot, …) and
someone handed you only this link:**
`https://github.com/yuanyunchen/multi-agent-job-apply`. This file is your entry
point. Follow it top to bottom. It tells you how to install everything yourself,
build the agent team, walk the user through setup in plain language, and hand
over — **without ever sending or submitting anything until the user switches
that on.**

The person reading your messages is **not a programmer**. Talk to them the way
[`START_HERE.md`](START_HERE.md) and [`agents/bootstrap.md`](agents/bootstrap.md)
describe: plain words, one question at a time, a sensible default every time.

## Outline

1. [Install and check](#1-install-and-check) — clone, venv, `pip install -e .`, `jobpilot doctor`
2. [Build the agent team](#2-build-the-agent-team) — Lead, Search, Apply, Mail + schedule
3. [Guided preferences](#3-guided-preferences) — `jobpilot start --explain-only`, then `jobpilot setup`
4. [Sign-ins](#4-sign-ins) — `jobpilot logins` (the user signs in, you only check)
5. [Practice run and hand over](#5-practice-run-and-hand-over) — dry runs, explain, start
6. [Standing rules](#standing-rules) — never cross these
7. [How you talk](#how-you-talk) — simple vs technical mode
8. [If a step fails](#if-a-step-fails)
9. [For contributors](#for-contributors)

Use **only** the commands shown here; they all exist in `src/jobpilot/cli.py`. Every
command prints plain language by default and sends nothing unless the settings
allow it. Never invent a flag.

---

## 1. Install and check

Run these in order. Python **3.10 or newer** is required.

```bash
git clone https://github.com/yuanyunchen/multi-agent-job-apply
cd multi-agent-job-apply
python3 -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e .                # PyYAML + the standard library, nothing heavy
```

**Where the settings live.** The user owns exactly one file. By default it is
`config/preferences.yaml` inside the checkout, which is gitignored (it never
gets committed). To keep it elsewhere, set `JOBPILOT_CONFIG` to the path you
want *before* running any command:

```bash
export JOBPILOT_CONFIG=~/jobpilot-preferences.yaml
```

One resolver (`config.settings_path`) handles this for every command that reads
*or writes* settings — an explicit `--config` → `JOBPILOT_CONFIG` → the
checkout's `config/preferences.yaml` — so setup and every other command always
agree on the file.

Then confirm the ground is solid:

```bash
jobpilot doctor
```

`doctor` touches no account. It reports settings, the data folder, the
application record, the answer bank, each model, room to work, helpers and
permissions — each as a plain sentence. On a fresh install it will say there is
no settings file yet: that is expected, so go on to steps 2–3 (setup writes the
file) and run `doctor` again afterwards. For any other problem, relay it in one
sentence and do not continue until it is fixed or the user chooses to continue
anyway.

## 2. Build the agent team

jobpilot is four roles plus optional helpers. Load each role prompt and have
your host play it; the shared rules live in [`agents/README.md`](agents/README.md).

| role | prompt | talks to |
|---|---|---|
| **Lead** | [`agents/lead.md`](agents/lead.md) | the user — **the only role that does** |
| **Search** | [`agents/search.md`](agents/search.md) | the Lead |
| **Apply** | [`agents/apply.md`](agents/apply.md) | the Lead |
| **Mail** | [`agents/mail.md`](agents/mail.md) | the Lead (read-only) |

**Map the roles onto whatever your host offers:**

- If your host has **subagents**, create one per role and give it that file as
  its system prompt. Only Lead is user-facing; the rest report to Lead.
- If it has **separate sessions**, open one per role and route everything to the
  user through the Lead session.
- If it is **one agent**, play the roles in turn, but keep the boundary: speak
  to the user only as the Lead, and keep Search/Apply/Mail reasoning internal.

**The schedule** is declarative in [`routines/routines.yaml`](routines/routines.yaml)
(find jobs, read them, apply on weekdays, a daily email, check receipts, reflect,
weekly suggestions). You do not hand-build it:

```bash
jobpilot routines list            # the timetable, in the user's words
jobpilot routines run-due         # run whatever is due; safe to call repeatedly
```

`run-due` records when each routine last ran, so calling it again does nothing —
which is why it is safe from cron. The single cron line is shown by
`jobpilot routines list --technical` (`*/10 * * * *` calling `routines run-due`).

**Optional plugins** (`linkedin`, `handshake`, `yc`) add more sources and
outreach; each ships its own browser prompt at `src/jobpilot/plugins/<name>/agent.md`.
**Optional model providers** are `claude`, `codex`, `openai_compatible`, `fake`.
All plugins and all providers except `claude` are **off** until the user turns
them on during setup. Do not enable any of them on your own.

## 3. Guided preferences

First, show the user what they are getting — generated from what is actually
installed, so it cannot drift from reality:

```bash
jobpilot start --explain-only     # prints the team, the timetable, the promises
```

Introduce the team in about 200 words using *that* output, then run the setup
conversation:

```bash
jobpilot setup                    # add --force to go through the questions again
```

It covers: the jobs they want most and would still take; locations and whether
remote is fine; visa sponsorship; years of experience; companies to avoid;
companies to hold for their decision; how far back to look; which companies' job
pages to watch; which helpers and models to switch on; where and when the daily
summary arrives; and how much detail they want to see.

**Do not re-explain how to relay this here — follow
[`agents/bootstrap.md`](agents/bootstrap.md) steps 2–5** (also in
[`START_HERE.md`](START_HERE.md)): one question at a time, a default each time,
one concrete consequence after each answer ("a 'Senior ML Engineer' posting gets
skipped, but 'Machine Learning Engineer II' is still considered"), and a
plain-prose summary to confirm before anything is saved. Any previous settings
are kept alongside.

## 4. Sign-ins

```bash
jobpilot logins
```

Walk the sign-ins one platform at a time: what it is, why it is needed, exactly
what the user should do, and what will never be done with that account. **The
user signs in, in their own browser. You only check that it worked.** Wait for
them to say "done" before checking. If they skip one, say plainly which features
stay off.

> ⚠️ `jobpilot logins --non-interactive` only checks *settings*, not real login
> state. **Never report a platform as signed in based on the non-interactive
> run** — it cannot see the browser.

## 5. Practice run and hand over

Run a full dry run. Nothing is sent or submitted by any of these:

```bash
jobpilot run search --dry-run
jobpilot run screen --dry-run
jobpilot run apply --dry-run
jobpilot digest
```

Report in plain language: how many jobs matched, two examples it would apply to,
and one it would skip — **with the exact sentence from the posting that caused
the skip**. Ask whether those decisions look right. If not, adjust in the user's
own words and run again:

```bash
jobpilot ask "stop applying outside New York"
jobpilot status
```

`ask` only proposes a change; nothing happens until the user runs
`jobpilot approve <id>` (or `jobpilot decline <id>`). Then hand over: explain the
system in plain language, tell them they get one summary a day, can ask "how is
it going?" any time, and that to let it run by itself they add the one cron line
from `jobpilot routines list --technical`. **Nothing is ever sent or submitted
until they switch the matching permission on.**

---

## Standing rules

These are not optional and the code enforces most of them. **Never work around a
guard, and never reach for a `--force`-style shortcut to get past one** — if a
guard stops you, ask the user.

- **Nothing leaves the machine until the user switches it on.** The permissions
  `permissions.submit_applications`, `permissions.send_outreach_messages` and
  `permissions.send_digest_email` all start **false**, and a switched-on
  permission still has to pass a separate outbound check.
- **Never reset a password**, never follow a "forgot password" / reset link,
  never ask a site for another verification code, never sign anything out.
- **Never ask for, type, or print a password, token, cookie or verification
  code** — not even partly, not even in a debug line. No secrets in chat. The
  user signs in themselves; you never sign in as them.
- **Never invent an answer** to a form question. No answer on file means the
  application stops and the user is asked. Personal identifiers (SSN, date of
  birth, licence/passport numbers) always stop.
- **Never apply to the same job twice.** The application record is the authority
  and is checked before anything is sent.
- **Never change a setting without a yes.** Propose it, show what it would
  change in plain words, and wait. The sending/submitting permissions are never
  inferred from a turn of phrase — switching them on is always deliberate.

The full per-role version is in [`agents/README.md`](agents/README.md) and each
of `agents/lead.md`, `agents/search.md`, `agents/apply.md`, `agents/mail.md`.

## How you talk

Two modes, set by `ui.mode` and overridable per command with `--technical`:

- **simple** (`ui.mode: simple`, the default) — progress and outcomes only.
  "Applied to 12 jobs today, 3 need your answer." No file names, settings keys,
  model names, identifiers or error codes.
- **technical** (`--technical`, or `ui.mode: technical`) — the same actions plus
  the detail behind them. The detail never changes what you actually do.

Default to simple. Only switch to technical if the user asks for the detail.

## If a step fails

Relay the plain-language cause and ask the user. Never bypass a guard.

| step | what to do |
|---|---|
| `jobpilot doctor` says there is no settings file | expected before setup — run `jobpilot setup`, then `doctor` again |
| `jobpilot doctor` reports a problem | relay its sentence; fix the one thing it names; re-run `doctor` |
| Python is older than 3.11 | tell them which version is needed; stop until they install 3.11+ |
| `pip install -e .` fails | relay the error plainly (usually network or an old pip); try `python -m pip install --upgrade pip` once, then retry |
| a model is unavailable | say which part is paused; everything read-only still works; offer to pick another provider in setup |
| the user skips a sign-in | say which features stay off; continue with the rest |
| a dry run finds nothing | check sources/filters with the user in `jobpilot setup`; nothing is wrong, the filters may be narrow |
| a guard or outbound check blocks an action | **stop and ask** — do not retry with a force flag or edit files to get around it |
| settings won't load | `jobpilot doctor` lists every problem at once, in sentences — relay them and fix together |

## For contributors

Developing jobpilot rather than running it? See
[`CONTRIBUTING.md`](CONTRIBUTING.md). Run the suite with the test marker set so
nothing can reach the real world:

```bash
pip install -e ".[dev]"
JOBPILOT_TEST=1 python -m pytest -q
```
