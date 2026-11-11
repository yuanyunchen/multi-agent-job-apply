"""One search pass: ask every enabled source, de-duplicate, report.

The pass never decides anything about a job. It returns rows; `rules` flags
them, `screen` judges them and `tracker` records them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..config import Config
from ..domain import Job
from .ats import FAMILIES, BoardSource
from .base import Fetcher, Source
from .dedupe import dedupe, is_known


@dataclass
class SearchReport:
    """What one pass did, per source — the funnel the Lead watches."""

    fetched: int = 0
    unique: int = 0
    new: int = 0
    per_source: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    jobs: list[Job] = field(default_factory=list)

    @property
    def dead_sources(self) -> list[str]:
        return sorted(name for name, count in self.per_source.items() if count == 0)


def built_in_sources(config: Config) -> list[Source]:
    """The no-login sources the user switched on.

    Read through :class:`~jobpilot.terms.Sources`, so a ``sources.yaml`` beside
    the settings works exactly as well as the settings block — and either way it
    is read fresh on every pass rather than baked in.
    """
    from ..terms import Sources

    chosen = Sources.from_config(config)
    return [
        BoardSource(family=family, boards=chosen.boards[family])
        for family in FAMILIES
        if chosen.boards.get(family)
    ]


def plugin_sources(config: Config, provider=None) -> list[Source]:
    """Sources contributed by enabled plugins (none when all are off).

    ``provider`` is a browser-capable model; without one, a plugin source
    reports that it was skipped instead of doing anything.
    """
    from ..plugins import load_plugins

    out: list[Source] = []
    for plugin in load_plugins(config):
        source = plugin.source(config, provider)
        if source is not None:
            out.append(source)
    return out


def run_search(
    config: Config,
    fetcher: Fetcher,
    *,
    sources: list[Source] | None = None,
    known_keys: set[str] | None = None,
    provider=None,
) -> SearchReport:
    """Collect from every source, then de-duplicate across all of them."""
    chosen = (
        sources
        if sources is not None
        else [*built_in_sources(config), *plugin_sources(config, provider)]
    )
    report = SearchReport()
    collected: list[Job] = []
    for source in chosen:
        before = len(collected)
        try:
            rows = list(source.fetch(fetcher))
        except Exception as exc:  # a broken source must not stop the pass
            report.errors.append(f"{source.name}: {exc}")
            rows = []
        collected.extend(rows)
        report.per_source[source.name] = len(collected) - before
        report.errors.extend(getattr(source, "errors", []))

    report.fetched = len(collected)
    unique = dedupe(collected)
    report.unique = len(unique)
    seen = known_keys or set()
    report.jobs = [job for job in unique if not is_known(job, seen)]
    report.new = len(report.jobs)
    return report
