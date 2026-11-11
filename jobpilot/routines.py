"""Routines: what runs by itself, declared in YAML and explained in words.

``config/routines.yaml`` is the only description of the timetable. The renderer
turns a schedule into the sentence a user would say — "Every weekday at 8am you
get one email" — so the timetable the user is told about cannot drift from the
one that runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import Config, DEFAULT_ROUTINES_PATH, repo_root
from .errors import ConfigError

DAY_WORDS = {
    "daily": "every day",
    "mon-fri": "every weekday",
    "weekdays": "every weekday",
    "sat-sun": "at the weekend",
    "mon": "on Monday",
    "tue": "on Tuesday",
    "wed": "on Wednesday",
    "thu": "on Thursday",
    "fri": "on Friday",
    "sat": "on Saturday",
    "sun": "on Sunday",
}


def clock(value: str) -> str:
    """``08:00`` → ``8am``; ``18:30`` → ``6:30pm``."""
    try:
        hour_text, minute_text = str(value).split(":")[:2]
        hour, minute = int(hour_text), int(minute_text)
    except (ValueError, IndexError):
        return str(value)
    suffix = "am" if hour < 12 else "pm"
    display = hour % 12 or 12
    return f"{display}{'' if minute == 0 else ':%02d' % minute}{suffix}"


@dataclass(frozen=True, slots=True)
class Routine:
    name: str
    schedule: dict[str, Any]
    what: str
    description: str

    @property
    def when_in_words(self) -> str:
        days = DAY_WORDS.get(str(self.schedule.get("days", "daily")).lower(), "every day")
        if "at" in self.schedule:
            return f"{days} at {clock(self.schedule['at'])}"
        if "window" in self.schedule:
            start, _, end = str(self.schedule["window"]).partition("-")
            return f"{days} between {clock(start)} and {clock(end)}"
        if "every" in self.schedule:
            return f"every {self.schedule['every']}"
        return days

    def explain(self) -> str:
        """One sentence the user would recognise as their own."""
        return self.description or f"{self.when_in_words.capitalize()} I run {self.name.replace('_', ' ')}."


def load_routines(path: str | Path | None = None) -> list[Routine]:
    chosen = Path(path) if path else (repo_root() / DEFAULT_ROUTINES_PATH)
    if not chosen.exists():
        return []
    payload = yaml.safe_load(chosen.read_text(encoding="utf-8")) or {}
    entries = payload.get("routines") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        raise ConfigError(
            f"The timetable in {chosen} should be a list of routines.",
            hint="Start again from the version in this repository.",
        )
    out: list[Routine] = []
    problems: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("name"):
            problems.append(f"one entry has no name: {entry!r}")
            continue
        schedule = entry.get("schedule")
        if not isinstance(schedule, dict) or not (
            {"at", "window", "every"} & set(schedule)
        ):
            problems.append(f"{entry['name']} needs a time ('at', 'window' or 'every').")
            continue
        out.append(
            Routine(
                name=str(entry["name"]),
                schedule=schedule,
                what=str(entry.get("what", "")),
                description=str(entry.get("description", "")),
            )
        )
    if problems:
        raise ConfigError(f"I could not read the timetable in {chosen}:", problems=problems)
    return out


def timetable(routines: list[Routine], config: Config | None = None) -> str:
    """The whole timetable, in the user's words."""
    if not routines:
        return "Nothing is scheduled yet."
    zone = config.get("timing.timezone") if config else None
    lines = [routine.explain() for routine in routines]
    if zone:
        lines.append(f"(All times are {zone} time.)")
    return "\n".join(f"- {line}" if not line.startswith("(") else line for line in lines)


def plugin_routines(config: Config) -> list[Routine]:
    """Routines contributed by whichever plugins are switched on."""
    from .plugins import load_plugins

    out: list[Routine] = []
    for plugin in load_plugins(config):
        for entry in plugin.manifest.routines:
            out.append(
                Routine(
                    name=f"{plugin.manifest.name}_{entry.get('id', 'cycle')}",
                    schedule=entry.get("schedule") or {"window": entry.get("window", "18:00-22:00")},
                    what=str(entry.get("action", "")),
                    description=str(entry.get("description", "")),
                )
            )
    return out


#: Routines whose time the user chooses during setup, and the setting that holds it.
USER_TIMES = {"daily_email": "notifications.digest_time"}


def with_user_times(routines: list[Routine], config: Config) -> list[Routine]:
    """Let a time the user chose in setup win over the one in the timetable file."""
    out = []
    for routine in routines:
        setting = USER_TIMES.get(routine.name)
        chosen = str(config.get(setting, "")) if setting else ""
        if chosen and routine.schedule.get("at") != chosen:
            schedule = {**routine.schedule, "at": chosen}
            description = routine.description
            if routine.description and routine.schedule.get("at"):
                description = routine.description.replace(
                    clock(str(routine.schedule["at"])), clock(chosen)
                )
            out.append(
                Routine(
                    name=routine.name,
                    schedule=schedule,
                    what=routine.what,
                    description=description,
                )
            )
        else:
            out.append(routine)
    return out


def all_routines(config: Config, path: str | Path | None = None) -> list[Routine]:
    return with_user_times([*load_routines(path), *plugin_routines(config)], config)
