"""The bot templates: complete, parseable, consistent, and safe to publish.

A template is the first thing a stranger imports, so a broken one is a bad
first impression that lasts. These tests check the things that would be
embarrassing: a missing file, a schedule that never fires, a skill the share
payload points at that is not there, a credential, a personal detail, or a
vendor's model name written into a prompt where a configurable slot belongs.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = REPO / "templates"
BOTS = TEMPLATES / "bots"

#: Every role the team needs. Search is one role with two focus modes, not two
#: roles: two roles means two copies of the screening rules, and those drift.
ROLES = ("lead", "search", "apply", "mail", "linkedin", "handshake", "yc")

REQUIRED_FILES = ("bot.yaml", "PROFILE.md", "memories.md", "routines.yaml", "share.json")


def builder():
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import build_bot_templates
    finally:
        sys.path.pop(0)
    return build_bot_templates


def payload(role: str) -> dict:
    return json.loads((BOTS / role / "share.json").read_text(encoding="utf-8"))


def all_text(role: str) -> str:
    """Everything a template says, in one string, for the hygiene checks."""
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((BOTS / role).rglob("*"))
        if path.is_file()
    )


# -- every role is present and complete ----------------------------------


def test_every_role_has_a_template():
    found = sorted(path.name for path in BOTS.glob("*") if path.is_dir())
    assert found == sorted(ROLES)


@pytest.mark.parametrize("role", ROLES)
def test_a_template_has_all_its_files(role):
    missing = [name for name in REQUIRED_FILES if not (BOTS / role / name).exists()]
    assert missing == [], f"{role} is missing {missing}"
    assert (BOTS / role / "getting-started" / "SKILL.md").exists()
    assert list((BOTS / role / "skills").glob("*/SKILL.md")), f"{role} has no skills"


@pytest.mark.parametrize("role", ROLES)
def test_the_description_is_a_few_sentences_not_an_essay(role):
    """Somebody is choosing a bot from this. It has to be readable at a glance."""
    description = yaml.safe_load((BOTS / role / "bot.yaml").read_text(encoding="utf-8"))[
        "description"
    ]
    words = len(description.split())
    assert 15 <= words <= 90, f"{role}: {words} words"
    assert description.count(".") <= 4


@pytest.mark.parametrize("role", ROLES)
def test_the_avatar_has_a_colour_and_a_shape(role):
    avatar = yaml.safe_load((BOTS / role / "bot.yaml").read_text(encoding="utf-8"))["avatar"]
    assert avatar["color"] and avatar["shape"]


# -- the files parse ------------------------------------------------------


@pytest.mark.parametrize("role", ROLES)
def test_bot_yaml_and_routines_yaml_parse(role):
    meta = yaml.safe_load((BOTS / role / "bot.yaml").read_text(encoding="utf-8"))
    assert isinstance(meta, dict)
    for key in ("name", "title", "description", "avatar"):
        assert meta.get(key), f"{role}/bot.yaml is missing {key}"

    routines = yaml.safe_load((BOTS / role / "routines.yaml").read_text(encoding="utf-8"))
    assert isinstance(routines.get("routines"), list) and routines["routines"]


@pytest.mark.parametrize("role", ROLES)
def test_every_skill_has_frontmatter_with_a_name_and_a_description(role):
    read_frontmatter = builder().read_frontmatter
    for path in sorted((BOTS / role).rglob("SKILL.md")):
        front, body = read_frontmatter(path)
        assert front["name"] and front["description"], path
        assert body.strip(), path
        # The slug on disk and the name inside have to agree, or an import
        # points at a skill nobody can find.
        assert front["name"] == path.parent.name, path


@pytest.mark.parametrize("role", ROLES)
def test_every_routine_schedule_is_valid_cron(role):
    check_cron = builder().check_cron
    routines = yaml.safe_load((BOTS / role / "routines.yaml").read_text(encoding="utf-8"))
    for entry in routines["routines"]:
        check_cron(entry["schedule"], where=f"{role}:{entry['name']}")
        assert entry["prompt"].strip()
        assert entry.get("human"), f"{role}:{entry['name']} needs a human sentence"


def test_a_broken_schedule_is_refused():
    """Proving the check can fail is the only way to know it can pass."""
    module = builder()
    for bad in ("30 7 * *", "70 7 * * *", "30 99 * * *", "* * * * * *", "every morning"):
        with pytest.raises(module.TemplateError):
            module.check_cron(bad, where="test")
    module.check_cron("*/30 10-17 * * 1-5", where="test")  # and a real one passes


# -- share.json is generated, and matches ---------------------------------


def test_every_share_payload_is_up_to_date():
    """share.json is generated. Two copies of the same text drift."""
    module = builder()
    stale = []
    for role in ROLES:
        stale += module.build(role, write=False)
    assert stale == [], f"out of date, run scripts/build_bot_templates.py: {stale}"


@pytest.mark.parametrize("role", ROLES)
def test_the_share_payload_has_the_expected_shape(role):
    data = payload(role)
    assert set(data) == {
        "name",
        "title",
        "description",
        "avatar",
        "memories",
        "skills",
        "routines",
        "plugins",
        "gettingStarted",
    }
    assert isinstance(data["memories"], list) and data["memories"]
    assert isinstance(data["skills"], list) and data["skills"]
    assert isinstance(data["routines"], list) and data["routines"]
    assert isinstance(data["plugins"], list)
    assert set(data["avatar"]) == {"color", "shape"}


@pytest.mark.parametrize("role", ROLES)
def test_every_skill_in_the_payload_exists_on_disk(role):
    for skill in payload(role)["skills"]:
        if skill["name"] == "getting-started":
            assert (BOTS / role / "getting-started" / "SKILL.md").exists()
            continue
        assert (BOTS / role / "skills" / skill["name"] / "SKILL.md").exists(), skill["name"]


@pytest.mark.parametrize("role", ROLES)
def test_getting_started_names_a_skill_that_is_included(role):
    data = payload(role)
    names = [skill["name"] for skill in data["skills"]]
    assert data["gettingStarted"] in names
    assert data["gettingStarted"] == "getting-started"


@pytest.mark.parametrize("role", ROLES)
def test_every_skill_carries_its_body(role):
    for skill in payload(role)["skills"]:
        assert len(skill["body"]) > 200, skill["name"]
        assert not skill["body"].startswith("---"), "the frontmatter is not part of the body"


@pytest.mark.parametrize("role", ROLES)
def test_the_memories_are_facts_not_a_document(role):
    for memory in payload(role)["memories"]:
        assert 20 < len(memory) < 400, memory
        assert not memory.startswith("#")


# -- the shared skills are shared, not copied by hand --------------------


@pytest.mark.parametrize("role", ROLES)
def test_every_role_has_the_shared_skills(role):
    for slug in ("agent-routing", "team-protocol"):
        own = BOTS / role / "skills" / slug / "SKILL.md"
        shared = TEMPLATES / "shared" / "skills" / slug / "SKILL.md"
        assert own.exists(), f"{role} is missing {slug}"
        assert own.read_text(encoding="utf-8") == shared.read_text(encoding="utf-8")


# -- the promises the README makes ---------------------------------------


@pytest.mark.parametrize("role", ROLES)
def test_no_template_carries_a_credential(role):
    """bot.yaml names services. It never holds a key, a token or an account."""
    meta = yaml.safe_load((BOTS / role / "bot.yaml").read_text(encoding="utf-8"))
    for name in meta.get("plugins") or []:
        assert re.fullmatch(r"[a-z][a-z0-9_-]*", str(name)), name
        assert len(str(name)) < 30, name

    text = all_text(role)
    for shape in (
        r"(?i)\b(pass(?:word|wd)|token|secret|api[_\- ]?key|cookie)\b\s*[:=]\s*\S",
        r"\bsk-[A-Za-z0-9]{8,}",
        r"\bBearer\s+[A-Za-z0-9._\-]{8,}",
    ):
        assert not re.search(shape, text), f"{role}: something shaped like a credential"


@pytest.mark.parametrize("role", ROLES)
def test_no_template_names_a_vendor_model(role):
    """A model belongs in a configurable slot, never written into a prompt."""
    text = all_text(role).lower()
    for name in (
        "gpt-",
        "claude-",
        "gemini",
        "llama",
        "haiku",
        "sonnet",
        "opus",
        "o1-",
        "o3-",
        "mistral",
    ):
        assert name not in text, f"{role}: names a model ({name}); use a provider slot"


def flat(text: str) -> str:
    """One long lower-case line, so a phrase split over two lines still matches."""
    return " ".join(text.lower().split())


@pytest.mark.parametrize("role", ROLES)
def test_every_template_says_nothing_is_sent_until_the_owner_allows_it(role):
    """Carried by the shared team-protocol skill, so no role can lose it."""
    text = flat(all_text(role))
    assert "nothing is sent, submitted or posted" in text
    assert "only the owner signs in" in text
    assert "never ask for a password" in text


@pytest.mark.parametrize("role", [r for r in ROLES if r != "lead"])
def test_a_teammate_reports_only_to_the_lead(role):
    text = flat(all_text(role))
    assert "report to the lead, never to the owner" in text
    assert "which bot is my lead" in text, "its first question must be who its Lead is"


def test_only_the_lead_talks_to_the_owner():
    assert "only member of the team who talks to the owner" in flat(all_text("lead"))


@pytest.mark.parametrize("role", ROLES)
def test_getting_started_asks_one_question_at_a_time(role):
    raw = (BOTS / role / "getting-started" / "SKILL.md").read_text(encoding="utf-8")
    text = flat(raw)
    assert "one question at a time" in text
    assert "never ask for a password" in text
    # It has to end by doing something with the answers, not just collecting them.
    assert "then do this" in text
    for step in ("write it down", "routines"):
        assert step in text, step


def test_the_search_template_merges_the_two_live_search_bots():
    text = flat(all_text("search"))
    assert "broad" in text and "channel" in text
    assert "one set of rules for both" in text


# -- hygiene, same rules as the rest of the repository -------------------


def test_the_templates_are_english_only():
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import sanitize_scan
    finally:
        sys.path.pop(0)
    assert sanitize_scan.scan_english_only(TEMPLATES) == []


def test_the_hygiene_scan_covers_the_templates():
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import sanitize_scan
    finally:
        sys.path.pop(0)
    scanned = {str(path) for path in sanitize_scan.files(REPO)}
    assert any("templates/bots/lead" in name for name in scanned)
    assert sanitize_scan.scan(REPO) == []


@pytest.mark.parametrize("role", ROLES)
def test_no_template_contains_a_personal_detail(role):
    text = all_text(role)
    assert not re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text), "an address"
    # No identifier of the kind a live installation hands out.
    assert not re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", text)
    assert not re.search(r"\b[0-9a-f]{12,}\b", text), "something that looks like an id"
    for word in ("yuan", "yunchen", "ethan", "columbia"):
        assert word not in text.lower(), word


def test_the_readme_lists_every_role():
    text = (TEMPLATES / "README.md").read_text(encoding="utf-8")
    for role in ROLES:
        assert f"bots/{role}" in text, role
    assert "share.json" in text
    assert "AGENTS.md" in text


def test_agents_md_points_at_the_templates():
    """The coding-agent path and the bot-product path use the same team."""
    text = (REPO / "AGENTS.md").read_text(encoding="utf-8")
    assert "templates/bots" in text
    assert "templates/README.md" in text


# -- the command line reads them -----------------------------------------


def test_the_command_line_lists_every_role(capsys):
    from jobpilot.cli import main

    assert main(["templates", "list"]) == 0
    out = capsys.readouterr().out
    for role in ROLES:
        assert role in out, role
    # The lead comes first, because it is the one the owner talks to.
    assert out.index("lead") < out.index("apply")
    assert "talks to you" in out


def test_the_command_line_shows_one_role(capsys):
    from jobpilot.cli import main

    assert main(["templates", "show", "search"]) == 0
    out = capsys.readouterr().out
    assert "Job Search Bot" in out
    assert "Reports to the lead, never to you directly." in out
    assert "What it does by itself:" in out
    assert "Every morning at" in out


def test_the_command_line_exports_the_payload(capsys):
    from jobpilot.cli import main

    assert main(["templates", "export", "yc"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data == payload("yc")


def test_an_unknown_role_is_explained(capsys):
    from jobpilot.cli import main

    assert main(["templates", "show", "nonesuch"]) == 1
    assert "do not have a template" in capsys.readouterr().err


def test_show_without_a_role_says_so(capsys):
    from jobpilot.cli import main

    assert main(["templates", "show"]) == 1
    assert "which role" in capsys.readouterr().err


def test_reading_a_template_needs_no_settings(tmp_path, monkeypatch, capsys):
    """Somebody looking at the templates has not set anything up yet."""
    monkeypatch.delenv("JOBPILOT_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    from jobpilot.cli import main

    assert main(["templates", "list"]) == 0
    assert main(["templates", "show", "lead"]) == 0
    assert "Job Application Lead" in capsys.readouterr().out
