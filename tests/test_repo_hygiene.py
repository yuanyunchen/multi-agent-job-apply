"""This is a public repository. Nothing personal, and nobody's machine, in it.

The documentation is generated from real runs, which is exactly how a path or a
name leaks into a published file — so the check belongs in the suite, not in
somebody's memory.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

#: Checked in every committed text file. v1 is excluded: it is a frozen export.
SEARCHED = ("*.py", "*.md", "*.yaml", "*.yml", "*.toml", "*.json", "*.cfg")
SKIP_DIRS = {"legacy", ".git", "__pycache__", ".pytest_cache", "build", "dist", ".venv", "venv"}

#: A path that belongs to one computer.
MACHINE_PATHS = re.compile(r"(/home/[a-z]|/Users/[A-Za-z]|/workspace|/private/var|/tmp/[a-z])")

#: Lines allowed to mention one, because they are the rules about them.
ALLOWED_PATH_MENTIONS = (
    "jobpilot/testmode.py",
    "tools/record_sample_session.py",
    "CONTRIBUTING.md",
    "tests/test_repo_hygiene.py",
    "tests/test_config.py",
    "tests/test_plain_language.py",
    "tests/test_ui.py",
    "tests/test_cli.py",
    "tests/test_plugins.py",
)


def committed_files() -> list[Path]:
    out: list[Path] = []
    for pattern in SEARCHED:
        for path in REPO.rglob(pattern):
            if any(part in SKIP_DIRS for part in path.relative_to(REPO).parts):
                continue
            if path.name == Path(__file__).name:
                continue  # this file quotes the things it is looking for
            out.append(path)
    return sorted(out)


def test_there_are_files_to_check():
    assert len(committed_files()) > 30


@pytest.mark.parametrize("needle", ["@gmail.", "@outlook.", "@yahoo."])
def test_no_real_mailbox_providers_appear(needle):
    for path in committed_files():
        assert needle not in path.read_text(encoding="utf-8"), path


def test_no_machine_paths_outside_the_rules_about_them():
    offenders = []
    for path in committed_files():
        relative = str(path.relative_to(REPO))
        if relative in ALLOWED_PATH_MENTIONS:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if MACHINE_PATHS.search(line):
                offenders.append(f"{relative}:{number}: {line.strip()[:90]}")
    assert offenders == []


def test_every_email_address_is_a_reserved_example_domain():
    address = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
    allowed = {"example.test", "example.com", "example.org", "example.invalid"}
    offenders = []
    for path in committed_files():
        for match in address.finditer(path.read_text(encoding="utf-8")):
            domain = match.group(1).lower().rstrip(".")
            if domain in allowed or domain.endswith(".example") or domain.endswith(".test"):
                continue
            if domain in ("anthropic.com", "greenhouse.io", "acme-robotics.example"):
                continue  # a vendor domain in a comment, not a person
            offenders.append(f"{path.relative_to(REPO)}: {match.group(0)}")
    assert offenders == []


def test_the_recorded_session_is_present_and_looks_recorded():
    document = (REPO / "docs" / "sample-session.md").read_text(encoding="utf-8")
    assert "Every line below is **real output**" in document
    assert "YOU >" in document  # the user's answers are marked
    assert document.count("$ jobpilot") > 10
    assert "Run 1 — everything switched on" in document
    assert "Run 2 — nothing switched on" in document


def test_the_things_a_user_is_pointed_at_exist():
    for name in ("README.md", "START_HERE.md", "CONTRIBUTING.md", "LICENSE"):
        assert (REPO / name).exists(), name
    for name in ("ARCHITECTURE.md", "sample-session.md"):
        assert (REPO / "docs" / name).exists(), name
    for name in ("README.md", "lead.md", "search.md", "apply.md", "mail.md", "bootstrap.md"):
        assert (REPO / "agents" / name).exists(), name


def test_the_pasteable_prompt_states_the_standing_rules():
    text = (REPO / "START_HERE.md").read_text(encoding="utf-8")
    for rule in (
        "Never invent an answer",
        "Never reset a password",
        "Never ask for a password",
        "Never send a message, post a comment or submit a form",
        "Never print a credential",
        "Never change one of their settings",
        "Never apply to the same job twice",
    ):
        assert rule in text, rule
    assert "agents/lead.md" in text
    assert "jobpilot doctor" in text


def test_the_readme_lists_everything_that_can_be_switched_on():
    from jobpilot.catalog import catalog

    text = (REPO / "README.md").read_text(encoding="utf-8")
    for entry in catalog():
        assert f"`{entry.name}`" in text, entry.name


def test_the_role_prompt_and_the_pasteable_prompt_say_the_same_thing():
    """agents/bootstrap.md is the same prompt START_HERE.md hands out."""
    start = (REPO / "START_HERE.md").read_text(encoding="utf-8")
    role = (REPO / "agents" / "bootstrap.md").read_text(encoding="utf-8")
    for heading in re.findall(r"^\*\*Step \d+ — .*?\*\*", start, re.MULTILINE):
        assert heading in role, heading
    assert "You are the **setup assistant**" in role


def test_every_role_prompt_states_the_shared_rules():
    shared = (REPO / "agents" / "README.md").read_text(encoding="utf-8")
    for rule in ("Evidence or nothing", "Never invent an answer", "No password resets"):
        assert rule in shared, rule
    for name in ("lead.md", "search.md", "apply.md", "mail.md"):
        text = (REPO / "agents" / name).read_text(encoding="utf-8")
        assert "agents/README.md" in text or "never" in text.lower(), name
