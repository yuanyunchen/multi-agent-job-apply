#!/usr/bin/env python3
"""Build ``share.json`` for every bot template, from the folder's own files.

A bot template is a folder of plain files a person can read and edit:

    templates/bots/<role>/
        bot.yaml                 name, title, description, avatar, plugins
        PROFILE.md               role, mission, reporting line, hard rules
        memories.md              generic facts the bot should start out knowing
        routines.yaml            what it does on a schedule, and the prompt
        getting-started/SKILL.md its first conversation with a new owner
        skills/<slug>/SKILL.md   one skill per folder, with frontmatter
        share.json               GENERATED — do not edit by hand

``share.json`` is the machine-readable version of all of that, for importing
into a hosted bot product in one step. It is **generated**, never written by
hand, because two copies of the same text drift: the folder would say one thing
and the import another, and nobody would notice until a bot behaved oddly.

    scripts/build_bot_templates.py            # write every share.json
    scripts/build_bot_templates.py --check    # fail if any is out of date
    scripts/build_bot_templates.py --role lead

Some shared skills belong in several roles (every bot needs the same routing
and team rules). Those live once in ``templates/shared/skills/`` and are copied
in, so there is still exactly one source for each.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
BOTS = TEMPLATES / "bots"
SHARED_SKILLS = TEMPLATES / "shared" / "skills"

#: The one entry point every template declares, and the folder it names.
GETTING_STARTED = "getting-started"

#: Files every template must have. A template missing one is incomplete, and
#: an incomplete template is worse than none: it imports and then misbehaves.
REQUIRED_FILES = ("bot.yaml", "PROFILE.md", "memories.md", "routines.yaml")

#: Which shared skills each role gets. Every bot needs the same two: how to
#: delegate work, and how the team talks to each other.
SHARED_FOR_EVERY_ROLE = ("agent-routing", "team-protocol")


class TemplateError(Exception):
    """A template is malformed. The message says which file and why."""


@dataclass
class Skill:
    name: str
    description: str
    body: str
    source: Path | None = None

    def as_dict(self) -> dict:
        return {"name": self.name, "description": self.description, "body": self.body}


@dataclass
class Template:
    role: str
    directory: Path
    name: str = ""
    title: str = ""
    description: str = ""
    avatar: dict = field(default_factory=dict)
    plugins: list[str] = field(default_factory=list)
    memories: list[str] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    routines: list[dict] = field(default_factory=list)

    def share_payload(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "avatar": self.avatar,
            "memories": self.memories,
            "skills": [skill.as_dict() for skill in self.skills],
            "routines": self.routines,
            "plugins": self.plugins,
            "gettingStarted": GETTING_STARTED,
        }


# -- reading the parts ----------------------------------------------------


def read_frontmatter(path: Path) -> tuple[dict, str]:
    """``(frontmatter, body)`` from a skill file. Both are required."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise TemplateError(f"{path}: needs YAML frontmatter with a name and a description")
    try:
        front = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise TemplateError(f"{path}: the frontmatter is not valid YAML ({exc})") from exc
    if not isinstance(front, dict):
        raise TemplateError(f"{path}: the frontmatter should be a block of settings")
    for key in ("name", "description"):
        if not str(front.get(key, "")).strip():
            raise TemplateError(f"{path}: the frontmatter needs a '{key}'")
    return front, match.group(2).strip()


def read_skill(path: Path) -> Skill:
    front, body = read_frontmatter(path)
    return Skill(
        name=str(front["name"]).strip(),
        description=" ".join(str(front["description"]).split()),
        body=body,
        source=path,
    )


def read_memories(path: Path) -> list[str]:
    """One memory per bullet. A memory is a fact, not a paragraph of prose.

    Headings organise the file for a reader and are not memories themselves,
    so the heading is folded into its bullets as a prefix — which keeps each
    memory readable on its own, the way the bot will see it.
    """
    out: list[str] = []
    heading = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            continue
        if line.startswith(("- ", "* ")):
            fact = line[2:].strip()
            if fact:
                out.append(f"{heading}: {fact}" if heading else fact)
    if not out:
        raise TemplateError(f"{path}: no memories found (write one per bullet)")
    return out


def read_routines(path: Path) -> list[dict]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = payload.get("routines") if isinstance(payload, dict) else payload
    if not isinstance(entries, list) or not entries:
        raise TemplateError(f"{path}: should hold a list under 'routines'")
    out = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise TemplateError(f"{path}: every routine should be a block of settings")
        for key in ("name", "schedule", "prompt"):
            if not str(entry.get(key, "")).strip():
                raise TemplateError(f"{path}: routine {entry.get('name', '?')!r} needs a '{key}'")
        check_cron(str(entry["schedule"]), where=f"{path}: {entry['name']}")
        routine = {
            "name": str(entry["name"]),
            "schedule": str(entry["schedule"]).strip(),
            "prompt": str(entry["prompt"]).strip(),
        }
        # Optional, and carried through when present: the human sentence, and
        # whether the routine starts switched on.
        if entry.get("human"):
            routine["human"] = " ".join(str(entry["human"]).split())
        if "enabled" in entry:
            routine["enabled"] = bool(entry["enabled"])
        out.append(routine)
    return out


#: A five-field cron schedule: minute, hour, day of month, month, day of week.
CRON_RANGES = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))


def check_cron(spec: str, *, where: str = "") -> None:
    """Refuse a schedule that would never fire, or would fire at the wrong time."""
    fields = spec.split()
    if len(fields) != 5:
        raise TemplateError(f"{where}: {spec!r} should have five fields, like '30 7 * * *'")
    for field_text, (low, high) in zip(fields, CRON_RANGES):
        for part in field_text.split(","):
            body, _, step = part.partition("/")
            if step and not step.isdigit():
                raise TemplateError(f"{where}: {spec!r} has a step that is not a number")
            if body == "*":
                continue
            start, _, end = body.partition("-")
            for number in (n for n in (start, end) if n):
                if not number.isdigit() or not low <= int(number) <= high:
                    raise TemplateError(
                        f"{where}: {spec!r} is out of range (expected {low}-{high})"
                    )


def load_template(directory: Path) -> Template:
    """Read one template folder into memory, checking it as we go."""
    missing = [name for name in REQUIRED_FILES if not (directory / name).exists()]
    if missing:
        raise TemplateError(f"{directory}: missing {', '.join(missing)}")
    started = directory / GETTING_STARTED / "SKILL.md"
    if not started.exists():
        raise TemplateError(f"{directory}: missing {GETTING_STARTED}/SKILL.md")

    meta = yaml.safe_load((directory / "bot.yaml").read_text(encoding="utf-8")) or {}
    if not isinstance(meta, dict):
        raise TemplateError(f"{directory}/bot.yaml: should be a block of settings")
    for key in ("name", "title", "description", "avatar"):
        if not meta.get(key):
            raise TemplateError(f"{directory}/bot.yaml: needs a '{key}'")
    avatar = meta["avatar"]
    if not isinstance(avatar, dict) or not avatar.get("color") or not avatar.get("shape"):
        raise TemplateError(f"{directory}/bot.yaml: 'avatar' needs a colour and a shape")

    template = Template(
        role=directory.name,
        directory=directory,
        name=str(meta["name"]),
        title=str(meta["title"]),
        description=" ".join(str(meta["description"]).split()),
        avatar={"color": str(avatar["color"]), "shape": str(avatar["shape"])},
        plugins=[str(item) for item in (meta.get("plugins") or [])],
        memories=read_memories(directory / "memories.md"),
        routines=read_routines(directory / "routines.yaml"),
    )

    # The first conversation is a skill like any other, so an import carries it.
    template.skills.append(read_skill(started))
    for skill_dir in sorted((directory / "skills").glob("*")):
        if (skill_dir / "SKILL.md").exists():
            template.skills.append(read_skill(skill_dir / "SKILL.md"))

    names = [skill.name for skill in template.skills]
    if GETTING_STARTED not in names:
        raise TemplateError(
            f"{started}: its frontmatter name must be {GETTING_STARTED!r}, "
            "because that is what share.json points at"
        )
    duplicates = {name for name in names if names.count(name) > 1}
    if duplicates:
        raise TemplateError(f"{directory}: two skills share a name: {sorted(duplicates)}")
    return template


# -- shared skills --------------------------------------------------------


def shared_for(role: str) -> tuple[str, ...]:
    return SHARED_FOR_EVERY_ROLE


def sync_shared(role_dir: Path, *, write: bool) -> list[str]:
    """Copy the shared skills into a role. Returns what was (or is) stale."""
    stale: list[str] = []
    for slug in shared_for(role_dir.name):
        source = SHARED_SKILLS / slug / "SKILL.md"
        if not source.exists():
            raise TemplateError(f"{source}: shared skill is missing")
        destination = role_dir / "skills" / slug / "SKILL.md"
        wanted = source.read_text(encoding="utf-8")
        if destination.exists() and destination.read_text(encoding="utf-8") == wanted:
            continue
        stale.append(str(destination.relative_to(ROOT)))
        if write:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(wanted, encoding="utf-8")
    return stale


# -- the command ----------------------------------------------------------


def roles() -> list[str]:
    return sorted(path.name for path in BOTS.glob("*") if (path / "bot.yaml").exists())


def render(template: Template) -> str:
    return json.dumps(template.share_payload(), indent=2, ensure_ascii=True) + "\n"


def build(role: str, *, write: bool) -> list[str]:
    """Build one role. Returns the list of files that were, or are, out of date."""
    directory = BOTS / role
    stale = sync_shared(directory, write=write)
    template = load_template(directory)
    destination = directory / "share.json"
    wanted = render(template)
    if not destination.exists() or destination.read_text(encoding="utf-8") != wanted:
        stale.append(str(destination.relative_to(ROOT)))
        if write:
            destination.write_text(wanted, encoding="utf-8")
    return stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="change nothing; fail if out of date")
    parser.add_argument("--role", default="", help="just one role")
    args = parser.parse_args(argv)

    chosen = [args.role] if args.role else roles()
    if not chosen:
        print(f"no templates found under {BOTS}")
        return 1

    stale: list[str] = []
    for role in chosen:
        try:
            stale += build(role, write=not args.check)
        except TemplateError as exc:
            print(f"error: {exc}")
            return 1

    if args.check:
        if stale:
            print(f"{len(stale)} generated file(s) are out of date:")
            for name in stale:
                print(f"  - {name}")
            print("Run scripts/build_bot_templates.py to bring them up to date.")
            return 1
        print(f"bot templates: up to date ({len(chosen)} roles)")
        return 0

    if stale:
        print(f"wrote {len(stale)} file(s):")
        for name in stale:
            print(f"  - {name}")
    else:
        print(f"bot templates: already up to date ({len(chosen)} roles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
