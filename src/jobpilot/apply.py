"""Applying: waves of jobs, one disposition each, every guard in the way.

The core ships a :class:`DryRunDriver` and nothing else. A driver that really
fills in a form in a browser is a plugin, and it must satisfy the same
:class:`ApplyDriver` interface, so the wave runner cannot tell the difference
and the guards apply either way.

Every row that is claimed is disposed of: ``submitted``, ``parked`` (a question
only the user can answer), ``blocked`` (a wall) or ``skipped``. A wave never
leaves a row claimed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .config import Config
from .domain import Message, iso
from .errors import GateBlocked
from .gates import AnswerBank, GateResult, LaneGuard, OutboundGate
from .queue import next_wave
from .testmode import ensure_live
from .tracker import Tracker
from .ui import Renderer, plural


#: The outcomes a wave may record. Every claimed row gets exactly one.
DISPOSITIONS = ("submitted", "parked", "blocked", "skipped")


@dataclass(frozen=True, slots=True)
class ApplyRequest:
    row: dict
    answers: dict[str, str]
    lane: str
    dry_run: bool


@dataclass(frozen=True, slots=True)
class ApplyOutcome:
    """What happened on one job. ``status`` is the tracker status to write."""

    status: str  # submitted | parked | blocked | skipped
    detail: str = ""
    questions: tuple[str, ...] = ()  # questions only the user can answer
    proof_url: str = ""
    proof_text: str = ""


@runtime_checkable
class ApplyDriver(Protocol):
    """How an application actually gets filled in.

    A driver must honour ``request.dry_run``: with it set, it may look at a page
    but must not type, click Submit, or change anything anywhere. That is the
    contract the practice run relies on.
    """

    name: str

    def apply(self, request: ApplyRequest) -> ApplyOutcome: ...

    def questions(self, row: dict) -> list[str]:
        """The questions this posting will ask, as far as the driver knows."""


@dataclass
class DryRunDriver:
    """Opens nothing, sends nothing. Reports what it *would* have done."""

    name: str = "dry_run"
    asks: dict[str, list[str]] = field(default_factory=dict)  # job_id → questions
    calls: list[ApplyRequest] = field(default_factory=list)

    def questions(self, row: dict) -> list[str]:
        return list(self.asks.get(str(row.get("job_id")), []))

    def apply(self, request: ApplyRequest) -> ApplyOutcome:
        self.calls.append(request)
        return ApplyOutcome(
            status="skipped",
            detail=f"practice run: I would have applied to {request.row.get('title', 'this job')}",
        )


class BrowserDriverBase:
    """Base class for a real driver. Blocked while the tests are running."""

    name = "browser"

    def __init__(self) -> None:
        ensure_live("browser driver")

    def questions(self, row: dict) -> list[str]:  # pragma: no cover - plugin territory
        raise NotImplementedError

    def apply(self, request: ApplyRequest) -> ApplyOutcome:  # pragma: no cover
        raise NotImplementedError


@dataclass
class WaveResult:
    submitted: int = 0
    parked: int = 0
    blocked: int = 0
    skipped: int = 0
    refused: int = 0
    would_apply: int = 0  # practice runs only: nothing was claimed or written
    questions: list[str] = field(default_factory=list)
    stopped_because: str = ""

    @property
    def handled(self) -> int:
        return self.submitted + self.parked + self.blocked + self.skipped + self.would_apply


@dataclass
class WaveRunner:
    """Works through one wave of the queue under the lane and outbound gates."""

    config: Config
    tracker: Tracker
    driver: ApplyDriver
    answers: AnswerBank
    gate: OutboundGate
    lanes: LaneGuard
    lane_name: str = "lane-1"

    @classmethod
    def build(
        cls,
        config: Config,
        *,
        tracker: Tracker | None = None,
        driver: ApplyDriver | None = None,
        lanes: LaneGuard | None = None,
        gate: OutboundGate | None = None,
    ) -> "WaveRunner":
        return cls(
            config=config,
            tracker=tracker or Tracker.from_config(config),
            driver=driver or DryRunDriver(),
            answers=AnswerBank.from_config(config),
            gate=gate or OutboundGate(config),
            lanes=lanes or LaneGuard.from_config(config),
        )

    def run(self, *, dry_run: bool = True, size: int | None = None) -> WaveResult:
        """Work through one wave.

        A practice run (``dry_run=True``) claims nothing and writes nothing: it
        reports what it would have done, and which questions would have stopped
        it. Only a real run touches the record.
        """
        result = WaveResult()
        wave_size = size if size is not None else int(self.config.get("apply.rows_per_wave", 20))
        rows = next_wave(self.tracker.read(), wave_size)
        if not rows:
            result.stopped_because = "nothing_to_do"
            return result

        admission = self.lanes.admit(running=0)
        if not admission.allowed:
            result.stopped_because = admission.code
            return result

        if dry_run:
            return self._practice(rows, result)

        for row in rows:
            job_id = str(row.get("job_id") or "")
            if not self.tracker.claim(job_id, self.lane_name):
                result.refused += 1
                continue
            outcome = self._handle(row, dry_run=dry_run)
            fields: dict[str, object] = {"notes": outcome.detail}
            if outcome.status == "skipped":
                fields.update(
                    skip_reason=outcome.detail or "the apply step decided against it",
                    skip_basis="apply_disposition",
                )
            if outcome.status == "submitted":
                fields.update(
                    submit_proof_url=outcome.proof_url or row.get("url", ""),
                    submit_proof_text=outcome.proof_text,
                    submit_proof_at=iso(),
                )
            if outcome.questions:
                fields["pending_questions"] = list(outcome.questions)
                result.questions.extend(outcome.questions)
            # Every claimed row is disposed of, whatever happened. If the record
            # refuses the disposition, say so rather than leaving a row claimed.
            written = self.tracker.dispose(job_id, outcome.status, **fields)
            if written.refused:
                result.refused += 1
                self.tracker.record_event(
                    "disposition_refused", job_id=job_id, codes=[code for _, code in written.refused]
                )
                continue
            counter = outcome.status if outcome.status in DISPOSITIONS else "blocked"
            setattr(result, counter, getattr(result, counter) + 1)
        return result

    def _practice(self, rows: list[dict], result: WaveResult) -> WaveResult:
        """Look at each row and say what would happen. Nothing is written."""
        for row in rows:
            questions = self.driver.questions(row)
            _answers, unknown = self.answers.answer_all(questions)
            if unknown:
                result.parked += 1
                result.questions.extend(unknown)
                continue
            try:
                self.driver.apply(
                    ApplyRequest(row=row, answers=_answers, lane=self.lane_name, dry_run=True)
                )
            except GateBlocked:
                result.blocked += 1
                continue
            result.would_apply += 1
        return result

    def _handle(self, row: dict, *, dry_run: bool) -> ApplyOutcome:
        questions = self.driver.questions(row)
        answers, unknown = self.answers.answer_all(questions)
        if unknown and self.config.get("apply.park_when_unanswerable", True):
            return ApplyOutcome(
                status="parked",
                detail="I stopped on this one because I will not make up an answer.",
                questions=tuple(unknown),
            )

        if not dry_run:
            gate: GateResult = self.gate.check(
                "submit_applications", context={"job_id": row.get("job_id"), "url": row.get("url")}
            )
            if not gate.allowed:
                return ApplyOutcome(status="blocked", detail=gate.reason)

        try:
            return self.driver.apply(
                ApplyRequest(row=row, answers=answers, lane=self.lane_name, dry_run=dry_run)
            )
        except GateBlocked as exc:
            return ApplyOutcome(status="blocked", detail=exc.message)


def describe(result: WaveResult, renderer: Renderer) -> str:
    """One line for the user about a wave."""
    if result.stopped_because == "nothing_to_do":
        message = Message("apply", "There was nothing waiting to be applied to.")
    elif result.stopped_because:
        message = Message(
            "apply",
            "I paused applying for now and will pick it up again shortly.",
            technical=f"stopped because: {result.stopped_because}",
        )
    else:
        pieces = [f"I worked through {plural(result.handled, 'application')}"]
        if result.would_apply:
            verb = "is" if result.would_apply == 1 else "are"
            pieces.append(f"{result.would_apply} {verb} ready to go whenever you say so")
        if result.submitted:
            pieces.append(f"{result.submitted} went out")
        if result.parked:
            pieces.append(f"{plural(result.parked, 'needs', 'need')} your answer")
        if result.blocked:
            pieces.append(f"{result.blocked} ran into something I could not pass")
        message = Message(
            "apply",
            ", ".join(pieces) + ".",
            technical=f"refused by guards: {result.refused}",
        )
    return renderer.render(message)
