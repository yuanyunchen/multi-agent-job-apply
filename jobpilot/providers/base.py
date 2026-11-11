"""The model-provider interface.

No module outside this package may name a command-line tool or an API. Core
code asks for a *role* (``screen``, ``review``, ``browser``) and gets whichever
provider the user configured, with a fallback chain and ``answered_by``
recorded on every result — a single provider logging itself out must never stop
the whole system.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

ROLES = ("screen", "review", "browser")

#: Anything that looks like a credential is scrubbed out of provider output
#: before it is logged or returned.
_SECRETS = re.compile(
    r"(?i)\b(sk-[A-Za-z0-9_\-]{8,}|gh[pousr]_[A-Za-z0-9]{8,}|Bearer\s+[A-Za-z0-9._\-]{8,}|"
    r"eyJ[A-Za-z0-9._\-]{10,})"
)


def redact(text: str) -> str:
    return _SECRETS.sub("[REDACTED]", text or "")


@dataclass(frozen=True, slots=True)
class Health:
    ok: bool
    detail: str = ""


@dataclass(slots=True)
class ModelResult:
    ok: bool
    text: str
    answered_by: str
    failure: str = ""  # not_installed | not_signed_in | rate_limited | timeout | refused | error
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def data(self) -> Any:
        """The reply parsed as JSON, or ``None``."""
        payload = self.text.strip()
        if not payload.startswith(("[", "{")):
            match = re.search(r"(\[.*\]|\{.*\})", payload, re.DOTALL)
            payload = match.group(1) if match else ""
        try:
            return json.loads(payload)
        except ValueError:
            return None


@runtime_checkable
class ModelProvider(Protocol):
    """One way of asking a model a question."""

    name: str
    capabilities: frozenset[str]

    def complete(self, prompt: str, *, schema: dict | None = None, timeout: int = 600) -> ModelResult: ...

    def health(self) -> Health: ...


def schema_hint(schema: dict | None) -> str:
    """Appended to a prompt for providers with no structured-output support."""
    if not schema:
        return ""
    return (
        "\n\nAnswer with JSON only, with no prose before or after it, matching "
        f"this shape:\n{json.dumps(schema, indent=2)}\n"
    )
