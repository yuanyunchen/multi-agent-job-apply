from __future__ import annotations

import json

import pytest
import yaml

from jobpilot.cli import main
from jobpilot.tracker import Tracker
from jobpilot.ui import lint_plain

from .synthetic import iso_days_ago


@pytest.fixture
def settings_file(tmp_path, make_config):
    """A settings file pointing at a throwaway data directory, using the fake model."""
    config = make_config(
        paths={"data_dir": str(tmp_path / "data")},
        models={
            "screen": "fake",
            "review": "fake",
            "browser": "fake",
            "providers": {"claude": {"enabled": False}, "fake": {"enabled": True}},
        },
        search={"sources": {"greenhouse": {"enabled": True, "boards": ["acme-robotics"]}}},
    )
    path = tmp_path / "preferences.yaml"
    path.write_text(yaml.safe_dump(config.data), encoding="utf-8")
    return path


def run(argv, settings_file=None):
    if settings_file is not None:
        argv = ["--config", str(settings_file), *argv]
    return main(argv)


def test_start_explains_the_system_in_plain_language(capsys):
    assert run(["start", "--explain-only"]) == 0
    out = capsys.readouterr().out
    assert "never do" in out
    assert "apply to the same job twice" in out
    for name in ("linkedin", "handshake", "yc"):
        assert name in out
    # the explanation is generated, so the timetable and the promises are in it
    assert "you get one email" in out
    assert "reset a password" in out
    assert "jobpilot setup" in out


def test_start_runs_the_whole_first_conversation(tmp_path, capsys):
    destination = tmp_path / "preferences.yaml"
    assert run(["start", "--out", str(destination), "--non-interactive"]) == 0
    out = capsys.readouterr().out
    assert destination.exists()
    assert "Here is everything, in plain words:" in out
    assert "Now the sign-ins" in out  # it walks the logins too
    assert "I never see a password" in out


def test_setup_asks_questions_and_saves(tmp_path, capsys):
    destination = tmp_path / "preferences.yaml"
    assert run(["setup", "--out", str(destination), "--non-interactive"]) == 0
    assert destination.exists()
    assert "schema_version" in destination.read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert "What name should go on your applications?" in out
    assert "Saved. Your answers are written down" in out
    assert run(["setup", "--out", str(destination), "--non-interactive"]) == 1  # no overwrite
    assert "--force" in capsys.readouterr().out


def test_setup_can_be_answered_from_a_file(tmp_path, capsys):
    answers = tmp_path / "answers.yaml"
    answers.write_text(
        "name: Sam Example\nemail: sam@example.test\ncore_roles: [Data Analyst]\n"
        "enable: [fake]\ndigest_time: 9am\n",
        encoding="utf-8",
    )
    destination = tmp_path / "preferences.yaml"
    assert run(["setup", "--out", str(destination), "--answers", str(answers)]) == 0
    written = yaml.safe_load(destination.read_text(encoding="utf-8"))
    assert written["identity"]["full_name"] == "Sam Example"
    assert written["search"]["categories"]["core"] == ["Data Analyst"]
    assert written["notifications"]["digest_time"] == "09:00"
    assert written["models"]["screen"] == "fake"


def test_logins_walks_one_platform_at_a_time(settings_file, capsys):
    assert run(["logins", "--non-interactive"], settings_file) in (0, 1)
    out = capsys.readouterr().out
    assert "The email account you put on applications" in out
    assert "I never ask for your password" in out
    assert "Ready:" in out


def test_status_reports_progress_and_the_timetable(settings_file, capsys):
    assert run(["status"], settings_file) == 0
    out = capsys.readouterr().out
    assert "So far:" in out
    assert "What happens by itself:" in out
    assert "you get one email" in out


def test_status_stays_plain(settings_file, capsys):
    run(["status"], settings_file)
    for line in capsys.readouterr().out.splitlines():
        if line.startswith("- ") or not line.strip():
            continue
        assert lint_plain(line) == [], line


def test_technical_mode_adds_detail(settings_file, capsys):
    run(["--technical", "status"], settings_file)
    assert "statuses:" in capsys.readouterr().out


def test_digest_runs_on_an_empty_record(settings_file, capsys):
    assert run(["digest"], settings_file) == 0
    assert "Your job search" in capsys.readouterr().out


def test_a_practice_search_writes_nothing(settings_file, capsys, monkeypatch):
    class Canned:
        def get_json(self, url):
            return {
                "jobs": [
                    {
                        "id": 1,
                        "title": "Machine Learning Engineer",
                        "absolute_url": "https://job-boards.greenhouse.io/acme-robotics/jobs/1",
                        "company_name": "Acme Robotics",
                        "location": {"name": "New York, NY"},
                        "content": "A fake posting.",
                        "first_published": iso_days_ago(1),
                    }
                ]
            }

    monkeypatch.setattr("jobpilot.search.UrllibFetcher", lambda *a, **k: Canned())
    assert run(["run", "search", "--dry-run"], settings_file) == 0
    out = capsys.readouterr().out
    assert "1 new job" in out
    assert "did not write anything down" in out


def test_search_then_screen_then_apply(settings_file, capsys, monkeypatch):
    from jobpilot.providers import FakeProvider

    posting = {
        "jobs": [
            {
                "id": 1,
                "title": "Machine Learning Engineer",
                "absolute_url": "https://job-boards.greenhouse.io/acme-robotics/jobs/1",
                "company_name": "Acme Robotics",
                "location": {"name": "New York, NY"},
                "content": "A fake posting with no reason to say no.",
                "first_published": iso_days_ago(1),
            }
        ]
    }
    monkeypatch.setattr(
        "jobpilot.search.UrllibFetcher", lambda *a, **k: type("F", (), {"get_json": lambda s, u: posting})()
    )
    assert run(["run", "search"], settings_file) == 0
    assert "I added 1 job" in capsys.readouterr().out

    config = __import__("jobpilot.config", fromlist=["load"]).load(settings_file)
    tracker = Tracker.from_config(config)
    job_id = tracker.read()[0]["job_id"]

    def answer(prompt):
        return json.dumps([{"job_id": job_id, "verdict": "keep", "tier": "core", "reason": "a fit"}])

    monkeypatch.setattr(
        "jobpilot.providers._providers_from_config", lambda cfg: {"fake": FakeProvider(answer=answer)}
    )
    assert run(["run", "screen"], settings_file) == 0
    assert "look worth applying to" in capsys.readouterr().out
    assert tracker.by_id()[job_id]["status"] == "pipeline"

    assert run(["run", "apply", "--dry-run"], settings_file) == 0
    out = capsys.readouterr().out
    assert "ready to go whenever you say so" in out
    assert tracker.by_id()[job_id]["status"] == "pipeline"  # still nothing sent


def test_doctor_reports_each_check(settings_file, capsys):
    code = run(["doctor"], settings_file)
    out = capsys.readouterr().out
    assert "Settings: fine" in out
    assert "Your application record: fine" in out
    assert "Model for reading job descriptions: fine" in out
    assert "Permissions: nothing may be sent or submitted yet." in out
    assert "Helper 'linkedin': off." in out
    assert code == 0


def test_doctor_explains_a_broken_settings_file(tmp_path, capsys):
    path = tmp_path / "preferences.yaml"
    path.write_text("schema_version: 99\n", encoding="utf-8")
    assert run(["doctor"], path) == 1
    assert "schema_version" in capsys.readouterr().out


def test_a_missing_settings_file_is_explained_not_crashed(tmp_path, capsys):
    assert run(["status"], tmp_path / "nope.yaml") == 1
    assert "jobpilot setup" in capsys.readouterr().err


def test_the_module_can_be_run_directly():
    import jobpilot.__main__  # noqa: F401


def test_asking_for_a_change_in_words_proposes_but_does_not_act(settings_file, capsys, monkeypatch):
    from jobpilot.providers import FakeProvider

    answer = json.dumps(
        {
            "change": {"search.recency_days": 7},
            "summary": "I would only look at openings from the last week.",
            "effect": "Fewer but fresher matches.",
        }
    )
    monkeypatch.setattr(
        "jobpilot.providers._providers_from_config",
        lambda cfg: {"fake": FakeProvider(replies=[answer])},
    )
    assert run(["ask", "only look at jobs from the last week"], settings_file) == 0
    out = capsys.readouterr().out
    assert "how far back I look: now 21; would become 7." in out
    assert "changed nothing yet" in out
    assert yaml.safe_load(settings_file.read_text(encoding="utf-8"))["search"]["recency_days"] == 21

    assert run(["approve", "your-request"], settings_file) == 0
    assert "Done." in capsys.readouterr().out
    assert yaml.safe_load(settings_file.read_text(encoding="utf-8"))["search"]["recency_days"] == 7


def test_declining_a_suggestion_leaves_everything_alone(settings_file, capsys, monkeypatch):
    from jobpilot.providers import FakeProvider

    answer = json.dumps({"change": {"search.recency_days": 7}, "summary": "s", "effect": "e"})
    monkeypatch.setattr(
        "jobpilot.providers._providers_from_config",
        lambda cfg: {"fake": FakeProvider(replies=[answer])},
    )
    run(["ask", "look back a week"], settings_file)
    capsys.readouterr()
    assert run(["decline", "your-request"], settings_file) == 0
    assert "left everything exactly as it was" in capsys.readouterr().out
    assert yaml.safe_load(settings_file.read_text(encoding="utf-8"))["search"]["recency_days"] == 21


def test_approving_something_that_is_not_waiting_is_explained(settings_file, capsys):
    assert run(["approve", "nonsense"], settings_file) == 1
    assert "do not have a suggestion" in capsys.readouterr().err


def test_a_suggestion_from_the_numbers_can_be_approved_from_status(settings_file, capsys):
    config = __import__("jobpilot.config", fromlist=["load"]).load(settings_file)
    tracker = Tracker.from_config(config)
    tracker.upsert([{"job_id": f"s{n}", "status": "submitted"} for n in range(4)], caller="test")
    assert run(["status"], settings_file) == 0
    out = capsys.readouterr().out
    assert "Want me to do this?" in out
    assert "approve confirm_rate_low" in out
    assert run(["decline", "confirm_rate_low"], settings_file) == 0


def test_the_timetable_can_be_listed(settings_file, capsys):
    assert run(["routines", "list", "--now", "2026-11-09T08:00"], settings_file) == 0
    out = capsys.readouterr().out
    assert "What happens by itself:" in out
    assert "Due right now" in out  # an empty record means the morning things are due


def test_the_cron_line_is_shown_in_technical_mode(settings_file, capsys):
    assert run(["--technical", "routines", "list", "--now", "2026-11-09T08:00"], settings_file) == 0
    out = capsys.readouterr().out
    assert "crontab" in out
    assert "jobpilot routines run-due" in out
    assert "OnCalendar" in out  # and the systemd version, for people who prefer it


def test_the_cron_line_names_the_real_folder_not_a_guessed_one(settings_file):
    """The clone can be called anything, so the line must be worked out, not written down."""
    from jobpilot.cli import cron_line, shorten
    from jobpilot.config import repo_root

    line = cron_line()
    assert "cd ~/jobpilot " not in line, "the folder name must not be hardcoded"
    assert f"cd {shorten(repo_root())} " in line
    assert (repo_root() / "pyproject.toml").exists()


def test_the_cron_line_logs_inside_the_configured_data_folder(settings_file):
    from jobpilot.cli import cron_line, shorten
    from jobpilot.config import load

    config = load(settings_file)
    assert f"{shorten(config.paths.logs)}/cron.log" in cron_line(config)


def test_run_due_is_safe_to_call_twice(settings_file, capsys, monkeypatch):
    monkeypatch.setattr(
        "jobpilot.search.UrllibFetcher",
        lambda *a, **k: type("F", (), {"get_json": lambda s, u: {"jobs": []}})(),
    )
    when = ["--now", "2026-11-09T08:00"]
    assert run(["routines", "run-due", *when], settings_file) == 0
    first = capsys.readouterr().out
    assert "looked for new openings" in first
    assert run(["routines", "run-due", *when], settings_file) == 0
    assert "Nothing was due just now." in capsys.readouterr().out


def test_run_due_can_say_what_it_would_do(settings_file, capsys):
    assert run(["routines", "run-due", "--dry-run", "--now", "2026-11-09T08:00"], settings_file) == 0
    assert "(practice)" in capsys.readouterr().out


def test_reading_shows_an_example_and_the_sentence_that_caused_a_skip(settings_file, capsys, monkeypatch):
    from jobpilot.config import load
    from jobpilot.providers import FakeProvider

    config = load(settings_file)
    tracker = Tracker.from_config(config)
    tracker.upsert(
        [
            {
                "job_id": "keep-me",
                "status": "new",
                "company": "Acme Robotics",
                "title": "Machine Learning Engineer",
                "description": "A fine job with nothing ruling you out.",
            },
            {
                "job_id": "drop-me",
                "status": "new",
                "company": "Umbrella Logistics",
                "title": "Machine Learning Engineer",
                "description": "Minimum 8 years of experience in production is required for this role.",
            },
        ],
        caller="test",
    )

    def answer(prompt):
        rows = []
        for job_id in ("keep-me", "drop-me"):
            if job_id == "drop-me":
                rows.append(
                    {
                        "job_id": job_id,
                        "verdict": "drop",
                        "tier": "irrelevant",
                        "quote": "Minimum 8 years of experience in production is required for this role.",
                        "reason": "it asks for more experience than you have",
                    }
                )
            else:
                rows.append({"job_id": job_id, "verdict": "keep", "tier": "core", "reason": "a fit"})
        return json.dumps(rows)

    monkeypatch.setattr(
        "jobpilot.providers._providers_from_config", lambda cfg: {"fake": FakeProvider(answer=answer)}
    )
    assert run(["run", "screen"], settings_file) == 0
    out = capsys.readouterr().out
    assert "For example, I would apply to: Acme Robotics — Machine Learning Engineer" in out
    assert 'because the posting says: "Minimum 8 years of experience' in out


# -- where the settings file lives ---------------------------------------


def test_setup_writes_where_every_other_command_looks(tmp_path, monkeypatch, capsys):
    """One resolution order. Setup writing somewhere nothing else reads is the
    worst kind of bug: it all looks fine and nothing works."""
    from jobpilot.config import repo_root

    chosen = tmp_path / "preferences.yaml"
    monkeypatch.setenv("JOBPILOT_CONFIG", str(chosen))
    monkeypatch.setenv("JOBPILOT_DATA_DIR", str(tmp_path / "data"))
    before = {p.name for p in (repo_root() / "config").iterdir()}

    assert main(["setup", "--non-interactive"]) == 0
    assert chosen.exists()
    assert {p.name for p in (repo_root() / "config").iterdir()} == before
    capsys.readouterr()

    # and every later command finds it without being told where it is
    for argv in (["run", "search", "--dry-run"], ["status"], ["digest"], ["doctor"]):
        assert main(argv) in (0, 1), argv
        out = capsys.readouterr().out + capsys.readouterr().err
        assert "could not find your settings" not in out, argv


def test_an_explicit_path_still_wins_over_the_environment(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("JOBPILOT_CONFIG", str(tmp_path / "from-the-environment.yaml"))
    asked_for = tmp_path / "asked-for.yaml"
    assert main(["setup", "--out", str(asked_for), "--non-interactive"]) == 0
    assert asked_for.exists()
    assert not (tmp_path / "from-the-environment.yaml").exists()
    capsys.readouterr()


def test_start_also_honours_the_environment(tmp_path, monkeypatch, capsys):
    chosen = tmp_path / "preferences.yaml"
    monkeypatch.setenv("JOBPILOT_CONFIG", str(chosen))
    monkeypatch.setenv("JOBPILOT_DATA_DIR", str(tmp_path / "data"))
    assert main(["start", "--non-interactive"]) in (0, 1)
    assert chosen.exists()
    capsys.readouterr()


def test_the_first_hello_says_each_thing_once(capsys):
    assert main(["start", "--explain-only"]) == 0
    out = capsys.readouterr().out
    assert out.count("You can also switch these on later:") == 1
    assert out.count("linkedin: Get noticed on LinkedIn") == 1
    assert out.count("I will never do:") == 1
    assert "Three things I will never do" not in out  # the short repeat is gone
    assert out.count("apply to the same job twice") == 1


def test_a_helpers_own_promises_are_grouped_under_its_name(tmp_path, capsys):
    import yaml as _yaml

    from jobpilot.config import load_defaults

    config = load_defaults(
        {
            "paths": {"data_dir": str(tmp_path / "data")},
            "plugins": {"linkedin": {"enabled": True}},
            "search": {"categories": {"core": ["Data Analyst"]}},
        }
    )
    path = tmp_path / "preferences.yaml"
    path.write_text(_yaml.safe_dump(config.data), encoding="utf-8")
    assert run(["start", "--explain-only"], path) == 0
    out = capsys.readouterr().out
    assert "linkedin will never sign you in or out" in out
    assert "(linkedin)." not in out  # not mixed into the general promises


# -- the sign-in checklist never waits on nobody -------------------------


def test_logins_without_anyone_there_reads_the_list_and_stops(settings_file, capsys):
    assert run(["logins", "--non-interactive"], settings_file) in (0, 1)
    out = capsys.readouterr().out
    assert "Nobody is here to answer" in out
    assert out.count("What you do: open that site in your own browser") >= 1
    assert "Ready:" in out


def test_logins_with_closed_input_does_not_wait(settings_file, capsys, monkeypatch):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO(""))  # not a terminal, nothing to read
    assert run(["logins"], settings_file) in (0, 1)
    assert "Nobody is here to answer" in capsys.readouterr().out


def test_technical_works_before_or_after_the_command():
    from jobpilot.cli import build_parser

    parser = build_parser()
    assert parser.parse_args(["--technical", "routines", "list"]).technical is True
    assert parser.parse_args(["routines", "list", "--technical"]).technical is True
    assert parser.parse_args(["status", "--technical"]).technical is True
    assert parser.parse_args(["status"]).technical is False


# -- what the self-check reports -----------------------------------------


def test_doctor_reports_the_cv_the_answers_and_the_health(settings_file, capsys):
    assert run(["doctor"], settings_file) == 0
    out = capsys.readouterr().out
    for line in ("Your CV:", "Your answers:", "Employer sign-ups:", "Timetable:", "Health:"):
        assert line in out, line
    assert "all of them ready to run" in out


def test_doctor_notices_a_cv_that_is_not_there(settings_file, capsys, tmp_path):
    import yaml

    data = yaml.safe_load(settings_file.read_text(encoding="utf-8"))
    data["documents"] = {**data.get("documents", {}), "resume": str(tmp_path / "nowhere.pdf")}
    settings_file.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert run(["doctor"], settings_file) == 1
    assert "I cannot find it where you said it was" in capsys.readouterr().out


def test_doctor_does_not_call_a_placeholder_a_missing_file(settings_file, capsys):
    """"~/documents/{{RESUME_FILE}}" is not a file, so it is not a broken one."""
    import yaml

    data = yaml.safe_load(settings_file.read_text(encoding="utf-8"))
    data["documents"] = {**data.get("documents", {}), "resume": "~/documents/{{RESUME_FILE}}"}
    settings_file.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert run(["doctor"], settings_file) == 0
    assert "I do not know where it is" in capsys.readouterr().out


def test_doctor_says_when_an_employer_sign_up_needs_the_user(settings_file, capsys):
    from jobpilot.accounts import AccountRegistry
    from jobpilot.config import load

    registry = AccountRegistry.from_config(load(settings_file))
    registry.hand_back("acme", "phone")
    registry.save()

    assert run(["doctor"], settings_file) == 0
    out = capsys.readouterr().out
    assert "is waiting for you" in out
    assert "text a code to your phone" in out


def test_doctor_reports_an_unusable_data_folder_as_a_sentence(settings_file, capsys, tmp_path, monkeypatch):
    """A self-check that ends in a stack trace has failed at its one job."""
    import yaml

    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    data = yaml.safe_load(settings_file.read_text(encoding="utf-8"))
    data["paths"] = {"data_dir": str(blocked / "inside")}
    settings_file.write_text(yaml.safe_dump(data), encoding="utf-8")
    monkeypatch.delenv("JOBPILOT_DATA_DIR", raising=False)

    assert run(["doctor"], settings_file) == 1
    out = capsys.readouterr().out
    assert "I cannot write to" in out
    assert "is skipped until that is fixed" in out
    # and it still finishes the checks that do not need that folder
    assert "Timetable:" in out
    assert "needs fixing before I can run on my own" in out


def test_doctor_is_happy_with_the_shipped_example_settings(tmp_path, capsys, monkeypatch):
    """Somebody's very first run uses the example. It has to work."""
    from jobpilot.config import EXAMPLE_CONFIG_PATH, repo_root

    monkeypatch.setenv("JOBPILOT_DATA_DIR", str(tmp_path / "data"))
    assert run(["doctor"], repo_root() / EXAMPLE_CONFIG_PATH) == 0
    out = capsys.readouterr().out
    assert "Everything checks out." in out
    # the placeholders in it are treated as unanswered, not as broken answers
    assert "{{" not in out
