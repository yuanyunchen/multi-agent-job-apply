"""Running the timetable, safely, from something as dumb as cron.

``jobpilot routines run-due`` works out which routines are due, runs them, and
records when each one last ran. It is **idempotent**: calling it again straight
away does nothing, so it is safe to call every few minutes.

The schedule shapes in ``config/routines.yaml``:

* ``at: "08:00"`` with ``days:`` — once on each matching day, at or after that time;
* ``window: "09:30-18:00"`` — repeatedly while inside the window, at most once
  every ``every_minutes`` (default 60);
* ``every: "2 hours"`` — at most once per interval, all day.

Nothing here sends, submits or posts anything by itself: each action runs the
same code the command line runs, with the same permissions and the same gates.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .config import Config
from .domain import iso
from .routines import Routine, all_routines
from .ui import Renderer

DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DEFAULT_WINDOW_MINUTES = 60
STATE_FILE = "routines.json"


def _local_now(config: Config) -> datetime:
    """Now, in the timezone the user chose (falling back to this machine's)."""
    zone = str(config.get("timing.timezone") or "")
    if zone:
        try:
            from zoneinfo import ZoneInfo

            return datetime.now(ZoneInfo(zone))
        except Exception:  # an unknown zone name must not stop the timetable
            pass
    return datetime.now().astimezone()


def _parse_time(text: str) -> time | None:
    match = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", str(text or ""))
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def _days_allowed(spec: Any, moment: datetime) -> bool:
    text = str(spec or "daily").strip().lower()
    today = DAY_NAMES[moment.weekday()]
    if text in ("daily", "every day", "all", ""):
        return True
    if text in ("mon-fri", "weekdays"):
        return moment.weekday() < 5
    if text in ("sat-sun", "weekend", "weekends"):
        return moment.weekday() >= 5
    return today in {part.strip() for part in text.split(",")}


def _every_minutes(spec: Any) -> int | None:
    text = str(spec or "").strip().lower()
    match = re.match(r"^(\d+)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours)?$", text)
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2) or "minutes"
    return value * (60 if unit.startswith("h") else 1)


@dataclass
class State:
    """When each routine last ran. One small file, rewritten whole."""

    path: Path
    last_run: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, config: Config) -> "State":
        path = config.paths.ensure().state / STATE_FILE
        if not path.exists():
            return cls(path=path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return cls(path=path)
        runs = payload.get("last_run", {}) if isinstance(payload, dict) else {}
        return cls(path=path, last_run={str(k): str(v) for k, v in runs.items()})

    def when(self, name: str) -> datetime | None:
        raw = self.last_run.get(name)
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    def mark(self, name: str, moment: datetime) -> None:
        self.last_run[name] = moment.isoformat()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(
            json.dumps({"updated_at": iso(), "last_run": self.last_run}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp.replace(self.path)


def is_due(routine: Routine, last: datetime | None, moment: datetime) -> bool:
    """Should this routine run right now?"""
    schedule = routine.schedule
    if not _days_allowed(schedule.get("days"), moment):
        return False

    if "at" in schedule:
        at = _parse_time(schedule["at"])
        if at is None:
            return False
        scheduled = moment.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
        if moment < scheduled:
            return False
        return last is None or _as_aware(last, moment) < scheduled

    if "window" in schedule:
        start_text, _, end_text = str(schedule["window"]).partition("-")
        start, end = _parse_time(start_text), _parse_time(end_text)
        if start is None or end is None:
            return False
        inside = (
            start <= moment.time() <= end
            if start <= end
            else (moment.time() >= start or moment.time() <= end)  # a window over midnight
        )
        if not inside:
            return False
        gap = _every_minutes(schedule.get("every_minutes")) or DEFAULT_WINDOW_MINUTES
        return last is None or _as_aware(last, moment) <= moment - timedelta(minutes=gap)

    if "every" in schedule:
        gap = _every_minutes(schedule["every"])
        if gap is None:
            return False
        return last is None or _as_aware(last, moment) <= moment - timedelta(minutes=gap)

    return False


def _as_aware(moment: datetime, like: datetime) -> datetime:
    """Make ``moment`` comparable with ``like``, whichever of them knows its zone."""
    if like.tzinfo is None:
        return moment.replace(tzinfo=None)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=like.tzinfo or timezone.utc)
    return moment


def due(config: Config, *, now: datetime | None = None, state: State | None = None) -> list[Routine]:
    moment = now or _local_now(config)
    state = state or State.load(config)
    return [r for r in all_routines(config) if is_due(r, state.when(r.name), moment)]


# -- what each routine actually does -------------------------------------


def _say(text: str) -> str:
    return text


def action_search(config: Config, renderer: Renderer) -> str:
    from .providers import build_registry
    from .search import UrllibFetcher, run_search
    from .tracker import Tracker

    tracker = Tracker.from_config(config)
    registry = build_registry(config)
    try:
        browser = registry.for_role("browser")
    except Exception:
        browser = None
    report = run_search(config, UrllibFetcher(), known_keys=tracker.known_keys(), provider=browser)
    added = tracker.upsert((job.to_row() for job in report.jobs), caller="search").added
    return f"I looked for new openings and added {added} to my list."


def action_screen(config: Config, renderer: Renderer) -> str:
    from .cli import screen_new_rows

    reading = screen_new_rows(config)
    if reading.total == 0:
        return "There was nothing new to read."
    return (
        f"I read {reading.total} descriptions: {reading.kept} worth applying to, "
        f"{reading.dropped} ruled you out."
    )


def action_apply(config: Config, renderer: Renderer) -> str:
    from .apply import WaveRunner, describe

    runner = WaveRunner.build(config)
    result = runner.run(dry_run=not config.permitted("submit_applications"))
    return describe(result, renderer)


def action_digest(config: Config, renderer: Renderer) -> str:
    from .report import digest
    from .tracker import Tracker

    text = digest(Tracker.from_config(config).read(), config, renderer)
    path = config.paths.ensure().logs / f"digest-{datetime.now().date().isoformat()}.txt"
    path.write_text(text + "\n", encoding="utf-8")
    if config.permitted("send_digest_email"):
        return "I put your daily summary together and sent it."
    return "I put your daily summary together. (You have not asked me to email it, so it is saved for you.)"


def action_receipts(config: Config, renderer: Renderer) -> str:
    from .tracker import Tracker
    from .verify import reader_from_config, receipt_sweep

    reader = reader_from_config(config)
    if reader is None:
        return "I have no mailbox to check yet, so I left the applications as they are."
    tracker = Tracker.from_config(config)
    found = receipt_sweep(
        rows=tracker.read(),
        reader=reader,
        recipient=str(config.get("identity.apply_email", "")),
        window_minutes=int(config.get("verify.receipt_window_minutes", 10)),
    )
    for job_id, receipt in found:
        tracker.upsert(
            [{"job_id": job_id, "status": "applied", "receipt": receipt.as_row_field()}], caller="mail"
        )
    return f"I checked your mailbox and confirmed {len(found)} more applications arrived."


def action_reflection(config: Config, renderer: Renderer) -> str:
    from .report import append_reflection, reflection
    from .tracker import Tracker

    append_reflection(config, reflection(Tracker.from_config(config).read()))
    return ""  # the reflection is for me, not for the user


def action_proposals(config: Config, renderer: Renderer) -> str:
    from .lead import metrics, proposals, render_proposals, save_proposals
    from .tracker import Tracker

    rows = Tracker.from_config(config).read()
    items = proposals(metrics(rows), config)
    save_proposals(config, items)
    if not items:
        return ""
    return render_proposals(items)


#: Routine name in ``config/routines.yaml`` → what it does.
ACTIONS: dict[str, Callable[[Config, Renderer], str]] = {
    "search.daily_pass": action_search,
    "screen.pass": action_screen,
    "apply.waves": action_apply,
    "report.digest": action_digest,
    "verify.receipt_sweep": action_receipts,
    "report.reflection": action_reflection,
    "lead.proposals": action_proposals,
}


@dataclass
class RunReport:
    ran: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    said: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)

    def words(self) -> str:
        if not self.ran and not self.failed:
            return "Nothing was due just now."
        lines = [line for line in self.said if line.strip()]
        if self.failed:
            lines.append(
                "Some of it did not finish, and I will try again at the next opportunity."
            )
        return "\n".join(lines) if lines else "All done, with nothing worth reporting."


def run_due(
    config: Config,
    *,
    now: datetime | None = None,
    actions: dict[str, Callable[[Config, Renderer], str]] | None = None,
    renderer: Renderer | None = None,
    dry_run: bool = False,
) -> RunReport:
    """Run whatever is due. Safe to call repeatedly; safe to call from cron."""
    moment = now or _local_now(config)
    state = State.load(config)
    table = actions if actions is not None else ACTIONS
    renderer = renderer or Renderer(config.ui_mode)
    report = RunReport()

    for routine in all_routines(config):
        if not is_due(routine, state.when(routine.name), moment):
            report.skipped.append(routine.name)
            continue
        handler = table.get(routine.what)
        if handler is None:
            report.failed.append((routine.name, "nothing is wired up to do this yet"))
            continue
        if dry_run:
            report.ran.append(routine.name)
            report.said.append(f"(practice) {routine.explain()}")
            continue
        try:
            said = handler(config, renderer)
        except Exception as exc:  # one broken routine must not stop the rest
            report.failed.append((routine.name, str(exc)))
            continue
        state.mark(routine.name, moment)
        report.ran.append(routine.name)
        if said:
            report.said.append(said)

    if not dry_run:
        state.save()
    return report
