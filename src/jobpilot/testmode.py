"""Test isolation.

When ``JOBPILOT_TEST=1`` (set by ``tests/conftest.py`` for the whole suite)
every door to the real world is bolted shut:

* network requests,
* real mailboxes,
* real browser / apply drivers,
* real model command-line tools.

Each of those calls :func:`ensure_live` before doing anything, and
:func:`ensure_live` raises in test mode. The block lives in the code under test,
not in the tests, so a new code path cannot sneak past it (that is the whole
point: a test suite that fakes only *some* commands will eventually fall through
to a real one).
"""

from __future__ import annotations

import os

from .errors import TestModeViolation

ENV_VAR = "JOBPILOT_TEST"


def is_test_mode() -> bool:
    """True when the suite is running. Checked at call time, never cached."""
    return os.environ.get(ENV_VAR, "").strip().lower() in {"1", "true", "yes", "on"}


def ensure_live(what: str) -> None:
    """Raise unless we are allowed to touch the real world.

    ``what`` names the door, e.g. ``"network"``, ``"mailbox"``,
    ``"browser driver"``, ``"model command line"``.
    """
    if is_test_mode():
        raise TestModeViolation(
            f"Blocked: tests are not allowed to use the real {what}.",
            hint="Use a fake (FakeProvider, FixtureFetcher, FakeMailReader, DryRunDriver) instead.",
        )
