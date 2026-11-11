"""The account registry: site states, and nothing anybody could leak."""

from __future__ import annotations

import pytest

from jobpilot.accounts import AccountRegistry, site_key


# -- the key --------------------------------------------------------------


def test_a_tenant_host_keys_on_the_tenant():
    assert site_key("https://acme.myworkdayjobs.com/en-US/careers/job/4001") == "acme"
    assert site_key("https://acme.myworkdaysite.com/careers/job/9") == "acme"


def test_an_ordinary_host_keys_on_the_host():
    assert site_key("https://careers.acme-robotics.example/jobs/1") == "careers.acme-robotics.example"
    assert site_key("https://www.acme-robotics.example/jobs/1") == "acme-robotics.example"


def test_a_shared_host_keys_on_the_employer_not_the_host():
    """Two employers on one application system must not share an account entry."""
    first = site_key("https://jobs.smartrecruiters.com/AcmeRobotics/743", company="Acme Robotics")
    second = site_key("https://jobs.smartrecruiters.com/GlobexSystems/901", company="Globex Systems")
    assert first != second
    assert first.startswith("jobs.smartrecruiters.com/")


def test_a_shared_host_with_no_path_falls_back_to_the_company_name():
    assert site_key("https://apply.workable.com/", company="Acme Robotics").endswith("acme-robotics")


def test_no_url_means_no_key():
    assert site_key("") == ""


# -- the registry ---------------------------------------------------------


def test_a_site_starts_as_nothing_known(config):
    registry = AccountRegistry.from_config(config)
    assert registry.get("acme").state == "none"
    assert not registry.get("acme").usable


def test_a_recorded_state_comes_back_and_survives_a_reload(config):
    registry = AccountRegistry.from_config(config)
    registry.record("acme", "exists", system="workday")
    registry.save()

    again = AccountRegistry.from_config(config)
    assert again.get("acme").state == "exists"
    assert again.get("acme").usable
    assert again.get("acme").checked_at


def test_the_systems_that_never_ask_for_an_account_say_so(config):
    registry = AccountRegistry.from_config(config)
    row = {"url": "https://job-boards.greenhouse.io/acme-robotics/jobs/1", "ats": "greenhouse"}
    assert registry.for_row(row).state == "not_needed"


def test_a_wall_only_the_user_can_pass_is_recorded_in_their_words(config):
    registry = AccountRegistry.from_config(config)
    account = registry.hand_back("acme", "phone")
    assert account.state == "needs_user"
    assert "text a code to your phone" in account.reason
    assert "needs you" in account.words
    assert registry.needing_user() == [account]


def test_an_unknown_wall_still_reads_like_a_sentence(config):
    registry = AccountRegistry.from_config(config)
    assert "cannot do on your behalf" in registry.hand_back("acme", "something-new").reason


@pytest.mark.parametrize(
    "signup,allowed",
    [
        ("email_verify", True),
        ("sso", False),
        ("social", False),
        ("phone", False),
        ("captcha", False),
    ],
)
def test_an_account_is_only_created_where_sign_up_is_an_email_confirmation(config, signup, allowed):
    registry = AccountRegistry.from_config(config)
    may, why = registry.may_create(signup=signup)
    assert may is allowed
    assert why  # there is always a sentence, whichever way it goes


def test_the_registry_refuses_anything_shaped_like_a_credential(config):
    """There is nothing secret in here, and there is no way to put one in."""
    registry = AccountRegistry.from_config(config)
    for text in (
        "password: hunter2",
        "token=abc123def456",
        "api_key: Zm9vYmFyYmF6",
        "the value is Tr0ub4dor3xKcd9mz",
    ):
        with pytest.raises(ValueError, match="no credentials"):
            registry.record("acme", "exists", reason=text)


def test_talking_about_a_password_is_not_storing_one(config):
    """The reason has to read like a sentence, and sentences mention things."""
    registry = AccountRegistry.from_config(config)
    account = registry.record(
        "acme", "needs_user", reason="it wants a password I do not have, and a code by text"
    )
    assert account.state == "needs_user"


def test_an_unknown_state_is_refused(config):
    with pytest.raises(ValueError, match="not one of"):
        AccountRegistry.from_config(config).record("acme", "probably fine")


def test_the_registry_is_only_ever_reported_as_counts(config):
    registry = AccountRegistry.from_config(config)
    registry.record("acme", "exists")
    registry.record("globex", "needs_user", reason="it wants to text you")
    assert registry.summary() == {"exists": 1, "needs_user": 1}


def test_the_file_is_not_world_readable(config):
    """It is not secret, but it does say which employers somebody is applying to."""
    registry = AccountRegistry.from_config(config)
    registry.record("acme", "exists")
    path = registry.save()
    assert oct(path.stat().st_mode)[-3:] == "600"
