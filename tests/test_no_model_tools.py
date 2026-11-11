"""Nothing may depend on a tool that happens to be installed on this machine.

The first CI run of this project failed here: `jobpilot doctor` and the setup
example passed on their author's laptop, where a `claude` command line exists,
and failed on a fresh runner, where none does. The lesson is that "it works on
my machine" is a property the suite has to check, not one it can hope for.

So every test here runs the real commands with a `PATH` built by hand: every
directory the machine already has, minus any model command-line tool. If a
check starts depending on one again, these fail wherever they are run.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from .test_examples import scripts

REPO = Path(__file__).resolve().parent.parent

#: Names of model command-line tools, stripped out of the ``PATH`` below. The
#: prefixes are matched rather than the exact names so that ``claude-haiku``,
#: ``claude-opus`` and any future sibling are stripped too.
MODEL_TOOL = re.compile(r"^(claude|codex|gemini|ollama|aichat|llm|copilot)\b", re.IGNORECASE)


@pytest.fixture(scope="session")
def path_without_model_tools() -> str:
    """This machine's own ``PATH``, minus every folder holding a model tool.

    Dropping whole folders keeps the rest of the machine intact - the shell
    example needs ``sh``, ``mktemp`` and friends, and a ``PATH`` trimmed down
    to a guessed list of directories would prove nothing about the examples.
    (Mirroring each folder as symlinks would be finer-grained, but it leaves a
    thousand links behind in a temporary folder for no gain here.) The
    interpreter is passed to every subprocess as an absolute path, so losing
    ``python3`` with a dropped folder does not matter.
    """
    kept: list[str] = []
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        try:
            names = [entry.name for entry in Path(directory).iterdir()]
        except OSError:
            continue  # a folder on PATH that is not there, or not readable
        if not any(MODEL_TOOL.match(name) for name in names):
            kept.append(directory)
    path = os.pathsep.join(kept)
    for needed in ("sh", "mktemp"):
        if shutil.which(needed, path=path) is None:
            pytest.skip(
                f"this machine keeps a model tool in the same folder as {needed}; "
                "re-run with it out of PATH"
            )
    return path


def _run(command: list[str], *, path: str, test_mode: bool, **extra) -> subprocess.CompletedProcess:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"JOBPILOT_TEST", "JOBPILOT_CONFIG", "JOBPILOT_DATA_DIR", "PATH"}
    }
    environment["PATH"] = path
    environment["PYTHON"] = sys.executable  # the interpreter is not what is under test
    environment["PYTHONPATH"] = str(REPO / "src")
    if test_mode:
        environment["JOBPILOT_TEST"] = "1"
    environment.update(extra)
    return subprocess.run(
        command, cwd=REPO, env=environment, capture_output=True, text=True, timeout=180
    )


@pytest.fixture()
def example_settings(tmp_path: Path) -> Path:
    """The shipped example, pointed at a throwaway data folder."""
    data = yaml.safe_load((REPO / "config" / "preferences.example.yaml").read_text(encoding="utf-8"))
    data["paths"]["data_dir"] = str(tmp_path / "data")
    destination = tmp_path / "preferences.yaml"
    destination.write_text(yaml.safe_dump(data), encoding="utf-8")
    return destination


def test_the_built_path_really_has_no_model_tool_on_it(path_without_model_tools):
    for tool in ("claude", "claude-haiku", "claude-opus", "claude-sonnet", "codex"):
        found = shutil.which(tool, path=path_without_model_tools)
        assert found is None, f"{tool} is still reachable at {found}"
    # and it is still a usable PATH, or the tests below would prove nothing
    for needed in ("sh", "mktemp", "cat"):
        assert shutil.which(needed, path=path_without_model_tools), needed


def test_doctor_is_happy_on_a_machine_with_no_model_tools(
    path_without_model_tools, example_settings, tmp_path
):
    """The shipped example, in test mode, on a bare machine: this must pass."""
    done = _run(
        [sys.executable, "-m", "jobpilot", "doctor"],
        path=path_without_model_tools,
        test_mode=True,
        JOBPILOT_CONFIG=str(example_settings),
        JOBPILOT_DATA_DIR=str(tmp_path / "data"),
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Everything checks out." in done.stdout
    # it says so rather than pretending it checked a tool it may not use
    assert "not checked" in done.stdout


def test_doctor_still_calls_a_missing_tool_a_problem_in_real_use(
    path_without_model_tools, example_settings, tmp_path
):
    """Without the test marker the same situation is a fault, and says so.

    This is the other half of the rule: test mode must not be a way to make a
    broken installation look fine to somebody actually using it. Nothing here
    reaches the outside world - the self-check only reads.
    """
    done = _run(
        [sys.executable, "-m", "jobpilot", "doctor"],
        path=path_without_model_tools,
        test_mode=False,
        JOBPILOT_CONFIG=str(example_settings),
        JOBPILOT_DATA_DIR=str(tmp_path / "data"),
    )
    assert done.returncode == 1, done.stdout + done.stderr
    assert "not usable" in done.stdout
    assert "could not find" in done.stdout
    # three roles, one sentence, and the verb agrees with the number
    assert "3 things need fixing" in done.stdout


@pytest.mark.parametrize("script", scripts("*.py") + scripts("*.sh"), ids=lambda path: path.name)
def test_an_example_runs_with_no_model_tools_on_the_path(path_without_model_tools, script: Path):
    runner = ["sh"] if script.suffix == ".sh" else [sys.executable]
    done = _run([*runner, str(script)], path=path_without_model_tools, test_mode=True)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Traceback (most recent call last)" not in done.stdout + done.stderr


def test_the_only_place_that_looks_at_the_path_is_the_model_tool_provider():
    """One door to "what is installed here", so there is one place to fake."""
    looking = []
    for path in sorted((REPO / "src").rglob("*.py")):
        if "shutil.which" in path.read_text(encoding="utf-8"):
            looking.append(str(path.relative_to(REPO)))
    assert looking == ["src/jobpilot/providers/cli.py"], looking
