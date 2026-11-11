from __future__ import annotations

import json

import pytest

from jobpilot.errors import ConfigError
from jobpilot.gates import OutboundGate
from jobpilot.plugins import Draft, Manifest, describe_all, discover, load_plugins, render_prompt
from jobpilot.plugins.base import BrowserAgentSource, Outreach
from jobpilot.providers.fake import FakeProvider
from jobpilot.search import run_search
from jobpilot.search.base import FixtureFetcher

AGENT_ANSWER = {
    "jobs": [
        {
            "company": "Acme Robotics",
            "title": "Machine Learning Engineer",
            "url": "https://job-boards.greenhouse.io/acme-robotics/jobs/4001",
            "location": "New York, NY",
            "posted_at": "2026-11-09T10:00:00+00:00",
            "description": "A fake posting used only in tests.",
        },
        {"company": "Broken", "title": "", "url": ""},
    ],
    "drafts": [
        {"kind": "connect_note", "recipient": "A Person", "company": "Acme Robotics", "text": "Hello there."}
    ],
}


def test_every_installed_plugin_has_a_complete_manifest():
    names = {manifest.name for manifest in discover()}
    assert names == {"linkedin", "handshake", "yc"}
    for manifest in discover():
        assert manifest.summary and manifest.explain
        assert manifest.writes
        assert manifest.describe()


def test_anything_needing_a_login_starts_switched_off():
    for manifest in discover():
        if manifest.logins:
            assert manifest.enabled_default is False


def test_a_manifest_that_wants_a_login_and_default_on_is_rejected(tmp_path):
    path = tmp_path / "plugin.yaml"
    path.write_text(
        "name: pushy\nkind: outreach\nversion: 1\nsummary: s\nexplain: e\n"
        "writes: [runlog]\nenabled_default: true\n"
        "requires:\n  logins:\n    - {id: x, label: X, how: browser_session}\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError) as caught:
        Manifest.from_file(path)
    assert "switched off" in str(caught.value)


def test_an_incomplete_manifest_is_a_friendly_error(tmp_path):
    path = tmp_path / "plugin.yaml"
    path.write_text("name: thin\nkind: source\n", encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        Manifest.from_file(path)
    assert "incomplete" in str(caught.value)


def test_a_manifest_explains_itself_to_a_person():
    manifest = next(m for m in discover() if m.name == "linkedin")
    text = manifest.describe()
    assert "connection requests" in text
    assert "What it needs from you:" in text
    assert "never" in text.lower()


def test_nothing_is_loaded_while_the_plugins_are_off(config):
    assert load_plugins(config) == []
    assert "off" in describe_all(config)


def test_the_core_runs_with_no_plugins_at_all(config):
    report = run_search(config, FixtureFetcher())
    assert report.new == 0 and report.errors == []


@pytest.mark.parametrize("name", ["linkedin", "handshake", "yc"])
def test_each_plugin_can_be_switched_on_by_itself(make_config, name):
    settings = {"enabled": True}
    if name == "handshake":
        settings["school_name"] = "Example University"
    config = make_config(plugins={name: settings})
    plugins = load_plugins(config)
    assert [p.name for p in plugins] == [name]
    ok, detail = plugins[0].health(config)
    assert ok is True and detail


def test_a_plugin_source_turns_a_model_answer_into_ordinary_jobs(make_config):
    config = make_config(plugins={"linkedin": {"enabled": True}})
    plugin = load_plugins(config)[0]
    provider = FakeProvider(replies=[json.dumps(AGENT_ANSWER)])
    source = plugin.source(config, provider)
    jobs = list(source.fetch())
    assert len(jobs) == 1  # the row with no title or link is dropped
    assert jobs[0].company == "Acme Robotics"
    assert jobs[0].source == "linkedin"
    assert "source:linkedin" in jobs[0].tags


def test_a_plugin_prompt_is_filled_in_from_the_settings(make_config):
    config = make_config(
        plugins={"linkedin": {"enabled": True, "per_cycle_connect_cap": 5, "scope": ["connect"]}}
    )
    plugin = load_plugins(config)[0]
    provider = FakeProvider(replies=["{}"])
    list(plugin.source(config, provider).fetch())
    prompt = provider.prompts[0]
    assert "{{" not in prompt  # every placeholder was filled in
    assert "Machine Learning Engineer" in prompt  # the user's own interests
    assert "at most 5 people" in prompt
    assert "Choose at most 0 posts" in prompt  # comments were not switched on
    assert "Never follow a \"forgot password\"" in prompt


def test_plugin_prompts_contain_no_personal_data():
    for manifest in discover():
        prompt = manifest.prompt_path("agent.md")
        assert prompt is not None
        text = prompt.read_text(encoding="utf-8")
        assert "@" not in text  # no addresses of any kind
        for word in ("resume.pdf", "/home", "/workspace"):
            assert word not in text


def test_a_plugin_source_without_a_browser_model_says_so_and_does_nothing(make_config):
    config = make_config(plugins={"yc": {"enabled": True}})
    source = load_plugins(config)[0].source(config, None)
    assert list(source.fetch()) == []
    assert "no browser model" in source.errors[0]


def test_a_plugin_source_that_gets_nonsense_reports_it(make_config):
    config = make_config(plugins={"handshake": {"enabled": True, "school_name": "Example University"}})
    source = load_plugins(config)[0].source(config, FakeProvider(replies=["not json at all"]))
    assert list(source.fetch()) == []
    assert source.errors


def test_plugin_rows_go_through_the_same_pass(make_config):
    config = make_config(plugins={"yc": {"enabled": True}})
    provider = FakeProvider(replies=[json.dumps(AGENT_ANSWER)])
    report = run_search(config, FixtureFetcher(), provider=provider)
    assert report.per_source == {"yc": 1}
    assert report.new == 1


def test_a_message_is_not_sent_without_permission(make_config):
    config = make_config(plugins={"linkedin": {"enabled": True}})
    plugin = load_plugins(config)[0]
    drafts = plugin.drafts(config, AGENT_ANSWER["drafts"])
    assert len(drafts) == 1
    results = plugin.outreach(config).submit(drafts, OutboundGate(config))
    assert results[0].sent is False and results[0].code == "not_permitted"


def test_even_with_permission_the_core_has_no_way_to_send(make_config):
    config = make_config(
        plugins={"linkedin": {"enabled": True}}, permissions={"send_outreach_messages": True}
    )
    plugin = load_plugins(config)[0]
    results = plugin.outreach(config).submit(
        plugin.drafts(config, AGENT_ANSWER["drafts"]), OutboundGate(config)
    )
    assert results[0].sent is False and results[0].code == "no_sender"


def test_a_blocked_message_is_dropped_and_never_reworded(make_config):
    config = make_config(permissions={"post_public_comments": True})
    sent: list[Draft] = []
    outreach = Outreach(plugin="linkedin", permission="post_public_comments")
    drafts = [Draft("comment", "A Person", "I need visa sponsorship, by the way.")]
    results = outreach.submit(drafts, OutboundGate(config), send=sent.append)
    assert results[0].code == "banned_phrase"
    assert sent == []


def test_a_weekly_cap_is_enforced_by_the_plugin(make_config):
    config = make_config(permissions={"send_outreach_messages": True})
    sent: list[Draft] = []
    outreach = Outreach(plugin="yc", permission="send_outreach_messages", cap=1)
    drafts = [Draft("founder_note", f"Person {n}", "A short, friendly note.") for n in range(3)]
    results = outreach.submit(drafts, OutboundGate(config), send=sent.append)
    assert [r.code for r in results] == ["sent", "cap_reached", "cap_reached"]
    assert len(sent) == 1


def test_an_over_long_note_never_becomes_a_draft(make_config):
    config = make_config(plugins={"linkedin": {"enabled": True, "connect_note_limit": 10}})
    plugin = load_plugins(config)[0]
    assert plugin.drafts(config, [{"kind": "connect_note", "text": "x" * 50}]) == []


def test_school_replies_need_the_users_say_so(make_config):
    base = {"enabled": True, "school_name": "Example University"}
    off = load_plugins(make_config(plugins={"handshake": base}))[0]
    assert off.drafts(make_config(plugins={"handshake": base}), [{"text": "Hello"}]) == []
    on_config = make_config(plugins={"handshake": {**base, "reply_to_recruiters": True}})
    on = load_plugins(on_config)[0]
    assert len(on.drafts(on_config, [{"text": "Hello"}])) == 1


def test_the_weekly_allowance_resets_on_monday(make_config):
    from datetime import date

    from jobpilot.plugins.yc import cap_remaining, week_key

    config = make_config(plugins={"yc": {"enabled": True, "weekly_application_cap": 3}})
    manifest = next(m for m in discover() if m.name == "yc")
    assert cap_remaining(config, manifest, sent_this_week=1) == 2
    assert cap_remaining(config, manifest, sent_this_week=99) == 0
    assert week_key(date(2026, 11, 9)) == week_key(date(2026, 11, 15))
    assert week_key(date(2026, 11, 9)) != week_key(date(2026, 11, 16))


def test_placeholders_without_a_value_become_blank():
    assert render_prompt("Hello {{NAME}}, from {{NOWHERE}}.", {"NAME": "there"}) == "Hello there, from ."


def test_outreach_plugins_declare_what_they_may_write():
    for manifest in discover():
        assert "runlog" in manifest.writes
        assert "tracker" not in manifest.writes  # only rows, through screening


def test_a_browser_source_needs_no_fetcher_at_all():
    source = BrowserAgentSource(plugin="x", prompt="go", provider=FakeProvider(replies=["{}"]))
    assert list(source.fetch(None)) == []


# -- the three helpers, each complete ------------------------------------

HELPERS = ("linkedin", "handshake", "yc")


@pytest.mark.parametrize("name", HELPERS)
def test_every_helper_is_installed_and_described(name):
    from jobpilot.plugins import discover

    manifest = next((m for m in discover() if m.name == name), None)
    assert manifest is not None, f"{name} is not installed"
    assert manifest.summary and manifest.explain
    assert manifest.logins, "a helper that needs no login does not belong in this list"
    assert manifest.routines, "a helper with no routine would never do anything"


@pytest.mark.parametrize("name", HELPERS)
def test_every_helper_starts_switched_off(name):
    """Anything that needs an account is off until the person says otherwise."""
    from jobpilot.plugins import discover

    manifest = next(m for m in discover() if m.name == name)
    assert manifest.enabled_default is False


@pytest.mark.parametrize("name", HELPERS)
def test_every_helper_can_look_for_jobs(make_config, name):
    from jobpilot.plugins import load_plugins
    from jobpilot.providers import FakeProvider

    config = make_config(plugins={name: {"enabled": True, "school_name": "Example University"}})
    plugin = next(p for p in load_plugins(config) if p.name == name)
    source = plugin.source(config, FakeProvider(replies=['{"jobs": []}']))
    assert source is not None, f"{name} contributes no way of finding jobs"
    assert list(source.fetch(None)) == []  # an empty answer is an empty result, not an error


@pytest.mark.parametrize("name", HELPERS)
def test_every_helper_drafts_through_the_gate_and_cannot_send(make_config, name):
    from jobpilot.gates import OutboundGate
    from jobpilot.plugins import load_plugins

    config = make_config(
        plugins={
            name: {
                "enabled": True,
                "school_name": "Example University",
                "reply_to_recruiters": True,
            }
        },
        permissions={"send_outreach_messages": True},
    )
    plugin = next(p for p in load_plugins(config) if p.name == name)
    lead = {"kind": "connect_note", "recipient": "someone", "text": "A short, polite note.", "company": "Acme Robotics"}
    drafts = plugin.drafts(config, [lead])
    assert drafts, f"{name} drafted nothing"

    outreach = plugin.outreach(config)
    assert outreach is not None
    # No sender is passed, because the core has none to pass.
    results = outreach.submit(drafts, OutboundGate(config))
    assert [r.sent for r in results] == [False]
    assert [r.code for r in results] == ["no_sender"]


@pytest.mark.parametrize("name", HELPERS)
def test_every_helper_reports_its_own_readiness(make_config, name):
    from jobpilot.plugins import load_plugins

    config = make_config(plugins={name: {"enabled": True, "school_name": "Example University"}})
    plugin = next(p for p in load_plugins(config) if p.name == name)
    ok, detail = plugin.health(config)
    assert isinstance(ok, bool)
    assert detail, "a readiness answer with no sentence is no use to anybody"


@pytest.mark.parametrize("name", HELPERS)
def test_every_helpers_prompt_tells_the_browser_what_it_may_not_do(name):
    from jobpilot.plugins import discover

    manifest = next(m for m in discover() if m.name == name)
    prompt = manifest.prompt_path("agent.md")
    assert prompt is not None, f"{name} ships no browser prompt"
    text = prompt.read_text(encoding="utf-8").lower()
    assert "never" in text
    assert "password" in text  # every prompt states the password rule


@pytest.mark.parametrize("name", HELPERS)
def test_a_helpers_outbound_actions_are_declared_and_known(make_config, name):
    from jobpilot.config import PERMISSIONS
    from jobpilot.plugins import discover

    manifest = next(m for m in discover() if m.name == name)
    for action in manifest.outbound_actions:
        assert action in PERMISSIONS, f"{name} declares an unknown permission: {action}"
