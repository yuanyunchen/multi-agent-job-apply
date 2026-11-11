"""Settings: one user file, sensible defaults, friendly validation.

* The user owns exactly one file, ``config/preferences.yaml``.
* Everything missing from it falls back to :data:`DEFAULTS`.
* Every path the assistant writes to is derived from ``paths.data_dir``, which
  itself comes from the file or from ``JOBPILOT_DATA_DIR``. Nothing in this
  package contains an absolute path to anybody's machine.
* Validation collects *all* problems and reports them in one friendly message.
"""

from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigError

SCHEMA_VERSION = 2

ENV_DATA_DIR = "JOBPILOT_DATA_DIR"
ENV_CONFIG = "JOBPILOT_CONFIG"
ENV_HOME = "JOBPILOT_HOME"

DEFAULT_CONFIG_PATH = Path("config/preferences.yaml")
EXAMPLE_CONFIG_PATH = Path("config/preferences.example.yaml")
#: Where the timetable lives. The second entry is where it used to live, so a
#: checkout made before the move keeps working.
ROUTINES_PATHS = (Path("routines/routines.yaml"), Path("config/routines.yaml"))
DEFAULT_ROUTINES_PATH = ROUTINES_PATHS[0]

UI_MODES = ("simple", "technical")
UI_MODE_ALIASES = {"plain": "simple", "default": "simple", "verbose": "technical"}

PERMISSIONS = (
    "submit_applications",
    "send_outreach_messages",
    "post_public_comments",
    "send_digest_email",
)

DEFAULTS: dict[str, Any] = {
    "schema_version": SCHEMA_VERSION,
    "paths": {"data_dir": "~/.jobpilot"},
    "ui": {"mode": "simple", "self_optimization_notice": "one_line"},
    "identity": {
        "full_name": "",
        "apply_email": "",
        "digest_email": "",
        "never_use_emails": [],
        "phone": "",
        "current_location": "",
        "linkedin_url": "",
        "github_url": "",
    },
    "documents": {"resume": "", "answers": "config/answers.yaml", "background_notes": ""},
    "work_authorization": {
        "authorized_to_work": True,
        "needs_sponsorship_now_or_later": True,
        "has_clearance": False,
        "hard_exclude_on": {
            "no_sponsorship_at_all": True,
            "citizen_or_gc_only": True,
            "clearance_required": True,
            "itar_us_person": True,
        },
    },
    "timing": {"earliest_start_date": "", "timezone": "UTC"},
    "search": {
        "recency_days": 21,
        "max_required_years_experience": 2,
        "seniority_excludes": ["Senior", "Staff", "Principal", "Lead", "Manager"],
        "locations": {"countries": ["US"], "remote_ok": True, "preferred": []},
        "categories": {"core": [], "non_core": [], "excluded": []},
        "company_rules": {"hard_exclude": [], "hold_pending_user": []},
        "sources": {
            "greenhouse": {"enabled": False, "boards": []},
            "lever": {"enabled": False, "boards": []},
            "ashby": {"enabled": False, "boards": []},
        },
    },
    "apply": {
        "rows_per_wave": 20,
        "max_lanes": 2,
        "min_free_memory_mb": 1500,
        "projected_memory_per_lane_mb": 1200,
        "driver": "dry_run",
        "never_reapply": True,
        "park_when_unanswerable": True,
    },
    "permissions": {name: False for name in PERMISSIONS},
    "verify": {"receipt_window_minutes": 10, "mail_reader": "none", "mail_export_dir": ""},
    "models": {
        "screen": "claude-haiku",
        "review": "claude-opus",
        "browser": "claude-haiku",
        "fallback": [],
        "providers": {
            "claude": {
                "enabled": True,
                "command": "claude",
                "models": {
                    "claude-haiku": "claude-haiku-4-5-20251001",
                    "claude-sonnet": "claude-sonnet-5",
                    "claude-opus": "claude-opus-4-8",
                },
            },
            "codex": {"enabled": False, "command": "codex"},
            "openai_compatible": {
                "enabled": False,
                "base_url": "",
                "model": "",
                "api_key_env": "",
            },
            "fake": {"enabled": False},
        },
    },
    "plugins": {
        "linkedin": {"enabled": False, "weekly_connect_cap": 90, "scope": ["connect"]},
        "handshake": {"enabled": False, "school_name": ""},
        "yc": {"enabled": False, "weekly_application_cap": 10},
    },
    "notifications": {
        "digest_time": "08:00",
        "report_rejections": False,
        "immediate_alerts": [],
    },
    "tracker": {"backups_to_keep": 20, "lock_timeout_seconds": 30},
}


@dataclass(frozen=True, slots=True)
class Paths:
    """Every file the assistant writes, derived from one directory."""

    data_dir: Path

    @property
    def tracker(self) -> Path:
        return self.data_dir / "applications.json"

    @property
    def interviews(self) -> Path:
        return self.data_dir / "oa-interviews.json"

    @property
    def events(self) -> Path:
        return self.data_dir / "events.jsonl"

    @property
    def backups(self) -> Path:
        return self.data_dir / "backups"

    @property
    def state(self) -> Path:
        return self.data_dir / "state"

    @property
    def logs(self) -> Path:
        return self.data_dir / "logs"

    @property
    def lock(self) -> Path:
        return self.data_dir / "applications.lock"

    @property
    def changelog(self) -> Path:
        return self.data_dir / "changelog.md"

    @property
    def reflections(self) -> Path:
        return self.data_dir / "reflections.md"

    def ensure(self) -> "Paths":
        for directory in (self.data_dir, self.backups, self.state, self.logs):
            directory.mkdir(parents=True, exist_ok=True)
        return self


def expand(raw: str) -> Path:
    """``~`` and ``$VARS`` are allowed in every configured path."""
    return Path(os.path.expandvars(str(raw))).expanduser()


def _merge(base: Any, override: Any) -> Any:
    """Override on top of base, copying all the way down.

    The copy matters: without it the result shares nested dictionaries with
    :data:`DEFAULTS`, and anything that edits a loaded settings tree would
    quietly change the defaults for the rest of the process.
    """
    if isinstance(base, dict) and isinstance(override, dict):
        merged = {key: copy.deepcopy(value) for key, value in base.items()}
        for key, value in override.items():
            merged[key] = _merge(base[key], value) if key in base else copy.deepcopy(value)
        return merged
    return copy.deepcopy(base) if override is None else copy.deepcopy(override)


@dataclass(frozen=True)
class Config:
    """Read-only view over the merged settings."""

    data: dict[str, Any]
    source: Path | None = None

    # -- access ----------------------------------------------------------
    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def section(self, name: str) -> dict[str, Any]:
        value = self.get(name, {})
        return value if isinstance(value, dict) else {}

    @property
    def paths(self) -> Paths:
        raw = os.environ.get(ENV_DATA_DIR) or self.get("paths.data_dir") or "./data"
        return Paths(expand(raw).resolve())

    @property
    def ui_mode(self) -> str:
        mode = str(self.get("ui.mode", "simple")).strip().lower()
        return UI_MODE_ALIASES.get(mode, mode)

    def permitted(self, action: str) -> bool:
        """Permissions are opt-in: anything unknown is a no."""
        return bool(self.get(f"permissions.{action}", False))

    def plugin_enabled(self, name: str) -> bool:
        return bool(self.get(f"plugins.{name}.enabled", False))

    def repo_path(self, dotted: str) -> Path | None:
        """A configured path that is relative to the repository root, not data_dir."""
        raw = self.get(dotted)
        if not raw:
            return None
        path = expand(str(raw))
        return path if path.is_absolute() else (repo_root() / path)


#: Files that mark the top of a checkout. ``pyproject.toml`` alone is not
#: enough: a nested build directory can have one too.
ROOT_MARKERS = ("pyproject.toml", "config")


def repo_root() -> Path:
    """The project directory, whatever it is called and wherever it is run from.

    Looked up in this order, and never hardcoded:

    1. ``JOBPILOT_HOME``, for an installed copy whose files live elsewhere;
    2. the first directory at or above this package holding ``pyproject.toml``
       and a ``config`` directory — which works for both ``src/jobpilot`` and a
       flat checkout;
    3. the current directory, if it looks like a checkout;
    4. the package's own parent, as a last resort.

    This is why nothing in the project prints ``cd ~/jobpilot``: the folder is
    whatever the user cloned into.
    """
    override = os.environ.get(ENV_HOME)
    if override:
        return expand(override).resolve()
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if all((candidate / marker).exists() for marker in ROOT_MARKERS):
            return candidate
    cwd = Path.cwd().resolve()
    if all((cwd / marker).exists() for marker in ROOT_MARKERS):
        return cwd
    return here.parent.parent


def routines_path() -> Path:
    """The timetable file in this checkout, new location first."""
    root = repo_root()
    for relative in ROUTINES_PATHS:
        candidate = root / relative
        if candidate.exists():
            return candidate
    return root / DEFAULT_ROUTINES_PATH


# -- validation ----------------------------------------------------------


def _problems(data: dict[str, Any]) -> list[str]:
    out: list[str] = []
    cfg = Config(data)

    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        out.append(
            f"'schema_version' should be {SCHEMA_VERSION} (found {version!r}). "
            "Copy the current config/preferences.example.yaml and move your answers over."
        )

    if cfg.ui_mode not in UI_MODES:
        out.append(
            f"'ui.mode' should be 'simple' or 'technical' (found {cfg.get('ui.mode')!r})."
        )
    notice = cfg.get("ui.self_optimization_notice")
    if notice not in ("none", "one_line"):
        out.append(f"'ui.self_optimization_notice' should be 'none' or 'one_line' (found {notice!r}).")

    email = str(cfg.get("identity.apply_email", ""))
    if email and ("@" not in email or email.startswith("{{")):
        out.append(
            f"'identity.apply_email' does not look like an email address ({email!r}). "
            "This is the address that goes on every form."
        )

    for key, minimum in (
        ("search.recency_days", 1),
        ("search.max_required_years_experience", 0),
        ("apply.rows_per_wave", 1),
        ("apply.max_lanes", 1),
        ("apply.min_free_memory_mb", 0),
        ("apply.projected_memory_per_lane_mb", 0),
        ("verify.receipt_window_minutes", 1),
        ("tracker.backups_to_keep", 1),
    ):
        value = cfg.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
            out.append(f"'{key}' should be a whole number of at least {minimum} (found {value!r}).")

    for key in ("search.categories.core", "search.categories.non_core", "search.categories.excluded"):
        value = cfg.get(key)
        if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
            out.append(f"'{key}' should be a list of job titles (found {value!r}).")
    if not cfg.get("search.categories.core"):
        out.append(
            "'search.categories.core' is empty, so nothing would ever be applied to first. "
            "List the job titles you care about most."
        )

    for name, block in cfg.section("search.sources").items():
        if not isinstance(block, dict):
            out.append(f"'search.sources.{name}' should be a block with 'enabled' and 'boards'.")
            continue
        if block.get("enabled") and not block.get("boards"):
            out.append(
                f"'search.sources.{name}' is on but lists no boards, so it can never find anything."
            )

    for action in PERMISSIONS:
        value = cfg.get(f"permissions.{action}")
        if not isinstance(value, bool):
            out.append(f"'permissions.{action}' should be true or false (found {value!r}).")

    digest_time = str(cfg.get("notifications.digest_time", ""))
    if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", digest_time):
        out.append(
            f"'notifications.digest_time' should be a time like '08:00' (found {digest_time!r})."
        )

    reader = cfg.get("verify.mail_reader")
    if reader not in ("none", "json_export"):
        out.append(f"'verify.mail_reader' should be 'none' or 'json_export' (found {reader!r}).")
    if reader == "json_export" and not cfg.get("verify.mail_export_dir"):
        out.append("'verify.mail_export_dir' is needed when 'verify.mail_reader' is 'json_export'.")

    known_models = _known_model_ids(cfg)
    for role in ("screen", "review", "browser"):
        chosen = cfg.get(f"models.{role}")
        if not isinstance(chosen, str) or not chosen:
            out.append(f"'models.{role}' should name a model (for example 'claude-haiku').")
        elif chosen not in known_models:
            out.append(
                f"'models.{role}' is {chosen!r}, which no enabled provider offers. "
                f"Available right now: {', '.join(sorted(known_models)) or 'none'}."
            )
    fallback = cfg.get("models.fallback", [])
    if not isinstance(fallback, list):
        out.append("'models.fallback' should be a list of model names, in the order to try them.")

    http = cfg.section("models.providers.openai_compatible")
    if http.get("enabled"):
        if not http.get("api_key_env"):
            out.append(
                "'models.providers.openai_compatible.api_key_env' should be the NAME of an "
                "environment variable holding the key. Never put the key itself in this file."
            )
        if not http.get("base_url") or not http.get("model"):
            out.append(
                "'models.providers.openai_compatible' needs both 'base_url' and 'model' when enabled."
            )

    for name, block in cfg.section("plugins").items():
        if not isinstance(block, dict) or not isinstance(block.get("enabled", False), bool):
            out.append(f"'plugins.{name}.enabled' should be true or false.")

    driver = cfg.get("apply.driver")
    if not isinstance(driver, str) or not driver:
        out.append("'apply.driver' should name an apply driver ('dry_run' ships with the core).")

    return out


def _known_model_ids(cfg: Config) -> set[str]:
    ids: set[str] = set()
    for name, block in cfg.section("models.providers").items():
        if not isinstance(block, dict) or not block.get("enabled"):
            continue
        models = block.get("models")
        if isinstance(models, dict) and models:
            ids.update(str(k) for k in models)
        elif isinstance(block.get("model"), str) and block["model"]:
            ids.add(str(block["model"]))
            ids.add(name)
        else:
            ids.add(name)
    return ids


def validate(data: dict[str, Any], source: Path | None = None) -> Config:
    problems = _problems(data)
    if problems:
        where = f" in {source}" if source else ""
        raise ConfigError(
            f"I could not use your settings{where}. Please fix:",
            problems=problems,
            hint="Then run 'jobpilot doctor' and I will check them again.",
        )
    return Config(data, source)


def settings_path(path: str | Path | None = None) -> Path:
    """Where the user's settings file lives.

    One resolution order, used by everything that reads *or writes* it:
    an explicit path → ``JOBPILOT_CONFIG`` → ``config/preferences.yaml`` next to
    the checkout. Setup writing to one place while every other command reads
    another is the worst kind of bug: everything looks fine and nothing works.
    """
    chosen = path or os.environ.get(ENV_CONFIG) or (repo_root() / DEFAULT_CONFIG_PATH)
    return Path(chosen)


def backup_settings(path: str | Path) -> Path | None:
    """Copy the settings file aside before it is replaced. ``None`` if there is none.

    Every writer uses this, so a change always leaves the previous answers
    recoverable, whoever made it.
    """
    import shutil

    original = Path(path)
    if not original.exists():
        return None
    stamp = iso_stamp()
    spare = original.with_name(f"{original.stem}.before-{stamp}{original.suffix}")
    shutil.copy2(original, spare)
    return spare


def iso_stamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def load(path: str | Path | None = None, *, overrides: dict[str, Any] | None = None) -> Config:
    """Load, merge over the defaults and validate the user's settings."""
    config_path = settings_path(path)
    if not config_path.exists():
        raise ConfigError(
            f"I could not find your settings file at {config_path}.",
            hint=(
                "Run 'jobpilot setup' and I will build one with you, or copy "
                "config/preferences.example.yaml to config/preferences.yaml."
            ),
        )
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(
            f"Your settings file at {config_path} is not valid YAML.",
            hint=f"The line it stopped on: {exc}",
        ) from exc
    if not isinstance(raw, dict):
        raise ConfigError(
            f"Your settings file at {config_path} should be a list of settings, not {type(raw).__name__}.",
            hint="Start again from config/preferences.example.yaml.",
        )
    merged = _merge(DEFAULTS, raw)
    if overrides:
        merged = _merge(merged, overrides)
    return validate(merged, config_path)


def load_defaults(overrides: dict[str, Any] | None = None) -> Config:
    """A valid config with no user file. Used by tests and by ``setup``."""
    merged = _merge(DEFAULTS, overrides or {})
    merged["search"]["categories"]["core"] = merged["search"]["categories"]["core"] or ["Engineer"]
    return validate(merged, None)


def write(config: Config, path: str | Path) -> Path:
    """Write settings back out, preserving comments is *not* a goal here.

    The setup conversation echoes the result back as prose; this just stores it.
    """
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(config.data, sort_keys=False, allow_unicode=True)
    destination.write_text("# written by jobpilot setup\n" + text, encoding="utf-8")
    return destination
