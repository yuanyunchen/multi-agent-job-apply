"""The command line.

    jobpilot start                 meet the team, then set it up with you
    jobpilot setup                 the setup conversation on its own
    jobpilot logins                walk the sign-ins, one platform at a time
    jobpilot status                how is it going? what needs you?
    jobpilot ask "..."             change a setting in your own words
    jobpilot approve <id>          say yes to a suggestion
    jobpilot decline <id>          say no to a suggestion
    jobpilot run search            look for jobs
    jobpilot run screen            read the new ones
    jobpilot run apply --dry-run   work through the list without sending anything
    jobpilot routines list         the timetable, in your words
    jobpilot routines run-due      run whatever is due (safe to call from cron)
    jobpilot digest                today's summary
    jobpilot doctor                check everything is set up properly

Every command prints plain language by default. ``--technical`` adds the detail.
Nothing here sends, submits or posts anything unless the settings say it may.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .config import EXAMPLE_CONFIG_PATH, Config, load, repo_root, settings_path
from .domain import Message
from .errors import JobpilotError
from .ui import Renderer, plural, verb


def _renderer(config: Config | None, technical: bool) -> Renderer:
    if technical:
        return Renderer(mode="technical")
    return Renderer(mode=config.ui_mode if config else "simple")


# -- commands ------------------------------------------------------------


def _settings_destination(args: argparse.Namespace) -> Path:
    """Where setup writes — the same place every other command reads from."""
    return settings_path(getattr(args, "out", None) or getattr(args, "config", None))


def _starting_point(destination: Path) -> dict:
    """What the conversation starts from: your settings if you have any, else the example."""
    import yaml

    from .config import DEFAULTS, _merge

    for candidate in (destination, repo_root() / EXAMPLE_CONFIG_PATH):
        if candidate.exists():
            raw = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
            if isinstance(raw, dict):
                return _merge(DEFAULTS, raw)
    return _merge(DEFAULTS, {})


def _build_asker(args: argparse.Namespace):
    """Who is answering: a person, a file of answers, or nobody (defaults)."""
    from .wizard import ConsoleAsker, ScriptedAsker, read_answers_file

    if getattr(args, "answers", None):
        return ScriptedAsker(answers=read_answers_file(args.answers))
    if getattr(args, "non_interactive", False):
        # Nobody to ask: take every default and confirm it.
        return ScriptedAsker(answers={})
    # A person typing, or answers piped in one line at a time. Either way, a
    # line that is not there means "use the default".
    return ConsoleAsker()


def cmd_start(args: argparse.Namespace) -> int:
    """Meet the team, then set it up — the whole first conversation."""
    from .explain import explain_team
    from .wizard import run as run_wizard

    destination = _settings_destination(args)
    data = _starting_point(destination)
    # The explanation is generated: it already covers the team, the timetable,
    # what needs you, the promises and everything you could switch on. Saying
    # any of it again here is how two versions of the truth start.
    print("Hello — I look for jobs you would want, apply to them, and tell you how it is going.\n")
    print(explain_team(Config(data)))
    print()

    if getattr(args, "explain_only", False):
        print("Next step: run 'jobpilot setup' and I will ask you a short list of questions.")
        return 0

    asker = _build_asker(args)
    result = run_wizard(asker=asker, base=data, destination=destination, intro=False)
    if not result.confirmed:
        return 1
    if getattr(args, "skip_logins", False):
        return 0
    return _walk_logins(
        load(result.saved_to or destination), asker, wait_for_user=_someone_is_there(args)
    )


def cmd_setup(args: argparse.Namespace) -> int:
    """The setup conversation: questions, a summary to confirm, then saving."""
    from .wizard import run as run_wizard

    destination = _settings_destination(args)
    if destination.exists() and not args.force:
        print("You already have settings. Run 'jobpilot setup --force' to go through the questions again.")
        return 1
    result = run_wizard(asker=_build_asker(args), base=_starting_point(destination), destination=destination)
    return 0 if result.confirmed else 1


def _walk_logins(config: Config, asker, *, wait_for_user: bool = True) -> int:
    from .logins import Checklist, LiveProbe

    # The probe is what makes "ready" mean something: it opens the mailbox or
    # the page and reports what it actually saw. Without somebody there to sign
    # in, the walk ignores it and never claims a sign-in.
    results = Checklist(config, probe=LiveProbe(config)).walk(asker, wait_for_user=wait_for_user)
    return 0 if all(r.state != "needs_help" for r in results) else 1


def _someone_is_there(args: argparse.Namespace) -> bool:
    """Is there a person to answer? Never wait on an input nobody is using."""
    if getattr(args, "non_interactive", False):
        return False
    if getattr(args, "answers", None):
        return True
    try:
        return sys.stdin.isatty()
    except ValueError:  # the input was closed under us
        return False


def cmd_logins(args: argparse.Namespace) -> int:
    """Walk the sign-ins on their own, without the rest of setup."""
    return _walk_logins(load(args.config), _build_asker(args), wait_for_user=_someone_is_there(args))


def cmd_status(args: argparse.Namespace) -> int:
    config = load(args.config)
    renderer = _renderer(config, args.technical)
    from .catalog import model_jobs, status_lines
    from .lead import render_proposals
    from .queue import depth
    from .report import summarize
    from .routines import all_routines, timetable
    from .tracker import Tracker

    rows = Tracker.from_config(config).read()
    numbers = summarize(rows)
    sizes = depth(rows)
    print(
        renderer.render(
            Message(
                "status",
                f"So far: {plural(numbers.applied, 'application')} confirmed, "
                f"{numbers.sent_waiting} waiting for a confirmation, "
                f"{plural(sizes['total'], 'job')} still on my list.",
                technical=f"statuses: {Tracker.from_config(config).counts()}",
            )
        )
    )
    if numbers.needs_you:
        count = len(numbers.needs_you)
        print(f"\n{plural(count, 'thing')} {verb(count, 'needs', 'need')} you:")
        for item in numbers.needs_you[:3]:
            print(f"  - {item}")

    print("\nWhat happens by itself:")
    print(timetable(all_routines(config), config))

    print("\nWhat is switched on:")
    for line in status_lines(config):
        print(line)
    if renderer.technical:
        print("\nWho is doing the thinking:")
        for line in model_jobs(config):
            print(line)

    suggestions = _fresh_proposals(config, rows)
    if suggestions:
        print()
        print(render_proposals(suggestions))
    return 0


def _fresh_proposals(config: Config, rows: list[dict]) -> list:
    """Work out today's suggestions and remember them, so 'approve' can find them."""
    from .lead import metrics, proposals, save_proposals

    return save_proposals(config, proposals(metrics(rows), config))


def cmd_ask(args: argparse.Namespace) -> int:
    """Change a setting in your own words. Nothing happens without your yes."""
    from .lead import interpret_request, save_proposals
    from .providers import build_registry

    config = load(args.config)
    provider = build_registry(config).for_role("review")
    proposal = interpret_request(" ".join(args.words), config, provider, proposal_id="your-request")
    save_proposals(config, [proposal])
    print(proposal.text)
    print(f"\nWhat you would notice: {proposal.expected_effect}")
    print("\nI have changed nothing yet. Say 'jobpilot approve your-request' and I will.")
    return 0


def cmd_decide(args: argparse.Namespace) -> int:
    """Say yes or no to a suggestion."""
    from .lead import decide
    from .tracker import Tracker

    config = load(args.config)
    approve = args.command == "approve"
    _updated, line = decide(
        config,
        args.id,
        approve=approve,
        by="you",
        config_path=str(config.source) if config.source else None,
        tracker=Tracker.from_config(config),
    )
    print(line)
    if approve:
        print("I will use the new setting from the next time I look for jobs.")
    return 0


def cmd_routines(args: argparse.Namespace) -> int:
    """The timetable, and the one command cron needs."""
    from .routines import all_routines, timetable
    from .scheduler import due, run_due

    config = load(args.config)
    renderer = _renderer(config, args.technical)
    routines = all_routines(config)

    moment = _moment(args)
    if args.action == "list":
        print("What happens by itself:")
        print(timetable(routines, config))
        waiting = due(config, now=moment)
        if waiting:
            print(f"\nDue right now: {plural(len(waiting), 'thing')}.")
        if renderer.technical:
            print("\nTo let this run by itself, add one line to your crontab:")
            print(cron_line(config))
            print("\nOr, with systemd:")
            print(systemd_snippet(config))
        return 0

    report = run_due(config, now=moment, renderer=renderer, dry_run=args.dry_run)
    print(report.words())
    if renderer.technical:
        print(f"ran={report.ran} failed={report.failed}")
    return 0 if not report.failed else 1


def _moment(args: argparse.Namespace):
    """``--now`` lets you ask "what would happen at this time?". Optional."""
    from datetime import datetime

    raw = getattr(args, "now", None)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError as exc:
        raise JobpilotError(
            f"I could not read {raw!r} as a date and time.",
            hint="Write it like 2026-11-09T08:00 .",
        ) from exc


def cron_line(config: Config | None = None) -> str:
    """The one line a user adds to run the timetable by itself.

    The folder is the one they actually cloned into, and the log sits in their
    own data directory — both worked out when asked. A printed line with a
    guessed folder name in it is a line that does not work.
    """
    root = repo_root()
    logs = config.paths.logs if config is not None else Path("~/.jobpilot/logs").expanduser()
    return (
        f"*/10 * * * * cd {shorten(root)} && "
        f"jobpilot routines run-due >> {shorten(logs)}/cron.log 2>&1"
    )


def systemd_snippet(config: Config | None = None) -> str:
    """The same timetable as a systemd user timer, for people who prefer it."""
    root = repo_root()
    return "\n".join(
        [
            "# ~/.config/systemd/user/jobpilot.service",
            "[Service]",
            "Type=oneshot",
            f"WorkingDirectory={shorten(root)}",
            "ExecStart=%h/.local/bin/jobpilot routines run-due",
            "",
            "# ~/.config/systemd/user/jobpilot.timer",
            "[Timer]",
            "OnCalendar=*:0/10",
            "Persistent=true",
            "[Install]",
            "WantedBy=timers.target",
        ]
    )


def shorten(path: Path | str) -> str:
    """Write a path under the home directory as ``~/...``; leave the rest alone."""
    try:
        return "~/" + str(Path(path).resolve().relative_to(Path.home()))
    except (ValueError, OSError, RuntimeError):
        return str(path)


def cmd_digest(args: argparse.Namespace) -> int:
    config = load(args.config)
    renderer = _renderer(config, args.technical)
    from .lead import render_proposals
    from .report import digest
    from .tracker import Tracker

    rows = Tracker.from_config(config).read()
    print(digest(rows, config, renderer))
    suggestions = _fresh_proposals(config, rows)
    if suggestions:
        print()
        print(render_proposals(suggestions))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    config = load(args.config)
    renderer = _renderer(config, args.technical)
    if args.stage == "search":
        return _run_search(config, renderer, args)
    if args.stage == "screen":
        return _run_screen(config, renderer, args)
    return _run_apply(config, renderer, args)


def _run_search(config: Config, renderer: Renderer, args: argparse.Namespace) -> int:
    from .providers import build_registry
    from .search import UrllibFetcher, run_search
    from .tracker import Tracker

    tracker = Tracker.from_config(config)
    registry = build_registry(config)
    try:
        browser = registry.for_role("browser")
    except JobpilotError:
        browser = None
    report = run_search(config, UrllibFetcher(), known_keys=tracker.known_keys(), provider=browser)
    print(
        renderer.render(
            Message(
                "search",
                f"I looked around and found {plural(report.new, 'new job', 'new jobs')} worth reading.",
                technical=f"fetched={report.fetched} unique={report.unique} per source={report.per_source}",
            )
        )
    )
    if args.dry_run:
        print("This was a practice run, so I did not write anything down.")
        return 0
    result = tracker.upsert((job.to_row() for job in report.jobs), caller="search")
    print(f"I added {plural(result.added, 'job')} to my list.")
    return 0


def jobs_awaiting_reading(config: Config) -> tuple[list, dict]:
    """The rows nobody has read yet, as jobs. Shared by the command and the timetable."""
    from .domain import Job
    from .tracker import Tracker

    tracker = Tracker.from_config(config)
    rows = [row for row in tracker.read() if row.get("status") == "new"]
    jobs = [
        Job(
            company=str(row.get("company", "")),
            title=str(row.get("title", "")),
            url=str(row.get("url", "")),
            source=str(row.get("source", "")),
            ats=str(row.get("ats", "")),
            ats_job_id=str(row.get("ats_job_id", "")),
            location=str(row.get("location", "")),
            description=str(row.get("description", "")),
            posted_at=str(row.get("posted_at", "")),
            id_hint=str(row.get("job_id", "")),
        )
        for row in rows
    ]
    return jobs, {"tracker": tracker}


@dataclass
class Reading:
    """What came of reading a batch of descriptions, with examples to show."""

    kept: int = 0
    dropped: int = 0
    reviewed: int = 0
    examples_kept: list[str] = field(default_factory=list)
    examples_skipped: list[tuple[str, str]] = field(default_factory=list)  # (job, the sentence)

    @property
    def total(self) -> int:
        return self.kept + self.dropped + self.reviewed


def screen_new_rows(config: Config, *, write: bool = True) -> Reading:
    """Read every new description and record the verdicts."""
    from .providers import build_registry
    from .screen import decision_to_update, screen

    jobs, extra = jobs_awaiting_reading(config)
    reading = Reading()
    if not jobs:
        return reading
    outcome = screen(jobs, config, build_registry(config).for_role("screen"))
    by_id = {job.job_id: job for job in jobs}

    for decision in outcome.decisions:
        job = by_id.get(decision.job_id)
        label = f"{job.company} — {job.title}" if job else "a job"
        if decision.verdict == "keep":
            reading.kept += 1
            if len(reading.examples_kept) < 2:
                reading.examples_kept.append(label)
        elif decision.verdict == "drop":
            reading.dropped += 1
            if len(reading.examples_skipped) < 1:
                reading.examples_skipped.append((label, decision.quote or decision.reason))
        else:
            reading.reviewed += 1

    if write:
        updates = [
            decision_to_update(by_id[d.job_id], d) for d in outcome.decisions if d.job_id in by_id
        ]
        extra["tracker"].upsert(updates, caller="screen", require_verdict=True)
    return reading


def _run_screen(config: Config, renderer: Renderer, args: argparse.Namespace) -> int:
    reading = screen_new_rows(config, write=not args.dry_run)
    if reading.total == 0:
        print("There is nothing new to read right now.")
        return 0
    print(
        renderer.render(
            Message(
                "screen",
                f"I read {plural(reading.total, 'job')}: {reading.kept} look worth applying to and "
                f"{reading.dropped} rule you out.",
                technical=(
                    f"kept={reading.kept} dropped={reading.dropped} "
                    f"kept for a closer look={reading.reviewed}"
                ),
            )
        )
    )
    if reading.examples_kept:
        print("For example, I would apply to: " + "; ".join(reading.examples_kept) + ".")
    for label, why in reading.examples_skipped:
        # The sentence is the whole point: it is why you can check my reasoning.
        print(f'I skipped {label}, because the posting says: "{why}"')
    if reading.reviewed:
        kept_back = "one" if reading.reviewed == 1 else str(reading.reviewed)
        print(f"I kept {kept_back} for a closer look rather than guessing.")
    if args.dry_run:
        print("This was a practice run, so I did not change anything.")
    return 0


def _run_apply(config: Config, renderer: Renderer, args: argparse.Namespace) -> int:
    from .apply import WaveRunner, describe

    runner = WaveRunner.build(config)
    result = runner.run(dry_run=args.dry_run or not config.permitted("submit_applications"))
    print(describe(result, renderer))
    if result.questions:
        print("\nI need your answer to these before I can finish:")
        for question in result.questions[:5]:
            print(f"  - {question}")
    return 0


def cmd_templates(args: argparse.Namespace) -> int:
    """The bot templates: the team, ready to hand to a bot product.

    Reads only, and needs no settings — somebody looking at the templates has
    not set anything up yet, which is rather the point of looking.
    """
    from . import templates

    if args.action == "list":
        print(templates.summary())
        return 0

    if not args.role:
        raise JobpilotError(
            f"Tell me which role to {args.action}.",
            hint=f"For example: jobpilot templates {args.action} lead",
        )
    template = templates.load(args.role)
    if args.action == "export":
        print(template.share_json())
        return 0
    print(template.words())
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Check everything without touching a single account."""
    from .accounts import AccountRegistry
    from .gates import AnswerBank, LaneGuard
    from .plugins import discover
    from .providers import ROLES, build_registry, role_words
    from .routines import all_routines
    from .scheduler import resolve
    from .testmode import is_test_mode
    from .tracker import Tracker
    from .watch import freshly_found, last_submit_from_rows, login_states_from_disk, tick

    problems = 0
    rows: list[dict] = []
    try:
        config = load(args.config)
    except JobpilotError as exc:
        print(str(exc))
        return 1
    print(f"Settings: fine ({config.source}).")

    paths = config.paths
    # Whether the data folder is usable decides how much else can be checked:
    # everything below that reads the record needs it. A check that cannot run
    # is reported as a sentence like all the others — the whole purpose of this
    # command is that it never ends in a stack trace.
    usable = True
    try:
        paths.ensure()
        print(f"My own files: fine ({paths.data_dir}).")
    except OSError as exc:
        usable = False
        problems += 1
        print(f"My own files: I cannot write to {paths.data_dir} ({exc}).")
        print("  Everything below that needs my own files is skipped until that is fixed.")

    if usable:
        try:
            rows = Tracker.from_config(config).read()
            print(f"Your application record: fine ({plural(len(rows), 'job')} on file).")
        except (JobpilotError, OSError) as exc:
            problems += 1
            print(f"Your application record: {exc}")

    answers = AnswerBank.from_config(config)
    if answers.entries:
        print(f"Your answers: fine ({plural(len(answers.entries), 'answer')} written down).")
    else:
        print("Your answers: none yet, so forms with questions will wait for you.")

    resume = config.user_path("documents.resume")
    if resume is None:
        print("Your CV: I do not know where it is, so applications needing one will wait.")
    elif resume.exists():
        print("Your CV: fine (I know where it is, and I attach exactly that file).")
    else:
        problems += 1
        print(f"Your CV: I cannot find it where you said it was ({resume}).")

    registry = build_registry(config)
    # Reaching a model tool is deliberately impossible in test mode (see
    # testmode.ensure_live), which is also the mode the examples and the
    # dry runs use. "I cannot use one" is the expected answer there, so it is
    # reported and not counted: otherwise this command would fail on every
    # machine that simply has no model tools installed, which is most of them.
    # In real use a model nobody can reach is still something to fix.
    for_real = not is_test_mode()
    for role in ROLES:
        candidates = registry.candidates(role)
        healthy = [name for name in candidates if registry.health_of(name).ok]
        if healthy:
            spare = len(healthy) - 1
            extra = f" (with {plural(spare, 'spare')} if it is busy)" if spare else ""
            print(f"Model for {role_words(role)}: fine{extra}.")
        else:
            why = "; ".join(registry.health_of(name).detail for name in candidates) or "nothing is set up"
            if for_real:
                problems += 1
                print(f"Model for {role_words(role)}: not usable — {why}.")
            else:
                print(f"Model for {role_words(role)}: not checked — {why}.")

    guard = LaneGuard.from_config(config)
    admission = guard.admit(running=0)
    print(
        "Room to work: fine."
        if admission.allowed
        else f"Room to work: {admission.reason}"
    )

    for manifest in discover():
        state = "on" if config.plugin_enabled(manifest.name) else "off"
        print(f"Helper '{manifest.name}': {state}.")

    if usable:
        waiting = AccountRegistry.from_config(config).needing_user()
        if waiting:
            print(
                f"Employer sign-ups: {plural(len(waiting), 'one')} "
                f"{verb(len(waiting), 'is', 'are')} waiting for you."
            )
            for account in waiting:
                print(f"  - {account.words}")
        else:
            print("Employer sign-ups: nothing waiting for you.")

    # Every timetable entry must have something behind it; an entry that cannot
    # run is a promise that fails silently every time it comes due.
    routines = all_routines(config)
    unwired = [routine.name for routine in routines if resolve(routine.what) is None]
    if unwired:
        problems += 1
        print(
            f"Timetable: {plural(len(unwired), 'thing')} "
            f"{verb(len(unwired), 'is', 'are')} scheduled but cannot run."
        )
    else:
        print(f"Timetable: {plural(len(routines), 'routine')}, all of them ready to run.")

    if usable:
        health = tick(
            config,
            rows=rows,
            found_recently=freshly_found(rows),
            last_submit_at=last_submit_from_rows(rows),
            login_states=login_states_from_disk(config),
        )
        if health.healthy:
            print("Health: nothing looks stuck.")
        else:
            print("Health:")
            for alert in health.alerts:
                print(f"  - {alert.detail}")
    allowed = [a for a in ("submit_applications", "send_outreach_messages", "post_public_comments")
               if config.permitted(a)]
    print(
        "Permissions: nothing may be sent or submitted yet."
        if not allowed
        else "Permissions: allowed to " + ", ".join(a.replace("_", " ") for a in allowed) + "."
    )
    if problems:
        print(
            f"\n{plural(problems, 'thing')} {verb(problems, 'needs', 'need')} fixing "
            "before I can run on my own."
        )
        return 1
    print("\nEverything checks out.")
    return 0


# -- wiring --------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobpilot", description="A job-application assistant.")
    parser.add_argument("--version", action="version", version=f"jobpilot {__version__}")
    parser.add_argument("--config", default=None, help="a settings file other than the usual one")
    parser.add_argument("--technical", action="store_true", help="show the details as well")
    sub = parser.add_subparsers(dest="command", required=True)

    def conversational(command: argparse.ArgumentParser) -> argparse.ArgumentParser:
        command.add_argument("--answers", default=None, help="a file of answers, instead of typing them")
        command.add_argument(
            "--non-interactive", action="store_true", help="take every default without asking"
        )
        return command

    start = conversational(sub.add_parser("start", help="meet the team, then set it up with you"))
    start.add_argument("--out", default=None, help="write the settings somewhere else")
    start.add_argument("--explain-only", action="store_true", help="just explain, change nothing")
    start.add_argument("--skip-logins", action="store_true", help="leave the sign-ins for later")
    start.set_defaults(func=cmd_start)

    setup = conversational(sub.add_parser("setup", help="the setup conversation"))
    setup.add_argument("--out", default=None)
    setup.add_argument("--force", action="store_true", help="go through the questions again")
    setup.set_defaults(func=cmd_setup)

    conversational(sub.add_parser("logins", help="walk the sign-ins one at a time")).set_defaults(
        func=cmd_logins
    )

    sub.add_parser("status", help="how is it going?").set_defaults(func=cmd_status)
    sub.add_parser("digest", help="today's summary").set_defaults(func=cmd_digest)
    sub.add_parser("doctor", help="check everything is set up properly").set_defaults(func=cmd_doctor)

    ask = sub.add_parser("ask", help="change a setting in your own words")
    ask.add_argument("words", nargs="+", help='for example: "also include data scientist roles"')
    ask.set_defaults(func=cmd_ask)

    for verb, helptext in (("approve", "say yes to a suggestion"), ("decline", "say no to a suggestion")):
        decision = sub.add_parser(verb, help=helptext)
        decision.add_argument("id", help="the name I gave the suggestion")
        decision.set_defaults(func=cmd_decide)

    bots = sub.add_parser("templates", help="the team, one template per role")
    bots.add_argument("action", choices=["list", "show", "export"], nargs="?", default="list")
    bots.add_argument("role", nargs="?", default="", help="which role, for show and export")
    bots.set_defaults(func=cmd_templates)

    routines = sub.add_parser("routines", help="the timetable")
    routines.add_argument("action", choices=["list", "run-due"], nargs="?", default="list")
    routines.add_argument("--dry-run", action="store_true", help="say what is due, run nothing")
    routines.add_argument("--now", default=None, help="pretend it is this time, e.g. 2026-11-09T08:00")
    routines.set_defaults(func=cmd_routines)

    run = sub.add_parser("run", help="run one stage")
    run.add_argument("stage", choices=["search", "screen", "apply"])
    run.add_argument("--dry-run", action="store_true", help="change nothing and send nothing")
    run.set_defaults(func=cmd_run)

    # ``--technical`` is accepted after the command too ("jobpilot status --technical"),
    # which is how the documentation writes it. SUPPRESS keeps the top-level value
    # when the flag is not repeated after the command.
    for command in sub.choices.values():
        command.add_argument(
            "--technical", action="store_true", default=argparse.SUPPRESS, help="show the details as well"
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except JobpilotError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:  # pragma: no cover
        print("\nStopped. Nothing was left half-done.", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
