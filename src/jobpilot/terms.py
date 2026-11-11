"""The two lists the search actually runs on: job titles, and where to look.

Both can live either in the settings file or in a file of their own next to it
(``search_terms.json``, ``sources.yaml``). The separate files exist because
these two lists are the things a person edits most often, and a long list of
company names does not belong in the middle of everything else.

The rule that matters: **they are read fresh every pass, and never copied into
the code.** Adding a title or a company here changes the next search, with no
restart and no release. A term that lived in two places drifted apart twice in
the system this was taken from, so there is exactly one reader for each.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import Config
from .errors import ConfigError

TERMS_FILE = "search_terms.json"
SOURCES_FILE = "sources.yaml"

#: Wording added to each title to find the entry-level version of it.
DEFAULT_LEVELS = (
    "New Grad",
    "Entry Level",
    "Early Career",
    "Junior",
    "Associate",
    "University Graduate",
)


def _beside_settings(config: Config, name: str) -> Path | None:
    """A companion file next to the user's settings, if they wrote one."""
    base = Path(config.source).parent if config.source else None
    if base is None:
        return None
    candidate = base / name
    return candidate if candidate.exists() else None


def _read(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ConfigError(
            f"I could not read {path.name}.",
            hint=f"The line it stopped on: {exc}",
        ) from exc


@dataclass
class Terms:
    """Which job titles count, and how to ask for the entry-level version."""

    core: list[str] = field(default_factory=list)
    non_core: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    levels: list[str] = field(default_factory=lambda: list(DEFAULT_LEVELS))
    seniority: list[str] = field(default_factory=list)
    source: Path | None = None

    @classmethod
    def from_config(cls, config: Config) -> "Terms":
        """The settings' own lists, with a companion file overriding them."""
        terms = cls(
            core=_strings(config.get("search.categories.core")),
            non_core=_strings(config.get("search.categories.non_core")),
            exclude=_strings(config.get("search.categories.excluded")),
            seniority=_strings(config.get("search.seniority_excludes")),
        )
        path = _beside_settings(config, TERMS_FILE)
        if path is None:
            return terms
        payload = _read(path) or {}
        if not isinstance(payload, dict):
            raise ConfigError(f"{path.name} should be a list of job titles in groups.")
        return cls(
            core=_strings(payload.get("core")) or terms.core,
            non_core=_strings(payload.get("non_core")) or terms.non_core,
            exclude=_strings(payload.get("exclude")) or terms.exclude,
            levels=_strings(payload.get("levels")) or list(DEFAULT_LEVELS),
            seniority=_strings(payload.get("seniority")) or terms.seniority,
            source=path,
        )

    def queries(self) -> list[str]:
        """Every search to run: each title bare, and again with each level word.

        A title listed here is *in focus*. Whether a particular posting is too
        senior is decided by reading the whole description and quoting it — never
        by the title, and never by leaving the term unsearched.
        """
        out: list[str] = []
        for term in [*self.core, *self.non_core]:
            out.append(term)
            out.extend(f"{level} {term}" for level in self.levels)
        seen: set[str] = set()
        return [q for q in out if not (q.lower() in seen or seen.add(q.lower()))]

    def tier_of(self, title: str) -> str:
        """``core`` / ``non_core`` / ``irrelevant`` from the title alone.

        An unknown title is ``non_core``, never ``irrelevant``: a title nobody
        listed is a question for a model, not a reason to throw a job away.
        """
        low = (title or "").lower()
        if any(term.lower() in low for term in self.exclude):
            return "irrelevant"
        if any(term.lower() in low for term in self.core):
            return "core"
        if any(term.lower() in low for term in self.non_core):
            return "non_core"
        return "non_core"

    def matched(self, title: str, group: str) -> str:
        """The first term from ``group`` that appears in the title, or ``""``."""
        low = (title or "").lower()
        return next((t for t in getattr(self, group) if t.lower() in low), "")


@dataclass
class Sources:
    """Which public job pages to read, and how politely."""

    boards: dict[str, list[str]] = field(default_factory=dict)  # family → boards
    per_board_max: int = 200
    seconds_between_requests: float = 1.0
    timeout_seconds: int = 20
    quiet_days_before_suggesting: int = 7
    source: Path | None = None

    @classmethod
    def from_config(cls, config: Config) -> "Sources":
        from .search.ats import FAMILIES

        boards: dict[str, list[str]] = {}
        for family in FAMILIES:
            block = config.section(f"search.sources.{family}")
            if block.get("enabled"):
                names = [str(b).strip() for b in (block.get("boards") or []) if str(b).strip()]
                if names:
                    boards[family] = names
        found = cls(boards=boards)

        path = _beside_settings(config, SOURCES_FILE)
        if path is None:
            return found
        payload = _read(path) or {}
        if not isinstance(payload, dict):
            raise ConfigError(f"{path.name} should list the job pages to read.")
        declared: dict[str, list[str]] = {}
        for family, block in (payload.get("sources") or {}).items():
            if not isinstance(block, dict) or not block.get("enabled"):
                continue
            names = [str(b).strip() for b in (block.get("boards") or []) if str(b).strip()]
            if names:
                declared[str(family)] = names
        limits = payload.get("limits") or {}
        health = payload.get("health") or {}
        return cls(
            boards=declared or found.boards,
            per_board_max=int(limits.get("per_board_max", 200) or 200),
            seconds_between_requests=float(limits.get("seconds_between_requests", 1.0) or 0),
            timeout_seconds=int(limits.get("timeout_seconds", 20) or 20),
            quiet_days_before_suggesting=int(health.get("quiet_days_before_suggesting", 7) or 7),
            source=path,
        )

    @property
    def families(self) -> list[str]:
        return sorted(self.boards)

    def words(self) -> str:
        """What is being watched, as a person would say it."""
        if not self.boards:
            return "no company job pages yet"
        total = sum(len(names) for names in self.boards.values())
        return f"{total} company job page(s) across {len(self.boards)} kind(s) of system"


def _strings(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
