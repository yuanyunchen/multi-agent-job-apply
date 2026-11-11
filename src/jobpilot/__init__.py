"""jobpilot — a multi-agent job-application assistant.

The pieces, in the order a job moves through them:

    search   find postings on public job boards (no login)
    rules    deterministic checks that only ever add FLAGS
    screen   a model reads the description and must quote its evidence
    tracker  the one writer of the application record
    queue    what to apply to next: core first, newest first
    apply    waves of applications through an ApplyDriver, behind guards
    verify   confirmations and verification codes, read-only
    report   the daily summary in plain language
    lead     metrics and proposals, which always need your approval

Everything a user owns lives in ``config/preferences.yaml``; everything the
assistant owns lives under ``paths.data_dir``. No module hardcodes a path.
"""

__version__ = "2.0.0a1"

__all__ = ["__version__"]
