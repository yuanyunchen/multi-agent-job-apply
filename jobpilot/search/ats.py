"""Built-in sources: public job-board APIs that need no login and no account.

Each family is a URL template plus a parse function, wrapped in one
:class:`BoardSource`. Adding a family is one entry in :data:`FAMILIES`.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from ..domain import Job
from .base import FetchError, Fetcher

_TAG = re.compile(r"<[^>]+>")
_BREAK = re.compile(r"(?i)</(p|div|li|h[1-6]|tr)>|<br\s*/?>")


def plain_text(raw: str) -> str:
    """HTML (sometimes double-escaped) to readable text, newlines preserved.

    Quoted evidence is checked against this text, so it must stay faithful to
    the employer's sentences: tags become whitespace, nothing is reworded.
    """
    text = html.unescape(html.unescape(raw or ""))
    text = _BREAK.sub("\n", text)
    text = _TAG.sub(" ", text)
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _iso(value: Any) -> str:
    """Whatever the board gave us, as an ISO timestamp (or an empty string)."""
    if value in (None, "", 0):
        return ""
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, timezone.utc).isoformat()
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


# -- per-family parsers --------------------------------------------------


def parse_greenhouse(payload: Any, board: str) -> list[Job]:
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    out: list[Job] = []
    for item in jobs:
        job_id = str(item.get("id") or "").strip()
        url = item.get("absolute_url") or (
            f"https://job-boards.greenhouse.io/{board}/jobs/{job_id}" if job_id else ""
        )
        if not url:
            continue
        location = (item.get("location") or {}).get("name", "") if isinstance(item.get("location"), dict) else ""
        company = (item.get("company_name") or board).strip()
        out.append(
            Job(
                company=company,
                title=(item.get("title") or "").strip(),
                url=url,
                source="greenhouse",
                ats="greenhouse",
                ats_job_id=job_id,
                location=location,
                description=plain_text(item.get("content") or ""),
                posted_at=_iso(item.get("first_published") or item.get("updated_at")),
            )
        )
    return out


def parse_lever(payload: Any, board: str) -> list[Job]:
    items = payload if isinstance(payload, list) else payload.get("data", [])
    out: list[Job] = []
    for item in items:
        job_id = str(item.get("id") or "").strip()
        url = item.get("hostedUrl") or (
            f"https://jobs.lever.co/{board}/{job_id}" if job_id else ""
        )
        if not url:
            continue
        categories = item.get("categories") or {}
        description = "\n".join(
            part
            for part in (
                item.get("descriptionPlain") or plain_text(item.get("description") or ""),
                *(
                    f"{section.get('text', '')}\n{plain_text(section.get('content', ''))}"
                    for section in (item.get("lists") or [])
                ),
                item.get("additionalPlain") or plain_text(item.get("additional") or ""),
            )
            if part and part.strip()
        )
        out.append(
            Job(
                company=(item.get("companyName") or board).strip(),
                title=(item.get("text") or "").strip(),
                url=url,
                source="lever",
                ats="lever",
                ats_job_id=job_id,
                location=str(categories.get("location") or ""),
                description=description.strip(),
                posted_at=_iso(item.get("createdAt")),
                remote=str(categories.get("location") or "").lower().startswith("remote") or None,
            )
        )
    return out


def parse_ashby(payload: Any, board: str) -> list[Job]:
    jobs = payload.get("jobs", []) if isinstance(payload, dict) else []
    out: list[Job] = []
    for item in jobs:
        if item.get("isListed") is False:
            continue
        job_id = str(item.get("id") or "").strip()
        url = item.get("jobUrl") or item.get("applyUrl") or ""
        if not url:
            continue
        out.append(
            Job(
                company=(item.get("organizationName") or board).strip(),
                title=(item.get("title") or "").strip(),
                url=url,
                source="ashby",
                ats="ashby",
                ats_job_id=job_id,
                location=str(item.get("location") or ""),
                description=item.get("descriptionPlain") or plain_text(item.get("descriptionHtml") or ""),
                posted_at=_iso(item.get("publishedAt") or item.get("updatedAt")),
                remote=item.get("isRemote") if isinstance(item.get("isRemote"), bool) else None,
            )
        )
    return out


@dataclass(frozen=True, slots=True)
class Family:
    url: str  # one ``{board}`` placeholder
    parse: Callable[[Any, str], list[Job]]


FAMILIES: dict[str, Family] = {
    "greenhouse": Family(
        "https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true", parse_greenhouse
    ),
    "lever": Family("https://api.lever.co/v0/postings/{board}?mode=json", parse_lever),
    "ashby": Family(
        "https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=false", parse_ashby
    ),
}


@dataclass
class BoardSource:
    """One ATS family across however many boards the user listed."""

    family: str
    boards: list[str]
    errors: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.family

    def urls(self) -> list[str]:
        template = FAMILIES[self.family].url
        return [template.format(board=board) for board in self.boards]

    def fetch(self, fetcher: Fetcher) -> Iterable[Job]:
        spec = FAMILIES[self.family]
        for board in self.boards:
            url = spec.url.format(board=board)
            try:
                payload = fetcher.get_json(url)
            except FetchError as exc:
                # A board that is down is a reportable gap, never a crash.
                self.errors.append(f"{self.family}:{board}: {exc.message}")
                continue
            yield from spec.parse(payload, board)
