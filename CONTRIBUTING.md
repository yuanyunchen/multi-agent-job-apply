# Contributing

Thanks for looking. This is a small, deliberately boring codebase: the
interesting part is the guarantees it keeps, and most review effort goes into
not weakening them.

## Development setup

```bash
python -m venv .venv && . .venv/bin/activate   # Python 3.11+
pip install -e ".[dev]"
python -m pytest -q
```

Runtime dependencies are **PyYAML and the standard library**. Please do not add
more without a good reason: this runs on other people's laptops.

## Tests

```bash
python -m pytest -q                    # everything, in a few seconds
python -m pytest -q tests/test_rules.py
```

Two rules about tests, both enforced by the suite itself:

1. **Tests can never reach the real world.** `tests/conftest.py` sets
   `JOBPILOT_TEST=1`, and with that set the real HTTP fetcher, the real mailbox
   reader, any real apply driver and every model command line raise
   `TestModeViolation`. Use `FixtureFetcher`, `FakeMailReader`, `DryRunDriver`
   and `FakeProvider`. If you add a new door to the outside world, call
   `testmode.ensure_live("...")` behind it and add a case to
   `tests/test_testmode.py`.
2. **Fixtures are synthetic.** Invented companies (Acme Robotics, Globex
   Systems, Northwind Analytics, Umbrella Logistics, Stark Grid), invented
   postings, invented mail, `example.test` addresses. See `tests/synthetic.py`.

The suite also asserts that no test writes into the checkout's `config/`
folder, and that no module contains a path from somebody's computer.

## The sanitization rule

This is a public repository used by real job seekers.

- **No personal data anywhere.** No real names, email addresses, phone numbers,
  schools, employers, account handles, tokens or machine paths — not in code,
  tests, fixtures, docs or commit messages.
- Use `{{PLACEHOLDER}}` in example files and synthetic values everywhere else.
- Paths come from settings or the environment. `~/.jobpilot` and repository-
  relative paths are fine; `/home/...`, `/Users/...` and `/workspace/...` are
  not, including in documentation.
- Plugin prompts (`src/jobpilot/plugins/*/agent.md`) are templated from settings and
  must contain no personal data of any kind.

## Writing a plugin

Four extension points. Each is a small protocol, and the core only ever sees the
protocol.

### A search source

```python
class MySource:
    name = "my-source"

    def fetch(self, fetcher):           # fetcher.get_json(url) -> parsed JSON
        yield Job(company="Acme Robotics", title="...", url="...", source=self.name)
```

Take the fetcher as an argument — never import `urllib` yourself — so tests can
hand you fixtures. Report a source that is down in `self.errors` rather than
raising. Rows you return face exactly the same rules and the same reading step
as everything else; do not pre-filter and do not summarise a description.

### An apply driver

```python
class MyDriver:
    name = "my-driver"

    def questions(self, row) -> list[str]: ...
    def apply(self, request) -> ApplyOutcome: ...
```

`request.dry_run` **must** be honoured: with it set, look but change nothing.
Answers arrive in `request.answers` and come only from the user's answer file —
never invent one, and never fall back to "the closest option". Return exactly
one outcome per job: `submitted`, `parked`, `blocked` or `skipped`. If you drive
a real browser, inherit from `BrowserDriverBase` so the test-mode guard applies.

### A model provider

```python
class MyProvider:
    name = "my-provider"
    capabilities = frozenset({"screen", "review"})

    def complete(self, prompt, *, schema=None, timeout=600) -> ModelResult: ...
    def health(self) -> Health: ...
```

`health()` must be cheap and must touch no account. `complete()` must call
`testmode.ensure_live(...)` if it uses the network or a subprocess, must scrub
credential-shaped strings out of what it returns, and must report a failure as
`ModelResult(ok=False, failure=...)` rather than raising. Add it to
`jobpilot/catalog.py` so it appears in the setup conversation, the README table
and `status` — a provider nobody can discover may as well not exist.

### A mailbox reader

```python
class MyReader:
    def messages(self, *, since, until, recipient="") -> list[MailMessage]: ...
```

Read-only. There is deliberately no other verb. Never return a message's
verification code as plain text — wrap it in `verify.Code`, which cannot be
printed.

### The manifest

A plugin is a directory under `src/jobpilot/plugins/<name>/` with `plugin.yaml`, an
`__init__.py` and (if it drives a browser) `agent.md`. The manifest is what the
user is shown, so `summary` and `explain` are written for them, not for you. If
your plugin needs a login, `enabled_default` **must** be `false` — the loader
refuses a manifest that says otherwise.

Outbound actions (anything sent, posted or submitted) must go through
`OutboundGate` and declare themselves in `outbound_actions`. A blocked action is
a hard skip: never reword it and try again.

## The guarantees, and how to not break them

If a change touches one of these, say so in the pull request and add a test:

| guarantee | where it lives |
|---|---|
| rules only flag; a model decides | `rules.py`, `screen.py` |
| a drop needs a verbatim quote, verified against the posting | `screen.quote_is_verbatim` |
| one writer, atomic write, backups, append-only event log | `tracker.py` |
| never re-apply; reopening a skip needs the user | `tracker._guard` |
| an answer comes from the answer file or the job stops | `gates.AnswerBank` |
| nothing leaves the machine without permission *and* a gate pass | `gates.OutboundGate` |
| no password resets, anywhere | `gates.is_password_reset`, `verify.py` |
| a receipt needs sender, recipient and a time window to match | `verify.match_receipt` |
| a verification code cannot be printed | `verify.Code` |
| the Lead proposes, the user decides | `lead.apply_proposal`, `lead.decide` |
| simple mode contains no jargon | `ui.lint_plain`, `tests/test_plain_language.py` |
| tests cannot touch the real world | `testmode.py` |

## Style

- Small modules with a docstring that says *why*, not *what*.
- Names a non-programmer could read out loud. User-facing strings are sentences.
- An error a user can see must say what to do about it — see `errors.py`.
- No new concepts in the settings file unless a user would ask for them by name.

## Pull requests

Describe the behaviour change in the words a user would use, then the mechanism.
Run `python -m pytest -q` and paste the summary line. If you changed anything
user-facing, paste the before and after output.
