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
* the maintainer's own words, anywhere except the public repository URL;
* **any non-English script** - see :data:`NON_ENGLISH` below.

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

#: Everything committed here is English, and this is what enforces it.
#:
#: The project is read by people who will not share the author's first
#: language, and by agents whose prompts are assembled from these files. A
#: sentence in another script is unreadable to half the audience and invisible
#: to a reviewer who cannot read it - which is exactly where an instruction
#: nobody intended survives for months.
#:
#: The ranges, in order: CJK symbols and punctuation, Hiragana, Katakana, CJK
#: unified ideographs extension A, CJK unified ideographs, Hangul Jamo, Hangul
#: syllables, and halfwidth/fullwidth forms.
#:
#: Written as escapes rather than as the characters themselves, so this
#: repository contains no such character anywhere - including in the rule that
#: looks for them. That makes the claim checkable with a plain search.
NON_ENGLISH = re.compile(
    "["
    "\u3000-\u303f"  # CJK symbols and punctuation
    "\u3040-\u309f"  # Hiragana
    "\u30a0-\u30ff"  # Katakana
    "\u3400-\u4dbf"  # CJK unified ideographs, extension A
    "\u4e00-\u9fff"  # CJK unified ideographs
    "\u1100-\u11ff"  # Hangul Jamo
    "\uac00-\ud7af"  # Hangul syllables
    "\uff00-\uffef"  # halfwidth and fullwidth forms
    "]"
)

ALLOWED_EMAIL_DOMAINS = {"example.test", "example.com", "example.org", "example.invalid"}
ALLOWED_VENDOR_DOMAINS = {"anthropic.com", "greenhouse.io", "acme-robotics.example"}

#: The files whose content *is* the patterns. Scanning them for their own rules
#: would fail by definition. The English-only rule still applies to them, and
#: they pass it by writing escapes rather than characters.
RULE_FILES = {
    "scripts/sanitize_scan.py",
    "tests/test_repo_hygiene.py",
    "tests/test_templates.py",
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


#: Extensions that are never text, so never worth decoding.
BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz",
    ".whl", ".so", ".dylib", ".pyc", ".woff", ".woff2", ".ttf", ".mp4", ".webm",
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


def text_files(root: Path) -> list[Path]:
    """Every text file, whatever it is called.

    Broader than :func:`files` on purpose: the English-only rule applies to
    anything a person or an agent reads, not only to the handful of extensions
    the other rules care about.
    """
    out: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        out.append(path)
    return sorted(out)


def scan_english_only(root: Path) -> list[str]:
    """Every text file is English. No exemptions, including the rule files.

    The rule files escape these characters rather than writing them, so they
    pass their own rule - which is the point: the claim "there is none of this
    anywhere" should be true of the whole repository, checkable with a plain
    search, with no file anybody has to take on trust.
    """
    problems: list[str] = []
    for path in text_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            match = NON_ENGLISH.search(line)
            if match:
                point = f"U+{ord(match.group(0)):04X}"
                problems.append(
                    f"{path.relative_to(root)}:{number}: non-English character {point} "
                    "(everything here is English)"
                )
                break  # one report per file is enough to act on
    return problems


def scan(root: Path) -> list[str]:
    problems: list[str] = scan_english_only(root)
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
