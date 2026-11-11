"""School job platform (optional).

Contributes a browser-driven source — including postings only visible to
students at the user's school — and optional recruiter replies behind the
outbound gate. It never applies and never submits anything.
"""

from __future__ import annotations

from typing import Any

from ...config import Config
from ...providers.base import ModelProvider
from ..base import BrowserAgentSource, Draft, Manifest, Outreach

PROMPT_FILE = "agent.md"


def _values(config: Config, manifest: Manifest, mode: str = "full") -> dict[str, Any]:
    settings = manifest.settings(config)
    locations = config.get("search.locations.preferred", []) or config.get(
        "search.locations.countries", ["US"]
    )
    return {
        "SCHOOL_NAME": settings.get("school_name") or "your school",
        "MODE": mode,
        "SEARCH_TERMS": ", ".join(
            str(t)
            for t in (
                settings.get("search_terms")
                or [*config.get("search.categories.core", []), *config.get("search.categories.non_core", [])]
            )
        ),
        "LOCATIONS": ", ".join(str(x) for x in locations),
        "MAX_YEARS": config.get("search.max_required_years_experience", 2),
        "EXCLUDED_COMPANIES": ", ".join(
            str(c) for c in config.get("search.company_rules.hard_exclude", [])
        )
        or "nobody in particular",
        "NOTE_EVENTS": bool(settings.get("note_events", True)),
        "REPLY_TO_RECRUITERS": bool(settings.get("reply_to_recruiters", False)),
    }


def make_source(config: Config, manifest: Manifest, provider: ModelProvider | None):
    prompt_path = manifest.prompt_path(PROMPT_FILE)
    if prompt_path is None:
        return None
    return BrowserAgentSource(
        plugin=manifest.name,
        prompt=prompt_path.read_text(encoding="utf-8"),
        provider=provider,
        values=_values(config, manifest),
    )


def make_outreach(config: Config, manifest: Manifest) -> Outreach:
    return Outreach(plugin=manifest.name, permission="send_outreach_messages", cap=None)


def make_drafts(config: Config, manifest: Manifest, leads: list[dict]) -> list[Draft]:
    """Replies the agent drafted. Dropped entirely unless the user allowed them."""
    settings = manifest.settings(config)
    if not settings.get("reply_to_recruiters", False):
        return []
    drafts = []
    for lead in leads:
        text = str(lead.get("text") or "").strip()
        if not text:
            continue
        drafts.append(
            Draft(
                kind=str(lead.get("kind") or "reply"),
                recipient=str(lead.get("recipient") or ""),
                text=text,
                context={"company": lead.get("company", ""), "target_url": lead.get("target_url", "")},
            )
        )
    return drafts


def health(config: Config, manifest: Manifest) -> tuple[bool, str]:
    if not config.plugin_enabled(manifest.name):
        return True, "switched off"
    if not manifest.settings(config).get("school_name"):
        return False, "I need to know which school's platform to use."
    return True, "ready, as long as you are signed in to your school platform"
