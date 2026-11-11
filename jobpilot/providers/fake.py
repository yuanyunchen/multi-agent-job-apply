"""A deterministic provider for tests and for ``--dry-run``.

It never starts a process and never opens a socket, so it is the only provider
that works while the test suite is running.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .base import Health, ModelResult


@dataclass
class FakeProvider:
    """Answers from a list, from a callable, or with a canned reply.

    * ``replies``  — answered in order; the last one repeats.
    * ``answer``   — a function of the prompt, for prompt-dependent tests.
    """

    name: str = "fake"
    capabilities: frozenset[str] = frozenset({"screen", "review", "browser"})
    replies: list[str] = field(default_factory=list)
    answer: Callable[[str], str] | None = None
    healthy: bool = True
    prompts: list[str] = field(default_factory=list)

    def complete(self, prompt: str, *, schema: dict | None = None, timeout: int = 600) -> ModelResult:
        self.prompts.append(prompt)
        if self.answer is not None:
            return ModelResult(True, self.answer(prompt), self.name)
        if not self.replies:
            return ModelResult(True, "[]", self.name)
        index = min(len(self.prompts) - 1, len(self.replies) - 1)
        return ModelResult(True, self.replies[index], self.name)

    def health(self) -> Health:
        return Health(self.healthy, "a stand-in that makes things up deterministically")
