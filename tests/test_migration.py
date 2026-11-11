"""Can somebody else clone this and run it?

Everything here is about *portability*: the project must not care what the
folder is called, where it is, or what the current directory happens to be when
a command runs. The shell version of this (``scripts/migration_check.sh``) does
the full clone-install-test loop; these tests cover the parts that can be
checked in-process, so a regression shows up in seconds rather than in CI.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from jobpilot.cli import cron_line, main, shorten, systemd_snippet
from jobpilot.config import ENV_HOME, repo_root, routines_path
from jobpilot.routines import load_routines
from jobpilot.scheduler import ACTIONS

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture()
def example_settings(tmp_path: Path) -> Path:
    """The shipped example, pointed at a throwaway data directory."""
    data = yaml.safe_load((REPO / "config" / "preferences.example.yaml").read_text(encoding="utf-8"))
    data["paths"]["data_dir"] = str(tmp_path / "data")
    # The example lists placeholders for a person; setup strips them, and the
    # self-check must cope with them being blank.
    data["identity"] = {key: "" for key in data["identity"]}
    destination = tmp_path / "preferences.yaml"
    destination.write_text(yaml.safe_dump(data), encoding="utf-8")
    return destination


def test_repo_root_is_found_from_the_package_not_from_the_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert repo_root() == REPO
    assert (repo_root() / "pyproject.toml").exists()


def test_repo_root_can_be_overridden_for_an_installed_copy(tmp_path, monkeypatch):
    elsewhere = tmp_path / "somewhere-else"
    elsewhere.mkdir()
    monkeypatch.setenv(ENV_HOME, str(elsewhere))
    assert repo_root() == elsewhere.resolve()


def test_doctor_works_from_an_arbitrary_working_directory(example_settings, tmp_path, capsys):
    """``jobpilot doctor`` must not depend on being run inside the checkout."""
    somewhere = tmp_path / "unrelated"
    somewhere.mkdir()
    previous = Path.cwd()
    try:
        os.chdir(somewhere)
        assert main(["--config", str(example_settings), "doctor"]) == 0
    finally:
        os.chdir(previous)
    out = capsys.readouterr().out
    assert "Everything checks out." in out
    assert "Timetable:" in out


def test_doctor_works_as_a_subprocess_from_another_directory(example_settings, tmp_path):
    """The same thing again, for real, through the installed entry point."""
    somewhere = tmp_path / "elsewhere"
    somewhere.mkdir()
    environment = {
        **os.environ,
        "JOBPILOT_CONFIG": str(example_settings),
        "JOBPILOT_TEST": "1",
        # The suite runs from the source tree, which may not be installed.
        "PYTHONPATH": os.pathsep.join([str(REPO / "src"), os.environ.get("PYTHONPATH", "")]).rstrip(
            os.pathsep
        ),
    }
    done = subprocess.run(
        [sys.executable, "-m", "jobpilot", "doctor"],
        cwd=somewhere,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Everything checks out." in done.stdout


def test_the_timetable_is_found_without_being_told_where_it_is(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert routines_path().exists()
    assert load_routines()


def test_every_routine_in_the_file_has_something_wired_up_to_do_it():
    """A timetable entry nobody implements is a promise that silently fails."""
    missing = sorted({r.what for r in load_routines()} - set(ACTIONS))
    assert missing == [], f"no action is registered for: {missing}"


def test_the_scheduler_line_is_generated_and_names_this_checkout():
    line = cron_line()
    assert "~/jobpilot" not in line  # never a guessed folder name
    assert shorten(repo_root()) in line
    assert shorten(repo_root()) in systemd_snippet()


def test_the_two_hygiene_checks_agree():
    """The standalone scanner and the test suite must enforce the same rules."""
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import sanitize_scan
    finally:
        sys.path.pop(0)

    from tests import test_repo_hygiene as suite

    assert sanitize_scan.MACHINE_PATHS.pattern == suite.MACHINE_PATHS.pattern
    assert sanitize_scan.PUBLIC_REPO_URL == suite.PUBLIC_REPO_URL
    assert sanitize_scan.scan(REPO) == []
