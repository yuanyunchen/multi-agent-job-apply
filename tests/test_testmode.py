"""The suite must never be able to touch a live account.

If any of these stop raising, a test could reach a real mailbox, a real browser
or a real model account, which is exactly the accident this guard exists for.
"""

from __future__ import annotations

import pytest

from jobpilot.apply import BrowserDriverBase
from jobpilot.errors import TestModeViolation as Violation
from jobpilot.providers.cli import claude_provider, codex_provider
from jobpilot.providers.http import OpenAICompatibleProvider
from jobpilot.search.base import UrllibFetcher
from jobpilot.testmode import ensure_live, is_test_mode
from jobpilot.verify import JsonExportMailReader


def test_test_mode_is_on_for_the_whole_suite():
    assert is_test_mode() is True


def test_ensure_live_explains_itself():
    with pytest.raises(Violation) as caught:
        ensure_live("network")
    assert "real network" in str(caught.value)
    assert "FakeProvider" in str(caught.value)


def test_network_is_blocked():
    with pytest.raises(Violation):
        UrllibFetcher().get_json("https://example.test/jobs")


def test_real_mailbox_is_blocked(tmp_path):
    with pytest.raises(Violation):
        JsonExportMailReader(tmp_path)


def test_real_browser_driver_is_blocked():
    with pytest.raises(Violation):
        BrowserDriverBase()


@pytest.mark.parametrize(
    "provider",
    [
        claude_provider("claude-haiku-4-5-20251001"),
        codex_provider(),
        OpenAICompatibleProvider(base_url="https://example.test/v1", model="m", api_key_env="NOPE"),
    ],
)
def test_real_model_providers_are_blocked(provider):
    with pytest.raises(Violation):
        provider.complete("hello")


def test_health_checks_are_allowed_because_they_touch_nothing():
    # A health check only looks for the tool; it never runs it.
    health = claude_provider("claude-haiku-4-5-20251001").health()
    assert health.ok in (True, False)


def test_unsetting_the_marker_is_the_only_way_through(monkeypatch):
    monkeypatch.delenv("JOBPILOT_TEST")
    assert is_test_mode() is False
    ensure_live("network")  # no exception: this is the production path
