from __future__ import annotations

import pytest

from jobpilot.errors import ProviderUnavailable
from jobpilot.providers import FakeProvider, build_registry
from jobpilot.providers.base import Health, ModelProvider, ModelResult, redact, schema_hint
from jobpilot.providers.cli import claude_provider, codex_provider


def test_the_fake_provider_is_deterministic():
    provider = FakeProvider(replies=['[{"job_id": "a", "verdict": "keep"}]'])
    first = provider.complete("one")
    second = provider.complete("two")
    assert first.text == second.text
    assert first.answered_by == "fake"
    assert provider.prompts == ["one", "two"]


def test_replies_are_used_in_order_and_the_last_one_repeats():
    provider = FakeProvider(replies=["first", "second"])
    assert [provider.complete("x").text for _ in range(3)] == ["first", "second", "second"]


def test_a_result_can_be_read_as_json():
    assert ModelResult(True, 'Sure: {"a": 1}', "fake").data == {"a": 1}
    assert ModelResult(True, "no json", "fake").data is None


def test_anything_that_looks_like_a_key_is_scrubbed():
    assert "sk-abcdefgh12345678" not in redact("here is sk-abcdefgh12345678 for you")
    assert redact("Authorization: Bearer abcdefghijklmnop") .endswith("[REDACTED]")
    assert redact("nothing to hide") == "nothing to hide"


def test_a_schema_is_turned_into_an_instruction():
    hint = schema_hint({"type": "array"})
    assert "JSON only" in hint and '"type": "array"' in hint
    assert schema_hint(None) == ""


def test_the_fake_provider_satisfies_the_interface():
    assert isinstance(FakeProvider(), ModelProvider)
    assert isinstance(claude_provider("claude-haiku-4-5-20251001"), ModelProvider)


def test_roles_are_mapped_from_the_settings(make_config):
    config = make_config(
        models={
            "screen": "claude-haiku",
            "review": "claude-opus",
            "browser": "claude-haiku",
        }
    )
    registry = build_registry(config)
    assert registry.candidates("screen") == ["claude-haiku"]
    assert registry.candidates("review") == ["claude-opus"]


def test_a_provider_that_is_switched_off_is_not_offered(make_config):
    config = make_config(
        models={
            "providers": {"claude": {"enabled": False}, "fake": {"enabled": True}},
            "screen": "fake",
            "review": "fake",
            "browser": "fake",
        }
    )
    registry = build_registry(config)
    assert registry.candidates("screen") == ["fake"]
    assert registry.for_role("screen").name == "fake"


def test_an_unhealthy_provider_falls_back_to_the_next_one():
    from jobpilot.providers import Registry

    registry = Registry(
        providers={"sulky": FakeProvider(name="sulky", healthy=False), "fake": FakeProvider()},
        roles={"screen": "sulky", "review": "fake", "browser": "fake"},
        fallback=["fake"],
    )
    assert registry.for_role("screen").name == "fake"
    assert registry.candidates("screen") == ["sulky", "fake"]


def test_when_nothing_is_healthy_the_message_explains_itself(make_config):
    config = make_config(
        models={
            "providers": {"claude": {"enabled": False}, "fake": {"enabled": True}},
            "screen": "fake",
            "review": "fake",
            "browser": "fake",
        }
    )
    registry = build_registry(config, extra={"fake": FakeProvider(healthy=False)})
    with pytest.raises(ProviderUnavailable) as caught:
        registry.for_role("screen")
    assert "reading job descriptions" in str(caught.value)


def test_a_role_with_nothing_configured_says_what_to_do():
    from jobpilot.providers import Registry

    registry = Registry(providers={}, roles={"screen": "ghost"}, fallback=[])
    with pytest.raises(ProviderUnavailable) as caught:
        registry.for_role("screen")
    assert "jobpilot doctor" in str(caught.value)


def test_health_is_only_checked_once_per_model(make_config):
    config = make_config(
        models={
            "providers": {"claude": {"enabled": False}, "fake": {"enabled": True}},
            "screen": "fake",
            "review": "fake",
            "browser": "fake",
        }
    )
    counted = {"n": 0}

    class Counting(FakeProvider):
        def health(self):
            counted["n"] += 1
            return Health(True, "fine")

    registry = build_registry(config, extra={"fake": Counting()})
    registry.for_role("screen")
    registry.for_role("screen")
    assert counted["n"] == 1


def test_the_report_covers_every_role(make_config):
    registry = build_registry(make_config())
    roles = {role for role, *_ in registry.report()}
    assert roles == {"screen", "review", "browser"}


def test_the_claude_provider_passes_the_prompt_on_standard_input():
    provider = claude_provider("claude-haiku-4-5-20251001")
    assert provider.argv == ["-p", "--model", "claude-haiku-4-5-20251001"]
    assert "browser" in provider.capabilities


def test_the_codex_provider_is_a_second_engine():
    assert codex_provider().command == "codex"


def test_a_missing_tool_is_reported_in_words():
    provider = claude_provider("x", command="definitely-not-installed-anywhere")
    health = provider.health()
    assert health.ok is False
    assert "could not find" in health.detail
