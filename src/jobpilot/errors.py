"""Every error the user or an agent can see, with a plain-language message.

Rule: an exception that can reach a user carries a sentence that says what to do
about it. Never a bare stack trace, never an exit code as the whole message.
"""

from __future__ import annotations


class JobpilotError(Exception):
    """Base class. ``str(e)`` is always safe to show a user."""

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.message} {self.hint}".strip()


class ConfigError(JobpilotError):
    """The settings file is missing, unreadable or does not make sense."""

    def __init__(self, message: str, *, hint: str = "", problems: list[str] | None = None) -> None:
        super().__init__(message, hint=hint)
        self.problems = problems or []

    def __str__(self) -> str:
        parts = [self.message]
        parts.extend(f"  - {p}" for p in self.problems)
        if self.hint:
            parts.append(self.hint)
        return "\n".join(parts)


class TrackerRefused(JobpilotError):
    """The tracker refused a write. ``code`` names the guard that said no."""

    def __init__(self, code: str, message: str, *, hint: str = "") -> None:
        super().__init__(message, hint=hint)
        self.code = code


class TrackerLocked(TrackerRefused):
    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__("locked", message, hint=hint)


class TestModeViolation(JobpilotError):
    """Something tried to reach the real world while the tests were running."""


class GateBlocked(JobpilotError):
    """An outbound action was blocked. This is final: never rewrite and retry."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class NeedsUser(JobpilotError):
    """We stopped because only the user can answer this truthfully."""

    def __init__(self, question: str) -> None:
        super().__init__(f"I need your answer before I can continue: {question}")
        self.question = question


class ProviderUnavailable(JobpilotError):
    """A model provider is not usable right now (not installed, not signed in)."""
