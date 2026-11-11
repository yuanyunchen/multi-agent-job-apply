"""The tracker: one file, one writer, every change evidenced.

This module is the only thing in the system that writes the application record.
Everything else asks it to. That is what makes the record trustworthy, so the
rules here are strict on purpose:

* **One writer.** Every change goes through :class:`Tracker`. A lock file keeps
  two processes apart; the lock is taken for the whole read-modify-write.
* **Atomic write.** Write a temporary file, then rename it over the real one, so
  a crash can never leave half a record.
* **Backups with rotation.** A copy before every write, the newest few kept raw,
  older ones gzipped, one per day beyond that. (Unrotated backups are how a disk
  fills up.)
* **An append-only event log.** Every accepted change is also one line in
  ``events.jsonl``, which is never rewritten.
* **Never re-apply.** A job that was already submitted cannot be submitted
  again, and re-opening a job the user skipped needs their explicit approval.
* **Claim guard.** A job can be claimed by one lane only.
* **Evidence.** A skip needs a reason and a quote (or a named company / a closed
  posting); a move to "confirmed" needs a receipt.

A refused write raises :class:`~jobpilot.errors.TrackerRefused` with a ``code``
naming the guard. Nothing is written when a write is refused.
"""

from __future__ import annotations

import gzip
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator

from .config import Config
from .domain import IN_PROGRESS_STATUSES, STATUSES, SUBMITTED_STATUSES, iso, now
from .errors import TrackerLocked, TrackerRefused
from .search.dedupe import row_identities

#: A skip may skip the quote only when the evidence is of one of these kinds:
#: a company the user named, a posting proven closed, the user's own decision, a
#: duplicate, or the apply step deciding not to proceed (there is no employer
#: sentence to quote in those cases). A screening drop is never one of these.
SKIP_BASES_WITHOUT_QUOTE = frozenset(
    {"company_excluded", "posting_closed", "user_request", "duplicate", "apply_disposition"}
)

#: Fields that may be changed on an already-applied row without a forced write.
SAFE_UPDATE_FIELDS = frozenset(
    {
        "job_id",
        "notes",
        "tags",
        "flags",
        "outcome",
        "outcome_evidence",
        "interview_note",
        "last_seen",
        "submit_proof_url",
        "submit_proof_at",
        "receipt",
        "updated_at",
    }
)

LEASE_MINUTES = 40


def normalize_status(raw: Any) -> str:
    """Trim, case-fold, hyphenate. No synonym mapping: a typo is a refusal."""
    text = str(raw or "").strip().lower()
    text = text.replace(" ", "-").replace("_", "-")
    while "--" in text:
        text = text.replace("--", "-")
    return text.replace("-", "_")


@dataclass
class UpsertResult:
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    refused: list[tuple[str, str]] = field(default_factory=list)  # (job_id, code)

    @property
    def touched(self) -> int:
        return self.added + self.updated


@dataclass
class Tracker:
    path: Path
    lock_path: Path
    backups_dir: Path
    events_path: Path
    backups_to_keep: int = 20
    lock_timeout_seconds: int = 30

    # -- construction ----------------------------------------------------
    @classmethod
    def from_config(cls, config: Config) -> "Tracker":
        paths = config.paths.ensure()
        return cls(
            path=paths.tracker,
            lock_path=paths.lock,
            backups_dir=paths.backups,
            events_path=paths.events,
            backups_to_keep=int(config.get("tracker.backups_to_keep", 20)),
            lock_timeout_seconds=int(config.get("tracker.lock_timeout_seconds", 30)),
        )

    # -- reading ---------------------------------------------------------
    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8") or "[]")
        except ValueError as exc:
            raise TrackerRefused(
                "unreadable",
                "I could not read the record of your applications, so I stopped instead of guessing.",
                hint=f"The newest backup is in {self.backups_dir}. ({exc})",
            ) from exc
        rows = payload.get("applications", []) if isinstance(payload, dict) else payload
        return [row for row in rows if isinstance(row, dict)]

    def by_id(self) -> dict[str, dict]:
        return {str(row.get("job_id")): row for row in self.read() if row.get("job_id")}

    def known_keys(self) -> set[str]:
        """Every URL/ATS identity already on file, for de-duplication."""
        keys: set[str] = set()
        for row in self.read():
            keys.update(row_identities(row))
        return keys

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for row in self.read():
            status = normalize_status(row.get("status"))
            out[status] = out.get(status, 0) + 1
        return out

    # -- locking ---------------------------------------------------------
    def _lock(self):
        tracker = self

        class _Lock:
            def __enter__(self) -> None:
                deadline = time.monotonic() + tracker.lock_timeout_seconds
                tracker.lock_path.parent.mkdir(parents=True, exist_ok=True)
                while True:
                    try:
                        handle = os.open(str(tracker.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    except FileExistsError:
                        if tracker._lock_is_stale():
                            tracker.lock_path.unlink(missing_ok=True)
                            continue
                        if time.monotonic() >= deadline:
                            raise TrackerLocked(
                                "Something else is already updating your applications, so I waited and then stopped.",
                                hint="Try again in a moment; nothing was changed.",
                            )
                        time.sleep(0.05)
                        continue
                    os.write(handle, f"{os.getpid()} {iso()}\n".encode())
                    os.close(handle)
                    return

            def __exit__(self, *_exc: object) -> None:
                tracker.lock_path.unlink(missing_ok=True)

        return _Lock()

    def _lock_is_stale(self, max_age_seconds: int = 300) -> bool:
        try:
            age = time.time() - self.lock_path.stat().st_mtime
        except OSError:
            return True
        return age > max_age_seconds

    # -- writing ---------------------------------------------------------
    def _backup_and_rotate(self) -> None:
        if not self.path.exists():
            return
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        stamp = now().strftime("%Y%m%dT%H%M%S%f")
        (self.backups_dir / f"applications.json.bak-{stamp}").write_bytes(self.path.read_bytes())
        self._rotate()

    def _rotate(self) -> None:
        raw = sorted(self.backups_dir.glob("applications.json.bak-*"), reverse=True)
        for old in raw[self.backups_to_keep :]:
            gz = old.with_suffix(old.suffix + ".gz")
            with open(old, "rb") as src, gzip.open(gz, "wb") as dst:
                dst.write(src.read())
            old.unlink()
        # keep at most one gzip per calendar day
        seen_days: set[str] = set()
        for archive in sorted(self.backups_dir.glob("applications.json.bak-*.gz"), reverse=True):
            day = archive.name.split("bak-")[1][:8]
            if day in seen_days:
                archive.unlink()
            else:
                seen_days.add(day)

    def _write(self, rows: list[dict]) -> None:
        """The one place bytes are written. Always inside the lock."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._backup_and_rotate()
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, self.path)

    def record_event(self, action: str, **fields: Any) -> None:
        """Append one line to the event log. Public: other modules record too."""
        self._event(action, **fields)

    def _event(self, action: str, **fields: Any) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"at": iso(), "action": action, **fields}, sort_keys=True)
        with open(self.events_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    # -- the public write API --------------------------------------------
    def upsert(
        self,
        updates: Iterable[dict],
        *,
        caller: str,
        require_verdict: bool = False,
        force: bool = False,
        force_reason: str = "",
        batch: str = "",
    ) -> UpsertResult:
        """Add or change rows. Each update is a dict with at least ``job_id``.

        Every guard runs per row; a refused row is reported in the result and
        the rest are still written. Refusals that mean the *call* is wrong (an
        unknown status, a batch-level verdict, a forced write with no reason)
        raise instead.
        """
        updates = list(updates)
        if force and not force_reason:
            raise TrackerRefused(
                "force_without_reason",
                "I will not override my own checks without a reason recorded.",
            )
        for update in updates:
            if "verdict" in update and "job_id" not in update:
                raise TrackerRefused(
                    "batch_verdict",
                    "A single verdict for a whole batch is not evidence. Give me one verdict per job.",
                )
            if "status" in update and normalize_status(update["status"]) not in STATUSES:
                raise TrackerRefused(
                    "unknown_status",
                    f"{update['status']!r} is not a status I know, so I wrote nothing.",
                )

        result = UpsertResult()
        with self._lock():
            rows = self.read()
            index = {str(row.get("job_id")): position for position, row in enumerate(rows) if row.get("job_id")}
            identity_index: dict[str, int] = {}
            for position, row in enumerate(rows):
                for key in row_identities(row):
                    identity_index.setdefault(key, position)

            for update in updates:
                job_id = str(update.get("job_id") or "")
                if not job_id:
                    result.refused.append(("", "missing_job_id"))
                    continue
                position = index.get(job_id)
                if position is None:
                    position = next(
                        (identity_index[key] for key in row_identities(update) if key in identity_index),
                        None,
                    )
                existing = rows[position] if position is not None else None

                refusal = self._guard(existing, update, require_verdict=require_verdict, force=force)
                if refusal:
                    result.refused.append((job_id, refusal))
                    continue

                if existing is None:
                    row = self._new_row(update, caller=caller, batch=batch)
                    rows.append(row)
                    index[job_id] = len(rows) - 1
                    for key in row_identities(row):
                        identity_index.setdefault(key, len(rows) - 1)
                    result.added += 1
                    self._event("add", job_id=job_id, caller=caller, status=row["status"])
                else:
                    changed = self._merge(existing, update, caller=caller, batch=batch)
                    if changed:
                        result.updated += 1
                        self._event(
                            "update",
                            job_id=job_id,
                            caller=caller,
                            status=existing.get("status"),
                            fields=sorted(changed),
                            force_reason=force_reason or None,
                        )
                    else:
                        result.unchanged += 1

            if result.touched:
                self._write(rows)
        return result

    # -- guards ----------------------------------------------------------
    def _guard(self, existing: dict | None, update: dict, *, require_verdict: bool, force: bool) -> str:
        new_status = normalize_status(update.get("status")) if "status" in update else ""
        old_status = normalize_status(existing.get("status")) if existing else ""

        if require_verdict and new_status in ("pipeline", "skipped", "review"):
            if not str(update.get("review_verdict") or "").strip():
                return "verdict_missing"

        # A skip must carry its evidence.
        if new_status == "skipped":
            has_quote = bool(str(update.get("skip_quote") or "").strip())
            basis = str(update.get("skip_basis") or update.get("review_verdict_source") or "")
            allowed = any(token in basis for token in SKIP_BASES_WITHOUT_QUOTE)
            if not str(update.get("skip_reason") or "").strip():
                return "skip_without_reason"
            if not has_quote and not allowed:
                return "skip_without_evidence"

        # Confirmed means confirmed: a receipt, or an explicitly forced write.
        if new_status == "applied" and not force:
            receipt = update.get("receipt") or (existing or {}).get("receipt") or {}
            if not (isinstance(receipt, dict) and receipt.get("mail_id") and receipt.get("basis")):
                return "receipt_missing"

        if existing is None:
            return ""

        # Never re-apply. A forced write may override it, with a recorded reason.
        if old_status in SUBMITTED_STATUSES and new_status in ("claimed", "pipeline", "submitted"):
            if not update.get("rerun_approved") and not force:
                return "already_applied"

        # Re-opening something the user skipped needs the user.
        if old_status == "skipped" and new_status in ("pipeline", "claimed", "submitted"):
            if not update.get("reapply_approved") and not force:
                return "reapply_needs_approval"

        # An applied row is protected: notes and evidence only, unless forced.
        if old_status == "applied" and not force:
            touched = set(update) - SAFE_UPDATE_FIELDS
            if touched - {"status"} or (new_status and new_status != "applied"):
                return "protected_row"

        # One lane at a time.
        if new_status == "claimed":
            holder = existing.get("claimed_by")
            if holder and holder != update.get("claimed_by") and not self._lease_expired(existing):
                return "claimed_elsewhere"
        return ""

    @staticmethod
    def _lease_expired(row: dict, minutes: int = LEASE_MINUTES) -> bool:
        stamp = row.get("claimed_at")
        if not stamp:
            return True
        try:
            from datetime import datetime

            claimed = datetime.fromisoformat(str(stamp))
        except ValueError:
            return True
        return (now() - claimed).total_seconds() > minutes * 60

    # -- row shaping -----------------------------------------------------
    def _new_row(self, update: dict, *, caller: str, batch: str) -> dict:
        row = {
            "status": "new",
            "tags": [],
            "flags": [],
            "notes": [],
            "added_at": iso(),
            "caller": caller,
        }
        row.update({k: v for k, v in update.items() if k != "notes"})
        row["status"] = normalize_status(row.get("status"))
        row["notes"] = _as_notes(update.get("notes"))
        row["updated_at"] = iso()
        row["status_changed_at"] = iso()
        if batch:
            row["batch"] = batch
        return row

    def _merge(self, existing: dict, update: dict, *, caller: str, batch: str) -> set[str]:
        changed: set[str] = set()
        for key, value in update.items():
            if key in ("job_id",):
                continue
            if key == "notes":
                added = [n for n in _as_notes(value) if n not in existing.get("notes", [])]
                if added:
                    existing["notes"] = [*existing.get("notes", []), *added]
                    changed.add("notes")
                continue
            if key in ("tags", "flags", "alternate_urls"):  # add-only lists
                merged = sorted({*existing.get(key, []), *(value or [])})
                if merged != existing.get(key):
                    existing[key] = merged
                    changed.add(key)
                continue
            if key == "status":
                value = normalize_status(value)
            if existing.get(key) != value:
                existing[key] = value
                changed.add(key)
        if "status" in changed:
            existing["status_changed_at"] = iso()
        if changed:
            existing["updated_at"] = iso()
            existing["caller"] = caller
            if batch:
                existing["batch"] = batch
        return changed

    # -- convenience operations -------------------------------------------
    def claim(self, job_id: str, lane: str) -> bool:
        """Try to take a job for one lane. False when a guard said no."""
        result = self.upsert(
            [{"job_id": job_id, "status": "claimed", "claimed_by": lane, "claimed_at": iso()}],
            caller=f"apply:{lane}",
        )
        return not result.refused

    def dispose(self, job_id: str, status: str, **fields: Any) -> UpsertResult:
        """Record the outcome of working on a job. Every claimed row gets one."""
        update = {"job_id": job_id, "status": status, "claimed_by": "", "claimed_at": "", **fields}
        return self.upsert([update], caller="apply")

    def approve_reapply(self, job_id: str, *, approved_by: str, reason: str) -> UpsertResult:
        """The user's explicit go-ahead to reconsider a job that was skipped."""
        self._event("reapply_approved", job_id=job_id, approved_by=approved_by, reason=reason)
        return self.upsert(
            [
                {
                    "job_id": job_id,
                    "status": "pipeline",
                    "reapply_approved": True,
                    "reapply_approved_by": approved_by,
                    "notes": f"Reconsidered at your request: {reason}",
                    "review_verdict": "keep",
                    "review_verdict_source": f"user:{approved_by}",
                }
            ],
            caller="lead",
        )

    def already_submitted(self, job_id: str) -> bool:
        row = self.by_id().get(job_id)
        return bool(row) and normalize_status(row.get("status")) in SUBMITTED_STATUSES

    def events(self) -> Iterator[dict]:
        if not self.events_path.exists():
            return iter(())
        return (
            json.loads(line)
            for line in self.events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )


def _as_notes(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(item) for item in value if str(item).strip()]


def in_progress(rows: Iterable[dict]) -> list[dict]:
    return [row for row in rows if normalize_status(row.get("status")) in IN_PROGRESS_STATUSES]
