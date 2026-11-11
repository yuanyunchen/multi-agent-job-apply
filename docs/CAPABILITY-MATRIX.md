# Capability matrix

What a long-running, hand-built job-application system does, and whether this
reusable version does it. The reference column describes a working private
system that had been running daily for weeks; this project is the generic
rebuild of it, so the matrix is the honest answer to "what did the rebuild
lose?"

**Before** is this repository at the start of the audit (commit `a15129c`,
456 tests). **After** is now. Nothing here names a person, a company, an
employer, a machine or an account.

Key: **yes** — present and tested · **part** — present but narrower than the
reference · **no** — absent · **n/a** — deliberately out of scope.

---

## 1. Finding jobs

| capability | reference behaviour | before | after | where it lives now |
|---|---|---|---|---|
| Read employers' own public job pages | several application-system families, read directly, no account | yes | yes | `search/ats.py` |
| Two search lanes (wide recall, deep reading) | two separate bots | part (one role) | yes | `agents/search.md`, one role with two lanes |
| Title terms loaded fresh every pass, never baked in | a term file re-read on every pass | no | yes | `terms.py`, `config/search_terms.example.json` |
| Entry-level variants of every term searched | each term run bare and with level wording | no | yes | `Terms.queries()` |
| Which pages to read, as its own editable list | a long board registry | part (in settings) | yes | `terms.Sources`, `config/sources.example.yaml` |
| De-duplicate by canonical URL | tracking parameters stripped | yes | yes | `search/dedupe.py` |
| De-duplicate by the site's own job identifier | scoped to company and system | yes | yes | `search/dedupe.py` |
| De-duplicate by company and title, as a **flag** | flags, never drops — loose matching once removed good rows | no | yes | `possible_duplicates()` |
| Per-source funnel counts, and "found nothing" reported | per-source yield logging | yes | yes | `SearchReport`, weekly review |
| Thousands of known boards, aggregators, archive crawling | a large source registry | no | **no** | out of scope: see §9 |
| Platform one-click apply during search | in-app quick apply | part (plugin manifests) | part | plugin territory; core ships no sender |

## 2. Deciding what is worth applying to

| capability | reference behaviour | before | after | where it lives now |
|---|---|---|---|---|
| Rules **flag**, they never drop | the backbone of the design | yes | yes | `rules.py` |
| Exactly three automatic drops | named company · quoted disqualifying line · proven-closed posting | yes | yes | `rules.hard_exclude` |
| A model may drop a job only by quoting the posting | quote re-checked locally against the raw text | yes | yes | `screen.py`, `tiering.py` |
| An unprovable drop is discarded and the job kept | invalid quote becomes a keep | yes | yes | `tiering.classify` |
| No model answer leaves the rule answer, marked pending | `model_pending` | part | yes | `TierDecision.model_pending` |
| First-choice / second-choice / never tiering from the user's own terms | core / non-core / exclude | part (inside the screen) | yes | `tiering.py` as one module |
| Ambiguity favours the first-choice queue | documented product rule | yes | yes | `tiering.py` |
| Sponsorship decided in exactly one place | accepting an existing permit is **not** a disqualifier | yes | yes | `rules.denies_sponsorship` |
| Only an explicitly *required* minimum experience drops a job | preferred / ranges / ceilings all keep | yes | yes | `rules.required_years` |
| Non-local, clearance, citizenship, doctorate rules | each needing a quote | yes | yes | `rules.py` |
| Freshness as a ranking signal, never a disqualifier | undated rows marked, not dropped | yes | yes | `queue.py` |
| Description fetched from the application system when a listing is thin | HTTP backfill | part | part | `search/ats.py` returns descriptions; no separate backfill pass |
| Description compacted before the model sees it | boilerplate stripped, protected lines kept | no | **no** | out of scope: see §9 |

## 3. The record

| capability | reference behaviour | before | after | where it lives now |
|---|---|---|---|---|
| One file, one writer | the heart of its trustworthiness | yes | yes | `tracker.py` |
| Lock, re-read, atomic write | no half-written record | yes | yes | `tracker.Tracker._write` |
| A copy before every write, with rotation | unrotated copies once filled a disk | yes | yes | `_backup_and_rotate` |
| A periodic prune as well as rotation on write | a separate pruner | no | yes | `tidy_backups`, the `tidy_up` routine |
| Append-only event log | every accepted change | yes | yes | `events.jsonl` |
| A per-job verdict required from screening | a batch-level verdict is not evidence | yes | yes | `require_verdict` |
| A skip needs a reason and a quote | the quote's provenance recorded | yes | yes | `SKIP_BASES_WITHOUT_QUOTE` |
| "Confirmed" needs a mailbox receipt | or an explicit, recorded override | yes | yes | `_guard` |
| Never re-apply | by identifier and by posting identity | yes | yes | `SUBMITTED_STATUSES` |
| Re-opening a skipped job needs the user | explicit approval | yes | yes | `approve_reapply` |
| An already-applied row is protected | notes and evidence only | yes | yes | `SAFE_UPDATE_FIELDS` |
| One lane at a time, with an expiring claim | lease + heartbeat | yes | yes | `claim`, `_lease_expired` |
| Inspect a batch before writing it, dry-run by default | dry-run-then-commit, relied on by every caller | no | yes | `Tracker.plan` / `commit` |
| Refusals explained in the user's words | — | part | yes | `REFUSAL_WORDS` |
| Merging two rows requires identity evidence | same URL or same id within one company | no | **part** | the writer de-duplicates by identity; there is no separate merge tool |
| Named exit codes per guard | 11/12/13/14/15 | part (typed refusals) | part | typed `TrackerRefused.code`; no numeric contract |

## 4. Applying

| capability | reference behaviour | before | after | where it lives now |
|---|---|---|---|---|
| First choices first, newest first | second choices may starve | yes | yes | `queue.build_queue` |
| How deep the queue is, after the guards | an eligible-depth estimate | part | yes | `queue.depth`, `watch.py` |
| A frozen, fingerprinted batch handed over | a pin, identified by hash, never edited in place | no | yes | `pins.build_pin` |
| A batch written once and never changed | — | no | yes | `PinStore` |
| Flags must be real booleans | the string `"False"` once bypassed a guard | no | yes | `pins._check_flags` |
| Batches of ~20, several lanes | waves per lane | part (one wave) | yes | `pins.Driver` |
| Lane admission on projected free memory | admitted only if the floor survives *n* lanes | yes | yes | `gates.LaneGuard` |
| A running batch always finishes; no new one starts after a stop | stop file, drain | no | yes | `Driver.stop_file` |
| Jobs a dead batch never reached are handed back | requeued after the duplicate checks | no | yes | `WaveRecord.unreached` |
| Every job picked up gets an outcome | applied / parked / blocked / skipped | yes | yes | `apply.DISPOSITIONS` |
| Watchdog: a batch that stopped moving | lane and progress both idle | no | yes | `watch_handoff`, `watch.tick` |
| Watchdog: found jobs that never reached the queue | "queued=0 while matched>N" | no | yes | `watch_handoff` |
| Watchdog: jobs left half-started by a crash | held rows re-checked, not re-sent | no | yes | `watch_handoff` |
| Nothing submitted without permission **and** a check | permission plus gate | yes | yes | `gates.OutboundGate` |
| Never invent a form answer | no answer on file ⇒ stop and ask | yes | yes | `gates.AnswerBank` |
| Personal identifiers always stop | regardless of the answer file | yes | yes | `ALWAYS_ASK` |
| Lane *phases* by time of day, borrow and lend | windows assigning lanes to bots | no | **no** | out of scope: see §9 |
| Read back the live form and compare before submitting | a browser-side submit guard | no | **no** | driver territory: see §9 |
| Per-application-system form handlers | one module per family | no | **no** | plugin territory: see §9 |

## 5. Mail, receipts and codes

| capability | reference behaviour | before | after | where it lives now |
|---|---|---|---|---|
| Read-only mailbox access behind an interface | any backend | yes | yes | `verify.MailReader` |
| A receipt upgrades "sent" to "confirmed" | sender, recipient, time window | yes | yes | `match_receipt` |
| Identity mail is never a receipt | — | yes | yes | `VERIFICATION_PHRASES` |
| A missing receipt never downgrades anything | fail open, in that one direction | yes | yes | `receipt_sweep` |
| Verification codes: sender, recipient, window, newest wins | all four must hold | yes | yes | `find_code` |
| The export must say what it searched | an export header, fail closed | no | yes | `check_export_header` |
| Switched on one application system at a time | per-family flags, all off | no | yes | `verify.email_codes.*` |
| A code that cannot be printed or logged | redaction enforced by the type | yes | yes | `verify.Code` |
| Never a password reset, a reset link, or a second code | no exceptions | yes | yes | `gates.is_password_reset` |
| Classify outcomes: test, interview, offer, rejection, reply | with the sentence that justified it | no | yes | `mail.classify` |
| Tie an outcome to a job before writing it | the posting's site, or the company in the subject | no | yes | `mail.triage` |
| Pull the date out of the message | several formats, year inferred forwards | no | yes | `mail.find_date` |
| Reminders morning and evening | 09:30 and 20:00 | no | yes | `mail.reminders`, two routines |
| A private note surfaced with each reminder | protected on the row | part | yes | `Appointment.note` |
| Starring important mail | the one write it was allowed | n/a | **no** | out of scope: strictly read-only here |

## 6. Accounts

| capability | reference behaviour | before | after | where it lives now |
|---|---|---|---|---|
| A registry of which employer sites need an account | keyed by tenant or board | no | yes | `accounts.py` |
| One employer per key on a shared application system | the host alone is not the key | no | yes | `accounts.site_key` |
| An account only where sign-up is an email confirmation | anything else is handed back | no | yes | `may_create` |
| Hand back a wall only the user can pass | in the user's own words | no | yes | `hand_back`, `WALLS` |
| Reported as counts and keys, never values | — | no | yes | `summary()` |
| Credentials stored | passwords in a private registry | n/a | **no** (by design) | nothing secret is stored at all |

## 7. Reporting, learning and health

| capability | reference behaviour | before | after | where it lives now |
|---|---|---|---|---|
| One summary a day, in plain language | no internal names | yes | yes | `report.digest` |
| At most one summary per day, however often asked | deduped | no | yes | `action_digest` |
| "Needs you" ranked and capped | at most three | yes | yes | `digest` |
| Rejections only if the user asked | — | yes | yes | `report_rejections` |
| An end-of-day note, even on a quiet day | always written | yes | yes | `report.reflection` |
| The end-of-day note **produces suggestions** | a trigger, not a diary | **no** | yes | `action_reflection` |
| A weekly review by source and by application system | yield, confirm rate, proposals | no | yes | `report.weekly_review` |
| Suggestions state evidence, effect, and ask | never applied by themselves | yes | yes | `lead.proposals` |
| Suggestions remembered across conversations | approve / decline later | yes | yes | `lead.save_proposals` |
| Change a setting in plain words | mapped, diffed, confirmed | yes | yes | `lead.interpret_request` |
| An approved change is written to a changelog | — | yes | yes | `_append_changelog` |
| Hourly health check, costing no model calls | queue leaks, stuck batches, idle lanes, logins | no | yes | `watch.py` |
| Confirmations drying up raises a proposal | the signature of a new form step | part | yes | `watch.tick`, `lead.proposals` |
| Quiet hours | no alerts inside the window | no | yes | `watch.in_quiet_hours` |
| Per-source and per-stage metric history | a metrics rollup | part | part | the weekly review computes them; no long history kept |

## 8. Setting it up, and the agent team

| capability | reference behaviour | before | after | where it lives now |
|---|---|---|---|---|
| One file the user owns | everything else derived | yes | yes | `config/preferences.yaml` |
| A conversation, not a file to edit | one question, a default, a consequence | yes | yes | `wizard.py` |
| **Asks where the CV is** | the document to attach | **no** | yes | `documents.resume` |
| **Builds the answer bank by asking** | the form answers | **no** | yes | `wizard.answer_questions` |
| A summary in prose, confirmed before anything is written | — | yes | yes | `summary_prose` |
| Re-running is safe; "change one thing" works | idempotent, diff-first | yes | yes | `interview(only=...)` |
| A login checklist: what, why, how to verify, what it never does | per platform | yes | yes | `logins.steps` |
| **A login check that actually reaches the platform** | opens the page read-only | **no** (settings only) | yes | `logins.LiveProbe` |
| **Non-interactive never reports a sign-in** | — | **no** | yes | `Checklist.walk` |
| A self-check that touches no account | `doctor` | yes | yes | `cmd_doctor` |
| An explanation generated from what is installed | cannot drift | yes | yes | `explain.py` |
| Role prompts, one per role | behaviour, not implementation | yes | yes | `agents/` |
| Engagement helpers: a network, a school platform, a startup list | off until switched on | yes | yes | `src/jobpilot/plugins/` |
| Declarative timetable covering everything | one entry per scheduled unit | part (7 entries) | yes (15) | `routines/routines.yaml` |
| Every timetable entry maps to a real callable | — | part | yes | `scheduler.resolve` |
| A helper's own routine resolves to something | — | **no** (reported a failure) | yes | `plugins.<name>.<action>` |
| The scheduler line names the real folder | — | **no** (`cd ~/jobpilot`) | yes | `cli.cron_line` |
| A systemd timer as well as cron | — | no | yes | `cli.systemd_snippet` |
| A cheap "is there work?" check before spending anything | precheck per bot | no | **part** | each routine exits early on an empty queue; no separate precheck |
| Several model providers with a fallback chain | typed failure, `answered_by` | yes | yes | `providers/` |
| A read-only reviewer model, and a sandboxed worker | separate guards | part | **part** | the provider interface supports the roles; the sandboxes are not reimplemented |

## 9. Deliberately not rebuilt

Each of these was in the reference system and is **not** here. They are left
out for a reason, not forgotten.

| left out | why |
|---|---|
| A browser driver that really fills in forms | It needs a real browser, a real model and a real account. It belongs in a plugin, outside a repository anyone can run offline, and the whole point of `ApplyDriver` is that the core cannot tell the difference. The dry-run driver ships; the submit path does not. |
| The browser-side submit guard and its canary | Only meaningful with a real browser attached. The *rule* it enforces survives as the outbound check plus "every job gets an outcome"; the mechanism belongs with the driver. |
| Per-application-system form handlers | Dozens of modules encoding the quirks of particular employers' systems. Each is a plugin; shipping them would mean shipping a guess about every one. |
| Lane phases by time of day, borrow and lend | Built for one machine with exactly three browsers and several competing bots. The generic part — admission on projected free memory — is in `LaneGuard`. The rest would be ceremony for a single user. |
| A registry of thousands of known job boards | That is data, and data is the one thing that must not be ported. The mechanism for reading a board is here; the list is the user's. |
| Description compaction before the model call | A cost optimisation that only pays at the reference system's volume, and one more place for the evidence to be damaged before the quote is checked. |
| Aggregator-to-employer URL resolution, archive crawling, source probes | Each is a source-specific scraper. They belong in source plugins. |
| Model-worker sandboxes (filesystem, process, shell allowlists) | They sandbox *one* machine's tools. The provider interface keeps the seam; the sandbox is the operator's choice. |
| Starring or labelling mail | The reference system allowed itself exactly one mailbox write. Here the mailbox is strictly read-only, which is easier to trust and easier to verify. |
| Storing employer-account credentials | The registry stores states, never secrets. A password belongs in the user's own password manager. |
| Numeric exit codes per guard | Refusals are typed and named instead. The codes were an operator interface for one machine's scripts; the names read better and survive refactoring. |
| Tracker rows, mail, run logs, metrics history, résumé content, company lists | **Data, not logic.** Nothing was ported. Every fixture and example here is synthetic. |

## 10. How this was checked

- `JOBPILOT_TEST=1 pytest -q` — the whole suite, with every door to the real
  world bolted (no network, no mailbox, no browser, no model tool).
- `scripts/sanitize_scan.py` — no personal data, no machine paths, no address
  outside the reserved example domains, no template placeholder in a real
  settings file.
- `scripts/migration_check.sh` — clone into a differently named folder, fresh
  virtual environment, install, `doctor`, the whole suite, and a scan of the
  clone.
- `tests/test_examples.py` — every example script runs offline and sends
  nothing.
- `tests/test_migration.py` — `doctor` from an unrelated directory, the
  timetable found without being told where it is, and every routine wired to a
  real callable.
