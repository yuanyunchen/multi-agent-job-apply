"""Pins: the frozen list a wave of applications is worked from.

A **pin** is the apply queue at one moment, written down once and never edited.
It has a fingerprint over its contents, so there is no question later about
which list a wave came from, and the list cannot drift under a running wave.

Why it works this way:

* A queue that is rebuilt while a wave is running puts a job in two waves. One
  duplicate application is worse than ten missed ones.
* A queue file edited in place loses the evidence of what was handed out.
* A wave that dies mid-flight leaves jobs *claimed*. The pin says exactly which
  jobs those were, so they can be handed back after the duplicate checks rather
  than guessed at.

The pieces:

* :func:`build_pin` — take the ranked queue, freeze it, fingerprint it;
* :class:`PinStore` — write and read pins, never overwriting one;
* :class:`Driver` — hand waves out to lanes under the lane gate, record what
  came back, and hand unreached jobs back to the queue;
* :func:`watch_handoff` — the watchdog that notices a pin that stopped moving,
  or a search pass whose results never reached the queue.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable

from .config import Config
from .domain import iso, now
from .errors import JobpilotError
from .gates import LaneGuard
from .queue import build_queue, depth

#: A wave never leaves a job in limbo: it is submitted, parked, blocked or
#: skipped. Anything still claimed after this long is treated as abandoned.
LEASE_MINUTES = 40

#: A pin that has not moved for this long, with jobs still unreached, is stuck.
STUCK_MINUTES = 40

#: Fields copied onto a pinned job. The description is deliberately not one of
#: them: a pin is a work order, not a copy of the record.
PINNED_FIELDS = (
    "job_id",
    "url",
    "company",
    "title",
    "location",
    "ats",
    "ats_job_id",
    "apply_tier",
    "posted_at",
    "source",
)

#: Flags a pinned job may carry. A string that merely *looks* like a boolean is
#: refused: ``"False"`` is true in Python, and a row once slipped through a
#: guard that way.
BOOL_FIELDS = ("rerun_approved", "reapply_approved", "quick_apply", "verify_prior_submit")

_STRING_BOOLEANS = {"true", "false"}


class PinRefused(JobpilotError):
    """A pin was refused. Nothing was written."""

    def __init__(self, code: str, message: str, *, hint: str = "") -> None:
        super().__init__(message, hint=hint)
        self.code = code


def _check_flags(rows: list[dict]) -> list[str]:
    """Flags must be real booleans. A string boolean is a silent guard bypass."""
    problems: list[str] = []
    for position, row in enumerate(rows):
        for key, value in row.items():
            if isinstance(value, str) and value.strip().lower() in _STRING_BOOLEANS:
                problems.append(f"job {position + 1}: '{key}' is the word {value!r}, not true or false")
            elif key in BOOL_FIELDS and value is not None and not isinstance(value, bool):
                problems.append(f"job {position + 1}: '{key}' should be true or false, not {value!r}")
    return problems


def fingerprint(rows: list[dict]) -> str:
    """A stable short fingerprint over the pinned jobs, in order."""
    payload = json.dumps(
        [{key: row.get(key) for key in sorted(row)} for row in rows], sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Pin:
    """A frozen batch of jobs handed to the apply step."""

    pin_id: str
    created_at: str
    rows: tuple[dict, ...]
    digest: str
    wave_size: int = 20

    @property
    def job_ids(self) -> list[str]:
        return [str(row.get("job_id")) for row in self.rows]

    def waves(self) -> list[list[dict]]:
        """The pin cut into waves. The last one may be short."""
        size = max(1, self.wave_size)
        return [list(self.rows[start : start + size]) for start in range(0, len(self.rows), size)]

    def verify(self) -> None:
        """Refuse to work from a pin whose contents no longer match its fingerprint."""
        if fingerprint(list(self.rows)) != self.digest:
            raise PinRefused(
                "pin_changed",
                "The list of applications I was given has changed since it was written, "
                "so I stopped rather than risk applying to something twice.",
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "pin_id": self.pin_id,
            "created_at": self.created_at,
            "digest": self.digest,
            "wave_size": self.wave_size,
            "rows": list(self.rows),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Pin":
        return cls(
            pin_id=str(payload.get("pin_id", "")),
            created_at=str(payload.get("created_at", "")),
            rows=tuple(payload.get("rows") or ()),
            digest=str(payload.get("digest", "")),
            wave_size=int(payload.get("wave_size", 20) or 20),
        )


def build_pin(
    rows: Iterable[dict],
    *,
    limit: int = 0,
    wave_size: int = 20,
    moment: datetime | None = None,
) -> Pin:
    """Freeze the ranked queue into a pin. Raises if a flag is not a real boolean."""
    ordered = build_queue(rows)
    if limit > 0:
        ordered = ordered[:limit]
    pinned = [{key: row[key] for key in PINNED_FIELDS if key in row} for row in ordered]
    for source, target in zip(ordered, pinned):
        for key in BOOL_FIELDS:
            if key in source:
                target[key] = source[key]
    problems = _check_flags(pinned)
    if problems:
        raise PinRefused(
            "bad_flags",
            "I would not hand this list over, because some of it is not the shape I expect.",
            hint="; ".join(problems),
        )
    stamp = (moment or now()).strftime("%Y%m%dT%H%M%S")
    digest = fingerprint(pinned)
    return Pin(
        pin_id=f"pin-{stamp}-{digest[:8]}",
        created_at=iso(moment),
        rows=tuple(pinned),
        digest=digest,
        wave_size=wave_size,
    )


@dataclass
class PinStore:
    """Where pins live. A pin is written once and never changed."""

    directory: Path

    @classmethod
    def from_config(cls, config: Config) -> "PinStore":
        return cls(directory=config.paths.ensure().state / "pins")

    def path_for(self, pin: Pin | str) -> Path:
        pin_id = pin if isinstance(pin, str) else pin.pin_id
        return self.directory / f"{pin_id}.json"

    def write(self, pin: Pin) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self.path_for(pin)
        if destination.exists():
            raise PinRefused(
                "already_written",
                "I have already written that list down, and I never change one after the fact.",
            )
        destination.write_text(json.dumps(pin.as_dict(), indent=2) + "\n", encoding="utf-8")
        return destination

    def read(self, pin_id: str) -> Pin:
        path = self.path_for(pin_id)
        if not path.exists():
            raise PinRefused("missing", "I cannot find the list of applications I was working from.")
        pin = Pin.from_dict(json.loads(path.read_text(encoding="utf-8")))
        pin.verify()
        return pin

    def latest(self) -> Pin | None:
        paths = sorted(self.directory.glob("pin-*.json"))
        return self.read(paths[-1].stem) if paths else None

    def all_ids(self) -> list[str]:
        return [path.stem for path in sorted(self.directory.glob("pin-*.json"))]


# -- handing waves out ----------------------------------------------------


@dataclass
class WaveRecord:
    """What one wave did. Written to the progress file as it goes."""

    wave: str
    lane: str
    job_ids: list[str] = field(default_factory=list)
    disposed: dict[str, str] = field(default_factory=dict)  # job_id → disposition
    started_at: str = ""
    finished_at: str = ""
    stopped_because: str = ""

    @property
    def unreached(self) -> list[str]:
        """Jobs this wave never got to. They go back to the queue, not out again."""
        return [job_id for job_id in self.job_ids if job_id not in self.disposed]


@dataclass
class DriverReport:
    pin_id: str = ""
    waves: list[WaveRecord] = field(default_factory=list)
    lanes_used: int = 0
    stopped_because: str = ""
    requeued: list[str] = field(default_factory=list)

    @property
    def disposed(self) -> int:
        return sum(len(wave.disposed) for wave in self.waves)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for wave in self.waves:
            for disposition in wave.disposed.values():
                out[disposition] = out.get(disposition, 0) + 1
        return out


@dataclass
class Driver:
    """Hands waves of a pin to lanes, under the lane gate, and records the result.

    The driver itself opens nothing: ``run_wave`` is injected. That keeps the
    ordering, admission and hand-back logic testable offline, and lets a real
    browser driver be a plugin.
    """

    pin: Pin
    lanes: LaneGuard
    #: ``(wave_name, lane_name, rows) -> {job_id: disposition}``
    run_wave: Callable[[str, str, list[dict]], dict[str, str]]
    #: Touch-file style progress, so a watchdog can see movement without tokens.
    progress: Path | None = None
    stop_file: Path | None = None

    def run(self) -> DriverReport:
        """Work through the pin. A running wave always finishes."""
        self.pin.verify()
        report = DriverReport(pin_id=self.pin.pin_id)
        available = max(1, self.lanes.lanes_available(running=0))
        report.lanes_used = available

        for index, rows in enumerate(self.pin.waves(), start=1):
            if self.stop_file is not None and self.stop_file.exists():
                # A stop lets the wave in flight finish; it never starts a new one.
                report.stopped_because = "asked_to_stop"
                report.requeued.extend(str(row.get("job_id")) for row in rows)
                continue
            admission = self.lanes.admit(running=0)
            if not admission.allowed:
                report.stopped_because = admission.code
                report.requeued.extend(str(row.get("job_id")) for row in rows)
                continue

            lane = f"lane-{((index - 1) % available) + 1}"
            record = WaveRecord(
                wave=f"{self.pin.pin_id}-w{index:03d}",
                lane=lane,
                job_ids=[str(row.get("job_id")) for row in rows],
                started_at=iso(),
            )
            try:
                record.disposed = dict(self.run_wave(record.wave, lane, rows) or {})
            except Exception as exc:  # a dead wave hands its jobs back
                record.stopped_because = str(exc)
            record.finished_at = iso()
            report.waves.append(record)
            report.requeued.extend(record.unreached)
            self._note(record)
        return report

    def _note(self, record: WaveRecord) -> None:
        if self.progress is None:
            return
        self.progress.parent.mkdir(parents=True, exist_ok=True)
        with open(self.progress, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "at": iso(),
                        "pin_id": self.pin.pin_id,
                        "wave": record.wave,
                        "lane": record.lane,
                        "handed_out": len(record.job_ids),
                        "disposed": len(record.disposed),
                        "unreached": len(record.unreached),
                    },
                    sort_keys=True,
                )
                + "\n"
            )


# -- the watchdog ---------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HandoffProblem:
    code: str  # queue_leak | pin_stuck | claims_expired
    detail: str  # plain language, safe to show the user
    technical: str = ""


def watch_handoff(
    rows: list[dict],
    *,
    found_recently: int = 0,
    pin: Pin | None = None,
    progress_at: datetime | None = None,
    moment: datetime | None = None,
    stuck_minutes: int = STUCK_MINUTES,
    lease_minutes: int = LEASE_MINUTES,
) -> list[HandoffProblem]:
    """Did the morning's work actually reach the queue, and is it moving?

    Three things go wrong in practice, and none of them announce themselves:

    * **A queue leak.** Search reports plenty of matches and the queue stays
      empty — the jobs were found and then lost on the way.
    * **A stuck pin.** A list was handed out and nothing has been disposed of
      for a long while.
    * **Expired claims.** A wave died and left jobs marked as being worked on.
    """
    at = moment or now()
    problems: list[HandoffProblem] = []
    sizes = depth(rows)

    if found_recently > 0 and sizes["total"] == 0:
        problems.append(
            HandoffProblem(
                "queue_leak",
                f"I found {found_recently} matching jobs but none of them reached my list, "
                "so something went wrong between finding and applying.",
                technical=f"found={found_recently} queue_depth=0",
            )
        )

    if pin is not None and progress_at is not None:
        outstanding = len(pin.job_ids)
        idle = (at - _aware(progress_at, at)).total_seconds() / 60
        if outstanding and idle >= stuck_minutes:
            problems.append(
                HandoffProblem(
                    "pin_stuck",
                    "A group of applications has not moved for a while, so I will start them again "
                    "after checking nothing was already sent.",
                    technical=f"pin={pin.pin_id} idle_minutes={int(idle)} rows={outstanding}",
                )
            )

    expired = [row for row in rows if _claim_expired(row, at, lease_minutes)]
    if expired:
        problems.append(
            HandoffProblem(
                "claims_expired",
                f"{len(expired)} applications were left half-started, so I will pick them up again "
                "once I have checked none of them was already sent.",
                technical=f"job_ids={[str(r.get('job_id')) for r in expired]}",
            )
        )
    return problems


def _claim_expired(row: dict, at: datetime, lease_minutes: int) -> bool:
    from .tracker import normalize_status

    if normalize_status(row.get("status")) != "claimed":
        return False
    stamp = row.get("claimed_at")
    if not stamp:
        return True
    try:
        claimed = datetime.fromisoformat(str(stamp))
    except ValueError:
        return True
    return at - _aware(claimed, at) > timedelta(minutes=lease_minutes)


def _aware(moment: datetime, like: datetime) -> datetime:
    if like.tzinfo is None:
        return moment.replace(tzinfo=None)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=like.tzinfo)
    return moment
