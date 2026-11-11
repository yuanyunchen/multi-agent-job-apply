#!/usr/bin/env python3
"""Check that nothing personal or machine-specific is committed.

This is the same rule set the test suite enforces (``tests/test_repo_hygiene.py``),
packaged as a standalone script so continuous integration and the migration
check can run it against a bare clone without installing anything.

It fails on:

* a path that belongs to one computer (``/home/...``, ``/Users/...``,
  ``/workspace``, ``/private/var``, ``/tmp/<name>``);
* an email address outside the reserved example domains;
* a real mailbox provider (``@gmail.`` and friends);
* a ``{{PLACEHOLDER}}`` in a settings file that is not a ``.example.`` template
  (which means a real settings file was committed, or a template was renamed
  without being filled in);
* the maintainer's own words, anywhere except the public repository URL.

Usage: ``scripts/sanitize_scan.py [repo-root]``
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SEARCHED = ("*.py", "*.md", "*.yaml", "*.yml", "*.toml", "*.json", "*.cfg", "*.sh", "Makefile")
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "build", "dist", ".venv", "venv", "legacy"}

MACHINE_PATHS = re.compile(r"(/home/[a-z]|/Users/[A-Za-z]|/workspace|/private/var|/tmp/[a-z])")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
PLACEHOLDER = re.compile(r"\{\{[A-Z0-9_]+\}\}")
PROVIDERS = ("@gmail.", "@outlook.", "@yahoo.", "@hotmail.", "@icloud.")
PERSONAL_WORDS = ("yuan", "yunchen", "ethan", "columbia")

PUBLIC_REPO_URL = "github.com/yuanyunchen/multi-agent-job-apply"

ALLOWED_EMAIL_DOMAINS = {"example.test", "example.com", "example.org", "example.invalid"}
ALLOWED_VENDOR_DOMAINS = {"anthropic.com", "greenhouse.io", "acme-robotics.example"}

#: The two files whose whole content is the patterns themselves. Scanning them
#: for their own rules would fail by definition.
RULE_FILES = {
    "scripts/sanitize_scan.py",
    "tests/test_repo_hygiene.py",
}

#: Files allowed to write an absolute path, because they talk *about* paths:
#: the test-mode guard, the session recorder, and tests that build temporary
#: directories.
PATH_ALLOWED = {
    "src/jobpilot/testmode.py",
    "tools/record_sample_session.py",
    "CONTRIBUTING.md",
    "tests/test_config.py",
    "tests/test_plain_language.py",
    "tests/test_ui.py",
    "tests/test_cli.py",
    "tests/test_plugins.py",
    "tests/test_examples.py",
    "tests/test_migration.py",
}


def files(root: Path) -> list[Path]:
    out: list[Path] = []
    for pattern in SEARCHED:
        for path in root.rglob(pattern):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
                continue
            out.append(path)
    return sorted(set(out))


def scan(root: Path) -> list[str]:
    problems: list[str] = []
    checked = 0
    for path in files(root):
        relative = str(path.relative_to(root))
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        checked += 1
        if relative in RULE_FILES:
            continue

        for needle in PROVIDERS:
            if needle in text:
                problems.append(f"{relative}: real mailbox provider {needle!r}")

        for match in EMAIL.finditer(text):
            domain = match.group(1).lower().rstrip(".")
            if domain in ALLOWED_EMAIL_DOMAINS or domain.endswith((".example", ".test")):
                continue
            if domain in ALLOWED_VENDOR_DOMAINS:
                continue
            problems.append(f"{relative}: email address outside the example domains: {match.group(0)}")

        without_url = re.sub(re.escape(PUBLIC_REPO_URL), "", text, flags=re.IGNORECASE)
        for word in PERSONAL_WORDS:
            if word in without_url.lower():
                problems.append(f"{relative}: personal word {word!r}")

        if relative not in PATH_ALLOWED:
            for number, line in enumerate(text.splitlines(), start=1):
                if MACHINE_PATHS.search(line):
                    problems.append(f"{relative}:{number}: path belonging to one machine")

        # A placeholder belongs in a template. Anywhere else it means a real
        # settings file was committed by accident, or a template was renamed
        # without being filled in.
        if path.suffix in (".yaml", ".yml", ".json") and ".example." not in path.name:
            if "tests/fixtures" in relative:
                continue
            for number, line in enumerate(text.splitlines(), start=1):
                if PLACEHOLDER.search(line):
                    problems.append(f"{relative}:{number}: a placeholder outside a template file")

    if checked < 30:
        problems.append(f"only {checked} files were scanned — is {root} the project root?")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    root = Path(args[0]).resolve() if args else Path(__file__).resolve().parent.parent
    problems = scan(root)
    if problems:
        print(f"sanitize scan: {len(problems)} problem(s) in {root}")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"sanitize scan: clean ({root})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
