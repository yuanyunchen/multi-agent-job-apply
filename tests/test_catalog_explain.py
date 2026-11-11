from __future__ import annotations

from jobpilot import catalog
from jobpilot.config import DEFAULTS, _merge, load_defaults
from jobpilot.explain import automatic, explain_team, needs_you, never, optional_extras, the_team
from jobpilot.plugins import discover
from jobpilot.ui import PRODUCT_NAMES_OK, lint_plain


def test_helpers_and_models_are_offered_as_one_list():
    names = [entry.name for entry in catalog.catalog()]
    assert names[: len(discover())] == sorted(m.name for m in discover())
    assert {"claude", "codex", "openai_compatible", "fake"} <= set(names)


def test_helper_entries_are_generated_from_the_manifests():
    for manifest in discover():
        entry = catalog.find(manifest.name)
        assert entry is not None
        assert entry.summary == manifest.summary
        assert entry.default_on == manifest.enabled_default
        if manifest.logins:
            assert entry.login == manifest.logins[0].label
            assert entry.never == tuple(manifest.logins[0].never)


def test_every_entry_can_describe_itself_in_plain_words():
    for entry in catalog.catalog():
        text = entry.describe()
        assert entry.summary.split(".")[0] in text
        assert entry.needs_sentence in text
        assert ("no account and no sign-in" in text) == (not entry.login)
        assert lint_plain(text, allow=PRODUCT_NAMES_OK) == [], entry.name


def test_what_each_thing_needs_reads_as_a_sentence():
    """A label alone comes out wrong mid-sentence; a sentence does not."""
    for entry in catalog.catalog():
        sentence = entry.needs_sentence
        assert sentence.startswith("It needs") and sentence.endswith("."), entry.name
        # nothing mid-sentence should start with a stray capital
        for word in sentence.split()[2:]:
            assert not (word[:1].isupper() and word.lower() in ("your", "the", "a")), sentence
    key_based = catalog.find("openai_compatible")
    assert "signed in" not in key_based.needs_sentence  # it is a key, not a sign-in
    assert "key" in key_based.your_part


def test_what_the_user_has_to_do_is_phrased_as_their_action():
    for entry in catalog.catalog():
        if not entry.login:
            continue
        assert entry.your_part[:1].islower(), entry.name
        assert entry.your_part.split()[0].endswith("ing"), entry.your_part


def test_only_the_main_model_is_on_to_begin_with():
    config = load_defaults()
    on = [entry.name for entry in catalog.enabled_entries(config)]
    assert on == ["claude"]


def test_anything_needing_a_login_starts_off_except_the_model_you_already_have():
    for entry in catalog.catalog():
        if entry.login and entry.kind == "helper":
            assert entry.default_on is False


def test_the_models_a_choice_offers_decide_who_does_what():
    data = _merge(DEFAULTS, {})
    assert catalog.role_mapping(data) == {
        "screen": "claude-haiku",
        "review": "claude-opus",
        "browser": "claude-haiku",
        "fallback": ["claude-sonnet"],
    }


def test_turning_everything_off_but_one_remaps_every_job():
    data = _merge(DEFAULTS, {})
    catalog.Selection(chosen=["codex"]).apply_to(data)
    assert data["models"]["screen"] == "codex"
    assert data["models"]["review"] == "codex"
    assert data["models"]["browser"] == "codex"
    assert data["models"]["fallback"] == []


def test_a_hosted_model_is_offered_under_its_own_name():
    data = _merge(
        DEFAULTS,
        {
            "models": {
                "providers": {
                    "claude": {"enabled": False},
                    "openai_compatible": {"enabled": True, "model": "some-model"},
                }
            }
        },
    )
    assert catalog.available_models(data) == ["some-model"]
    assert catalog.role_mapping(data)["screen"] == "some-model"


def test_the_readme_table_covers_everything_switchable():
    rows = catalog.table_rows()
    assert len(rows) == len(catalog.catalog())
    for name, adds, login, default in rows:
        assert adds and login and default in ("on", "off")


def test_status_says_what_is_on_and_off():
    config = load_defaults()
    lines = catalog.status_lines(config)
    assert any(line.startswith("- claude (on)") for line in lines)
    assert any(line.startswith("- linkedin (off)") for line in lines)


def test_which_model_does_what_is_explained_in_words():
    lines = catalog.model_jobs(load_defaults())
    assert any("reading job descriptions" in line and "Haiku" in line for line in lines)
    assert any("working inside a web page" in line for line in lines)


# -- the generated explanation ------------------------------------------


def test_the_explanation_is_built_from_what_is_installed(make_config):
    config = make_config(plugins={"linkedin": {"enabled": True}})
    text = explain_team(config)
    assert "a coordinator" in text
    assert "linkedin" in text  # because it is switched on
    assert "handshake" in text  # as something you could switch on
    assert "Every weekday at 8am you get one email" in text
    assert "apply to the same job twice" in text


def test_the_explanation_changes_when_a_helper_is_switched_on(make_config):
    off = explain_team(make_config())
    on = explain_team(make_config(plugins={"yc": {"enabled": True}}))
    assert off != on
    assert "startup" in on.lower()


def test_the_explanation_names_the_logins_you_will_need(make_config):
    config = make_config(plugins={"handshake": {"enabled": True, "school_name": "Example University"}})
    assert any("job platform" in line for line in needs_you(config))


def test_the_timetable_in_the_explanation_follows_the_users_time(make_config):
    config = make_config(notifications={"digest_time": "18:15"})
    assert any("6:15pm" in line for line in automatic(config))


def test_the_promises_are_listed(make_config):
    text = "\n".join(never(make_config()))
    for promise in ("twice", "make up an answer", "reset a password", "without asking"):
        assert promise in text


def test_the_whole_explanation_stays_in_plain_words(make_config):
    config = make_config(plugins={"linkedin": {"enabled": True}})
    for line in explain_team(config).splitlines():
        assert lint_plain(line, allow=PRODUCT_NAMES_OK) == [], line


def test_what_you_could_switch_on_lists_everything_that_is_off(make_config):
    config = make_config()
    names = {entry.name for entry in catalog.catalog() if not catalog.is_enabled(config, entry)}
    text = "\n".join(optional_extras(config))
    for name in names:
        assert name in text


def test_the_core_team_is_there_even_with_nothing_switched_on(make_config):
    config = make_config(models={"providers": {"claude": {"enabled": False}, "fake": {"enabled": True}},
                                 "screen": "fake", "review": "fake", "browser": "fake"})
    assert len(the_team(config)) == 4
