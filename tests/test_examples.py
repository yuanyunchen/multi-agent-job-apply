"""Every example must still run, offline, and send nothing.

An example that quietly stops working is worse than no example: it is the first
thing a newcomer tries. So the suite runs all of them. They are run as
subprocesses, exactly as a person would run them, with the test marker set so
every door to the real world stays bolted.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
EXAMPLES = REPO / "examples"

#: Words that would mean an example had reached something real.
FORBIDDEN = ("Traceback (most recent call last)", "JOBPILOT_TEST", "ensure_live")


def scripts(pattern: str) -> list[Path]:
    return sorted(path for path in EXAMPLES.glob(pattern) if not path.name.startswith("_"))


def environment() -> dict[str, str]:
    return {
        **os.environ,
        "JOBPILOT_TEST": "1",
        "PYTHON": sys.executable,
        "PYTHONPATH": os.pathsep.join(
            [str(REPO / "src"), os.environ.get("PYTHONPATH", "")]
        ).rstrip(os.pathsep),
    }


def run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        command, cwd=REPO, env=environment(), capture_output=True, text=True, timeout=180
    )


def test_there_are_examples_to_run():
    assert len(scripts("*.py")) >= 6
    assert scripts("*.sh")


@pytest.mark.parametrize("script", scripts("*.py"), ids=lambda path: path.name)
def test_an_example_script_runs_offline(script: Path):
    done = run([sys.executable, str(script)])
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.strip(), "an example that prints nothing explains nothing"
    for word in FORBIDDEN:
        assert word not in done.stdout + done.stderr, word


@pytest.mark.parametrize("script", scripts("*.sh"), ids=lambda path: path.name)
def test_an_example_shell_script_runs_offline(script: Path):
    done = run(["sh", str(script)])
    assert done.returncode == 0, done.stdout + done.stderr
    assert "sent nothing" in done.stdout


def test_the_readme_lists_every_example():
    """A script nobody is pointed at may as well not be there."""
    listed = (EXAMPLES / "README.md").read_text(encoding="utf-8")
    for script in scripts("*.py") + scripts("*.sh"):
        assert script.name in listed, script.name


def test_no_example_claims_to_have_sent_anything():
    """Read every example's own words: none of them may promise to send."""
    for script in scripts("*.py") + scripts("*.sh"):
        text = script.read_text(encoding="utf-8").lower()
        assert "permissions.submit_applications: true" not in text
        assert "send_outreach_messages: true" not in text
