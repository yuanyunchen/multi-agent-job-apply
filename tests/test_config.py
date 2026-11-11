from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from jobpilot import config as config_module
from jobpilot.config import Config, load, load_defaults, validate, write
from jobpilot.errors import ConfigError


def test_defaults_are_valid_and_simple_by_default():
    config = load_defaults()
    assert config.ui_mode == "simple"
    assert config.get("apply.driver") == "dry_run"


def test_nothing_is_permitted_by_default():
    config = load_defaults()
    for action in ("submit_applications", "send_outreach_messages", "post_public_comments"):
        assert config.permitted(action) is False
    assert config.permitted("something_invented") is False


def test_every_plugin_starts_switched_off():
    config = load_defaults()
    for name in ("linkedin", "handshake", "yc"):
        assert config.plugin_enabled(name) is False


def test_plain_is_accepted_as_a_friendly_alias_for_simple():
    assert load_defaults({"ui": {"mode": "plain"}}).ui_mode == "simple"


def test_data_dir_comes_from_the_environment_first(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBPILOT_DATA_DIR", str(tmp_path / "elsewhere"))
    config = load_defaults({"paths": {"data_dir": "~/ignored"}})
    assert config.paths.data_dir == (tmp_path / "elsewhere").resolve()


def test_paths_all_hang_off_one_directory(tmp_path):
    config = load_defaults({"paths": {"data_dir": str(tmp_path / "d")}})
    paths = config.paths
    for path in (paths.tracker, paths.events, paths.backups, paths.state, paths.logs, paths.lock):
        assert str(path).startswith(str(tmp_path / "d"))


def test_user_and_home_are_expanded(monkeypatch, tmp_path):
    monkeypatch.delenv("JOBPILOT_DATA_DIR")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert load_defaults({"paths": {"data_dir": "~/.jobpilot"}}).paths.data_dir == (
        tmp_path / ".jobpilot"
    ).resolve()


def test_no_module_hardcodes_someone_elses_machine():
    """A path belonging to one machine in the source is a bug, not a setting."""
    package = Path(config_module.__file__).parent
    offenders = []
    for path in package.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for needle in ("/home/", "/workspace/", "/Users/"):
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
    assert offenders == []


@pytest.mark.parametrize(
    "broken, expected",
    [
        ({"ui": {"mode": "loud"}}, "'ui.mode'"),
        ({"search": {"recency_days": 0}}, "'search.recency_days'"),
        ({"apply": {"max_lanes": "two"}}, "'apply.max_lanes'"),
        ({"identity": {"apply_email": "not-an-email"}}, "apply_email"),
        ({"models": {"screen": "nonexistent-model"}}, "no enabled provider offers"),
        ({"verify": {"mail_reader": "json_export"}}, "mail_export_dir"),
        ({"search": {"categories": {"core": []}}}, "nothing would ever be applied to first"),
        (
            {"search": {"sources": {"greenhouse": {"enabled": True, "boards": []}}}},
            "lists no boards",
        ),
        (
            {
                "models": {
                    "providers": {
                        "openai_compatible": {"enabled": True, "base_url": "x", "model": "y"}
                    }
                }
            },
            "NAME of an",
        ),
    ],
)
def test_bad_settings_are_explained_in_words(broken, expected):
    data = config_module._merge(config_module.DEFAULTS, broken)
    data["search"]["categories"].setdefault("core", ["Engineer"])
    if not data["search"]["categories"]["core"] and "nothing would ever" not in expected:
        data["search"]["categories"]["core"] = ["Engineer"]
    with pytest.raises(ConfigError) as caught:
        validate(data)
    assert expected in str(caught.value)


def test_several_problems_are_reported_together():
    data = config_module._merge(
        config_module.DEFAULTS,
        {"ui": {"mode": "loud"}, "search": {"recency_days": -1, "categories": {"core": ["x"]}}},
    )
    with pytest.raises(ConfigError) as caught:
        validate(data)
    assert len(caught.value.problems) >= 2


def test_a_missing_file_tells_the_user_what_to_do(tmp_path):
    with pytest.raises(ConfigError) as caught:
        load(tmp_path / "nope.yaml")
    assert "jobpilot setup" in str(caught.value)


def test_broken_yaml_is_not_a_stack_trace(tmp_path):
    path = tmp_path / "preferences.yaml"
    path.write_text("identity: [unclosed\n", encoding="utf-8")
    with pytest.raises(ConfigError) as caught:
        load(path)
    assert "not valid YAML" in str(caught.value)


def test_the_example_file_in_the_repository_loads(tmp_path, monkeypatch):
    example = config_module.repo_root() / config_module.EXAMPLE_CONFIG_PATH
    raw = yaml.safe_load(example.read_text(encoding="utf-8"))
    # The example ships with placeholders; a user replaces them.
    raw["identity"]["apply_email"] = "sam@example.test"
    merged = config_module._merge(config_module.DEFAULTS, raw)
    assert validate(merged).get("schema_version") == config_module.SCHEMA_VERSION


def test_round_trip_through_a_file(tmp_path):
    config = load_defaults({"paths": {"data_dir": str(tmp_path / "d")}})
    destination = write(config, tmp_path / "out.yaml")
    assert load(destination).get("ui.mode") == "simple"


def test_repo_relative_paths_resolve_against_the_checkout():
    config = load_defaults({"documents": {"answers": "config/answers.example.yaml"}})
    assert Config(config.data).repo_path("documents.answers").exists()
