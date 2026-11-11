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

#: Checked in every committed text file.
SEARCHED = ("*.py", "*.md", "*.yaml", "*.yml", "*.toml", "*.json", "*.cfg", "*.sh", "Makefile")
SKIP_DIRS = {"legacy", ".git", "__pycache__", ".pytest_cache", "build", "dist", ".venv", "venv"}

#: The standalone version of these rules. It cannot pass its own rules: its
#: whole content is the patterns it looks for. ``test_the_two_hygiene_checks_agree``
#: is what keeps the two in step.
RULE_FILES = {"scripts/sanitize_scan.py"}

#: A path that belongs to one computer.
MACHINE_PATHS = re.compile(r"(/home/[a-z]|/Users/[A-Za-z]|/workspace|/private/var|/tmp/[a-z])")

#: Lines allowed to mention one, because they are the rules about them.
ALLOWED_PATH_MENTIONS = (
    "src/jobpilot/testmode.py",
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
            if str(path.relative_to(REPO)) in RULE_FILES:
                continue  # so does the standalone scanner
            out.append(path)
    return sorted(set(out))


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
    for name in ("AGENTS.md", "README.md", "START_HERE.md", "CONTRIBUTING.md", "LICENSE"):
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


#: The one public URL allowed to carry the maintainer's handle.
PUBLIC_REPO_URL = "github.com/yuanyunchen/multi-agent-job-apply"


def test_agents_md_points_at_the_pieces_an_agent_needs():
    text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    for pointer in (
        "START_HERE.md",
        "agents/lead.md",
        "agents/search.md",
        "agents/apply.md",
        "agents/mail.md",
        "routines/routines.yaml",
        "JOBPILOT_CONFIG",
        "`jobpilot setup`",
        "`jobpilot logins`",
        "`jobpilot doctor`",
    ):
        assert pointer in text, pointer


def test_agents_md_states_the_standing_rules():
    text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    for rule in (
        "permissions.submit_applications",
        "permissions.send_outreach_messages",
        "permissions.send_digest_email",
        "Never reset a password",
        "Never invent an answer",
        "Never apply to the same job twice",
        "Never change a setting without a yes",
    ):
        assert rule in text, rule


def test_readme_quick_start_comes_first_and_names_agents_md():
    text = (REPO / "README.md").read_text(encoding="utf-8")
    quick = text.find("## Quick start")
    assert quick != -1, "README is missing a '## Quick start' section"
    other = re.search(r"^## (?!Quick start).+$", text[quick + 1 :], re.MULTILINE)
    assert other is not None, "expected another ## heading after Quick start"
    following_heading = text.find("##", quick + 1)
    # Quick start must precede 5-minute start (and any other ## heading).
    five = text.find("## 5-minute start")
    assert five != -1 and quick < five, "Quick start must come before 5-minute start"
    section = text[quick:following_heading]
    assert "AGENTS.md" in section, "Quick start must point at AGENTS.md"
    assert PUBLIC_REPO_URL in section, "Quick start must give the repo link"


def test_every_jobpilot_command_in_agents_md_is_real():
    import argparse

    from jobpilot.cli import build_parser

    choices: set[str] = set()
    for action in build_parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            choices.update(action.choices)

    text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    mentioned = set()
    # Inline code spans that are themselves a command, e.g. `jobpilot setup`.
    for sub in re.findall(r"`jobpilot\s+([a-z][a-z-]*)[^`]*`", text):
        mentioned.add(sub)
    # Fenced code blocks are genuine shell; scan every jobpilot invocation.
    for block in re.findall(r"```[a-z]*\n(.*?)```", text, re.DOTALL):
        for sub in re.findall(r"\bjobpilot\s+([a-z][a-z-]*)", block):
            mentioned.add(sub)
    assert mentioned, "found no jobpilot commands in AGENTS.md"
    unknown = sorted(sub for sub in mentioned if sub not in choices)
    assert unknown == [], f"AGENTS.md names commands the CLI does not have: {unknown}"


@pytest.mark.parametrize("needle", ["yuan", "yunchen", "ethan", "columbia"])
def test_no_personal_words_outside_the_public_repo_url(needle):
    offenders = []
    for path in committed_files():
        text = path.read_text(encoding="utf-8")
        # The one sanctioned place the handle appears is the repo URL itself.
        stripped = re.sub(re.escape(PUBLIC_REPO_URL), "", text, flags=re.IGNORECASE)
        if needle in stripped.lower():
            offenders.append(str(path.relative_to(REPO)))
    assert offenders == [], f"{needle!r} appears in: {offenders}"


def test_every_role_prompt_states_the_shared_rules():
    shared = (REPO / "agents" / "README.md").read_text(encoding="utf-8")
    for rule in ("Evidence or nothing", "Never invent an answer", "No password resets"):
        assert rule in shared, rule
    for name in ("lead.md", "search.md", "apply.md", "mail.md"):
        text = (REPO / "agents" / name).read_text(encoding="utf-8")
        assert "agents/README.md" in text or "never" in text.lower(), name


@pytest.mark.parametrize("name", ["AGENTS.md", "README.md", "START_HERE.md"])
def test_every_jobpilot_line_in_the_setup_docs_parses(name):
    """Each shell line ``jobpilot …`` in a code block must be accepted by the real parser."""
    import shlex

    from jobpilot.cli import build_parser

    text = (REPO / name).read_text(encoding="utf-8")
    lines = []
    for block in re.findall(r"```[a-z]*\n(.*?)```", text, re.DOTALL):
        lines += [line for line in block.splitlines() if line.strip().startswith("jobpilot ")]
    lines += re.findall(r"`(jobpilot [^`]+)`", text)
    for line in lines:
        words = shlex.split(line.split("#")[0].split(">>")[0])[1:]
        words = [w if not (w.startswith("<") and w.endswith(">")) else "an-id" for w in words]
        try:
            build_parser().parse_args(words)
        except SystemExit:
            pytest.fail(f"{name}: '{line.strip()}' is not a valid jobpilot command")


# -- the documentation a reader is pointed at ----------------------------


def test_every_document_the_readme_links_to_exists():
    """A broken link in the first file somebody opens is the worst kind."""
    text = (REPO / "README.md").read_text(encoding="utf-8")
    missing = []
    for target in re.findall(r"\]\((?!https?:)([^)#]+)\)", text):
        if not (REPO / target).exists():
            missing.append(target)
    assert missing == []


@pytest.mark.parametrize(
    "name",
    [
        "docs/ARCHITECTURE.md",
        "docs/CAPABILITY-MATRIX.md",
        "docs/MIGRATION.md",
        "docs/ROUTINES.md",
        "docs/APPLY-METHOD.md",
        "docs/sample-session.md",
        "CHANGELOG.md",
        "Makefile",
        "scripts/setup.sh",
        "scripts/sanitize_scan.py",
        "scripts/migration_check.sh",
        "ci/github-actions-ci.yml",
        "routines/routines.yaml",
        "config/preferences.example.yaml",
        "config/answers.example.yaml",
        "config/search_terms.example.json",
        "config/sources.example.yaml",
        "examples/README.md",
    ],
)
def test_the_pieces_of_a_conventional_project_are_all_there(name):
    assert (REPO / name).exists(), name


def test_config_holds_templates_only():
    """A real settings file in the repository would be somebody's private data."""
    import subprocess

    listed = subprocess.run(
        ["git", "ls-files", "config"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.split()
    assert listed, "expected some templates under config/"
    for name in listed:
        assert ".example." in Path(name).name, f"{name} is not a template"


def test_nothing_private_is_sitting_in_the_checkout_either():
    """Not committed is not enough: a stray answer bank is still a leak waiting."""
    strays = [
        path.name
        for path in (REPO / "config").iterdir()
        if path.is_file() and ".example." not in path.name
    ]
    assert strays == [], f"private files left in config/: {strays}"


def test_the_capability_matrix_is_honest_about_what_is_missing():
    """A matrix with no "no" in it is marketing, not an audit."""
    text = (REPO / "docs" / "CAPABILITY-MATRIX.md").read_text(encoding="utf-8")
    assert "Deliberately not rebuilt" in text
    assert text.count("**no**") >= 5
    assert "Data, not logic" in text


def test_the_routines_document_matches_the_timetable():
    from jobpilot.routines import load_routines

    text = (REPO / "docs" / "ROUTINES.md").read_text(encoding="utf-8")
    for routine in load_routines():
        assert routine.what in text, routine.what


def test_the_changelog_says_what_moved_and_what_was_renamed():
    text = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "src/jobpilot/" in text
    assert "routines/routines.yaml" in text
    assert "apply.pass" in text


def test_the_workflow_runs_the_checks_it_should():
    text = (REPO / "ci" / "github-actions-ci.yml").read_text(encoding="utf-8")
    for needed in ("3.10", "3.11", "3.12", "pytest", "sanitize_scan.py", "migration_check.sh"):
        assert needed in text, needed
