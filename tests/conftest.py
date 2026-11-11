"""Test setup.

``JOBPILOT_TEST=1`` is set here, before anything is imported, so every door to
the real world (network, mailbox, browser, model command lines) is bolted shut
for the whole suite. ``tests/test_testmode.py`` proves it.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ["JOBPILOT_TEST"] = "1"

import pytest  # noqa: E402

from jobpilot.config import load_defaults  # noqa: E402
from jobpilot.tracker import Tracker  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


REPO_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """No test may see the real data directory or a real settings file.

    The second half also proves no test writes into the checkout: a wizard that
    defaults to ``config/preferences.yaml`` must never be pointed there by a
    test, because that is a real person's file on a real installation.
    """
    monkeypatch.setenv("JOBPILOT_TEST", "1")
    monkeypatch.setenv("JOBPILOT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("JOBPILOT_CONFIG", raising=False)
    before = set(REPO_CONFIG_DIR.iterdir()) if REPO_CONFIG_DIR.exists() else set()
    yield
    after = set(REPO_CONFIG_DIR.iterdir()) if REPO_CONFIG_DIR.exists() else set()
    created = {path.name for path in after - before}
    assert not created, f"a test wrote into the checkout's config folder: {sorted(created)}"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def make_config(tmp_path):
    """A valid settings object with the data directory inside the test's tmp."""

    def _factory(**overrides):
        base = {
            "paths": {"data_dir": str(tmp_path / "data")},
            "identity": {
                "full_name": "Sam Example",
                "apply_email": "sam@example.test",
                "digest_email": "sam@example.test",
            },
            "search": {
                "categories": {
                    "core": ["Machine Learning Engineer", "AI Engineer"],
                    "non_core": ["Software Engineer"],
                    "excluded": ["Sales", "Technician"],
                }
            },
        }
        return load_defaults(_merge(base, overrides))

    return _factory


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


@pytest.fixture
def config(make_config):
    return make_config()


@pytest.fixture
def tracker(config) -> Tracker:
    return Tracker.from_config(config)
