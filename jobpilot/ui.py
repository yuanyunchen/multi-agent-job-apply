"""The one place a user-facing message is rendered.

Simple mode (the default) is about features, progress and outcomes. It never
contains a file path, a script name, a model name, an id, a hash, an exit code
or a lane/wave number. A lint enforces that; if a message somehow fails the
lint, the renderer falls back to a safe line and records the violation instead
of showing jargon to the user.

Technical mode is the same message plus the details.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .domain import Message

#: Patterns that must never appear in a simple-mode message.
JARGON_PATTERNS: tuple[tuple[str, str], ...] = (
    ("a file name", r"\b[\w./-]+\.(py|json|jsonl|yaml|yml|log|sh|md)\b"),
    ("a file path", r"(?:^|\s)(?:/|~/|\./)[\w./-]{3,}"),
    ("a long identifier", r"\b[0-9a-f]{7,}\b"),
    ("an internal id", r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),
    ("a model name", r"\b(claude|codex|gpt|haiku|sonnet|opus|llm)\b"),
    ("an exit code", r"\bexit(?:ed with)? (?:code )?-?\d+\b"),
    ("an internal word", r"\b(tracker|lane|lanes|wave|waves|batch|stderr|stdout|traceback|subprocess|regex|json|yaml|sha|repo|commit)\b"),
    ("a process id", r"\b(pid|PID)\s*\d+\b"),
)

_COMPILED = tuple((label, re.compile(pattern, re.IGNORECASE)) for label, pattern in JARGON_PATTERNS)

#: The setup conversation has to name the things the user is choosing between,
#: and a model is a product with a name, like LinkedIn. Progress messages do
#: not get this allowance.
PRODUCT_NAMES_OK = ("a model name",)


def lint_plain(text: str, *, allow: tuple[str, ...] = ()) -> list[str]:
    """Return a list of human-readable reasons the text is too technical.

    ``allow`` names categories to let through, e.g. :data:`PRODUCT_NAMES_OK`
    while the user is picking which model to use.
    """
    found: list[str] = []
    for label, pattern in _COMPILED:
        if label in allow:
            continue
        match = pattern.search(text or "")
        if match:
            found.append(f"{label} ({match.group(0).strip()!r})")
    return found


@dataclass
class Renderer:
    """Renders messages for one mode and remembers anything it had to suppress."""

    mode: str = "simple"
    violations: list[tuple[str, list[str]]] = field(default_factory=list)

    @property
    def technical(self) -> bool:
        return self.mode == "technical"

    def render(self, message: Message) -> str:
        if self.technical:
            parts = [message.simple]
            if message.technical:
                parts.append(message.technical)
            return "\n".join(parts)
        problems = lint_plain(message.simple)
        if problems:
            self.violations.append((message.kind, problems))
            return message.fallback
        return message.simple

    def render_all(self, messages: list[Message]) -> str:
        return "\n".join(self.render(m) for m in messages)

    def self_optimization(self, what_changed: str, details: str = "", notice: str = "one_line") -> str:
        """After the assistant tunes itself: one plain line, or nothing.

        The details always go to the changelog; in simple mode they never go to
        the user.
        """
        if self.technical:
            return "\n".join(p for p in (what_changed, details) if p)
        if notice == "none":
            return ""
        first_line = what_changed.strip().splitlines()[0] if what_changed.strip() else ""
        problems = lint_plain(first_line)
        if problems:
            self.violations.append(("self_optimization", problems))
            return "I made a small improvement to how I work."
        return first_line


def renderer_for(config) -> Renderer:
    """Build the renderer the whole run should share."""
    return Renderer(mode=config.ui_mode)


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural_form or singular + 's')}"
