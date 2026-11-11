"""Everything the user can switch on, in one list.

Two kinds of thing are optional: **helpers** (the plugins — LinkedIn, a school
job platform, a startup list) and **models** (the engines that read job
descriptions and, for helpers that need it, drive a browser).

They live in different places in the code for good reasons, but a user should
not have to care: the wizard, the README table and ``status`` all read this one
catalogue, so what the user is offered can never drift from what is installed.

Helper entries are generated from the plugin manifests. Model entries are
declared here, because a model has no manifest to generate them from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import Config
from .plugins import discover

#: Which model answers which question. Kept here so one list explains all three.
ROLE_WORDS = {
    "screen": "reading job descriptions and deciding what is worth applying to",
    "review": "reviewing, planning and double-checking its own work",
    "browser": "working inside a web page, for the helpers that need a browser",
}


@dataclass(frozen=True, slots=True)
class Entry:
    """One switchable thing, described the way a person would describe it."""

    name: str
    kind: str  # "helper" | "model"
    summary: str  # one plain sentence
    adds: str  # what switching it on gives you
    enabled_key: str  # the dotted settings key that turns it on
    login: str = ""  # what you have to be signed in to; "" = nothing
    #: The same thing as a sentence that reads correctly mid-paragraph, e.g.
    #: "It needs a key from that service, kept in your computer's environment."
    #: Without this, "it needs you to be signed in to a key from that service"
    #: and "Needs: Your school's job platform" both come out wrong.
    login_sentence: str = ""
    #: What the user does about it, as a phrase: "signing in to LinkedIn, in
    #: your own browser", or "putting your key ... in your computer's
    #: environment" for the one that is not a sign-in at all.
    login_your_part: str = ""
    login_how: str = ""  # how you sign in, and how I check
    never: tuple[str, ...] = ()
    default_on: bool = False
    models: tuple[str, ...] = ()  # model names this entry provides
    needs: tuple[str, ...] = ()  # extra settings it needs before it works
    explain: str = ""

    @property
    def login_needed(self) -> str:
        """For a table cell, where a capitalised label is fine."""
        return self.login or "none"

    @property
    def your_part(self) -> str:
        """What the user has to do, as a phrase that fits in a list."""
        return self.login_your_part or f"signing in to {self.login}"

    @property
    def needs_sentence(self) -> str:
        """One sentence about what it needs from you. Reads as prose."""
        if not self.login:
            return "It needs no account and no sign-in."
        return self.login_sentence or f"It needs you to be signed in to {self.login}."

    def describe(self) -> str:
        """The paragraph the wizard reads out before asking about this entry."""
        lines = [self.summary]
        if self.explain:
            lines.append(self.explain)
        lines.append(f"{self.needs_sentence} {self.login_how}".strip())
        if self.never:
            lines.append("It will never " + "; ".join(self.never) + ".")
        return " ".join(line.strip() for line in lines if line.strip())


#: The models. Each entry says which model names it offers, so the wizard can
#: map the three jobs above onto whatever the user switched on.
MODEL_ENTRIES: tuple[Entry, ...] = (
    Entry(
        name="claude",
        kind="model",
        summary="Claude, through the Claude Code command-line tool.",
        adds="the engine that reads job descriptions, reviews its own work and can work in a browser",
        enabled_key="models.providers.claude.enabled",
        login="your Claude account, in the Claude Code tool",
        login_sentence="It needs you to be signed in to Claude in the Claude Code tool.",
        login_your_part="signing in to Claude in the Claude Code tool",
        login_how="Sign in once in that tool; I only ever check that it says you are signed in.",
        never=("sign you out", "copy your sign-in files", "change that tool's own settings"),
        default_on=True,
        models=("claude-haiku", "claude-sonnet", "claude-opus"),
        explain=(
            "Haiku is the quick, cheap one and does the bulk reading; Sonnet is the middle "
            "option; Opus is the careful one used for reviewing and planning."
        ),
    ),
    Entry(
        name="codex",
        kind="model",
        summary="Codex, through its own command-line tool.",
        adds="a second engine, so one being unavailable does not stop everything",
        enabled_key="models.providers.codex.enabled",
        login="your account in the Codex tool",
        login_sentence="It needs you to be signed in to the Codex tool.",
        login_your_part="signing in to the Codex tool",
        login_how="Sign in once in that tool; I only ever check that it says you are signed in.",
        never=("sign you out", "copy your sign-in files"),
        models=("codex",),
    ),
    Entry(
        name="openai_compatible",
        kind="model",
        summary="Another model service that you host yourself or already pay for.",
        adds="the option of using a model of your own instead of the ones above",
        enabled_key="models.providers.openai_compatible.enabled",
        login="a key from that service",
        login_sentence=(
            "It needs a key from that service, kept in your computer's environment."
        ),
        login_your_part="putting your key for that service in your computer's environment",
        login_how=(
            "Keep the key in your computer's environment and tell me the name you gave it. "
            "The key itself is never written into your settings."
        ),
        never=("write your key into a file", "show your key in any message"),
        needs=("models.providers.openai_compatible.base_url", "models.providers.openai_compatible.model"),
    ),
    Entry(
        name="fake",
        kind="model",
        summary="A stand-in that makes up answers in a fixed, predictable way.",
        adds="a practice mode that works end to end without a real model",
        enabled_key="models.providers.fake.enabled",
        models=("fake",),
        explain="Useful for a practice run. It is not a real model and should not be left on.",
    ),
)

#: When several models are available, this is the order each job prefers.
ROLE_PREFERENCE = {
    "screen": ("claude-haiku", "claude-sonnet", "codex", "openai_compatible", "fake"),
    "review": ("claude-opus", "claude-sonnet", "codex", "openai_compatible", "fake"),
    "browser": ("claude-haiku", "claude-sonnet", "codex", "fake"),
}


def helper_entries() -> list[Entry]:
    """One entry per installed plugin, generated from its manifest."""
    out: list[Entry] = []
    for manifest in discover():
        login = manifest.logins[0] if manifest.logins else None
        out.append(
            Entry(
                name=manifest.name,
                kind="helper",
                summary=manifest.summary,
                adds=_adds_from(manifest),
                enabled_key=f"plugins.{manifest.name}.enabled",
                login=login.label if login else "",
                login_sentence=(login.sentence if login else ""),
                login_your_part=(login.your_part if login else ""),
                # "you sign in yourself" is already said by your_part, and
                # saying it twice in one breath is how this read before.
                login_how=(f"I check by {login.verify}." if login and login.verify else ""),
                never=tuple(login.never) if login else (),
                default_on=manifest.enabled_default,
                explain=" ".join(manifest.explain.split()),
            )
        )
    return out


def _adds_from(manifest) -> str:
    parts = []
    if "tracker_rows" in manifest.writes:
        parts.append("more jobs to apply to")
    if manifest.outbound_actions:
        parts.append("messages on your behalf, only with your permission")
    return ", ".join(parts) or "extra information in your daily summary"


def catalog() -> list[Entry]:
    """Helpers first, then models — the order the wizard asks about them."""
    return [*helper_entries(), *MODEL_ENTRIES]


def find(name: str) -> Entry | None:
    return next((entry for entry in catalog() if entry.name == name), None)


def is_enabled(config: Config, entry: Entry) -> bool:
    return bool(config.get(entry.enabled_key, entry.default_on))


def enabled_entries(config: Config) -> list[Entry]:
    return [entry for entry in catalog() if is_enabled(config, entry)]


def logins_needed(config: Config) -> list[Entry]:
    """Everything switched on that the user has to be signed in to."""
    return [entry for entry in enabled_entries(config) if entry.login]


def available_models(data: dict[str, Any]) -> list[str]:
    """Every model name offered by the engines switched on in ``data``."""
    out: list[str] = []
    for entry in MODEL_ENTRIES:
        if not _get(data, entry.enabled_key):
            continue
        if entry.name == "openai_compatible":
            model = _get(data, "models.providers.openai_compatible.model")
            out.append(str(model) if model else "openai_compatible")
            continue
        out.extend(entry.models)
    return out


def role_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Pick a model for each of the three jobs, from what is switched on."""
    offered = available_models(data)
    chosen: dict[str, Any] = {}
    for role, preference in ROLE_PREFERENCE.items():
        pick = next((model for model in preference if model in offered), None)
        chosen[role] = pick or (offered[0] if offered else "")
    spares = [model for model in offered if model not in chosen.values()]
    chosen["fallback"] = spares
    return chosen


def table_rows() -> list[tuple[str, str, str, str]]:
    """``(name, what it adds, login needed, default)`` for the README table."""
    rows = []
    for entry in catalog():
        rows.append(
            (
                entry.name,
                entry.adds,
                entry.login_needed,
                "on" if entry.default_on else "off",
            )
        )
    return rows


def status_lines(config: Config) -> list[str]:
    """What ``status`` prints: every switchable thing and whether it is on."""
    lines = []
    for entry in catalog():
        state = "on" if is_enabled(config, entry) else "off"
        lines.append(f"- {entry.name} ({state}): {entry.summary}")
    return lines


def model_jobs(config: Config) -> list[str]:
    """Which model is doing each of the three jobs, in plain words."""
    lines = []
    for role, words in ROLE_WORDS.items():
        chosen = str(config.get(f"models.{role}", "")) or "nothing yet"
        lines.append(f"- {words}: {_model_words(chosen)}")
    return lines


def _model_words(model: str) -> str:
    return {
        "claude-haiku": "Claude Haiku (quick and cheap)",
        "claude-sonnet": "Claude Sonnet (the middle option)",
        "claude-opus": "Claude Opus (the careful one)",
        "codex": "Codex",
        "fake": "the stand-in that makes up answers (practice only)",
    }.get(model, model or "nothing yet")


def _get(data: dict[str, Any], dotted: str) -> Any:
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def set_enabled(data: dict[str, Any], entry: Entry, value: bool) -> None:
    """Switch an entry on or off inside a settings dictionary."""
    node = data
    parts = entry.enabled_key.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = bool(value)


@dataclass
class Selection:
    """What the user chose, and what it implies for the model mapping."""

    chosen: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def apply_to(self, data: dict[str, Any]) -> dict[str, Any]:
        for entry in catalog():
            set_enabled(data, entry, entry.name in self.chosen)
        data.setdefault("models", {}).update(role_mapping(data))
        return data
