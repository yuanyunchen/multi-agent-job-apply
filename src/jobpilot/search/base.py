"""The source interface and the two fetchers (real and fixture)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol, runtime_checkable

from ..domain import Job
from ..errors import JobpilotError
from ..testmode import ensure_live


class FetchError(JobpilotError):
    """A source could not read its board. Sources report this, never crash."""


@runtime_checkable
class Fetcher(Protocol):
    """Everything a source is allowed to use to reach the outside world."""

    def get_json(self, url: str) -> Any: ...


@dataclass
class UrllibFetcher:
    """The real fetcher. Standard library only, and blocked during tests."""

    timeout: float = 15.0
    user_agent: str = "jobpilot/2 (+https://github.com/)"

    def get_json(self, url: str) -> Any:
        ensure_live("network")
        import urllib.error  # imported here so test mode blocks before any import cost
        import urllib.request

        request = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": self.user_agent}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            raise FetchError(f"The job board answered with an error ({exc.code}).") from exc
        except OSError as exc:
            raise FetchError("I could not reach the job board just now.") from exc
        try:
            return json.loads(body)
        except ValueError as exc:
            raise FetchError("The job board sent something I could not read.") from exc


@dataclass
class FixtureFetcher:
    """Serves canned responses. ``responses`` maps a URL to parsed JSON.

    A URL that is not in the map raises, so a test can never silently fall
    through to a real request.
    """

    responses: dict[str, Any] = field(default_factory=dict)
    requested: list[str] = field(default_factory=list)

    @classmethod
    def from_dir(cls, directory, mapping: dict[str, str]) -> "FixtureFetcher":
        """``mapping`` maps a URL to a JSON file name inside ``directory``."""
        from pathlib import Path

        base = Path(directory)
        responses = {
            url: json.loads((base / name).read_text(encoding="utf-8"))
            for url, name in mapping.items()
        }
        return cls(responses=responses)

    def get_json(self, url: str) -> Any:
        self.requested.append(url)
        if url not in self.responses:
            raise FetchError(f"No fixture for {url}")
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        return value


@runtime_checkable
class Source(Protocol):
    """One place to look for jobs."""

    name: str

    def fetch(self, fetcher: Fetcher) -> Iterable[Job]: ...
