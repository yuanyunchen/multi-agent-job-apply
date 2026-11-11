"""The hourly health check: is anything quietly stuck?

The failures that cost the most are the silent ones. Nothing crashes, no error
appears, and a week later nothing has gone out. This module is the cheap,
frequent check for exactly those:

* **a leaking queue** — plenty found, nothing queued;
* **a stuck batch** — a list handed out that stopped moving;
* **idle capacity** — jobs waiting while nothing is being worked on;
* **a sign-in that has stopped working** — reported as "it needs you", never
  as an error the user cannot act on;
* **confirmations drying up** — applications going out and never coming back,
  which is what an application system silently adding a new step looks like.

It costs no model calls, reads nothing outside this machine, and writes only
its own alert file. Every alert carries the evidence and a plain sentence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from .config import Config
from .domain import iso, now
from .queue import depth
from .verify import unconfirmed_rate

#: How bad something is. ``needs_you`` means only the user can fix it.
LEVELS = ("ok", "watch", "needs_you")

#: Thresholds. All overridable from the settings under ``watch:``.
DEFAULTS = {
    "idle_minutes": 60,
    "stuck_minutes": 40,
    "unconfirmed_rate": 0.4,
    "unconfirmed_minimum": 5,
    "quiet_hours_start": "",  # e.g. "22:00" — no alerts raised inside the window
    "quiet_hours_end": "",
}


@dataclass(frozen=True, slots=True)
class Alert:
    code: str
    level: str
    detail: str  # plain language, safe to show the user
    technical: str = ""

    @property
    def needs_user(self) -> bool:
        return self.level == "needs_you"


@dataclass
class Tick:
    """One health check. ``alerts`` is empty on a healthy system."""

    at: str = ""
    alerts: list[Alert] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return not self.alerts

    def words(self) -> str:
        if self.healthy:
            return "Everything is moving as it should."
        lines = []
        for alert in self.alerts:
            lines.append(f"- {alert.detail}")
        if any(alert.needs_user for alert in self.alerts):
            lines.append("The ones above that mention you are the only ones I cannot sort out myself.")
        return "\n".join(lines)

    def as_dict(self) -> dict[str, Any]:
        return {
            "at": self.at,
            "checked": self.checked,
            "alerts": [
                {"code": a.code, "level": a.level, "detail": a.detail, "technical": a.technical}
                for a in self.alerts
            ],
        }


def _setting(config: Config, key: str) -> Any:
    return config.get(f"watch.{key}", DEFAULTS[key])


def in_quiet_hours(config: Config, moment: datetime) -> bool:
    """Inside the user's quiet hours nothing is raised; it waits for the morning."""
    start, end = str(_setting(config, "quiet_hours_start")), str(_setting(config, "quiet_hours_end"))
    if not start or not end:
        return False
    try:
        hour_start = datetime.strptime(start, "%H:%M").time()
        hour_end = datetime.strptime(end, "%H:%M").time()
    except ValueError:
        return False
    current = moment.time()
    if hour_start <= hour_end:
        return hour_start <= current <= hour_end
    return current >= hour_start or current <= hour_end


def tick(
    config: Config,
    *,
    rows: Iterable[dict],
    found_recently: int = 0,
    last_submit_at: datetime | None = None,
    pin_progress_at: datetime | None = None,
    pin_outstanding: int = 0,
    login_states: dict[str, str] | None = None,
    moment: datetime | None = None,
) -> Tick:
    """Run every check once. Nothing here changes anything."""
    at = moment or now()
    rows = list(rows)
    result = Tick(at=iso(at))
    if in_quiet_hours(config, at):
        result.checked.append("quiet hours — nothing raised")
        return result

    sizes = depth(rows)
    idle_limit = int(_setting(config, "idle_minutes"))
    stuck_limit = int(_setting(config, "stuck_minutes"))

    # 1. the queue leak
    result.checked.append("jobs found actually reached the list")
    if found_recently > 0 and sizes["total"] == 0:
        result.alerts.append(
            Alert(
                "queue_leak",
                "watch",
                f"I found {found_recently} matching jobs today but none of them reached my list.",
                technical=f"found={found_recently} queue_depth=0",
            )
        )

    # 2. a batch that stopped moving
    result.checked.append("the batch being worked on is moving")
    if pin_outstanding > 0 and pin_progress_at is not None:
        idle = (at - _aware(pin_progress_at, at)).total_seconds() / 60
        if idle >= stuck_limit:
            result.alerts.append(
                Alert(
                    "batch_stuck",
                    "watch",
                    "A batch of applications has not moved for a while. I will start it again after "
                    "checking nothing was already sent.",
                    technical=f"idle_minutes={int(idle)} outstanding={pin_outstanding}",
                )
            )

    # 3. idle while there is work
    result.checked.append("capacity is being used")
    if sizes["total"] > 0 and last_submit_at is not None:
        idle = (at - _aware(last_submit_at, at)).total_seconds() / 60
        if idle >= idle_limit:
            result.alerts.append(
                Alert(
                    "idle_with_work",
                    "watch",
                    f"{sizes['total']} jobs are waiting and nothing has gone out for a while.",
                    technical=f"idle_minutes={int(idle)} queue_depth={sizes['total']}",
                )
            )

    # 4. a sign-in that has stopped working
    result.checked.append("the sign-ins still work")
    for name, state in sorted((login_states or {}).items()):
        if state == "needs_help":
            result.alerts.append(
                Alert(
                    f"login:{name}",
                    "needs_you",
                    f"{name} wants you to sign in again. Open it in your browser, sign in, and "
                    "tell me when you are done — everything else keeps running.",
                    technical=f"login state for {name} is {state}",
                )
            )

    # 5. confirmations drying up
    result.checked.append("applications are being confirmed")
    rate, unconfirmed, considered = unconfirmed_rate(rows)
    minimum = int(_setting(config, "unconfirmed_minimum"))
    if considered >= minimum and rate >= float(_setting(config, "unconfirmed_rate")):
        result.alerts.append(
            Alert(
                "confirmations_low",
                "watch",
                f"{unconfirmed} of the last {considered} applications never came back with a "
                "confirmation, which usually means a site has added a step.",
                technical=f"unconfirmed_rate={rate:.2f}",
            )
        )
    return result


def _aware(moment: datetime, like: datetime) -> datetime:
    if like.tzinfo is None:
        return moment.replace(tzinfo=None)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=like.tzinfo)
    return moment


def record(config: Config, result: Tick, *, keep: int = 200) -> Path:
    """Append the tick to the health log, oldest lines dropped."""
    path = config.paths.ensure().logs / "health.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    lines.append(json.dumps(result.as_dict(), sort_keys=True))
    path.write_text("\n".join(lines[-keep:]) + "\n", encoding="utf-8")
    return path


def last_tick(config: Config) -> Tick | None:
    path = config.paths.ensure().logs / "health.jsonl"
    if not path.exists():
        return None
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return None
    payload = json.loads(lines[-1])
    return Tick(
        at=str(payload.get("at", "")),
        checked=[str(c) for c in payload.get("checked", [])],
        alerts=[
            Alert(
                code=str(a.get("code", "")),
                level=str(a.get("level", "watch")),
                detail=str(a.get("detail", "")),
                technical=str(a.get("technical", "")),
            )
            for a in payload.get("alerts", [])
            if isinstance(a, dict)
        ],
    )


def login_states_from_disk(config: Config) -> dict[str, str]:
    """What the last sign-in walk concluded, if there was one."""
    path = config.paths.ensure().state / "logins.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return {
        str(entry.get("name")): str(entry.get("state"))
        for entry in payload.get("results", [])
        if isinstance(entry, dict) and entry.get("name")
    }


def last_submit_from_rows(rows: Iterable[dict]) -> datetime | None:
    """When something last went out, as far as the record knows."""
    from .tracker import normalize_status

    best: datetime | None = None
    for row in rows:
        if normalize_status(row.get("status")) not in ("submitted", "applied"):
            continue
        stamp = row.get("submit_proof_at") or row.get("status_changed_at")
        if not stamp:
            continue
        try:
            when = datetime.fromisoformat(str(stamp))
        except ValueError:
            continue
        if best is None or when > best:
            best = when
    return best


def freshly_found(rows: Iterable[dict], *, within: timedelta = timedelta(days=1)) -> int:
    """How many jobs were added recently — the other half of the leak check."""
    at = now()
    count = 0
    for row in rows:
        stamp = row.get("added_at")
        if not stamp:
            continue
        try:
            when = datetime.fromisoformat(str(stamp))
        except ValueError:
            continue
        if at - _aware(when, at) <= within:
            count += 1
    return count
