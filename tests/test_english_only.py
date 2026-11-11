"""Everything committed here is English.

Why this is a test and not a convention: the project is read by people who will
not share the author's first language, and its files are assembled into prompts
for agents. A sentence in another script is unreadable to half the audience and
**invisible to a reviewer who cannot read it** - which is exactly where an
instruction nobody intended survives for months.

This file deliberately contains **no such character**. The ranges below are
written as escapes, so the claim "there is none of this anywhere in the
repository" is true of the checker too, and can be verified with a plain
search rather than taken on trust.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

#: The scripts that are not English, by Unicode range. Escapes only.
RANGES: tuple[tuple[str, str, str], ...] = (
    ("CJK symbols and punctuation", "\u3000", "\u303f"),
    ("Hiragana", "\u3040", "\u309f"),
    ("Katakana", "\u30a0", "\u30ff"),
    ("CJK unified ideographs, extension A", "\u3400", "\u4dbf"),
    ("CJK unified ideographs", "\u4e00", "\u9fff"),
    ("Hangul Jamo", "\u1100", "\u11ff"),
    ("Hangul syllables", "\uac00", "\ud7af"),
    ("halfwidth and fullwidth forms", "\uff00", "\uffef"),
)

NON_ENGLISH = re.compile("[" + "".join(f"{low}-{high}" for _, low, high in RANGES) + "]")

#: Directories that are not part of what is committed.
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "build", "dist", ".venv", "venv"}


def tracked_text_files() -> list[Path]:
    """Every tracked file that is text, from git rather than from a guess."""
    listed = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.split("\0")
    out = []
    for name in listed:
        if not name:
            continue
        path = REPO / name
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in Path(name).parts):
            continue
        out.append(path)
    return out


def test_there_are_tracked_files_to_check():
    assert len(tracked_text_files()) > 50


def test_no_tracked_file_contains_a_non_english_character():
    offenders = []
    for path in tracked_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # a binary file is not text, and not this test's business
        for number, line in enumerate(text.splitlines(), start=1):
            match = NON_ENGLISH.search(line)
            if match:
                point = f"U+{ord(match.group(0)):04X}"
                offenders.append(f"{path.relative_to(REPO)}:{number}: {point}")
                break
    assert offenders == [], "non-English text found: " + "; ".join(offenders)


def test_this_test_contains_none_of_what_it_looks_for():
    """The checker has to pass its own rule, or the claim is not checkable."""
    own = Path(__file__).read_text(encoding="utf-8")
    assert NON_ENGLISH.search(own) is None


@pytest.mark.parametrize("label,low,high", RANGES, ids=[r[0] for r in RANGES])
def test_every_range_is_actually_detected(label, low, high):
    """A range with a typo in it would silently check nothing."""
    for character in (low, high):
        assert NON_ENGLISH.search(f"text {character} text"), label


def test_plain_english_is_not_flagged():
    """Accented Latin, dashes, quotes and symbols are English text, not a script."""
    for safe in (
        "plain ASCII",
        "an em-dash \u2014 and an ellipsis \u2026",
        "curly \u201cquotes\u201d and an apostrophe \u2019",
        "caf\u00e9 na\u00efve r\u00e9sum\u00e9",
        "arrows \u2192 and a check \u2713",
        "emoji \U0001f534 in a heading",
    ):
        assert NON_ENGLISH.search(safe) is None, safe


# -- the standalone scanner agrees ---------------------------------------


def test_the_scanner_uses_the_same_ranges():
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import sanitize_scan
    finally:
        sys.path.pop(0)
    assert sanitize_scan.NON_ENGLISH.pattern == NON_ENGLISH.pattern


def test_the_scanner_reports_a_clean_repository():
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import sanitize_scan
    finally:
        sys.path.pop(0)
    assert sanitize_scan.scan_english_only(REPO) == []


def test_the_scanner_would_fail_on_a_file_that_was_not_english(tmp_path):
    """Proving the check can fail is the only way to know it can pass."""
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import sanitize_scan
    finally:
        sys.path.pop(0)

    (tmp_path / "fine.md").write_text("plain English\n", encoding="utf-8")
    (tmp_path / "not-fine.md").write_text(
        "a line with \u6c42\u8077 in it\n", encoding="utf-8"
    )
    (tmp_path / "also-not-fine.yaml").write_text("x: \ud55c\uad6d\uc5b4\n", encoding="utf-8")

    problems = sanitize_scan.scan_english_only(tmp_path)
    assert len(problems) == 2
    assert all("non-English character" in problem for problem in problems)
    named = {problem.split(":")[0] for problem in problems}
    assert named == {"not-fine.md", "also-not-fine.yaml"}


def test_the_scanner_looks_beyond_the_usual_extensions(tmp_path):
    """The rule covers anything a person or an agent reads, not just .py and .md."""
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import sanitize_scan
    finally:
        sys.path.pop(0)

    (tmp_path / "notes.txt").write_text("\u30ab\u30bf\u30ab\u30ca\n", encoding="utf-8")
    (tmp_path / "LICENCE").write_text("\u4e00\n", encoding="utf-8")
    problems = sanitize_scan.scan_english_only(tmp_path)
    assert len(problems) == 2


def test_a_binary_file_is_not_decoded(tmp_path):
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import sanitize_scan
    finally:
        sys.path.pop(0)

    (tmp_path / "picture.png").write_bytes(b"\x89PNG\r\n\x1a\n\xe6\xb1\x82")
    assert sanitize_scan.scan_english_only(tmp_path) == []
