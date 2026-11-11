# Routines — what runs by itself, and when

The timetable is one declarative file, [`routines/routines.yaml`](../routines/routines.yaml),
and it is the **only** description of the schedule there is. `jobpilot routines
list` reads the descriptions back to the user, so the timetable they are told
about cannot drift from the one that runs.

Nothing in it sends, submits or posts anything. Each entry runs the same code
the command line runs, with the same permissions and the same checks, and every
sending permission starts off.

---

## The whole timetable

Times are local to `timing.timezone` in the settings. The daily summary's time
is the one the user chose during setup; the rest are the defaults.

| when | what it does, in the user's words | what | needs a model? |
|---|---|---|---|
| 07:30 daily | looks for new jobs that match | `search.daily_pass` | only for helper sources |
| 08:00 weekdays | one summary, with anything that needs you | `report.digest` | no |
| 08:15 daily | reads each new description and decides | `screen.pass` | yes |
| 08:40 weekdays | writes up any messages worth sending, for you to look over | `outreach.manifest` | no |
| 09:30 daily | reminds you about a test or interview coming up | `mail.reminders` | no |
| 09:30–18:00 weekdays, every 30 min | works through the list and fills in applications | `apply.pass` | yes, with a real driver |
| 11:39 daily | checks the morning's finds really reached the list | `apply.handoff_watchdog` | no |
| every 2 hours | reads your mail for replies, tests and interviews | `mail.triage` | no |
| every hour | checks nothing is quietly stuck | `watch.tick` | no |
| 18:00 daily | checks the mailbox for confirmations | `verify.receipt_sweep` | no |
| 18:30 daily | looks back at the day, and brings any suggestion worth making | `report.reflection` | no |
| 20:00 daily | reminds you again, so a deadline is not a surprise | `mail.reminders` | no |
| every 6 hours | tidies away old copies of your records | `records.tidy` | no |
| 22:00–07:00 daily, hourly | keeps working through the list overnight | `apply.pass` | yes, with a real driver |
| Monday 10:00 | goes over the week and suggests what to change | `report.weekly_review` | no |

Plus one entry per switched-on helper, from its own manifest — for example
`linkedin_cycle`, every evening between 18:00 and 22:00.

## How it runs

```bash
jobpilot routines list                # the timetable, in the user's words
jobpilot routines list --technical    # the same, plus the scheduler line
jobpilot routines run-due             # run whatever is due
jobpilot routines run-due --dry-run   # say what is due, run nothing
jobpilot routines run-due --now 2026-11-09T08:00   # "what would happen then?"
```

`run-due` works out what is due, does it, and records when each one last ran.
It is **idempotent**: calling it again straight away does nothing. That is the
whole design — it means the schedule can be driven by something as dumb as
cron, with no daemon, no lock file and no state to corrupt.

```bash
jobpilot routines list --technical    # prints the line for your folder
crontab -e                            # paste it
```

Ask for the line rather than copying one from a document: it is generated from
your actual project folder and your own data folder. A systemd user timer is
printed alongside it for anyone who prefers that.

## The three schedule shapes

```yaml
- name: daily_email
  schedule: { at: "08:00", days: mon-fri }       # once per matching day
  what: report.digest
  description: "Every weekday at 8am you get one email ..."

- name: apply
  schedule: { window: "09:30-18:00", days: mon-fri, every_minutes: 30 }
  what: apply.pass                                # repeatedly while open

- name: check_mail
  schedule: { every: "2 hours" }                  # all day, at most once per interval
  what: mail.triage
```

- `at:` — due at or after that time on each matching day, and once only. A late
  start still runs that day rather than skipping it.
- `window:` — due repeatedly while the window is open, at most once every
  `every_minutes` (60 if not given). A window may cross midnight.
- `every:` — at most once per interval, all day.

`days:` accepts `daily`, `mon-fri` / `weekdays`, `sat-sun`, or a list like
`tue,thu`. A schedule the parser cannot read **never runs**, rather than running
at the wrong time.

## Writing a new routine

Two things have to be true, and both are tested:

1. an entry needs a `description` written in the user's own words, with no
   internal vocabulary in it (`test_every_description_reads_like_a_person_wrote_it`);
2. its `what` must resolve to a real callable
   (`test_every_routine_in_the_file_has_something_wired_up_to_do_it`).

```python
# src/jobpilot/scheduler.py

def action_my_thing(config: Config, renderer: Renderer) -> str:
    """Return what to tell the user, or "" to say nothing at all."""
    return ""

ACTIONS["mine.thing"] = action_my_thing
```

A routine returns a **plain sentence or nothing**. Returning `""` is normal and
common: housekeeping, a quiet health check and the end-of-day note all have
nothing to say to anybody. Everything returned is rendered through the
jargon lint before it reaches the user.

A **helper's** routines come from its manifest and arrive as
`plugins.<name>.<action>`. They all resolve through one drafting cycle, so
installing a helper can never leave a timetable entry with nothing behind it —
which it used to.

## Two behaviours worth knowing about

**The daily summary happens once a day, full stop.** The timetable asks for it
once each weekday, but a restart, a clock change or somebody running it by hand
must not produce a second one: two emails saying different things about the same
day is worse than neither. `action_digest` refuses if today's is already
written.

**The end-of-day look back is what triggers the suggestions.** A reflection
nobody acts on is a diary. So at 18:30 the numbers are read, anything worth
asking about becomes a proposal, and the proposal waits for a yes. No setting
is ever changed by a routine.

## What each one needs

| routine | needs | if it is missing |
|---|---|---|
| `search.daily_pass` | public job pages; a browser model for helper sources | reads whatever it can, reports what it could not |
| `screen.pass` | a model for reading descriptions | nothing is read; jobs wait |
| `apply.pass` | an apply driver; the submit permission | runs as a practice run and reports what it would do |
| `mail.triage`, `verify.receipt_sweep`, `mail.reminders` | a connected mailbox | says nothing; applications stay "sent" rather than "confirmed" |
| `outreach.manifest` | a switched-on helper | nothing to draft, so nothing is written |
| `watch.tick`, `records.tidy`, `report.*` | nothing at all | always work |

A routine that cannot do its job says so and leaves everything else running.
One broken routine never stops the rest: `run_due` catches it, records it, and
carries on.
