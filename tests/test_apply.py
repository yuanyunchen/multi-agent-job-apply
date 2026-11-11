from __future__ import annotations

from jobpilot.apply import ApplyOutcome, DryRunDriver, WaveRunner, describe
from jobpilot.gates import LaneGuard, OutboundGate
from jobpilot.tracker import Tracker
from jobpilot.ui import Renderer

from .synthetic import iso_days_ago


def ready_row(job_id: str, *, tier: str = "core", **fields):
    out = {
        "job_id": job_id,
        "status": "pipeline",
        "apply_tier": tier,
        "company": "Acme Robotics",
        "title": "Machine Learning Engineer",
        "url": f"https://job-boards.greenhouse.io/acme-robotics/jobs/{job_id}",
        "posted_at": iso_days_ago(1),
    }
    out.update(fields)
    return out


def runner_for(config, tracker: Tracker, driver=None, probe=lambda: 100_000, **kwargs):
    return WaveRunner(
        config=config,
        tracker=tracker,
        driver=driver or DryRunDriver(),
        answers=__import__("jobpilot.gates", fromlist=["AnswerBank"]).AnswerBank(),
        gate=OutboundGate(config),
        lanes=LaneGuard.from_config(config, probe=probe),
        **kwargs,
    )


def test_a_practice_run_changes_nothing(config, tracker):
    tracker.upsert([ready_row("a"), ready_row("b")], caller="test")
    driver = DryRunDriver()
    before = tracker.read()
    result = runner_for(config, tracker, driver).run(dry_run=True)
    assert result.would_apply == 2 and result.handled == 2
    assert all(call.dry_run for call in driver.calls)
    assert tracker.read() == before
    assert {row["status"] for row in tracker.read()} == {"pipeline"}


def test_every_row_that_is_claimed_is_disposed_of(make_config, tmp_path):
    config = make_config(
        paths={"data_dir": str(tmp_path / "data")}, permissions={"submit_applications": True}
    )
    tracker = Tracker.from_config(config)
    tracker.upsert([ready_row("a")], caller="test")
    runner_for(config, tracker).run(dry_run=False)
    row = tracker.by_id()["a"]
    assert row["status"] == "skipped"  # the practice driver sends nothing
    assert row["claimed_by"] == ""
    assert row["skip_reason"]


def test_an_unanswerable_question_parks_the_job_and_names_the_question(make_config, tmp_path):
    config = make_config(
        paths={"data_dir": str(tmp_path / "data")}, permissions={"submit_applications": True}
    )
    tracker = Tracker.from_config(config)
    tracker.upsert([ready_row("a")], caller="test")
    driver = DryRunDriver(asks={"a": ["What is your employee referral code?"]})
    result = runner_for(config, tracker, driver).run(dry_run=False)
    assert result.parked == 1
    assert result.questions == ["What is your employee referral code?"]
    row = tracker.by_id()["a"]
    assert row["status"] == "parked"
    assert row["pending_questions"] == ["What is your employee referral code?"]
    assert driver.calls == []  # the driver never even started


def test_a_practice_run_still_reports_what_would_stop_it(config, tracker):
    tracker.upsert([ready_row("a")], caller="test")
    driver = DryRunDriver(asks={"a": ["What is your employee referral code?"]})
    result = runner_for(config, tracker, driver).run(dry_run=True)
    assert result.parked == 1 and result.would_apply == 0
    assert tracker.by_id()["a"]["status"] == "pipeline"


def test_an_answer_the_user_gave_is_passed_through(config, tracker, tmp_path):
    from jobpilot.gates import AnswerBank

    path = tmp_path / "answers.yaml"
    path.write_text(
        'answers:\n  - id: auth\n    match: ["authorized to work"]\n    answer: "Yes"\n', encoding="utf-8"
    )
    tracker.upsert([ready_row("a")], caller="test")
    driver = DryRunDriver(asks={"a": ["Are you authorized to work in the US?"]})
    runner = runner_for(config, tracker, driver)
    runner.answers = AnswerBank.from_file(path)
    runner.run(dry_run=True)
    assert driver.calls[0].answers == {"Are you authorized to work in the US?": "Yes"}


def test_a_real_run_without_permission_is_blocked_not_attempted(make_config, tmp_path):
    config = make_config(paths={"data_dir": str(tmp_path / "data")})
    tracker = Tracker.from_config(config)
    tracker.upsert([ready_row("a")], caller="test")

    class Eager:
        name = "eager"
        started = False

        def questions(self, row):
            return []

        def apply(self, request):
            Eager.started = True
            return ApplyOutcome(status="submitted")

    result = runner_for(config, tracker, Eager()).run(dry_run=False)
    assert result.blocked == 1
    assert Eager.started is False
    assert "permission" in tracker.by_id()["a"]["notes"][0]


def test_with_permission_a_submit_is_recorded_with_its_proof(make_config, tmp_path):
    config = make_config(
        paths={"data_dir": str(tmp_path / "data")}, permissions={"submit_applications": True}
    )
    tracker = Tracker.from_config(config)
    tracker.upsert([ready_row("a")], caller="test")

    class Submitter:
        name = "submitter"

        def questions(self, row):
            return []

        def apply(self, request):
            return ApplyOutcome(status="submitted", detail="sent", proof_text="Application received")

    result = runner_for(config, tracker, Submitter()).run(dry_run=False)
    assert result.submitted == 1
    row = tracker.by_id()["a"]
    assert row["status"] == "submitted"
    assert row["submit_proof_url"] == row["url"]
    assert row["submit_proof_at"]


def test_a_job_already_applied_to_is_never_picked_up_again(config, tracker):
    tracker.upsert([ready_row("a")], caller="test")
    tracker.upsert(
        [{"job_id": "b", "status": "applied", "receipt": {"mail_id": "m", "basis": "matched"}}],
        caller="mail",
    )
    result = runner_for(config, tracker).run(dry_run=True)
    assert result.handled == 1


def test_nothing_starts_when_the_machine_is_low_on_memory(make_config, tmp_path):
    config = make_config(
        paths={"data_dir": str(tmp_path / "data")},
        apply={"min_free_memory_mb": 4000, "projected_memory_per_lane_mb": 2000},
    )
    tracker = Tracker.from_config(config)
    tracker.upsert([ready_row("a")], caller="test")
    result = runner_for(config, tracker, probe=lambda: 2500).run(dry_run=True)
    assert result.stopped_because == "low_memory"
    assert tracker.by_id()["a"]["status"] == "pipeline"  # left where it was


def test_an_empty_queue_is_reported_calmly(config, tracker):
    result = runner_for(config, tracker).run(dry_run=True)
    assert result.stopped_because == "nothing_to_do"


def test_the_wave_size_comes_from_the_settings(make_config, tmp_path):
    config = make_config(paths={"data_dir": str(tmp_path / "data")}, apply={"rows_per_wave": 2})
    tracker = Tracker.from_config(config)
    tracker.upsert([ready_row(str(n)) for n in range(5)], caller="test")
    assert runner_for(config, tracker).run(dry_run=True).handled == 2


def test_a_gate_stop_raised_by_a_driver_blocks_that_row_only(make_config, tmp_path):
    from jobpilot.errors import GateBlocked

    config = make_config(
        paths={"data_dir": str(tmp_path / "data")}, permissions={"submit_applications": True}
    )
    tracker = Tracker.from_config(config)
    tracker.upsert([ready_row("a"), ready_row("b")], caller="test")

    class Fussy:
        name = "fussy"
        seen = 0

        def questions(self, row):
            return []

        def apply(self, request):
            Fussy.seen += 1
            if Fussy.seen == 1:
                raise GateBlocked("captcha", "The site asked me to prove I am a person.")
            return ApplyOutcome(status="skipped", detail="practice run")

    result = runner_for(config, tracker, Fussy()).run(dry_run=False)
    assert result.blocked == 1 and result.skipped == 1
    assert sorted(row["status"] for row in tracker.read()) == ["blocked", "skipped"]


def test_the_user_hears_about_a_wave_in_plain_words(config, tracker):
    tracker.upsert([ready_row("a")], caller="test")
    result = runner_for(config, tracker).run(dry_run=True)
    simple = describe(result, Renderer("simple"))
    assert "application" in simple
    for word in ("lane", "wave", "tracker", ".py"):
        assert word not in simple.lower()


def test_technical_mode_adds_the_detail(config, tracker):
    tracker.upsert([ready_row("a")], caller="test")
    result = runner_for(config, tracker).run(dry_run=True)
    assert "refused by guards" in describe(result, Renderer("technical"))
