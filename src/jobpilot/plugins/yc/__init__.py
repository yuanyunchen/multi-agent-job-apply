"""Startup list / in-platform applications (optional).

Contributes a browser-driven source and in-platform notes, both behind the
outbound gate and a weekly cap this module enforces itself.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from ...config import Config
from ...providers.base import ModelProvider
from ..base import BrowserAgentSource, Draft, Manifest, Outreach

PROMPT_FILE = "agent.md"


def week_key(today: date | None = None) -> str:
    """Which week an application counts against. The allowance resets Monday."""
    day = today or date.today()
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def cap_remaining(config: Config, manifest: Manifest, sent_this_week: int = 0) -> int:
    cap = int(manifest.settings(config).get("weekly_application_cap", 10))
    return max(0, cap - max(0, sent_this_week))


def _values(config: Config, manifest: Manifest, sent_this_week: int = 0) -> dict[str, Any]:
    settings = manifest.settings(config)
    locations = config.get("search.locations.preferred", []) or config.get(
        "search.locations.countries", ["US"]
    )
    return {
        "CAP_REMAINING": cap_remaining(config, manifest, sent_this_week),
        "SKIP_COMPANIES": ", ".join(
            str(c)
            for c in (
                settings.get("skip_companies") or config.get("search.company_rules.hard_exclude", [])
            )
        )
        or "nobody in particular",
        "SEARCH_TERMS": ", ".join(str(t) for t in config.get("search.categories.core", [])),
        "LOCATIONS": ", ".join(str(x) for x in locations),
        "MAX_YEARS": config.get("search.max_required_years_experience", 2),
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
    return Outreach(
        plugin=manifest.name,
        permission="send_outreach_messages",
        cap=int(manifest.settings(config).get("weekly_application_cap", 10)),
    )


def make_drafts(config: Config, manifest: Manifest, leads: list[dict]) -> list[Draft]:
    limit = int(manifest.settings(config).get("note_limit", 500))
    drafts = []
    for lead in leads:
        text = str(lead.get("text") or "").strip()
        if not text or len(text) > limit:
            continue
        drafts.append(
            Draft(
                kind=str(lead.get("kind") or "founder_note"),
                recipient=str(lead.get("recipient") or ""),
                text=text,
                context={
                    "company": lead.get("company", ""),
                    "target_url": lead.get("target_url", ""),
                    "week": week_key(),
                },
            )
        )
    return drafts


def health(config: Config, manifest: Manifest) -> tuple[bool, str]:
    if not config.plugin_enabled(manifest.name):
        return True, "switched off"
    if cap_remaining(config, manifest) == 0:
        return True, "ready, but this week's allowance is already used up"
    return True, "ready, as long as you are signed in to the startup platform"
