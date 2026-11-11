"""Shared scaffolding for the examples: synthetic data, a throwaway data folder.

Nothing here reads the user's settings or their records. Every example builds
its own settings in memory, points the data folder at a temporary directory, and
makes up the jobs it works on.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jobpilot.config import load_defaults
from jobpilot.domain import Job

#: Reserved example domains only. None of these companies exist.
COMPANIES = ("Acme Robotics", "Globex Systems", "Northwind Analytics", "Initech Defense")


def sandbox(name: str) -> Path:
    """A throwaway data folder for one example."""
    directory = Path(tempfile.mkdtemp(prefix=f"jobpilot-example-{name}-"))
    return directory


def settings(name: str, **overrides):
    """Settings for an example: real defaults, a made-up person, a temporary folder."""
    base = {
        "paths": {"data_dir": str(sandbox(name))},
        "identity": {
            "full_name": "Sam Example",
            "apply_email": "sam@example.test",
            "digest_email": "sam@example.test",
            "phone": "+1 555 0100",
            "current_location": "New York, NY",
        },
        "search": {
            "categories": {
                "core": ["Machine Learning Engineer", "AI Engineer"],
                "non_core": ["Software Engineer", "Data Engineer"],
                "excluded": ["Sales", "Technician"],
            },
            "max_required_years_experience": 2,
        },
        "models": {"providers": {"fake": {"enabled": True}}},
    }
    return load_defaults(_merge(base, overrides))


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def days_ago(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


JD_GOOD = """
Acme Robotics is hiring a Machine Learning Engineer in New York.
You will train and serve demand models for warehouse robots.
We welcome candidates on OPT, CPT or an existing visa, although we do not sponsor new work visas.
2 years of experience with Python is preferred.
"""

JD_NO_SPONSORSHIP = """
Globex Systems is looking for a Machine Learning Engineer.
This position is not eligible for visa sponsorship.
You will work on our forecasting stack.
"""

JD_TOO_SENIOR = """
Northwind Analytics is hiring a Machine Learning Engineer.
8 years of experience in production machine learning is required.
You will lead the modelling team.
"""

JD_PLAIN = """
Initech Defense is hiring a Software Engineer in Boston.
You will work on load forecasting for the grid.
We review applications weekly.
"""


def jobs() -> list[Job]:
    """Four made-up postings: one good, one ruled out, one too senior, one second choice."""
    return [
        Job(
            company="Acme Robotics",
            title="Machine Learning Engineer",
            url="https://job-boards.greenhouse.io/acme-robotics/jobs/4001",
            source="greenhouse",
            ats="greenhouse",
            ats_job_id="4001",
            location="New York, NY",
            description=JD_GOOD,
            posted_at=days_ago(1),
        ),
        Job(
            company="Globex Systems",
            title="Machine Learning Engineer",
            url="https://jobs.lever.co/globex-systems/9f2c",
            source="lever",
            ats="lever",
            ats_job_id="9f2c",
            location="Remote (US)",
            description=JD_NO_SPONSORSHIP,
            posted_at=days_ago(2),
        ),
        Job(
            company="Northwind Analytics",
            title="Machine Learning Engineer",
            url="https://jobs.ashbyhq.com/northwind-analytics/77",
            source="ashby",
            ats="ashby",
            ats_job_id="77",
            location="Seattle, WA",
            description=JD_TOO_SENIOR,
            posted_at=days_ago(5),
        ),
        Job(
            company="Initech Defense",
            title="Software Engineer",
            url="https://job-boards.greenhouse.io/initech-defense/jobs/12",
            source="greenhouse",
            ats="greenhouse",
            ats_job_id="12",
            location="Boston, MA",
            description=JD_PLAIN,
            posted_at=days_ago(3),
        ),
    ]


def heading(text: str) -> None:
    print()
    print(text)
    print("-" * len(text))
