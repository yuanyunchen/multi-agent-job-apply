"""The things that say "no".

Three independent guards, all fail-closed:

* :class:`AnswerBank` — a form answer comes from the user's answer file or it
  does not exist. An unknown question stops that application and asks the user;
  it is never invented. Personal identifiers always stop.
* :class:`OutboundGate` — nothing is submitted, sent or posted unless the
  matching permission is on in the settings **and** the action passes every
  check. A blocked action is a hard skip: never reworded and retried.
* :class:`LaneGuard` — how many browsers may run at once, given the memory on
  this machine.

There is also a flat refusal built in: password resets. The system never
triggers, reads or follows a password-reset flow, in any plugin, ever.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

from .config import Config
from .errors import GateBlocked, NeedsUser

#: Wording that means a password reset. Never followed, never requested.
RESET_WORDS = (
    "forgot password",
    "forgot your password",
    "reset password",
    "reset your password",
    "password reset",
    "set a new password",
)

#: Questions that always wait for the user, whatever the answer file says.
ALWAYS_ASK_DEFAULT = (
    "social security",
    "date of birth",
    "driver's license number",
    "passport number",
)


def is_password_reset(text: str) -> bool:
    low = (text or "").lower()
    return any(phrase in low for phrase in RESET_WORDS)


@dataclass(frozen=True, slots=True)
class Answer:
    id: str
    value: str


@dataclass
class AnswerBank:
    """Answers the user wrote down, and nothing else."""

    entries: list[dict[str, Any]] = field(default_factory=list)
    always_ask: tuple[str, ...] = ALWAYS_ASK_DEFAULT

    @classmethod
    def from_file(cls, path: str | Path | None) -> "AnswerBank":
        if not path or not Path(path).exists():
            return cls()
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        entries = [e for e in (payload.get("answers") or []) if isinstance(e, dict)]
        extra = tuple(str(x).lower() for x in (payload.get("always_ask") or []))
        return cls(entries=entries, always_ask=extra or ALWAYS_ASK_DEFAULT)

    @classmethod
    def from_config(cls, config: Config) -> "AnswerBank":
        return cls.from_file(config.user_path("documents.answers"))

    def lookup(self, question: str) -> Answer | None:
        """The answer for this question, or ``None`` if the user never gave one."""
        low = " ".join((question or "").lower().split())
        if any(phrase in low for phrase in self.always_ask):
            return None
        for entry in self.entries:
            for phrase in entry.get("match") or []:
                if str(phrase).lower() in low:
                    return Answer(str(entry.get("id") or "answer"), str(entry.get("answer", "")))
        return None

    def answer_or_ask(self, question: str) -> str:
        """Either the user's answer, or a stop. Never a guess."""
        found = self.lookup(question)
        if found is None:
            raise NeedsUser(question)
        return found.value

    def answer_all(self, questions: list[str]) -> tuple[dict[str, str], list[str]]:
        """``(answers, questions_we_must_ask)`` — no exceptions, for a wave."""
        answers: dict[str, str] = {}
        unknown: list[str] = []
        for question in questions:
            found = self.lookup(question)
            if found is None:
                unknown.append(question)
            else:
                answers[question] = found.value
        return answers, unknown


@dataclass(frozen=True, slots=True)
class GateResult:
    allowed: bool
    code: str = "ok"
    reason: str = ""

    def raise_if_blocked(self) -> None:
        if not self.allowed:
            raise GateBlocked(self.code, self.reason)


@dataclass
class OutboundGate:
    """Every submit, message and comment passes through here first."""

    config: Config
    #: Extra per-action checks, e.g. a plugin's weekly cap.
    checks: dict[str, Callable[[str, dict], GateResult]] = field(default_factory=dict)
    pause_file: Path | None = None
    banned_phrases: tuple[str, ...] = ("visa", "sponsorship", "work authorization", "immigration")
    max_chars: int = 1200

    def check(self, action: str, *, text: str = "", context: dict | None = None) -> GateResult:
        context = context or {}

        if self.pause_file is not None and self.pause_file.exists():
            return GateResult(False, "paused", "Everything outbound is paused right now.")

        if not self.config.permitted(action):
            return GateResult(
                False,
                "not_permitted",
                f"You have not given me permission to do this yet ({_words(action)}).",
            )

        if is_password_reset(text) or is_password_reset(str(context.get("page_text", ""))):
            return GateResult(False, "password_reset", "This looks like a password reset. I never do those.")

        if text:
            if len(text) > self.max_chars:
                return GateResult(False, "too_long", "That message is longer than I am allowed to send.")
            low = text.lower()
            if action == "post_public_comments":
                for phrase in self.banned_phrases:
                    if re.search(rf"\b{re.escape(phrase)}\b", low):
                        return GateResult(
                            False, "banned_phrase", f"A public comment must not mention {phrase}."
                        )
            if context.get("approved_text") is not None and text != context["approved_text"]:
                return GateResult(
                    False,
                    "text_changed",
                    "The wording changed after it was approved, so I did not send it.",
                )

        extra = self.checks.get(action)
        if extra is not None:
            return extra(text, context)
        return GateResult(True)


def _words(action: str) -> str:
    return action.replace("_", " ")


# -- lanes ---------------------------------------------------------------


def memory_available_mb() -> int:
    """Free memory on this machine, or a large number if we cannot tell."""
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        pass
    return 1 << 20


@dataclass(frozen=True, slots=True)
class Admission:
    allowed: bool
    code: str = "ok"  # ok | at_capacity | low_memory
    reason: str = ""


@dataclass
class LaneGuard:
    """How many applications may be in flight at once on this machine."""

    max_lanes: int
    min_free_memory_mb: int
    projected_per_lane_mb: int
    probe: Callable[[], int] = memory_available_mb

    @classmethod
    def from_config(cls, config: Config, probe: Callable[[], int] | None = None) -> "LaneGuard":
        return cls(
            max_lanes=int(config.get("apply.max_lanes", 2)),
            min_free_memory_mb=int(config.get("apply.min_free_memory_mb", 1500)),
            projected_per_lane_mb=int(config.get("apply.projected_memory_per_lane_mb", 1200)),
            probe=probe or memory_available_mb,
        )

    def admit(self, running: int) -> Admission:
        """Admit one more lane? Memory is checked as a *projection*."""
        if running >= self.max_lanes:
            return Admission(False, "at_capacity", "I am already working on as many as I can at once.")
        free = self.probe()
        projected = free - (running + 1) * self.projected_per_lane_mb
        if projected < self.min_free_memory_mb:
            return Admission(
                False,
                "low_memory",
                "This computer is low on memory, so I will wait before starting another one.",
            )
        return Admission(True)

    def lanes_available(self, running: int = 0) -> int:
        count = 0
        while self.admit(running + count).allowed:
            count += 1
            if running + count >= self.max_lanes:
                break
        return count
