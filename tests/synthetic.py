"""Synthetic material for the tests. Fake companies, fake postings, fake mail.

Nothing in here refers to a real person, a real employer or a real account.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jobpilot.domain import Job
from jobpilot.search.base import FixtureFetcher
from jobpilot.verify import MailMessage

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/acme-robotics/jobs?content=true"
LEVER_URL = "https://api.lever.co/v0/postings/globex-systems?mode=json"
ASHBY_URL = "https://api.ashbyhq.com/posting-api/job-board/northwind-analytics?includeCompensation=false"

JD_OPT_FRIENDLY = """
Acme Robotics is hiring a Machine Learning Engineer in New York.
You will train and serve demand models for warehouse robots.
We welcome candidates on OPT, CPT or an existing visa, although we do not sponsor new work visas.
2 years of experience with Python is preferred.
"""

JD_NO_SPONSORSHIP = """
Globex Systems is looking for a Machine Learning Engineer.
Candidates must be authorized to work in the United States without sponsorship now or in the future.
You will work on our forecasting stack.
"""

JD_NOT_ELIGIBLE = """
Northwind Analytics seeks an AI Engineer for its modelling team.
This position is not eligible for visa sponsorship.
You will build pipelines for utility forecasting.
"""

JD_CITIZEN_ONLY = """
Initech Defense is hiring an Applied Scientist.
Applicants must be a U.S. citizen because of customer requirements.
The work involves signal processing.
"""

JD_CLEARANCE = """
Initech Defense needs a Machine Learning Engineer for a government programme.
An active secret clearance is required on day one.
"""

JD_YOE = """
Umbrella Logistics is hiring a Machine Learning Engineer.
5 years of experience in production machine learning is required.
Nice to have: 8 years of experience with distributed training.
"""

JD_YOE_CEILING = """
Umbrella Logistics is hiring a Machine Learning Engineer, early career.
Up to 3 years of experience is ideal, and 5 years of experience is preferred but not required.
"""

JD_PHD = """
Northwind Analytics is hiring a Research Engineer.
A PhD required in statistics or a related field.
"""

JD_PLAIN = """
Stark Grid is hiring a Machine Learning Engineer in Boston.
You will work on load forecasting for the grid.
We review applications weekly.
"""


def job(
    title: str = "Machine Learning Engineer",
    company: str = "Acme Robotics",
    url: str = "https://job-boards.greenhouse.io/acme-robotics/jobs/4001",
    description: str = JD_PLAIN,
    **kwargs,
) -> Job:
    defaults = {
        "source": "greenhouse",
        "ats": "greenhouse",
        "ats_job_id": "4001",
        "location": "New York, NY",
        "posted_at": iso_days_ago(1),
    }
    defaults.update(kwargs)
    return Job(company=company, title=title, url=url, description=description, **defaults)


def iso_days_ago(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def board_fetcher(fixtures_dir) -> FixtureFetcher:
    return FixtureFetcher.from_dir(
        fixtures_dir,
        {
            GREENHOUSE_URL: "greenhouse_acme.json",
            LEVER_URL: "lever_globex.json",
            ASHBY_URL: "ashby_northwind.json",
        },
    )


def mail(
    *,
    subject: str = "Thank you for applying to Acme Robotics",
    sender: str = "Acme Robotics Careers <no-reply@greenhouse.io>",
    recipient: str = "sam@example.test",
    minutes_after: float = 2,
    submitted_at: datetime | None = None,
    body: str = "We have received your application and will be in touch.",
    message_id: str = "mail-1",
) -> MailMessage:
    base = submitted_at or datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
    return MailMessage(
        message_id=message_id,
        sender=sender,
        recipient=recipient,
        subject=subject,
        received_at=base + timedelta(minutes=minutes_after),
        body=body,
    )


def screen_reply(job_id: str, verdict: str = "keep", tier: str = "core", quote: str = "", reason: str = "ok") -> str:
    import json

    return json.dumps(
        [{"job_id": job_id, "verdict": verdict, "tier": tier, "quote": quote, "reason": reason}]
    )
