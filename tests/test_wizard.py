from __future__ import annotations

import yaml

from jobpilot import catalog
from jobpilot.config import DEFAULTS, _merge, load
from jobpilot.ui import PRODUCT_NAMES_OK, lint_plain
from jobpilot.wizard import (
    Question,
    ScriptedAsker,
    interview,
    parse_answer,
    questions,
    read_answers_file,
    run,
    summary_prose,
)

ANSWERS = {
    "identity.full_name": "Sam Example",
    "identity.apply_email": "sam@example.test",
    "identity.phone": "+1 555 0100 222",
    "identity.current_location": "Austin, TX",
    "search.categories.core": ["Machine Learning Engineer", "AI Engineer"],
    "search.categories.non_core": ["Software Engineer"],
    "search.categories.excluded": ["Sales"],
    "search.locations.preferred": ["Austin", "Remote"],
    "search.locations.remote_ok": True,
    "work_authorization.needs_sponsorship_now_or_later": False,
    "search.max_required_years_experience": 3,
    "search.company_rules.hard_exclude": ["Umbrella Logistics"],
    "search.company_rules.hold_pending_user": ["Stark Grid"],
    "search.recency_days": 30,
    "search.sources.greenhouse.boards": ["acme-robotics", "globex-systems:lever"],
    "identity.digest_email": "",
    "notifications.digest_time": "7:30am",
    "ui.mode": "simple",
}


def scripted(**overrides):
    answers = {**ANSWERS, **overrides}
    return ScriptedAsker(answers=answers, quiet=True)


def test_scripted_answers_become_settings(tmp_path):
    path = tmp_path / "preferences.yaml"
    result = run(asker=scripted(), destination=path)
    assert result.confirmed is True
    assert result.saved_to == path

    written = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert written["identity"]["full_name"] == "Sam Example"
    assert written["identity"]["apply_email"] == "sam@example.test"
    assert written["identity"]["digest_email"] == "sam@example.test"  # blank means the same
    assert written["search"]["categories"]["core"] == ["Machine Learning Engineer", "AI Engineer"]
    assert written["search"]["max_required_years_experience"] == 3
    assert written["search"]["recency_days"] == 30
    assert written["search"]["company_rules"]["hard_exclude"] == ["Umbrella Logistics"]
    assert written["notifications"]["digest_time"] == "07:30"
    assert written["work_authorization"]["needs_sponsorship_now_or_later"] is False


def test_the_written_file_is_valid_settings(tmp_path):
    path = tmp_path / "preferences.yaml"
    run(asker=scripted(), destination=path)
    config = load(path)  # raises if anything is wrong
    assert config.ui_mode == "simple"


def test_one_list_of_company_pages_is_spread_over_the_right_services(tmp_path):
    path = tmp_path / "preferences.yaml"
    run(
        asker=scripted(
            **{"search.sources.greenhouse.boards": ["acme-robotics", "globex:lever", "northwind:ashby"]}
        ),
        destination=path,
    )
    sources = yaml.safe_load(path.read_text(encoding="utf-8"))["search"]["sources"]
    assert sources["greenhouse"] == {"enabled": True, "boards": ["acme-robotics"]}
    assert sources["lever"] == {"enabled": True, "boards": ["globex"]}
    assert sources["ashby"] == {"enabled": True, "boards": ["northwind"]}


def test_naming_no_company_pages_switches_those_sources_off(tmp_path):
    path = tmp_path / "preferences.yaml"
    run(asker=scripted(**{"search.sources.greenhouse.boards": "none"}), destination=path)
    sources = yaml.safe_load(path.read_text(encoding="utf-8"))["search"]["sources"]
    assert all(block["enabled"] is False for block in sources.values())


def test_plugins_on(tmp_path):
    path = tmp_path / "preferences.yaml"
    run(
        asker=scripted(
            **{"enable.linkedin": True, "enable.yc": True, "enable.handshake": False}
        ),
        destination=path,
    )
    written = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert written["plugins"]["linkedin"]["enabled"] is True
    assert written["plugins"]["yc"]["enabled"] is True
    assert written["plugins"]["handshake"]["enabled"] is False


def test_plugins_off_is_the_default(tmp_path):
    path = tmp_path / "preferences.yaml"
    run(asker=scripted(), destination=path)
    written = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert [name for name, block in written["plugins"].items() if block["enabled"]] == []


def test_switching_a_model_on_remaps_who_does_what(tmp_path):
    path = tmp_path / "preferences.yaml"
    run(
        asker=scripted(**{"enable.claude": False, "enable.fake": True}),
        destination=path,
    )
    written = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert written["models"]["providers"]["claude"]["enabled"] is False
    assert written["models"]["screen"] == "fake"
    assert written["models"]["review"] == "fake"
    assert written["models"]["browser"] == "fake"
    load(path)  # the mapping has to stay valid


def test_nothing_is_written_before_the_user_confirms(tmp_path):
    path = tmp_path / "preferences.yaml"
    asker = ScriptedAsker(answers=ANSWERS, say_confirm=False, quiet=True)
    result = run(asker=asker, destination=path)
    assert result.confirmed is False
    assert result.saved_to is None
    assert not path.exists()
    assert "Nothing saved" in "\n".join(asker.transcript)


def test_an_existing_file_is_kept_before_it_is_replaced(tmp_path):
    path = tmp_path / "preferences.yaml"
    path.write_text("schema_version: 2\n# my old settings\n", encoding="utf-8")
    result = run(asker=scripted(), destination=path)
    assert result.backup is not None and result.backup.exists()
    assert "my old settings" in result.backup.read_text(encoding="utf-8")
    assert "my old settings" not in path.read_text(encoding="utf-8")


def test_the_summary_is_prose_not_settings(tmp_path):
    data = _merge(DEFAULTS, {})
    interview(data, scripted())
    text = summary_prose(data)
    assert "Jobs I will go after first: Machine Learning Engineer, AI Engineer." in text
    assert "07:30 on weekdays" in text
    for forbidden in ("search.categories", "{", "}", "enabled:", "yaml"):
        assert forbidden not in text


def test_the_summary_stays_in_plain_words():
    data = _merge(DEFAULTS, {})
    interview(data, scripted())
    for line in summary_prose(data).splitlines():
        # The models the user picked are named, the way LinkedIn is named.
        assert lint_plain(line, allow=PRODUCT_NAMES_OK) == [], line


def test_every_question_offers_a_default_and_a_consequence():
    for question in questions(_merge(DEFAULTS, {})):
        assert question.ask.strip()
        assert question.changes.strip()
        assert question.default is not None
        assert lint_plain(question.ask, allow=PRODUCT_NAMES_OK) == [], question.ask
        assert lint_plain(question.changes, allow=PRODUCT_NAMES_OK) == [], question.changes


def test_the_job_questions_show_an_example_either_way():
    asked = {q.key: q for q in questions(_merge(DEFAULTS, {}))}
    assert asked["search.categories.core"].kept
    assert asked["search.categories.excluded"].dropped
    assert asked["search.max_required_years_experience"].kept
    assert asked["search.max_required_years_experience"].dropped
    assert "not eligible for visa sponsorship" in (
        asked["work_authorization.needs_sponsorship_now_or_later"].dropped
    )


def test_every_switchable_thing_is_offered_with_its_login():
    asked = {q.key: q for q in questions(_merge(DEFAULTS, {}))}
    for entry in catalog.catalog():
        question = asked[f"enable.{entry.name}"]
        assert entry.summary.split(".")[0] in question.ask
        if entry.login:
            assert entry.login in question.ask or entry.login in question.changes


def test_defaults_alone_produce_valid_settings(tmp_path):
    path = tmp_path / "preferences.yaml"
    result = run(asker=ScriptedAsker(answers={}, quiet=True), destination=path)
    assert result.confirmed is True
    load(path)
    assert any("email address" in w for w in result.warnings), result.warnings


def test_changing_one_thing_leaves_everything_else_alone():
    data = _merge(DEFAULTS, {})
    interview(data, scripted())
    before = yaml.safe_dump(data)
    asker = ScriptedAsker(answers={"search.recency_days": 7}, quiet=True)
    interview(data, asker, only="how far back to look")
    assert data["search"]["recency_days"] == 7
    assert asker.asked == ["search.recency_days"]
    assert yaml.safe_load(before)["search"]["categories"] == data["search"]["categories"]


def test_answers_can_be_written_in_friendly_words(tmp_path):
    path = tmp_path / "answers.yaml"
    path.write_text(
        "name: Sam Example\n"
        "email: sam@example.test\n"
        "core_roles: [Data Analyst]\n"
        "max_years: 1\n"
        "enable: [linkedin, fake]\n",
        encoding="utf-8",
    )
    answers = read_answers_file(path)
    assert answers["identity.full_name"] == "Sam Example"
    assert answers["search.categories.core"] == ["Data Analyst"]
    assert answers["search.max_required_years_experience"] == 1
    assert answers["enable.linkedin"] is True
    assert answers["enable.yc"] is False


def test_people_can_answer_the_way_people_talk():
    q = Question("k", "?", ["a"], "", kind="list")
    assert parse_answer(q, "one, two; three") == ["one", "two", "three"]
    assert parse_answer(q, "none") == []
    assert parse_answer(q, "") == ["a"]
    assert parse_answer(q, "I don't know") == ["a"]

    yes_no = Question("k", "?", True, "", kind="bool")
    assert parse_answer(yes_no, "yeah") is True
    assert parse_answer(yes_no, "nope.") is False
    assert parse_answer(yes_no, "hmm") is True  # the default

    number = Question("k", "?", 2, "", kind="int")
    assert parse_answer(number, "about 5 years") == 5
    assert parse_answer(number, "lots") == 2

    clock = Question("k", "?", "08:00", "", kind="time")
    assert parse_answer(clock, "7am") == "07:00"
    assert parse_answer(clock, "6:30pm") == "18:30"
    assert parse_answer(clock, "noon") == "08:00"


def test_the_conversation_can_be_replayed(tmp_path):
    asker = scripted()
    run(asker=asker, destination=tmp_path / "preferences.yaml")
    transcript = "\n".join(asker.transcript)
    assert "What name should go on your applications?" in transcript
    assert "> Sam Example" in transcript
    assert "Here is everything, in plain words:" in transcript
    assert transcript.count("(use the default)") >= 1


def test_a_helper_that_needs_more_detail_is_asked_about_it(tmp_path):
    path = tmp_path / "preferences.yaml"
    asker = scripted(
        **{
            "enable.handshake": True,
            "enable.yc": True,
            "plugins.handshake.school_name": "Example University",
            "plugins.yc.weekly_application_cap": 4,
        }
    )
    run(asker=asker, destination=path)
    written = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert written["plugins"]["handshake"]["school_name"] == "Example University"
    assert written["plugins"]["yc"]["weekly_application_cap"] == 4
    assert "Which school's job platform should I use?" in "\n".join(asker.transcript)


def test_follow_up_questions_are_not_asked_about_things_that_are_off(tmp_path):
    asker = scripted()
    run(asker=asker, destination=tmp_path / "preferences.yaml")
    assert "Which school's job platform should I use?" not in "\n".join(asker.transcript)


def test_a_hosted_model_is_asked_for_its_details(tmp_path):
    path = tmp_path / "preferences.yaml"
    asker = scripted(
        **{
            "enable.openai_compatible": True,
            "models.providers.openai_compatible.base_url": "https://models.example.test/v1",
            "models.providers.openai_compatible.model": "some-model",
            "models.providers.openai_compatible.api_key_env": "MY_MODEL_KEY",
        }
    )
    run(asker=asker, destination=path)
    written = yaml.safe_load(path.read_text(encoding="utf-8"))["models"]["providers"]["openai_compatible"]
    assert written["base_url"] == "https://models.example.test/v1"
    assert written["api_key_env"] == "MY_MODEL_KEY"
    # the key itself is never asked for, and never stored
    said = "\n".join(asker.transcript).lower()
    assert "paste the key" not in said and "what is your key" not in said
    load(path)


def test_placeholders_from_the_example_file_never_survive(tmp_path):
    from jobpilot.config import repo_root
    from jobpilot.wizard import strip_placeholders

    example = yaml.safe_load((repo_root() / "config" / "preferences.example.yaml").read_text())
    assert "{{" in yaml.safe_dump(example)  # the example does have placeholders

    path = tmp_path / "preferences.yaml"
    run(asker=ScriptedAsker(answers={}, quiet=True), base=_merge(DEFAULTS, example), destination=path)
    assert "{{" not in path.read_text(encoding="utf-8")
    assert strip_placeholders({"a": "{{X}}", "b": ["{{Y}}", "real"]}) == {"a": "", "b": ["real"]}


def test_the_summary_counts_things_the_way_people_say_them():
    data = _merge(DEFAULTS, {})
    interview(data, scripted(**{"search.max_required_years_experience": 1}))
    assert "more than 1 year." in summary_prose(data)
    interview(data, scripted(**{"search.max_required_years_experience": 4}))
    assert "more than 4 years." in summary_prose(data)


# -- the example file's placeholders are not answers ---------------------


def from_the_example() -> dict:
    """The settings tree the real `setup` starts from: the shipped example."""
    from jobpilot.config import repo_root

    raw = yaml.safe_load((repo_root() / "config" / "preferences.example.yaml").read_text())
    return _merge(DEFAULTS, raw)


def test_no_question_offers_a_placeholder_as_its_default():
    data = from_the_example()
    for question in questions(data):
        assert "{{" not in question.default_words(), question.key
        assert "{{" not in str(question.default), question.key


def test_a_question_with_nothing_to_suggest_says_nothing():
    asked = {q.key: q for q in questions(from_the_example())}
    assert asked["identity.full_name"].default_words() == "nothing"
    assert asked["identity.apply_email"].default_words() == "nothing"
    assert asked["search.locations.preferred"].default_words() == "nothing"
    assert asked["search.locations.preferred"].default == []


def test_the_follow_up_questions_do_not_offer_placeholders_either():
    from jobpilot.wizard import followups

    data = from_the_example()
    data["plugins"]["handshake"]["enabled"] = True
    data["models"]["providers"]["openai_compatible"]["enabled"] = True
    for question in followups(data):
        assert "{{" not in question.default_words(), question.key


def test_the_summary_and_the_saved_file_are_free_of_placeholders(tmp_path):
    path = tmp_path / "preferences.yaml"
    asker = ScriptedAsker(answers={}, quiet=True)
    run(asker=asker, base=from_the_example(), destination=path)
    assert "{{" not in "\n".join(asker.transcript)
    assert "{{" not in path.read_text(encoding="utf-8")


def test_where_reads_sensibly_with_no_city_named():
    data = from_the_example()
    interview(data, ScriptedAsker(answers={"search.locations.preferred": "none"}, quiet=True))
    assert "Where: anywhere in US, and fully remote jobs count too." in summary_prose(data)


def test_where_names_the_cities_when_there_are_some():
    data = from_the_example()
    interview(data, ScriptedAsker(answers={"search.locations.preferred": "Austin, Chicago"}, quiet=True))
    assert "Where: Austin, Chicago, and fully remote jobs count too." in summary_prose(data)


def test_where_says_so_when_remote_is_not_wanted():
    data = from_the_example()
    interview(
        data,
        ScriptedAsker(
            answers={"search.locations.preferred": "Austin", "search.locations.remote_ok": "no"},
            quiet=True,
        ),
    )
    assert "Where: Austin, and not remote jobs." in summary_prose(data)


def test_a_placeholder_board_name_is_not_a_board():
    from jobpilot.wizard import _boards_default

    data = _merge(DEFAULTS, {"search": {"sources": {"lever": {"boards": ["{{BOARD}}", "globex"]}}}})
    assert _boards_default(data) == ["globex:lever"]


# -- the CV, and the answer bank -----------------------------------------


def test_the_conversation_asks_where_the_cv_is():
    from jobpilot.wizard import questions

    keys = [q.key for q in questions(_merge(DEFAULTS, {}))]
    assert "documents.resume" in keys
    question = next(q for q in questions(_merge(DEFAULTS, {})) if q.key == "documents.resume")
    assert "never copied into this project" in question.changes


def test_only_the_path_to_the_cv_is_kept(tmp_path):
    """The file stays where the person put it; nothing is copied anywhere."""
    cv = tmp_path / "my-cv.pdf"
    cv.write_text("not really a pdf", encoding="utf-8")
    asker = ScriptedAsker(answers={"documents.resume": str(cv)}, quiet=True)
    result = run(asker=asker, base=_merge(DEFAULTS, {}), write=False)
    assert result.data["documents"]["resume"] == str(cv)
    assert cv.read_text(encoding="utf-8") == "not really a pdf"


def test_a_cv_that_is_not_where_they_said_is_pointed_out(tmp_path):
    from jobpilot.wizard import warnings_for

    data = _merge(DEFAULTS, {"documents": {"resume": str(tmp_path / "missing.pdf")}})
    assert any("cannot find your CV" in w for w in warnings_for(data))


def test_the_conversation_builds_the_answer_bank():
    from jobpilot.wizard import answer_questions

    keys = [q.key for q in answer_questions(_merge(DEFAULTS, {}))]
    assert keys == [
        "answers.work_authorization",
        "answers.needs_sponsorship",
        "answers.relocate",
        "answers.start_date",
        "answers.salary_expectation",
        "answers.how_did_you_hear",
    ]


def test_the_answer_bank_defaults_follow_what_they_already_said():
    from jobpilot.wizard import answer_questions

    data = _merge(
        DEFAULTS,
        {
            "work_authorization": {"authorized_to_work": False, "needs_sponsorship_now_or_later": True},
            "timing": {"earliest_start_date": "2027-06-01"},
        },
    )
    defaults = {q.key: q.default for q in answer_questions(data)}
    assert defaults["answers.work_authorization"] == "No"
    assert defaults["answers.needs_sponsorship"] == "Yes"
    assert defaults["answers.start_date"] == "2027-06-01"


def test_the_answer_bank_is_written_beside_the_settings(tmp_path):
    settings_file = tmp_path / "preferences.yaml"
    asker = ScriptedAsker(
        answers={
            "identity.apply_email": "sam@example.test",
            "answers.relocate": "No",
            "answers.salary_expectation": "Open to discussion",
        },
        quiet=True,
    )
    result = run(asker=asker, base=_merge(DEFAULTS, {}), destination=settings_file)
    assert result.answers_saved_to == tmp_path / "answers.yaml"

    written = yaml.safe_load(result.answers_saved_to.read_text(encoding="utf-8"))
    by_id = {entry["id"]: entry["answer"] for entry in written["answers"]}
    assert by_id["relocate"] == "No"
    assert by_id["salary_expectation"] == "Open to discussion"
    assert "authorized to work" in next(
        e["match"] for e in written["answers"] if e["id"] == "work_authorization"
    )


def test_the_form_answers_are_not_mixed_into_the_settings(tmp_path):
    """Two different kinds of thing, two files; the settings stay readable."""
    settings_file = tmp_path / "preferences.yaml"
    run(asker=ScriptedAsker(answers={}, quiet=True), base=_merge(DEFAULTS, {}), destination=settings_file)
    saved = yaml.safe_load(settings_file.read_text(encoding="utf-8"))
    assert "answers" not in saved


def test_personal_identifiers_always_stop_however_the_file_is_edited(tmp_path):
    from jobpilot.gates import AnswerBank
    from jobpilot.wizard import write_answer_bank

    path = write_answer_bank({"answers": {"relocate": "Yes"}}, tmp_path / "answers.yaml")
    bank = AnswerBank.from_file(path)
    assert bank.lookup("Are you willing to relocate?") is not None
    for question in (
        "Please enter your social security number.",
        "What is your date of birth?",
        "Passport number?",
    ):
        assert bank.lookup(question) is None, question


def test_an_answer_left_blank_is_simply_not_written(tmp_path):
    from jobpilot.wizard import answer_bank

    written = answer_bank({"answers": {"relocate": "Yes", "salary_expectation": "  "}})
    assert [entry["id"] for entry in written["answers"]] == ["relocate"]


def test_no_answers_at_all_is_said_out_loud():
    from jobpilot.wizard import warnings_for

    data = _merge(DEFAULTS, {})
    assert any("stop and wait for you" in w for w in warnings_for(data))


def test_the_summary_mentions_the_cv_and_the_answers(tmp_path):
    from jobpilot.wizard import summary_prose

    data = _merge(
        DEFAULTS,
        {"documents": {"resume": "~/documents/cv.pdf"}, "answers": {"relocate": "Yes"}},
    )
    text = summary_prose(data)
    assert "The CV I will attach: ~/documents/cv.pdf." in text
    assert "whether you would move" in text


def test_rewriting_the_answer_bank_keeps_the_old_one(tmp_path):
    from jobpilot.wizard import write_answer_bank

    path = write_answer_bank({"answers": {"relocate": "Yes"}}, tmp_path / "answers.yaml")
    write_answer_bank({"answers": {"relocate": "No"}}, path)
    spares = [p for p in tmp_path.iterdir() if "before-" in p.name]
    assert len(spares) == 1
    assert "Yes" in spares[0].read_text(encoding="utf-8")
