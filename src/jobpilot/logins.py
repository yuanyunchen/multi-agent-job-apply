"""The sign-in checklist, one platform at a time.

The rule this module exists to enforce: **only the user ever signs in.** This
code never asks for a password, never types one, never stores one and never sees
one. All it does is tell the user which page to open, wait for them to say
"done", and then ask the helper itself whether it looks signed in.

A helper that is skipped is reported, not silently ignored: the user is told
which features stay off.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from . import catalog
from .config import Config
from .domain import iso
from .ui import plural

SKIP_WORDS = {"skip", "later", "not now", "no"}
DONE_WORDS = {"done", "yes", "y", "ok", "okay", "signed in", "finished", "ready"}


@dataclass(frozen=True, slots=True)
class Step:
    """One platform to sign in to, in the words the user needs."""

    name: str
    login: str
    why: str
    how: str
    never: tuple[str, ...] = ()

    def read_out(self) -> str:
        lines = [
            f"{self.login}.",
            f"Why I need it: {self.why}",
            "What you do: open that site in your own browser and sign in as you normally would, "
            "then tell me 'done'. I never ask for your password and never sign in as you.",
        ]
        if self.how:
            lines.append(f"How I check: {self.how}")
        if self.never:
            lines.append("I will never " + "; ".join(self.never) + ".")
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class Result:
    name: str
    #: confirmed  — something actually reached a signed-in page or mailbox
    #: unverified — the settings look right, but nobody has *seen* a sign-in
    #: skipped    — the user asked to leave it for later
    #: unavailable— nothing is wrong, but a part of it is not connected yet
    #: needs_help — it should work and does not
    state: str
    detail: str = ""

    @property
    def words(self) -> str:
        return {
            "confirmed": (f"{self.name}: ready — {self.detail}." if self.detail else f"{self.name}: ready."),
            "unverified": (
                f"{self.name}: set up, but I have not watched you sign in, so I will not call it "
                f"ready. {self.detail}".rstrip()
            ),
            "skipped": f"{self.name}: left for later, so its part stays switched off.",
            "unavailable": f"{self.name}: {self.detail}.",
            "needs_help": f"{self.name}: not working yet — {self.detail}",
        }[self.state]

    @property
    def ready(self) -> bool:
        return self.state == "confirmed"


def steps(config: Config) -> list[Step]:
    """Every sign-in the current settings imply, and nothing more."""
    out = [
        Step(
            name="mailbox",
            login="The email account you put on applications",
            why=(
                "it is how I know which applications really arrived, and how I spot an "
                "interview invitation"
            ),
            how="I read the newest subject lines back to you, and nothing else.",
            never=(
                "send, reply to, delete or file your mail",
                "follow a password-reset link",
                "write down a verification code",
            ),
        )
    ]
    for entry in catalog.logins_needed(config):
        out.append(
            Step(
                name=entry.name,
                login=entry.login,
                why=f"it is what '{entry.name}' works with: {entry.summary}",
                how=entry.login_how,
                never=entry.never,
            )
        )
    return out


@dataclass(frozen=True, slots=True)
class Reach:
    """What a real check found. ``ok`` means it genuinely got to a signed-in page."""

    ok: bool
    detail: str


@runtime_checkable
class Probe(Protocol):
    """Something that can actually reach a platform, read-only.

    ``reach`` returns ``None`` for "I could not tell" — which is different from
    "not signed in", and must never be reported as a sign-in.
    """

    def reach(self, step: Step) -> Reach | None: ...


@dataclass
class LiveProbe:
    """The real check: open the thing and see whether it answers as you.

    Three kinds of platform, three ways of asking:

    * **the mailbox** — read the newest few subject lines. Read-only, and the
      subjects are counted rather than shown anywhere they could be logged.
    * **a model tool** — ask the tool itself; it reports whether you are signed
      in, and that answer comes from the tool, not from the settings.
    * **a helper** — hand its own verification instruction to a browser-capable
      model, which opens the page without changing anything and says what
      account it sees.

    What it never does: type a password, create a session, sign anything in or
    out, or click anything on the page.
    """

    config: Config

    def reach(self, step: Step) -> Reach | None:
        if step.name == "mailbox":
            return self._mailbox()
        entry = catalog.find(step.name)
        if entry is not None and entry.kind == "model":
            return self._model(entry)
        return self._helper(step)

    def _mailbox(self) -> Reach | None:
        from datetime import timedelta

        from .domain import now
        from .verify import reader_from_config

        reader = reader_from_config(self.config)
        if reader is None:
            return None
        try:
            at = now()
            messages = list(reader.messages(since=at - timedelta(days=7), until=at))
        except Exception as exc:  # unreadable is not the same as not signed in
            return Reach(False, f"I could not read that mailbox ({type(exc).__name__})")
        return Reach(True, f"I read {plural(len(messages), 'recent message')} without changing anything")

    def _model(self, entry) -> Reach | None:
        from .providers import build_registry

        registry = build_registry(self.config)
        models = [name for name in entry.models if name in registry.providers]
        if not models:
            return None
        healthy = [name for name in models if registry.health_of(name).ok]
        if healthy:
            return Reach(True, "the tool itself says you are signed in")
        why = "; ".join(registry.health_of(name).detail for name in models)
        return Reach(False, why or "the tool does not report a sign-in")

    def _helper(self, step: Step) -> Reach | None:
        """Ask a browser-capable model to open the page and report, read-only."""
        from .errors import JobpilotError
        from .providers import build_registry

        if not step.how:
            return None
        try:
            provider = build_registry(self.config).for_role("browser")
        except JobpilotError:
            return None  # no browser model: cannot tell, so do not claim
        prompt = (
            f"Open {step.login} in the already-signed-in browser session and {step.how} "
            "Change nothing: do not click, type, send, post or sign in or out. "
            'Answer with JSON only: {"signed_in": true|false, "saw": "what you saw, in one short line"}'
        )
        try:
            result = provider.complete(prompt, schema=_REACH_SCHEMA)
        except Exception:
            return None
        payload = result.data if result.ok else None
        if not isinstance(payload, dict) or "signed_in" not in payload:
            return None
        saw = " ".join(str(payload.get("saw", "")).split())[:120]
        if payload.get("signed_in"):
            return Reach(True, saw or "I opened the page and it knew who you were")
        return Reach(False, saw or "the page asked me to sign in, which only you can do")


_REACH_SCHEMA = {
    "type": "object",
    "required": ["signed_in"],
    "properties": {"signed_in": {"type": "boolean"}, "saw": {"type": "string"}},
}


def check(config: Config, step: Step, *, probe: Probe | None = None) -> Result:
    """Is this platform ready?

    A sign-in is only ever reported as ready when something **actually reached
    it**. Settings that merely look right give ``unverified``: the difference
    matters, because telling somebody they are signed in when nobody looked is
    how a whole day's applications quietly fail.
    """
    shallow = _settings_look_right(config, step)
    if shallow.state != "confirmed":
        return shallow

    found = probe.reach(step) if probe is not None else None
    if found is None:
        return Result(
            step.name,
            "unverified",
            f"To be sure, {step.how[0].lower() + step.how[1:] if step.how else 'open it and check'}",
        )
    if found.ok:
        return Result(step.name, "confirmed", found.detail)
    return Result(step.name, "needs_help", found.detail)


def _settings_look_right(config: Config, step: Step) -> Result:
    """The cheap half: is this platform configured at all? Touches no account."""
    if step.name == "mailbox":
        reader = str(config.get("verify.mail_reader", "none"))
        if reader == "none":
            return Result(
                step.name,
                "unavailable",
                "you are signed in, but I have no way to read that mailbox yet, so "
                "applications will stay 'sent' rather than 'confirmed'",
            )
        return Result(step.name, "confirmed", "a mailbox is connected")

    from .plugins import load_plugins

    plugin = next((p for p in load_plugins(config) if p.name == step.name), None)
    if plugin is None:
        entry = catalog.find(step.name)
        if entry and entry.kind == "model":
            from .providers import build_registry

            registry = build_registry(config)
            models = [m for m in entry.models if m in registry.providers]
            if not models:
                return Result(step.name, "needs_help", "it is not switched on")
            return Result(step.name, "confirmed", "it is switched on")
        return Result(step.name, "skipped", "it is switched off")
    ok, detail = plugin.health(config)
    return Result(step.name, "confirmed" if ok else "needs_help", detail)


@dataclass
class Checklist:
    """Walks the steps with whoever is answering, and remembers the outcome."""

    config: Config
    results: list[Result] = field(default_factory=list)
    probe: Probe | None = None

    def walk(self, asker: Any, *, wait_for_user: bool = True) -> list[Result]:
        """Read out each sign-in and, unless told not to, wait for the user.

        ``wait_for_user=False`` reads the checklist out and checks what it can
        without asking anything — which is what happens when nobody is there to
        answer, so this never sits waiting on a closed input. In that case it
        also **never reports a platform as signed in**: with nobody present to
        sign in, and often no browser to look with, "ready" would be a guess.
        """
        from .wizard import Question, parse_answer

        asker.say(
            "Now the sign-ins. One at a time, and you are the only one who ever signs in to "
            "anything. I never see a password."
        )
        probe = self.probe if wait_for_user else None
        if not wait_for_user:
            asker.say(
                "Nobody is here to answer, so I will read the list out and say what the settings "
                "look like. I will not call anything ready: that needs someone to sign in."
            )
        for step in steps(self.config):
            asker.say("")
            asker.say(step.read_out())
            if wait_for_user:
                question = Question(
                    f"login.{step.name}",
                    "Tell me 'done' when you are signed in, or press enter to leave it for later.",
                    # Nothing to read — a closed input, or someone pressing
                    # enter — means "later". Assuming "done" would report a
                    # sign-in nobody made.
                    "skip",
                    "Nothing happens until you say so.",
                )
                said = str(parse_answer(question, asker.ask(question))).strip().lower()
                if said in SKIP_WORDS:
                    self.results.append(Result(step.name, "skipped", "you asked me to leave it"))
                    asker.say(Result(step.name, "skipped", "").words)
                    continue
            result = check(self.config, step, probe=probe)
            self.results.append(result)
            asker.say(result.words)
        self.save()
        asker.say("")
        asker.say(summary(self.results))
        return self.results

    def save(self) -> None:
        path = self.config.paths.ensure().state / "logins.json"
        payload = {
            "checked_at": iso(),
            "results": [{"name": r.name, "state": r.state, "detail": r.detail} for r in self.results],
        }
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def summary(results: list[Result]) -> str:
    ready = [r.name for r in results if r.state == "confirmed"]
    waiting = [r for r in results if r.state != "confirmed"]
    lines = [f"Ready: {', '.join(ready) if ready else 'nothing yet'}."]
    if waiting:
        lines.append("Still to do, and what stays off until then:")
        lines += [f"  - {r.words}" for r in waiting]
    else:
        lines.append("Everything you need to be signed in to is signed in.")
    return "\n".join(lines)
