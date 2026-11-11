"""What a plugin is, and the two things plugins are allowed to contribute.

A plugin is a directory with a ``plugin.yaml`` manifest, an ``__init__.py`` and
(if it drives a browser) an agent prompt in Markdown. Core never imports a
plugin: the registry finds them, the manifest says what they need, and the
settings decide whether they are on. Anything that needs a login is off until
the user turns it on.

Plugins may contribute:

* a **search source** — rows that then go through the same rules and the same
  screen as everything else;
* **outreach** — messages, which only leave the machine if the matching
  permission is on *and* the outbound gate passes. Core ships no sender, so a
  plugin cannot send anything by itself.

Real browser work is delegated to a model provider with the ``browser``
capability: the plugin writes a prompt, the provider drives the browser, and the
plugin parses the answer. No plugin opens a browser itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from ..config import Config
from ..domain import Job
from ..errors import ConfigError, GateBlocked
from ..gates import GateResult, OutboundGate
from ..providers.base import ModelProvider

MANIFEST_NAME = "plugin.yaml"
REQUIRED_FIELDS = ("name", "kind", "version", "summary", "explain", "writes", "enabled_default")


@dataclass(frozen=True, slots=True)
class Login:
    id: str
    label: str
    how: str
    verify: str = ""
    never: tuple[str, ...] = ()
    #: The label as a sentence, for prose: "It needs you to be signed in to
    #: your school's job platform." A label alone reads wrong mid-sentence.
    sentence: str = ""
    #: What the user does, as a phrase: "signing in to LinkedIn, in your own
    #: browser". Used in the list of things only they can do.
    your_part: str = ""

    def explain(self) -> str:
        never = "; ".join(self.never)
        line = f"{self.label}: you sign in yourself, in your own browser. I check by {self.verify or 'opening the page'}."
        return f"{line} I will never {never}." if never else line


@dataclass(frozen=True, slots=True)
class Manifest:
    name: str
    kind: str  # source | outreach | provider | ats
    version: int
    summary: str
    explain: str
    logins: tuple[Login, ...] = ()
    providers: tuple[str, ...] = ()
    defaults: dict[str, Any] = field(default_factory=dict)
    routines: tuple[dict[str, Any], ...] = ()
    gates: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    metrics: tuple[str, ...] = ()
    caps: dict[str, Any] = field(default_factory=dict)
    enabled_default: bool = False
    outbound_actions: tuple[str, ...] = ()
    directory: Path | None = None

    @classmethod
    def from_file(cls, path: str | Path) -> "Manifest":
        source = Path(path)
        payload = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
        missing = [field_name for field_name in REQUIRED_FIELDS if field_name not in payload]
        if missing:
            raise ConfigError(
                f"The add-on description at {source} is incomplete.",
                problems=[f"missing: {', '.join(missing)}"],
            )
        requires = payload.get("requires") or {}
        logins = tuple(
            Login(
                id=str(entry.get("id", "")),
                label=str(entry.get("label", "")),
                how=str(entry.get("how", "browser_session")),
                verify=str(entry.get("verify", "")),
                never=tuple(str(x) for x in entry.get("never") or ()),
                sentence=str(entry.get("sentence", "")),
                your_part=str(entry.get("your_part", "")),
            )
            for entry in requires.get("logins") or []
        )
        if logins and payload.get("enabled_default"):
            raise ConfigError(
                f"{payload['name']} needs a login, so it must start switched off.",
                problems=["set 'enabled_default: false'"],
            )
        return cls(
            name=str(payload["name"]),
            kind=str(payload["kind"]),
            version=int(payload["version"]),
            summary=str(payload["summary"]),
            explain=str(payload["explain"]).strip(),
            logins=logins,
            providers=tuple(str(x) for x in requires.get("providers") or ()),
            defaults=dict(payload.get("defaults") or {}),
            routines=tuple(payload.get("routines") or ()),
            gates=tuple(str(x) for x in payload.get("gates") or ()),
            writes=tuple(str(x) for x in payload.get("writes") or ()),
            metrics=tuple(str(x) for x in payload.get("metrics") or ()),
            caps=dict(payload.get("caps") or {}),
            enabled_default=bool(payload["enabled_default"]),
            outbound_actions=tuple(str(x) for x in payload.get("outbound_actions") or ()),
            directory=source.parent,
        )

    def describe(self) -> str:
        """What the user is told before deciding whether to switch it on."""
        lines = [f"{self.summary}", "", self.explain]
        if self.logins:
            lines += ["", "What it needs from you:"]
            lines += [f"  - {login.explain()}" for login in self.logins]
        if self.outbound_actions:
            lines += [
                "",
                "It can send things on your behalf, and only with your permission: "
                + ", ".join(action.replace("_", " ") for action in self.outbound_actions)
                + ".",
            ]
        return "\n".join(lines)

    def settings(self, config: Config) -> dict[str, Any]:
        """The plugin's own settings: its defaults with the user's on top."""
        return {**self.defaults, **config.section(f"plugins.{self.name}")}

    def prompt_path(self, name: str) -> Path | None:
        if self.directory is None:
            return None
        candidate = self.directory / name
        return candidate if candidate.exists() else None


# -- browser-driven sources ----------------------------------------------

_PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def render_prompt(template: str, values: dict[str, Any]) -> str:
    """Fill ``{{PLACEHOLDER}}`` from config. An unknown one becomes a blank."""
    return _PLACEHOLDER.sub(lambda m: str(values.get(m.group(1), "")), template)


@dataclass
class BrowserAgentSource:
    """A source whose looking-around is done by a browser-capable model.

    The plugin supplies the prompt; the model answers with JSON; this class
    turns the answer into ordinary rows, which then face exactly the same rules
    and the same screen as rows from a public job board.
    """

    plugin: str
    prompt: str
    provider: ModelProvider | None
    values: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    SCHEMA = {
        "type": "object",
        "properties": {
            "jobs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["company", "title", "url"],
                    "properties": {
                        "company": {"type": "string"},
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "location": {"type": "string"},
                        "posted_at": {"type": "string"},
                        "description": {"type": "string"},
                        "job_id": {"type": "string"},
                    },
                },
            }
        },
    }

    @property
    def name(self) -> str:
        return self.plugin

    def fetch(self, fetcher: Any = None) -> Iterable[Job]:
        if self.provider is None:
            self.errors.append(f"{self.plugin}: no browser model is set up, so I skipped it.")
            return []
        result = self.provider.complete(render_prompt(self.prompt, self.values), schema=self.SCHEMA)
        if not result.ok:
            self.errors.append(f"{self.plugin}: I could not look there just now.")
            return []
        payload = result.data
        rows = payload.get("jobs", []) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            self.errors.append(f"{self.plugin}: the answer was not something I could read.")
            return []
        return [job for job in (self._to_job(row) for row in rows) if job is not None]

    def _to_job(self, row: Any) -> Job | None:
        if not isinstance(row, dict) or not row.get("url") or not row.get("title"):
            return None
        return Job(
            company=str(row.get("company") or ""),
            title=str(row.get("title") or ""),
            url=str(row["url"]),
            source=self.plugin,
            ats=str(row.get("ats") or ""),
            ats_job_id=str(row.get("job_id") or ""),
            location=str(row.get("location") or ""),
            description=str(row.get("description") or ""),
            posted_at=str(row.get("posted_at") or ""),
            tags=(f"source:{self.plugin}",),
        )


# -- outreach ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Draft:
    kind: str  # connect_note | reply | comment
    recipient: str
    text: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SendResult:
    draft: Draft
    sent: bool
    code: str
    reason: str = ""


@dataclass
class Outreach:
    """Takes drafts to the gate. Core has no way to actually send them."""

    plugin: str
    permission: str  # the settings key that must be true
    cap: int | None = None

    def submit(
        self,
        drafts: Iterable[Draft],
        gate: OutboundGate,
        *,
        send: Any = None,
        already_sent: int = 0,
    ) -> list[SendResult]:
        results: list[SendResult] = []
        sent_count = already_sent
        for draft in drafts:
            if self.cap is not None and sent_count >= self.cap:
                results.append(SendResult(draft, False, "cap_reached", "That is as many as you allowed this week."))
                continue
            check: GateResult = gate.check(
                self.permission,
                text=draft.text,
                context={"plugin": self.plugin, "recipient": draft.recipient, **draft.context},
            )
            if not check.allowed:
                # A blocked message is a hard skip. Never reworded, never retried.
                results.append(SendResult(draft, False, check.code, check.reason))
                continue
            if send is None:
                results.append(
                    SendResult(draft, False, "no_sender", "Nothing is wired up to actually send this.")
                )
                continue
            try:
                send(draft)
            except GateBlocked as exc:
                results.append(SendResult(draft, False, exc.code, exc.message))
                continue
            sent_count += 1
            results.append(SendResult(draft, True, "sent"))
        return results
