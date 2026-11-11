"""Providers that shell out to a model command-line tool.

The prompt always goes in on **stdin**: it can be long, and it must never end up
in a process listing. Both providers are blocked while the tests run, and
neither ever signs in, signs out or reads an auth file.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field

from ..testmode import ensure_live, is_test_mode
from .base import Health, ModelResult, redact, schema_hint

#: What :meth:`CliProvider.health` says while the tests run. It is the same
#: sentence on every machine on purpose: see the method's own docstring.
BLOCKED_IN_TEST_MODE = "I am not allowed to use a model tool while the tests run"


@dataclass
class CliProvider:
    """Common behaviour: run ``argv``, feed the prompt on stdin, read stdout."""

    name: str
    command: str
    argv: list[str] = field(default_factory=list)
    capabilities: frozenset[str] = frozenset({"screen", "review"})

    def _resolve(self) -> str | None:
        return shutil.which(self.command)

    def health(self) -> Health:
        """Can this tool be used *right now*?

        In test mode the answer is no, whatever is installed: :meth:`complete`
        refuses to start a real process there. Answering from the machine's
        ``PATH`` instead would make the suite, the examples and ``doctor``
        report different things on different computers - which is how a check
        that passes on its author's laptop fails on a fresh one.
        """
        if is_test_mode():
            return Health(False, BLOCKED_IN_TEST_MODE)
        if self._resolve() is None:
            return Health(False, f"I could not find the {self.name} tool on this computer.")
        return Health(True, f"{self.name} is installed")

    def complete(self, prompt: str, *, schema: dict | None = None, timeout: int = 600) -> ModelResult:
        ensure_live("model command line")
        executable = self._resolve()
        if executable is None:
            return ModelResult(False, "", self.name, failure="not_installed")
        try:
            finished = subprocess.run(  # noqa: S603 - argv is built here, never user text
                [executable, *self.argv],
                input=prompt + schema_hint(schema),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ModelResult(False, "", self.name, failure="timeout")
        except OSError as exc:
            return ModelResult(False, "", self.name, failure="error", usage={"detail": str(exc)})
        if finished.returncode != 0:
            stderr = redact(finished.stderr)[-400:]
            failure = "not_signed_in" if "login" in stderr.lower() or "auth" in stderr.lower() else "error"
            return ModelResult(False, redact(finished.stdout), self.name, failure=failure, usage={"detail": stderr})
        return ModelResult(True, redact(finished.stdout), self.name)


def claude_provider(model_id: str, command: str = "claude", name: str = "claude") -> CliProvider:
    """The Claude Code CLI. ``model_id`` picks haiku / sonnet / opus."""
    return CliProvider(
        name=name,
        command=command,
        argv=["-p", "--model", model_id],
        capabilities=frozenset({"screen", "review", "browser"}),
    )


def codex_provider(command: str = "codex", name: str = "codex") -> CliProvider:
    """The Codex CLI, used as a second engine / fallback."""
    return CliProvider(
        name=name,
        command=command,
        argv=["exec", "-"],
        capabilities=frozenset({"screen", "review", "browser"}),
    )
