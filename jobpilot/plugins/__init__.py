"""The plugin registry.

Plugins are discovered by looking for ``plugin.yaml`` files next to this file.
They are only *used* when the settings switch them on, and the core runs
perfectly well with none of them: everything here is optional by construction.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import Config
from ..providers.base import ModelProvider
from .base import MANIFEST_NAME, BrowserAgentSource, Draft, Manifest, Outreach, SendResult, render_prompt

__all__ = [
    "BrowserAgentSource",
    "Draft",
    "Manifest",
    "Outreach",
    "Plugin",
    "SendResult",
    "discover",
    "load_plugins",
    "render_prompt",
]


@dataclass
class Plugin:
    manifest: Manifest
    module: Any

    @property
    def name(self) -> str:
        return self.manifest.name

    def source(self, config: Config, provider: ModelProvider | None = None):
        """A search source, if this plugin has one and is configured for it."""
        factory = getattr(self.module, "make_source", None)
        if factory is None:
            return None
        return factory(config, self.manifest, provider)

    def outreach(self, config: Config) -> Outreach | None:
        factory = getattr(self.module, "make_outreach", None)
        if factory is None:
            return None
        return factory(config, self.manifest)

    def drafts(self, config: Config, leads: list[dict]) -> list[Draft]:
        factory = getattr(self.module, "make_drafts", None)
        if factory is None:
            return []
        return factory(config, self.manifest, leads)

    def health(self, config: Config) -> tuple[bool, str]:
        check = getattr(self.module, "health", None)
        if check is None:
            return True, "nothing to check"
        return check(config, self.manifest)


def plugin_dirs() -> list[Path]:
    here = Path(__file__).resolve().parent
    return sorted(p.parent for p in here.glob(f"*/{MANIFEST_NAME}"))


def discover() -> list[Manifest]:
    """Every installed plugin's manifest, whether or not it is switched on."""
    return [Manifest.from_file(directory / MANIFEST_NAME) for directory in plugin_dirs()]


def load_plugins(config: Config) -> list[Plugin]:
    """The plugins the user has switched on, loaded and ready."""
    out: list[Plugin] = []
    for manifest in discover():
        if not config.plugin_enabled(manifest.name):
            continue
        module = importlib.import_module(f"{__name__}.{manifest.name}")
        out.append(Plugin(manifest=manifest, module=module))
    return out


def describe_all(config: Config) -> str:
    """What the bootstrap conversation reads out: every add-on, on or off."""
    lines: list[str] = []
    for manifest in discover():
        state = "on" if config.plugin_enabled(manifest.name) else "off"
        lines.append(f"{manifest.name} ({state}) — {manifest.summary}")
    return "\n".join(lines) if lines else "No optional helpers are installed."
