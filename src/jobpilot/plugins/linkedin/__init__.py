"""LinkedIn visibility (optional).

Contributes a browser-driven source (job posts seen while looking around) and
outreach (connection notes and comments). Every outbound action needs both the
matching permission in the settings and a pass from the outbound gate; this
module has no way to send anything itself.
"""

from __future__ import annotations

from typing import Any

from ...config import Config
from ...providers.base import ModelProvider
from ..base import BrowserAgentSource, Draft, Manifest, Outreach

PROMPT_FILE = "agent.md"


def _values(config: Config, manifest: Manifest) -> dict[str, Any]:
    settings = manifest.settings(config)
    return {
        "TIME_BUDGET_MIN": 45,
        "STOP_NEW_ACTIONS_MIN": 5,
        "SEARCH_TERMS": ", ".join(
            str(t) for t in (settings.get("search_terms") or config.get("search.categories.core", []))
        ),
        "EXCLUDED_COMPANIES": ", ".join(
            str(c)
            for c in (
                settings.get("excluded_companies")
                or config.get("search.company_rules.hard_exclude", [])
            )
        )
        or "nobody in particular",
        "PER_CYCLE_CONNECT_CAP": settings.get("per_cycle_connect_cap", 12),
        "CONNECT_NOTE_LIMIT": settings.get("connect_note_limit", 199),
        "COMMENTS_PER_CYCLE": settings.get("comments_per_cycle", 4)
        if "comment" in (settings.get("scope") or [])
        else 0,
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
    settings = manifest.settings(config)
    return Outreach(
        plugin=manifest.name,
        permission="send_outreach_messages",
        cap=int(settings.get("weekly_connect_cap", 90)),
    )


def make_drafts(config: Config, manifest: Manifest, leads: list[dict]) -> list[Draft]:
    """Turn the agent's suggested notes into drafts for the gate.

    The text comes from the model's answer unchanged: nothing is composed here,
    and nothing is reworded after a check.
    """
    settings = manifest.settings(config)
    limit = int(settings.get("connect_note_limit", 199))
    drafts: list[Draft] = []
    for lead in leads:
        kind = str(lead.get("kind") or "connect_note")
        text = str(lead.get("text") or "").strip()
        if not text or (kind == "connect_note" and len(text) > limit):
            continue
        drafts.append(
            Draft(
                kind=kind,
                recipient=str(lead.get("recipient") or ""),
                text=text,
                context={"company": lead.get("company", ""), "target_url": lead.get("target_url", "")},
            )
        )
    return drafts


def health(config: Config, manifest: Manifest) -> tuple[bool, str]:
    if not config.plugin_enabled(manifest.name):
        return True, "switched off"
    if not config.get("models.browser"):
        return False, "I need a model that can use a browser before this can run."
    return True, "ready, as long as you are signed in to LinkedIn in your browser"
