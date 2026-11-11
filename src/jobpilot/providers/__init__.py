"""Provider registry: config in, one provider per role out.

``models:`` in the settings maps a role to a model name, and
``models.providers`` says which engines exist. The registry resolves a role to
the first *healthy* provider that offers that model, falling back along
``models.fallback``. ``answered_by`` on the result always says who really
answered.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import Config
from ..errors import ProviderUnavailable
from .base import Health, ModelProvider, ModelResult, ROLES, redact
from .cli import CliProvider, claude_provider, codex_provider
from .fake import FakeProvider
from .http import OpenAICompatibleProvider

__all__ = [
    "CliProvider",
    "FakeProvider",
    "Health",
    "ModelProvider",
    "ModelResult",
    "OpenAICompatibleProvider",
    "Registry",
    "ROLES",
    "build_registry",
    "role_words",
    "claude_provider",
    "codex_provider",
    "redact",
]


def _providers_from_config(config: Config) -> dict[str, ModelProvider]:
    """Model name → provider, for every enabled engine."""
    out: dict[str, ModelProvider] = {}
    blocks = config.section("models.providers")

    claude = blocks.get("claude") or {}
    if claude.get("enabled"):
        command = str(claude.get("command") or "claude")
        for alias, model_id in (claude.get("models") or {}).items():
            out[str(alias)] = claude_provider(str(model_id), command=command, name=str(alias))

    codex = blocks.get("codex") or {}
    if codex.get("enabled"):
        out["codex"] = codex_provider(command=str(codex.get("command") or "codex"))

    http = blocks.get("openai_compatible") or {}
    if http.get("enabled"):
        provider = OpenAICompatibleProvider(
            base_url=str(http.get("base_url") or ""),
            model=str(http.get("model") or ""),
            api_key_env=str(http.get("api_key_env") or ""),
        )
        out[provider.model or "openai_compatible"] = provider
        out["openai_compatible"] = provider

    if (blocks.get("fake") or {}).get("enabled"):
        out["fake"] = FakeProvider()
    return out


@dataclass
class Registry:
    """Role → provider, with a fallback chain and a health cache."""

    providers: dict[str, ModelProvider] = field(default_factory=dict)
    roles: dict[str, str] = field(default_factory=dict)
    fallback: list[str] = field(default_factory=list)
    _health: dict[str, Health] = field(default_factory=dict, repr=False)

    def health_of(self, model: str) -> Health:
        if model not in self._health:
            provider = self.providers.get(model)
            self._health[model] = (
                provider.health() if provider else Health(False, "not configured")
            )
        return self._health[model]

    def candidates(self, role: str) -> list[str]:
        chosen = self.roles.get(role)
        order = ([chosen] if chosen else []) + [m for m in self.fallback if m != chosen]
        return [m for m in order if m in self.providers]

    def for_role(self, role: str, *, require_healthy: bool = True) -> ModelProvider:
        names = self.candidates(role)
        if not names:
            raise ProviderUnavailable(
                f"No model is set up for {role_words(role)}.",
                hint="Run 'jobpilot doctor' to see which engines I can reach.",
            )
        if not require_healthy:
            return self.providers[names[0]]
        for name in names:
            if self.health_of(name).ok:
                return self.providers[name]
        detail = "; ".join(f"{n}: {self.health_of(n).detail}" for n in names)
        raise ProviderUnavailable(
            f"I cannot reach any model for {role_words(role)} right now.",
            hint=detail,
        )

    def report(self) -> list[tuple[str, str, bool, str]]:
        """``(role, model, ok, detail)`` for ``doctor``."""
        rows = []
        for role in ROLES:
            for name in self.candidates(role) or [self.roles.get(role, "")]:
                health = self.health_of(name) if name in self.providers else Health(False, "not configured")
                rows.append((role, name, health.ok, health.detail))
        return rows


def role_words(role: str) -> str:
    return {
        "screen": "reading job descriptions",
        "review": "reviewing and planning",
        "browser": "working in a browser",
    }.get(role, role)


def build_registry(config: Config, *, extra: dict[str, ModelProvider] | None = None) -> Registry:
    providers = _providers_from_config(config)
    providers.update(extra or {})
    roles = {role: str(config.get(f"models.{role}", "")) for role in ROLES}
    fallback = [str(m) for m in config.get("models.fallback", []) or []]
    return Registry(providers=providers, roles=roles, fallback=fallback)
