"""The outreach manifest: what *would* be sent, written down for a human.

Nothing in this module sends anything. It cannot: it has no sender. What it
produces is a **manifest** — a dated list of drafts with, for each one, who it
is for, the exact words, and whether every check passed.

That separation is the point. Composing a message and sending it are two
different decisions, made at two different times, and the second one is the
user's. A manifest can be read over breakfast; a sent message cannot be
unsent.

Three guarantees:

* ``send`` is **false** on every entry unless the user has switched the
  matching permission on *and* the draft passed the outbound gate;
* a draft that fails the gate is kept in the manifest with the reason, and is
  **never reworded and retried** — a blocked message is a decision, not an
  obstacle;
* the words in the manifest are the words that would go out, byte for byte, so
  approving the manifest approves something real.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable

from .config import Config
from .domain import iso
from .gates import OutboundGate
from .plugins import Draft


@dataclass(frozen=True, slots=True)
class Entry:
    """One draft, and whether it may go."""

    plugin: str
    kind: str
    recipient: str
    text: str
    send: bool
    code: str = "ok"
    reason: str = ""
    company: str = ""

    @property
    def words(self) -> str:
        who = self.recipient or "someone"
        head = f"{self.plugin}: a {self.kind.replace('_', ' ')} to {who}"
        if self.send:
            return f"{head} — ready, waiting for your go-ahead.\n    “{self.text}”"
        return f"{head} — not going out: {self.reason}"


@dataclass
class Manifest:
    """Everything outreach would do today."""

    day: str
    entries: list[Entry] = field(default_factory=list)

    @property
    def ready(self) -> list[Entry]:
        return [entry for entry in self.entries if entry.send]

    @property
    def held(self) -> list[Entry]:
        return [entry for entry in self.entries if not entry.send]

    def as_dict(self) -> dict:
        return {
            "day": self.day,
            "written_at": iso(),
            # Said plainly in the file itself, so nobody has to infer it.
            "nothing_was_sent": True,
            "entries": [
                {
                    "plugin": e.plugin,
                    "kind": e.kind,
                    "recipient": e.recipient,
                    "text": e.text,
                    "send": e.send,
                    "code": e.code,
                    "reason": e.reason,
                    "company": e.company,
                }
                for e in self.entries
            ],
        }

    def words(self) -> str:
        """What the user reads. Plain language, and honest about the count."""
        if not self.entries:
            return "No messages to go out today."
        lines = [
            f"{len(self.ready)} message(s) are ready and {len(self.held)} will not go out. "
            "Nothing has been sent."
        ]
        lines += [f"  - {entry.words}" for entry in self.entries]
        lines.append("Say the word and I will send the ready ones. Until then they sit here.")
        return "\n".join(lines)


def build_manifest(
    config: Config,
    *,
    leads: dict[str, list[dict]] | None = None,
    gate: OutboundGate | None = None,
    today: date | None = None,
) -> Manifest:
    """Ask every switched-on helper for its drafts and check each one.

    ``leads`` maps a plugin name to whatever it found to write about. With no
    leads a plugin contributes nothing, which is what happens on a day when
    nobody was looking.
    """
    from .plugins import load_plugins

    leads = leads or {}
    checker = gate or OutboundGate(config)
    manifest = Manifest(day=(today or date.today()).isoformat())

    for plugin in load_plugins(config):
        drafts: Iterable[Draft] = plugin.drafts(config, list(leads.get(plugin.name, [])))
        actions = plugin.manifest.outbound_actions or ("send_outreach_messages",)
        for draft in drafts:
            action = _action_for(draft, actions)
            check = checker.check(
                action,
                text=draft.text,
                context={"plugin": plugin.name, "recipient": draft.recipient, **draft.context},
            )
            manifest.entries.append(
                Entry(
                    plugin=plugin.name,
                    kind=draft.kind,
                    recipient=draft.recipient,
                    text=draft.text,
                    send=check.allowed,
                    code=check.code,
                    reason=check.reason,
                    company=str(draft.context.get("company", "")),
                )
            )
    return manifest


def _action_for(draft: Draft, actions: tuple[str, ...]) -> str:
    """A public comment and a private note are different permissions."""
    if draft.kind == "comment" and "post_public_comments" in actions:
        return "post_public_comments"
    return "send_outreach_messages" if "send_outreach_messages" in actions else actions[0]


def write_manifest(config: Config, manifest: Manifest) -> Path:
    """Save the manifest next to the rest of the day's records."""
    directory = config.paths.ensure().state / "outreach"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"manifest-{manifest.day}.json"
    destination.write_text(json.dumps(manifest.as_dict(), indent=2) + "\n", encoding="utf-8")
    return destination


def read_manifest(config: Config, day: str) -> Manifest | None:
    path = config.paths.ensure().state / "outreach" / f"manifest-{day}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Manifest(
        day=str(payload.get("day", day)),
        entries=[
            Entry(
                plugin=str(e.get("plugin", "")),
                kind=str(e.get("kind", "")),
                recipient=str(e.get("recipient", "")),
                text=str(e.get("text", "")),
                send=bool(e.get("send", False)),
                code=str(e.get("code", "")),
                reason=str(e.get("reason", "")),
                company=str(e.get("company", "")),
            )
            for e in payload.get("entries", [])
            if isinstance(e, dict)
        ],
    )
