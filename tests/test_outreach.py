"""The outreach manifest: drafts written down, nothing sent."""

from __future__ import annotations

from datetime import date

from jobpilot.gates import OutboundGate
from jobpilot.outreach import build_manifest, read_manifest, write_manifest

TODAY = date(2026, 11, 10)

LEADS = {
    "linkedin": [
        {
            "kind": "connect_note",
            "recipient": "a hiring manager",
            "text": "Hello — I work on forecasting models and liked your post about warehouse robots.",
            "company": "Acme Robotics",
        }
    ]
}


def with_linkedin(make_config, **extra):
    return make_config(plugins={"linkedin": {"enabled": True}}, **extra)


def test_nothing_is_drafted_when_no_helper_is_switched_on(config):
    manifest = build_manifest(config, leads=LEADS, today=TODAY)
    assert manifest.entries == []
    assert manifest.words() == "No messages to go out today."


def test_a_draft_is_held_when_the_permission_is_off(make_config):
    config = with_linkedin(make_config)
    manifest = build_manifest(config, leads=LEADS, today=TODAY)
    assert len(manifest.entries) == 1
    entry = manifest.entries[0]
    assert entry.send is False
    assert entry.code == "not_permitted"
    assert "not going out" in entry.words


def test_a_draft_is_ready_only_when_the_permission_is_on(make_config):
    config = with_linkedin(make_config, permissions={"send_outreach_messages": True})
    manifest = build_manifest(config, leads=LEADS, today=TODAY)
    assert manifest.ready and not manifest.held
    assert manifest.ready[0].text == LEADS["linkedin"][0]["text"]


def test_the_manifest_says_plainly_that_nothing_was_sent(make_config):
    config = with_linkedin(make_config, permissions={"send_outreach_messages": True})
    manifest = build_manifest(config, leads=LEADS, today=TODAY)
    assert "Nothing has been sent." in manifest.words()
    assert manifest.as_dict()["nothing_was_sent"] is True


def test_a_blocked_draft_is_kept_with_its_reason_and_never_reworded(make_config):
    config = with_linkedin(make_config, permissions={"send_outreach_messages": True})
    too_long = {**LEADS["linkedin"][0], "text": "x" * 5000}
    manifest = build_manifest(config, leads={"linkedin": [too_long]}, today=TODAY)
    # The plugin's own note limit drops it before the gate even sees it.
    assert manifest.entries == []

    paused = OutboundGate(config, pause_file=__import__("pathlib").Path(__file__))
    held = build_manifest(config, leads=LEADS, gate=paused, today=TODAY)
    assert held.held[0].code == "paused"
    assert held.held[0].text == LEADS["linkedin"][0]["text"], "the words are untouched"


def test_a_public_comment_needs_its_own_permission(make_config):
    """Sending someone a note and posting in public are different decisions."""
    config = with_linkedin(make_config, permissions={"send_outreach_messages": True})
    comment = {"kind": "comment", "recipient": "a post", "text": "This matches what we saw too."}
    manifest = build_manifest(config, leads={"linkedin": [comment]}, today=TODAY)
    assert manifest.held[0].code == "not_permitted"

    allowed = with_linkedin(
        make_config,
        permissions={"send_outreach_messages": True, "post_public_comments": True},
    )
    assert build_manifest(allowed, leads={"linkedin": [comment]}, today=TODAY).ready


def test_a_comment_mentioning_visas_is_refused(make_config):
    config = with_linkedin(
        make_config,
        permissions={"send_outreach_messages": True, "post_public_comments": True},
    )
    comment = {"kind": "comment", "recipient": "a post", "text": "I need visa sponsorship, by the way."}
    manifest = build_manifest(config, leads={"linkedin": [comment]}, today=TODAY)
    assert manifest.held[0].code == "banned_phrase"


def test_a_manifest_can_be_written_and_read_back(make_config):
    config = with_linkedin(make_config, permissions={"send_outreach_messages": True})
    manifest = build_manifest(config, leads=LEADS, today=TODAY)
    path = write_manifest(config, manifest)
    assert path.name == "manifest-2026-11-10.json"

    again = read_manifest(config, "2026-11-10")
    assert again is not None
    assert [e.text for e in again.entries] == [e.text for e in manifest.entries]
    assert [e.send for e in again.entries] == [e.send for e in manifest.entries]


def test_reading_a_manifest_that_was_never_written_is_not_an_error(config):
    assert read_manifest(config, "1999-01-01") is None


def test_a_day_with_no_leads_produces_an_empty_manifest(make_config):
    config = with_linkedin(make_config, permissions={"send_outreach_messages": True})
    assert build_manifest(config, leads={}, today=TODAY).entries == []
