"""The "what am I getting?" explanation, generated rather than written.

Everything here is built from the plugin manifests, the timetable and the user's
own settings. Nothing is hand-written prose about what the system does, because
hand-written prose goes stale the moment a helper is switched on or a time is
changed — and a non-technical user has no way of knowing it has.
"""

from __future__ import annotations

from .catalog import catalog, enabled_entries, is_enabled, model_jobs
from .config import Config
from .routines import all_routines, timetable

#: The promises. These are properties of the code, not of the settings, so they
#: are the one part of the explanation that is a fixed list.
NEVER = (
    "apply to the same job twice",
    "make up an answer on a form",
    "send a message, post a comment or submit a form without the matching permission switched on",
    "reset a password, or follow a password-reset link",
    "ask you for a password, or sign in to anything as you",
    "change one of your settings without asking you first",
)

TEAM = (
    (
        "a coordinator",
        "talks to you, and is the only one that does, so you are not messaged from five places",
    ),
    ("a searcher", "looks for new openings and checks them against what you asked for"),
    (
        "an applier",
        "fills in application forms and records every single one, so nothing is applied to twice",
    ),
    (
        "a mail reader",
        "checks the inbox you use for applications, read-only, to see which ones arrived",
    ),
)


def the_team(config: Config) -> list[str]:
    """Who is working for you — core roles plus whichever helpers are on."""
    lines = [f"- {name}, which {what}." for name, what in TEAM]
    for entry in enabled_entries(config):
        if entry.kind == "helper":
            lines.append(f"- {entry.name}, which {entry.adds}. {entry.summary}")
    return lines


def automatic(config: Config) -> list[str]:
    """What runs by itself, in the user's own words, from the timetable."""
    routines = all_routines(config)
    return [line for line in timetable(routines, config).splitlines() if line.strip()]


def needs_you(config: Config) -> list[str]:
    """What only the user can do, worked out from what is switched on."""
    lines = [
        "- a few details that go on application forms (your name, an email address, a phone number);",
        "- the answers to form questions I do not have, which I always ask about rather than guess;",
        "- saying yes before I send anything, submit anything, or change one of your settings.",
    ]
    for entry in enabled_entries(config):
        if entry.login:
            lines.append(f"- {entry.your_part}. {entry.login_how}".rstrip())
    return lines


def never(config: Config) -> list[str]:
    """The promises that hold whatever is switched on."""
    return [f"- {item}." for item in NEVER]


def never_per_helper(config: Config) -> list[str]:
    """What each switched-on thing promises on top, grouped under its name."""
    lines = []
    for entry in enabled_entries(config):
        if entry.never:
            lines.append(f"- {entry.name} will never " + ", or ".join(entry.never) + ".")
    return lines


def optional_extras(config: Config) -> list[str]:
    """Everything not switched on yet, so the user knows it exists."""
    return [
        f"- {entry.name}: {entry.summary} {entry.needs_sentence}"
        for entry in catalog()
        if not is_enabled(config, entry)
    ]


def explain_team(config: Config) -> str:
    """The whole explanation, in the order a person wants to hear it."""
    blocks: list[str] = []
    blocks.append("Here is what you are getting.\n")
    blocks.append("A small team works for you:")
    blocks.extend(the_team(config))
    blocks.append("\nThese models do the thinking:")
    blocks.extend(model_jobs(config))
    blocks.append("\nThis happens by itself:")
    blocks.extend(automatic(config))
    blocks.append("\nThese are the things only you can do:")
    blocks.extend(needs_you(config))
    blocks.append("\nAnd these are the things I will never do:")
    blocks.extend(never(config))
    per_helper = never_per_helper(config)
    if per_helper:
        blocks.append("\nEach thing you have switched on promises more on top of that:")
        blocks.extend(per_helper)
    extras = optional_extras(config)
    if extras:
        blocks.append("\nYou can also switch these on later:")
        blocks.extend(extras)
    return "\n".join(blocks)
