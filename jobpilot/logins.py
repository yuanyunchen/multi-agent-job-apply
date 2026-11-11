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
from typing import Any

from . import catalog
from .config import Config
from .domain import iso

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
    #: confirmed  — signed in and working
    #: skipped    — the user asked to leave it for later
    #: unavailable— nothing is wrong, but a part of it is not connected yet
    #: needs_help — it should work and does not
    state: str
    detail: str = ""

    @property
    def words(self) -> str:
        return {
            "confirmed": f"{self.name}: ready.",
            "skipped": f"{self.name}: left for later, so its part stays switched off.",
            "unavailable": f"{self.name}: {self.detail}.",
            "needs_help": f"{self.name}: not working yet — {self.detail}",
        }[self.state]


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


def check(config: Config, step: Step) -> Result:
    """Ask the helper itself whether it looks ready. Never touches an account."""
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
        if entry and entry.kind == "helper":
            return Result(step.name, "skipped", "it is switched off")
        if entry and entry.kind == "model":
            from .providers import build_registry

            registry = build_registry(config)
            models = [m for m in entry.models if m in registry.providers]
            healthy = [m for m in models if registry.health_of(m).ok]
            if healthy:
                return Result(step.name, "confirmed", "the tool reports you are signed in")
            why = "; ".join(registry.health_of(m).detail for m in models) or "it is not switched on"
            return Result(step.name, "needs_help", why)
        return Result(step.name, "skipped", "it is switched off")
    ok, detail = plugin.health(config)
    return Result(step.name, "confirmed" if ok else "needs_help", detail)


@dataclass
class Checklist:
    """Walks the steps with whoever is answering, and remembers the outcome."""

    config: Config
    results: list[Result] = field(default_factory=list)

    def walk(self, asker: Any, *, wait_for_user: bool = True) -> list[Result]:
        """Read out each sign-in and, unless told not to, wait for the user.

        ``wait_for_user=False`` reads the checklist out and checks what it can
        without asking anything — which is what happens when nobody is there to
        answer, so this never sits waiting on a closed input.
        """
        from .wizard import Question, parse_answer

        asker.say(
            "Now the sign-ins. One at a time, and you are the only one who ever signs in to "
            "anything. I never see a password."
        )
        if not wait_for_user:
            asker.say(
                "Nobody is here to answer, so I will just read the list out and check what I can."
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
            result = check(self.config, step)
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
