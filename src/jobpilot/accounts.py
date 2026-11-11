"""Which employer sites have an account, and which are waiting for the user.

Some application systems make you create an account before you can submit. This
module remembers **which** sites those are and **what state** each one is in. It
stores nothing else — in particular:

* **no passwords, no tokens, no cookies, nothing secret.** Not encrypted, not
  obfuscated: simply absent. If a site needs a credential, the user holds it in
  their own password manager and types it themselves.
* **no personal data.** A key is a site, not a person.

An account is only ever created where the rule allows it: sign-up by email
confirmation alone. Anything else — single sign-on, a social login, a text
message to a phone, a puzzle to prove you are human — is handed back to the
user, because working around any of those means pretending to be them.

And the rule that has no exceptions: **a password is never reset.** Not a reset
link, not a "forgot password" page, not a second verification code. Those all
end an application and ask the user.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from .config import Config
from .domain import iso

#: What the registry knows about a site. Nothing here is a secret.
STATES = (
    "none",  # never needed an account there
    "not_needed",  # that system submits without one
    "exists",  # an account is there and usable
    "needs_user",  # only the user can get past the sign-up
    "blocked",  # we tried and could not, with a reason
)

#: Application systems that never ask for an account.
NO_ACCOUNT_SYSTEMS = frozenset({"greenhouse", "lever", "ashby"})

#: Walls we hand back instead of working around. The wording is the user's.
WALLS = {
    "sso": "it wants a company or Google/Microsoft sign-in",
    "social": "it wants you to sign in with another website's account",
    "phone": "it wants to text a code to your phone",
    "captcha": "it wants someone to prove they are a person",
    "unknown": "it wants something I cannot do on your behalf",
}

#: Hosts that belong to several employers, so the host alone is not the key.
SHARED_HOSTS = frozenset(
    {
        "jobs.smartrecruiters.com",
        "apply.workable.com",
        "jobs.jobvite.com",
        "recruiting.ultipro.com",
        "recruiting.paylocity.com",
        "ats.rippling.com",
    }
)

#: Hosts whose first label names the employer's own tenant.
TENANT_SUFFIXES = (".myworkdayjobs.com", ".myworkdaysite.com")


def site_key(url: str, *, company: str = "") -> str:
    """The key an account belongs under: a tenant, a board slug, or a host.

    The key has to be the same for every posting at one employer and different
    for two employers who happen to share an application system — which is why
    a shared host falls back to the company name rather than the host.
    """
    parts = urlsplit(url or "")
    host = (parts.hostname or "").lower().removeprefix("www.")
    if not host:
        return ""
    if host.endswith(TENANT_SUFFIXES):
        return host.split(".")[0]
    if host in SHARED_HOSTS:
        from .domain import normalize_name

        segments = [segment for segment in parts.path.split("/") if segment]
        slug = segments[0].lower() if segments else ""
        named = normalize_name(company).replace(" ", "-")
        return f"{host}/{slug or named or 'unknown'}"
    return host


#: ``password: hunter2`` — a named secret with a value after it.
_NAMED_VALUE = re.compile(
    r"(?i)\b(pass(?:word|wd|phrase)?|token|secret|cookie|session|otp|api[_\- ]?key)\b\s*[:=]\s*\S"
)

#: A long opaque run of characters, which is what a token looks like whatever
#: it is called.
_OPAQUE = re.compile(r"\b(?=[A-Za-z0-9_\-]{16,}\b)(?=[^\s]*[A-Z])(?=[^\s]*[a-z])(?=[^\s]*\d)\S+")


def looks_like_a_credential(text: str) -> str:
    """Why this text must not be stored, or ``""`` if it is fine.

    The words themselves are allowed: "it wants to text a code to your phone"
    is a perfectly good reason. A *value* is not.
    """
    if _NAMED_VALUE.search(text or ""):
        return "it has something named like a credential with a value after it"
    if _OPAQUE.search(text or ""):
        return "it has a long opaque string in it, which is what a token looks like"
    return ""


@dataclass(frozen=True, slots=True)
class Account:
    """One site's state. Deliberately boring: a key, a state, a reason, a date."""

    key: str
    state: str
    reason: str = ""
    checked_at: str = ""
    system: str = ""

    @property
    def usable(self) -> bool:
        return self.state in ("exists", "not_needed")

    @property
    def words(self) -> str:
        if self.state == "exists":
            return f"{self.key}: ready."
        if self.state == "not_needed":
            return f"{self.key}: no account needed."
        if self.state == "needs_user":
            return f"{self.key}: needs you — {self.reason or WALLS['unknown']}."
        if self.state == "blocked":
            return f"{self.key}: I could not get in — {self.reason}."
        return f"{self.key}: nothing yet."


@dataclass
class AccountRegistry:
    """The whole registry: one small JSON file of site states.

    Reading it out is safe by construction — there is nothing in it to leak.
    """

    path: Path
    entries: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_config(cls, config: Config) -> "AccountRegistry":
        return cls(path=config.paths.ensure().state / "accounts.json").load()

    def load(self) -> "AccountRegistry":
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except ValueError:
                payload = {}
            raw = payload.get("accounts", {}) if isinstance(payload, dict) else {}
            self.entries = {str(k): dict(v) for k, v in raw.items() if isinstance(v, dict)}
        return self

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(
            json.dumps({"updated_at": iso(), "accounts": self.entries}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp.replace(self.path)
        # Not a secret store, but not world-readable either: it says which
        # employers somebody is applying to.
        self.path.chmod(0o600)
        return self.path

    # -- reading ---------------------------------------------------------
    def get(self, key: str) -> Account:
        entry = self.entries.get(key, {})
        return Account(
            key=key,
            state=str(entry.get("state", "none")),
            reason=str(entry.get("reason", "")),
            checked_at=str(entry.get("checked_at", "")),
            system=str(entry.get("system", "")),
        )

    def for_row(self, row: dict) -> Account:
        key = site_key(str(row.get("url", "")), company=str(row.get("company", "")))
        if str(row.get("ats", "")).lower() in NO_ACCOUNT_SYSTEMS:
            return Account(key=key or str(row.get("ats", "")), state="not_needed", system=str(row.get("ats", "")))
        return self.get(key)

    def all(self) -> list[Account]:
        return [self.get(key) for key in sorted(self.entries)]

    def needing_user(self) -> list[Account]:
        return [account for account in self.all() if account.state == "needs_user"]

    def summary(self) -> dict[str, int]:
        """Counts per state — the only shape this is ever reported in."""
        out: dict[str, int] = {}
        for account in self.all():
            out[account.state] = out.get(account.state, 0) + 1
        return out

    # -- writing ---------------------------------------------------------
    def record(self, key: str, state: str, *, reason: str = "", system: str = "") -> Account:
        """Note what a site needs. Refuses anything shaped like a credential.

        Mentioning a password is fine — "it wants to text a code to your
        phone" is exactly the sort of reason that belongs here. Carrying a
        *value* is not, so the check looks for the shape of one rather than for
        the words.
        """
        if state not in STATES:
            raise ValueError(f"{state!r} is not one of {', '.join(STATES)}")
        for text in (key, reason, system):
            problem = looks_like_a_credential(str(text))
            if problem:
                raise ValueError(f"this registry stores no credentials: {problem}")
        self.entries[key] = {
            "state": state,
            "reason": reason,
            "system": system,
            "checked_at": iso(),
        }
        return self.get(key)

    def hand_back(self, key: str, wall: str, *, system: str = "") -> Account:
        """Record a wall only the user can get past, in their words."""
        return self.record(key, "needs_user", reason=WALLS.get(wall, WALLS["unknown"]), system=system)

    def may_create(self, *, signup: str) -> tuple[bool, str]:
        """May an account be created here? Only for email-confirmation sign-up.

        ``signup`` is how the site lets somebody sign up: ``email_verify``,
        ``sso``, ``social``, ``phone`` or ``captcha``.
        """
        if signup == "email_verify":
            return True, "sign-up is just an email confirmation, which is fine"
        return False, WALLS.get(signup, WALLS["unknown"])
