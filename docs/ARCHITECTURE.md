# jobpilot — architecture (v2)

A team of agents that finds jobs you would want, screens them against evidence,
applies through a pluggable driver, checks which applications actually arrived,
and reports to you once a day in plain language.

This document describes the v2 core, which lives in `jobpilot/`.

## Design rules

These are the load-bearing ideas. Everything else is an implementation detail.

1. **Rules flag; a model decides; code checks the evidence.** Pattern-matching
   code never drops a job — it annotates it. A model may drop a job only by
   quoting the employer's own description, and `screen.py` re-checks that the
   quote is really there. An unverifiable drop becomes a keep.
2. **One writer.** Every change to the application record goes through
   `tracker.py`: lock, re-read, atomic write, backup, rotate, append an event.
3. **Fail closed.** A missing confirmation never downgrades a row. A guard that
   cannot read what it needs refuses rather than guesses. A blocked outbound
   action is a hard skip, never a reworded retry.
4. **Never invent an answer.** A form question is answered from the user's
   answer file or the application stops and asks them.
5. **Never twice.** A job that was submitted is never submitted again, and
   reconsidering a job the user skipped needs their explicit approval.
6. **Permission before anything leaves the machine.** Nothing is submitted,
   sent or posted unless the matching permission is on *and* the outbound gate
   passes. All permissions default to off.
7. **One user file, no machine paths.** Everything the user owns is
   `config/preferences.yaml`; everything the assistant owns hangs off
   `paths.data_dir`. A test asserts that no module contains a path from
   somebody's computer.
8. **Plain words by default.** Every user-facing message goes through one
   renderer with a lint that rejects file names, identifiers, model names, exit
   codes and internal vocabulary. Technical mode adds detail and changes
   nothing else.
9. **Core never imports a plugin or a provider.** It sees interfaces and
   settings. The core runs with any subset of plugins installed, including none.
10. **Tests cannot reach the real world.** `JOBPILOT_TEST=1` makes the network,
    real mailboxes, real browser drivers and real model command lines raise.
    The block lives in the code under test, not in the tests.

## The path a job takes

```
sources ──► rules (FLAGS only) ──► model screen (verbatim quote required)
                                              │
                            ┌─────────────────┴──────────────────┐
                      drop, with a quote                  keep (core / non_core)
                            │                                   │
                   record: skipped + quote               record: pipeline
                                                                │
                                                 queue: core first, newest first
                                                                │
                                        claim guard · never-reapply · lane guard
                                                                │
                                          wave ──► driver ──► disposition (always)
                                                                │
                                   ┌────────────────────────────┴──────────────┐
                              submitted                                  parked / blocked
                                   │                                           │
                 receipt match (sender + recipient + window)            reported to the user
                                   │
                              confirmed
                                   │
                    daily digest · reflection · proposals
```

## Modules

| module | what it is |
|---|---|
| `config.py` | one user file, merged over defaults, validated into friendly sentences; every path derives from `paths.data_dir` (or `JOBPILOT_DATA_DIR`) |
| `domain.py` | the few values everything passes around: `Job`, `Flag`, `Decision`, `Proposal`, `Message`, the status vocabulary |
| `errors.py` | every error a user can see, each carrying what to do about it |
| `testmode.py` | the one gate between the code and the real world |
| `ui.py` | the renderer and the no-jargon lint; one plain line after a self-improvement |
| `search/` | `Source` + injectable `Fetcher`; built-in no-login board APIs (Greenhouse, Lever, Ashby); de-duplication on canonical URL **and** ATS job id, plus company+title as a deliberately weak third identity that only ever *flags*; a pass that reports its funnel per source |
| `terms.py` | the one reader for the two lists people edit most — job titles and which company pages to read — from the settings or from a companion file beside them, read fresh on every pass |
| `rules.py` | deterministic flags (sponsorship family, citizenship, clearance, export control, location, years of experience, doctorate, seniority, excluded categories, held companies, freshness) and the only three automatic drops |
| `screen.py` | the model screen, the quote check, and the tracker fields a decision writes |
| `tiering.py` | the one place a job's queue is decided: rules first, an optional model hook that may drop a job only by quoting the posting, and `model_pending` when nothing answers |
| `tracker.py` | the single writer: lock, atomic write, rotating backups, append-only event log, and the guards (unknown status, per-row verdicts, skip evidence, receipt required, never-reapply, approval to reconsider, protected rows, one lane per job) |
| `queue.py` | core first, newest first; non-core waits until core is empty |
| `pins.py` | the frozen, fingerprinted batch handed to the apply step; waves across lanes, the stop that lets the batch in flight finish, hand-back of jobs a dead wave never reached, and the handoff watchdog |
| `accounts.py` | which employer sites need an account and what state each is in — states only, never a credential |
| `gates.py` | the answer bank (or a stop), the outbound gate (permission + checks + caps + pause file + no password resets), the lane guard (count and projected memory) |
| `apply.py` | the wave runner, the `ApplyDriver` interface and the `DryRunDriver`; every claimed row gets exactly one disposition |
| `verify.py` | read-only `MailReader`; receipt matching (sender domain, recipient, time window, newest wins); verification codes in a `Code` that cannot be printed; the unconfirmed-rate metric |
| `report.py` | the daily digest, the reflection log, and the weekly review by source and by application system |
| `mail.py` | outcome classification with the sentence that justified it, the date pulled out of the message, and the morning and evening reminders |
| `outreach.py` | the dated manifest of drafts: what would be sent, whether it may go, and why not. It has no sender |
| `watch.py` | the hourly, token-free health check: queue leaks, a stalled batch, idle capacity, a sign-in that needs the user, confirmations drying up |
| `lead.py` | metrics, proposals with evidence and an expected effect, turning a sentence into a proposed change, the store of waiting suggestions, and an `apply_proposal`/`decide` pair that refuses without an explicit approval |
| `routines.py` | the declarative timetable and its rendering in the user's words |
| `scheduler.py` | works out what is due and runs it, once; the state file that makes it idempotent and safe to call from cron |
| `catalog.py` | the one list of everything switchable — helpers *and* models — used by the setup conversation, `status` and the README table |
| `explain.py` | the "what am I getting?" explanation, generated from manifests, timetable and settings so it cannot drift |
| `wizard.py` | the setup conversation: questions with defaults and consequences, a prose summary to confirm, then one write with a backup |
| `logins.py` | the sign-in checklist, one platform at a time. `LiveProbe` *reaches* the mailbox or the page read-only, so "ready" means something actually looked; settings that merely look right give `unverified`, and a run with nobody present never claims a sign-in. It never sees a password |
| `plugins/` | the registry, the manifest format, and LinkedIn / school platform / startup list as plugins, each with an agent prompt |
| `providers/` | the `ModelProvider` interface with Claude CLI, Codex CLI, any OpenAI-compatible HTTP service, and a deterministic fake; role mapping and a fallback chain |
| `cli.py` | `start`, `setup`, `logins`, `status`, `ask`, `approve`/`decline`, `run search\|screen\|apply`, `routines list\|run-due`, `digest`, `doctor` |

Outside the package:

| where | what |
|---|---|
| `routines/routines.yaml` | the whole timetable, declarative — see [ROUTINES.md](ROUTINES.md) |
| `agents/` | one prompt per role, plus each helper's prompt shipped with the helper |
| `templates/bots/` | the same seven roles as importable bot templates: profile, memories, skills, routines, and a generated `share.json` |
| `config/*.example.*` | templates: settings, the answer bank, job titles, which pages to read |
| `examples/` | eight scripts that run offline against synthetic data |
| `scripts/` | setup, the hygiene scan, and the clone-install-test migration check |
| `START_HERE.md` | the prompt a user pastes into their own assistant |
| `tools/record_sample_session.py` | records `docs/sample-session.md` from an actual run, so the documentation cannot drift from the behaviour either |

**Where everything lives.** The project directory is found by looking upward
from the package for `pyproject.toml` and `config/` (`config.repo_root()`,
overridable with `JOBPILOT_HOME`), so nothing depends on what the clone is
called or on the current working directory. A relative path under `documents:`
resolves **beside the user's settings file**, so moving the settings with
`JOBPILOT_CONFIG` moves everything private with them.

## Settings

`config/preferences.yaml` is the only file a user edits. `config/preferences.example.yaml`
is the committed template; `config/answers.example.yaml` is the answer bank;
`routines/routines.yaml` is the timetable.

Two environment variables move those files elsewhere: `JOBPILOT_CONFIG` for the
settings and `JOBPILOT_DATA_DIR` for everything the assistant writes. One
function resolves the settings path — `config.settings_path`: an explicit
`--config`/`--out` → `JOBPILOT_CONFIG` → the checkout's `config/preferences.yaml`
— and **everything that reads or writes the file goes through it**, including
the setup conversation and an approved change. Setup writing to one place while
every other command reads another looks like success and behaves like nothing
working at all.

Any `{{PLACEHOLDER}}` from the example file is treated as absent everywhere: as
a question's default, in the summary, and in what is saved.

Validation is collective and friendly: every problem is reported at once, in
sentences, with what to do. Examples:

```
I could not use your settings in config/preferences.yaml. Please fix:
  - 'search.categories.core' is empty, so nothing would ever be applied to first. List the job titles you care about most.
  - 'models.screen' is 'gpt-9', which no enabled provider offers. Available right now: claude-haiku, claude-opus, claude-sonnet.
Then run 'jobpilot doctor' and I will check them again.
```

The user's own facts (who they are, what they want, what they are allowed to do)
are settings. The reasoning (what a sentence in a posting means, how to rank,
how to de-duplicate) is code. The split is enforced by review, not by hope: a
rule that depends on one person's situation belongs in the settings file.

## The three automatic drops

Everything else is flagged and left to the model, and when in doubt a job is
kept.

1. a company on the user's never-apply list (name match, no quote needed);
2. an explicit, quoted sentence from the employer's own description that rules
   the user out entirely — no sponsorship at all, citizen/green-card only,
   clearance required, export-control/US-person — each family switchable by the
   user. A posting that accepts OPT/CPT/STEM-OPT/EAD or an existing visa but
   will not sponsor a new one is a normal role, not a disqualifier;
3. a posting proven closed by a structured liveness receipt
   (`{http_code, url, checked_at}`). Free text containing "404" is not a
   receipt.

Every drop is written down with its reason and its quote. Drops are data, not
silence.

## The record

One JSON document under `paths.data_dir`, plus an append-only `events.jsonl` and
rotating backups. Rows carry their identity (canonical URL, other URLs seen, ATS
family and id), their screening verdict and evidence, their tier, their status
and timestamps, their submit evidence and receipt, and append-only notes, tags
and flags.

Statuses: `new`, `pipeline`, `review`, `hold_pending_user`, `claimed`,
`skipped`, `closed`, `parked`, `blocked`, `submitted`, `applied`,
`online_assessment`, `interview`, `offer`, `rejected`. They are normalised but
never mapped onto each other: an unrecognised status is a refused write, because
a typo that silently becomes a different state is worse than an error.

Refusals are named, not numbered: `unknown_status`, `batch_verdict`,
`verdict_missing`, `skip_without_reason`, `skip_without_evidence`,
`receipt_missing`, `already_applied`, `reapply_needs_approval`,
`protected_row`, `claimed_elsewhere`, `locked`, `force_without_reason`.

## Models

A role maps to a model, and a model belongs to a provider:

```yaml
models:
  screen: claude-haiku     # reads job descriptions
  review: claude-opus      # reviews, plans, judges
  browser: claude-haiku    # drives a browser, for plugins that need one
  fallback: [claude-haiku] # tried in order when the chosen one is unhealthy
```

Providers: the Claude Code CLI (prompt on stdin, model selectable), the Codex
CLI, any OpenAI-compatible HTTP service (the key is read from the environment
variable the settings *name* — never stored in the file), and a deterministic
fake for tests. Every result records who actually answered. A provider that is
not installed or not signed in is a reported condition, not a crash, and never
stops read-only work.

Providers are plugins in the sense that matters — core sees only the
`ModelProvider` interface and the settings decide which one answers — but they
live in `jobpilot/providers/` rather than carrying a `plugin.yaml`, because they
have no logins to walk through, no routines to contribute and no outbound
actions to gate. A third-party provider only has to satisfy the interface and be
registered.

## Plugins

A plugin is a directory with `plugin.yaml`, an `__init__.py` and an agent prompt.
The manifest states, in plain language, what the plugin does, which logins it
needs and what it will never do with them, which outbound actions it can take,
what it may write, and its own caps. A plugin that needs a login must declare
`enabled_default: false` — the loader refuses a manifest that does not.

Plugins contribute search sources (whose rows face exactly the same rules and
screen as any other row) and outreach drafts (which only leave the machine if
the permission is on and the gate passes — the core ships no sender at all).
Real browser work is delegated to a browser-capable model: the plugin writes a
prompt, the model drives the browser, the plugin parses the answer.

Shipped: `linkedin`, `handshake` (school platform), `yc` (startup list). All
off by default. The core runs with any subset, including none.

## What the user sees

Simple mode is the default and is about progress and outcomes:

```
Your job search — Tuesday 10 November

Today: 2 applications confirmed, 1 sent and waiting for a confirmation, 3 new matches found

Needs you:
  - What is your employee referral code?

Good news: 1 interview.

Still on my list: 14 jobs to apply to.
```

Technical mode appends the detail. After the assistant tunes itself the user
gets one plain line ("I now retry the email-code step automatically, so fewer
applications should get stuck") or nothing; the particulars go to the changelog.

The Lead brings suggestions when the numbers justify them — a confirmation rate
that has dropped, an empty queue, a source with nothing in it, one site that
keeps stopping us, idle capacity, questions it had to stop on — each with its
evidence and its expected effect, each phrased as a question. Suggestions appear
in `status` and in the daily summary, and are remembered in the state folder, so
`jobpilot approve <id>` and `jobpilot decline <id>` work in a later
conversation.

It never changes a setting on its own. `apply_proposal` raises unless it is
handed an explicit approval, and every accepted change is written to the
changelog and the event log.

The same path handles a change asked for in plain words:

```console
$ jobpilot ask "also treat data scientist roles as a first choice"
I would also treat data scientist roles as a first choice:
- the jobs I go after first: now Machine Learning Engineer, AI Engineer; would become Machine Learning Engineer, AI Engineer, Data Scientist.

What you would notice: A few more jobs each morning, and they go out before the others.

I have changed nothing yet. Say 'jobpilot approve your-request' and I will.
```

`lead.interpret_request` asks the review model which setting the sentence meant,
then refuses anything outside `lead.CHANGEABLE` or of the wrong shape. The
permissions are deliberately **not** in that list: switching on sending or
submitting is always a deliberate act, never something inferred from a turn of
phrase.

## The timetable

`routines/routines.yaml` is declarative: a name, a schedule, what it does, and the
sentence the user hears. `jobpilot routines run-due` works out what is due,
runs it, and records when each one last ran — so calling it again straight away
does nothing. That makes it safe to drive from anything, including cron:

```cron
*/10 * * * * cd <this checkout> && jobpilot routines run-due >> <data_dir>/logs/cron.log 2>&1
```

`jobpilot routines list --technical` prints that line filled in, and a systemd
user-timer equivalent. Both are generated: the folder comes from
`config.repo_root()` (the directory above the package that holds `pyproject.toml`
and `config/`, overridable with `JOBPILOT_HOME`) and the log path from the
configured data directory. Nothing anywhere assumes what the clone is called.

Three schedule shapes: `at:` with `days:` (once per matching day), `window:`
(repeatedly while open, at most once per `every_minutes`), and `every:`. A
schedule the parser cannot read never runs, rather than running at the wrong
time. One routine failing never stops the others, and a time the user chose
during setup wins over the one in the file.

## Setting up

`jobpilot start` prints the generated explanation and then holds the
conversation; `jobpilot setup` is the conversation on its own. Fifteen or so
questions, each with a default, one sentence on what it changes, and — where it
helps — an example of a job it would keep and one it would drop. A few follow-up
questions appear only if they are relevant (which school, how many connection
requests a week, the address of your own model service).

Nothing is written until the user has read a prose summary and said yes; an
existing settings file is copied aside first; and any `{{PLACEHOLDER}}` left
over from the example file is stripped, because a placeholder that survives
looks like an answer and would be typed into a form.

The conversation is scriptable — `--answers file.yaml`, or `--non-interactive`
for every default — which is how it is tested and how
`docs/sample-session.md` is recorded.

Then the sign-ins, one platform at a time: what it is, why it is needed, what to
do, and what will never be done with that account. The user says "done" (or
"skip"), and only then is the helper asked whether it looks ready. Nothing here
ever sees a password, and a skipped sign-in is reported along with what stays
switched off because of it.

## Testing

```
JOBPILOT_TEST=1  (set by tests/conftest.py for the whole suite)
```

With the marker set, `UrllibFetcher`, `JsonExportMailReader`, any real apply
driver and every model command line raise `TestModeViolation`. Tests use
`FixtureFetcher`, `FakeMailReader`, `DryRunDriver` and `FakeProvider`. Fixtures
are synthetic throughout: invented companies, invented postings, invented mail.

Run them with:

```
python -m pytest -q
```

There is also a check that every user-facing surface stays in plain words:
`tests/test_plain_language.py` drives each command and compares the output
against a blacklist, rather than trusting each surface to behave. And the suite
asserts that no test writes into the checkout and that no module contains a path
from somebody's computer.

## What is deliberately not here yet

[`CAPABILITY-MATRIX.md`](CAPABILITY-MATRIX.md) §10 has the full list, with the
reason for each. The short version:

- **A real browser apply driver.** The core ships `DryRunDriver`; a real one
  implements `ApplyDriver` and must honour `request.dry_run`.
- **A real mailbox connector.** `JsonExportMailReader` reads an export written
  by something else; a connector implements `MailReader`, which has exactly one
  verb.
- **Sending the daily summary.** It is written to the logs folder; the
  permission exists (`send_digest_email`) and nothing uses it yet.
- **Outreach senders.** The helpers draft messages and take them to the gate;
  the core has no way to send one, deliberately.
- **A long-running process.** `routines run-due` is a single pass; anything that
  wants a daemon can call it in a loop.
