# Changelog

Notable changes, newest first. Dates are the day the work landed.

This project uses [semantic versioning](https://semver.org). Until `1.0.0` the
settings shape may still change; anything that does change is listed here with
what to do about it, and [`docs/MIGRATION.md`](docs/MIGRATION.md) has the
details.

---

## Unreleased

### Added

- **A frozen batch, handed over by fingerprint** (`jobpilot.pins`). The apply
  queue is written down once, fingerprinted over its contents, and never edited
  in place — so it cannot change under a running batch and a job cannot end up
  in two batches at once. Includes waves across lanes, a stop that lets the
  batch in flight finish, hand-back of jobs a dead wave never reached, and a
  watchdog for queue leaks, stalled batches and expired claims.
- **One place that decides which queue a job goes in** (`jobpilot.tiering`).
  Rules first; a model only as an optional hook that may drop a job solely by
  quoting the posting, with the quote re-checked. An unprovable drop is
  discarded, not the job.
- **Outcome reading from the mailbox** (`jobpilot.mail`). Tests, interviews,
  offers, rejections and recruiter replies, each with the sentence that
  justified it, tied to a job before anything is written. Dates are pulled out
  of the message, and reminders go out morning and evening.
- **An employer-account registry** (`jobpilot.accounts`). Which sites need an
  account and what state each is in, keyed so two employers sharing one
  application system never share an entry. It stores **no credentials** and
  refuses text shaped like one.
- **An outreach manifest** (`jobpilot.outreach`). A dated list of drafts with,
  for each one, whether it may go and why not. Nothing can be sent from it; a
  blocked draft is never reworded.
- **An hourly health check** (`jobpilot.watch`). Queue leaks, a batch that
  stopped moving, idle capacity, a sign-in that needs the user, confirmations
  drying up. No model calls, no network, quiet hours, every threshold the
  user's.
- **Company-and-title de-duplication, as a flag** (`search.dedupe`).
  Deliberately weaker than URL or identifier matching: it flags
  `possible_dup` and never removes a row, because loose name matching once
  removed good rows silently.
- **A batch can be inspected before it is written** (`Tracker.plan` /
  `Tracker.commit`). Every guard runs on the plan, so a plan with no refusals
  is a batch that will go through. `dry_run` defaults to **true**.
- **A mailbox-export header guard** (`verify.check_export_header`). An export
  must declare its mailbox, its query, its window and that it finished.
  Without it, "no code found" and "nobody looked" are the same answer.
- **Per-system switches for reading verification codes**
  (`verify.email_codes.*`), all off by default, so a risky path is enabled one
  application system at a time.
- **The weekly review** (`report.weekly_review`), broken down by source and by
  application system — "nothing is working" and "one source has gone quiet"
  look identical in a single total and need different answers.
- **Companion files for the two lists people edit most** (`jobpilot.terms`):
  `search_terms.json` and `sources.yaml` beside the settings, with templates in
  `config/`. One reader each, read fresh every pass, never baked into the code.
- **Examples that run** (`examples/`): eight offline scripts covering setup,
  searching, screening, ordering, applying, the summary, the look back and
  reading a verification code. `tests/test_examples.py` runs all of them.
- **`scripts/migration_check.sh`**: clone into a differently named folder, fresh
  virtual environment, install, self-check from an unrelated directory, the
  whole suite, and a scan of the clone.
- **`scripts/sanitize_scan.py`**: the repository-hygiene rules as a standalone
  script, so CI and the migration check can run them against a bare clone.
- **A Makefile**, `scripts/setup.sh`, and a GitHub Actions workflow at
  [`.github/workflows/ci.yml`](.github/workflows/ci.yml), which runs on every
  push and every pull request: Python 3.10-3.12, the tests, the self-check
  against the example settings, the sanitize scan, the bot-template check, and
  the full fresh-clone migration run.
- **Seven importable bot templates**, one per team role
  ([`templates/bots/`](templates/bots)): `lead`, `search`, `apply`, `mail`,
  `linkedin`, `handshake`, `yc`. Each is a folder holding a profile, the facts
  the bot starts out knowing, its skills, its routines, and the first
  conversation it has with a new owner - plus a `share.json` **generated** from
  those files by `scripts/build_bot_templates.py`, so the folder and the import
  cannot disagree. Search is **one role with two focus modes** rather than two
  bots, because two copies of the screening rules drift. No skill, prompt or
  routine names a model or a vendor: providers are configurable slots, and a
  test fails the build on a vendor name.
- **`jobpilot templates list|show|export <role>`** - reads the templates, and
  needs no settings, because somebody looking at them has not set anything up
  yet.
- **An English-only rule, enforced** (`NON_ENGLISH` in the sanitize scan,
  `tests/test_english_only.py`). Every tracked text file, no exemptions - the
  two files that define the patterns pass by writing escapes rather than
  characters, so "there is none of this anywhere" is true of the checker too.
- **Docs**: [`CAPABILITY-MATRIX.md`](docs/CAPABILITY-MATRIX.md),
  [`MIGRATION.md`](docs/MIGRATION.md), [`ROUTINES.md`](docs/ROUTINES.md),
  [`APPLY-METHOD.md`](docs/APPLY-METHOD.md),
  [`templates/README.md`](templates/README.md), this changelog.

### Changed

- **The project no longer cares what its folder is called.** The project
  directory is found by looking upward from the package for `pyproject.toml`
  and `config/`, overridable with `JOBPILOT_HOME`. The scheduler line is
  generated from that and from the user's own data folder, instead of printing
  `cd ~/jobpilot` and hoping.
- **The setup conversation asks where the CV is** (the path only — the file
  stays where the person put it) **and builds the answer bank** through six
  short questions, most of them already answered by earlier answers.
- **A login check now has to reach the platform.** "Ready" means something
  actually opened the mailbox or the page, read-only. Settings that merely look
  right give the new `unverified` state, and `--non-interactive` never reports
  a sign-in at all.
- **The end-of-day look back produces the suggestions.** It used to write a
  note nobody acted on; the numbers now trigger proposals, which wait for a
  yes.
- **The daily summary refuses to produce a second one for the same day.**
- **The timetable covers everything that should happen by itself** — fifteen
  entries, up from seven — and every entry maps to a real callable. A helper's
  own routine arrives as `plugins.<name>.<action>` and resolves, where enabling
  LinkedIn used to leave a timetable entry that reported a failure every time
  it came due.
- **A user's own files resolve next to their settings**, not inside the
  checkout, so `JOBPILOT_CONFIG` really moves everything private.
- **A path still holding a `{{PLACEHOLDER}}` counts as unset** rather than as a
  missing file, so the shipped example no longer looks like a broken install.
- `doctor` also reports the CV, the answer bank, employer sign-ups waiting on
  the user, whether every timetable entry can run, and the health check.
- **A model command-line tool is never reachable in test mode**, so that is now
  what its health says, whatever is installed on the machine. In test mode -
  which is what the examples, the dry runs and the suite use - `doctor` reports
  such a model as **not checked** instead of counting it as a fault, so a fresh
  machine with no `claude` or `codex` on `PATH` passes the self-check. On a real
  installation a configured tool that cannot be found is still a problem, and
  still names itself.
- **Counts and verbs agree**: "3 things need fixing", "1 thing needs fixing".
- `agents/search.md` documents the wide and deep lanes as **one role with one
  set of rules**: two roles means two copies of the rules, and those drift.
- `agents/README.md` lists every role, including the three helpers.
- `AGENTS.md`'s "build the team" step now works from `templates/bots/*`, so the
  coding-agent route and the bot-product route build the same seven roles from
  the same files.

### Moved

| from | to |
|---|---|
| `jobpilot/` | `src/jobpilot/` |
| `config/routines.yaml` | `routines/routines.yaml` (the old place is still read) |

### Renamed

| from | to | why |
|---|---|---|
| `apply.waves` | `apply.pass` | `routines.yaml` is something users read, and "waves" is internal vocabulary |
| `tracker.tidy` | `records.tidy` | the same |
| `documents.answers: config/answers.yaml` | `documents.answers: answers.yaml` | relative paths now resolve beside the settings file; the old form is still understood |

### Tests

456 → 920.
