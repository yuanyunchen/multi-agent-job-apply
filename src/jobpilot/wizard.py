"""The setup conversation.

One question at a time. Every question has a sensible default, one sentence
saying what the answer changes, and — where it helps — an example of a job it
would keep and one it would drop. "I don't know" and an empty answer both mean
"use the default".

Nothing is written until the user has seen a plain-prose summary and said yes,
and an existing settings file is copied aside before it is replaced.

The conversation is scriptable, which is how it is tested and how the sample
session in the documentation is produced:

* :class:`ConsoleAsker` — a real person typing, or answers piped in;
* :class:`ScriptedAsker` — answers from a dictionary (a ``--answers`` file);
* ``--non-interactive`` — every default, confirmed automatically.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml

from . import catalog
from .config import DEFAULTS, Config, backup_settings, validate
from .config import write as write_config
from .errors import ConfigError
from .explain import explain_team
from .ui import plural

YES = {"y", "yes", "yeah", "yep", "ok", "okay", "sure", "go ahead", "please do", "true", "on"}
NO = {"n", "no", "nope", "nah", "don't", "dont", "false", "off"}
#: "skip" is deliberately not here: in the sign-in checklist it means "not now",
#: and a word must not mean two things.
DEFAULT_WORDS = {"", "default", "use the default", "whatever", "idk", "i don't know", "i dont know"}


@dataclass(frozen=True, slots=True)
class Question:
    key: str  # dotted settings path, or "enable.<name>" for a switchable thing
    ask: str
    default: Any
    changes: str  # one sentence: what answering this changes
    kept: str = ""  # an example of a job this would keep
    dropped: str = ""  # an example of a job this would drop
    kind: str = "text"  # text | list | int | bool | time
    topic: str = ""  # the word the user would use to ask to change it again

    @property
    def topic_name(self) -> str:
        return self.topic or self.key.split(".")[-1].replace("_", " ")

    def default_words(self) -> str:
        if self.kind == "bool":
            return "yes" if self.default else "no"
        if isinstance(self.default, (list, tuple)):
            return ", ".join(str(x) for x in self.default) or "nothing"
        return str(self.default) if str(self.default) else "nothing"


def parse_answer(question: Question, raw: str) -> Any:
    """Turn what the user typed into a settings value. Never raises."""
    text = " ".join(str(raw or "").split())
    if text.strip().lower() in DEFAULT_WORDS:
        return question.default
    if question.kind == "bool":
        low = text.lower().rstrip(".!")
        if low in YES:
            return True
        if low in NO:
            return False
        return question.default
    if question.kind == "list":
        parts = [p.strip(" .") for p in text.replace(";", ",").split(",")]
        cleaned = [p for p in parts if p]
        if len(cleaned) == 1 and cleaned[0].lower() in {"none", "nothing", "no one", "nobody"}:
            return []
        return cleaned
    if question.kind == "int":
        digits = "".join(c for c in text if c.isdigit())
        return int(digits) if digits else question.default
    if question.kind == "time":
        return _clean_time(text) or question.default
    return text


def _clean_time(text: str) -> str:
    """``8am`` / ``08:00`` / ``8`` → ``08:00``."""
    low = text.lower().replace(" ", "")
    suffix = "pm" if "pm" in low else ("am" if "am" in low else "")
    low = low.removesuffix("am").removesuffix("pm")
    hour, _, minute = low.partition(":")
    if not hour.isdigit():
        return ""
    hours = int(hour) % 24
    if suffix == "pm" and hours < 12:
        hours += 12
    if suffix == "am" and hours == 12:
        hours = 0
    minutes = int(minute) if minute.isdigit() else 0
    return f"{hours:02d}:{min(minutes, 59):02d}"


# -- who is answering ----------------------------------------------------


class Asker(Protocol):
    transcript: list[str]

    def say(self, text: str) -> None: ...

    def ask(self, question: Question) -> str: ...

    def confirm(self, text: str) -> bool: ...


def _question_block(question: Question) -> str:
    lines = [question.ask]
    lines.append(f"  (default: {question.default_words()})")
    lines.append(f"  What this changes: {question.changes}")
    if question.kept:
        lines.append(f"  Example I would apply to: {question.kept}")
    if question.dropped:
        lines.append(f"  Example I would skip: {question.dropped}")
    return "\n".join(lines)


@dataclass
class ConsoleAsker:
    """A real person, typing. End of input means "use the default"."""

    transcript: list[str] = field(default_factory=list)

    def say(self, text: str) -> None:
        self.transcript.append(text)
        print(text)

    def ask(self, question: Question) -> str:
        self.say(_question_block(question))
        raw = self._read("> ")
        self.transcript.append(f"> {raw}")
        return raw

    def confirm(self, text: str) -> bool:
        self.say(text)
        raw = self._read("Shall I save this? (yes/no) ") or "yes"
        self.transcript.append(f"> {raw}")
        return " ".join(raw.split()).lower().rstrip(".!") not in NO

    @staticmethod
    def _read(prompt: str) -> str:
        """Read one line. Works for a person typing and for piped answers.

        Nothing left to read means "use the default", so a short pipe is fine:
        the rest of the questions simply take their suggestions.
        """
        try:
            return input(prompt)
        except (EOFError, OSError):
            return ""


@dataclass
class ScriptedAsker:
    """Answers from a dictionary. Anything missing falls back to the default."""

    answers: dict[str, Any] = field(default_factory=dict)
    say_confirm: bool = True
    transcript: list[str] = field(default_factory=list)
    quiet: bool = False
    asked: list[str] = field(default_factory=list)

    def say(self, text: str) -> None:
        self.transcript.append(text)
        if not self.quiet:
            print(text)

    def ask(self, question: Question) -> str:
        self.say(_question_block(question))
        raw = self.answers.get(question.key, "")
        if isinstance(raw, bool):
            raw = "yes" if raw else "no"
        elif isinstance(raw, (list, tuple)):
            raw = ", ".join(str(x) for x in raw)
        else:
            raw = str(raw)
        self.asked.append(question.key)
        self.transcript.append(f"> {raw or '(use the default)'}")
        if not self.quiet:
            print(f"> {raw or '(use the default)'}")
        return raw

    def confirm(self, text: str) -> bool:
        self.say(text)
        answer = "yes" if self.say_confirm else "no"
        self.transcript.append(f"> {answer}")
        if not self.quiet:
            print(f"> {answer}")
        return self.say_confirm


#: Friendlier keys allowed in a ``--answers`` file.
ALIASES = {
    "name": "identity.full_name",
    "email": "identity.apply_email",
    "phone": "identity.phone",
    "location": "identity.current_location",
    "core_roles": "search.categories.core",
    "other_roles": "search.categories.non_core",
    "never_roles": "search.categories.excluded",
    "cities": "search.locations.preferred",
    "remote": "search.locations.remote_ok",
    "needs_sponsorship": "work_authorization.needs_sponsorship_now_or_later",
    "max_years": "search.max_required_years_experience",
    "never_companies": "search.company_rules.hard_exclude",
    "hold_companies": "search.company_rules.hold_pending_user",
    "recency_days": "search.recency_days",
    "boards": "search.sources.greenhouse.boards",
    "digest_email": "identity.digest_email",
    "digest_time": "notifications.digest_time",
    "mode": "ui.mode",
}


def read_answers_file(path: str | Path) -> dict[str, Any]:
    """Load a ``--answers`` file, accepting either real keys or the aliases."""
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ConfigError(
            f"The answers in {path} should be a list of 'question: answer' lines.",
            hint="See docs/sample-session.md for an example.",
        )
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if key == "enable" and isinstance(value, (list, tuple)):
            for entry in catalog.catalog():
                out[f"enable.{entry.name}"] = entry.name in [str(v) for v in value]
            continue
        out[ALIASES.get(str(key), str(key))] = value
    return out


# -- the questions -------------------------------------------------------


def questions(data: dict[str, Any]) -> list[Question]:
    """The interview. Defaults come from whatever settings we already have."""
    here = Config(data)

    def get(dotted: str, fallback: Any = None) -> Any:
        return here.get(dotted, fallback)

    out = [
        Question(
            "identity.full_name",
            "What name should go on your applications?",
            _plain(get("identity.full_name")),
            "This is the name typed into every form.",
            topic="your name",
        ),
        Question(
            "identity.apply_email",
            "Which email address should I use on applications?",
            _plain(get("identity.apply_email")),
            "Every application and any account a company makes you create uses this one "
            "address, so confirmations all land in one place.",
            topic="your email address",
        ),
        Question(
            "identity.phone",
            "And a phone number for the forms that ask?",
            _plain(get("identity.phone")),
            "Only typed into forms. I never call or text anyone.",
            topic="your phone number",
        ),
        Question(
            "identity.current_location",
            "Where are you based? (city and state or country)",
            _plain(get("identity.current_location")),
            "Forms ask for this, and I use it to judge whether a job is close to you.",
            topic="where you live",
        ),
        Question(
            "documents.resume",
            "Where is your CV? Give me the path to the file and I will attach exactly that one.",
            _plain(get("documents.resume")),
            "I remember only where it is. The file stays where you put it, is never copied into "
            "this project, and only ever leaves your computer attached to an application.",
            topic="your CV",
        ),
        Question(
            "search.categories.core",
            "What kind of jobs do you want most? Give me a few job titles.",
            _plain_list(get("search.categories.core")) or ["Software Engineer", "Machine Learning Engineer"],
            "These are applied to first, newest first, so the jobs you care about go out while "
            "they are still fresh.",
            kept="'Machine Learning Engineer, Entry Level' at Acme Robotics",
            dropped="'Warehouse Supervisor' — nothing like what you asked for",
            kind="list",
            topic="the jobs you want most",
        ),
        Question(
            "search.categories.non_core",
            "Any jobs you would still take, but are not your first choice?",
            _plain_list(get("search.categories.non_core")) or ["Data Analyst", "Data Engineer"],
            "These wait until there is nothing in your first-choice list left to apply to.",
            kept="'Data Analyst' at Globex Systems, once your first choices are done",
            kind="list",
            topic="the jobs you would still take",
        ),
        Question(
            "search.categories.excluded",
            "Anything you never want, even if it matches otherwise?",
            _plain_list(get("search.categories.excluded")) or ["Sales", "Technician"],
            "Jobs whose title matches one of these are never applied to.",
            dropped="'Sales Analyst' — the title matches something on this list",
            kind="list",
            topic="the jobs you never want",
        ),
        Question(
            "search.locations.preferred",
            "Which cities would you work in?",
            _plain_list(get("search.locations.preferred")),
            "Jobs elsewhere are still kept, but marked, so you can decide rather than me.",
            kind="list",
            topic="the cities you would work in",
        ),
        Question(
            "search.locations.remote_ok",
            "Is a job that is fully remote fine?",
            bool(get("search.locations.remote_ok", True)),
            "If yes, remote jobs count as a match wherever the company is.",
            kept="'Machine Learning Engineer — Remote (US)'",
            kind="bool",
            topic="whether remote is fine",
        ),
        Question(
            "work_authorization.needs_sponsorship_now_or_later",
            "Will you need a company to sponsor a work visa, now or later?",
            bool(get("work_authorization.needs_sponsorship_now_or_later", True)),
            "If yes, I skip a job only when the posting itself says it rules you out — and I "
            "always keep the exact sentence that made me skip it. A posting that will not "
            "sponsor a new visa but accepts the permit you already have is a normal job, "
            "not a skip.",
            kept="a posting that says 'we accept candidates on existing work permits'",
            dropped="a posting that says 'this role is not eligible for visa sponsorship'",
            kind="bool",
            topic="whether you need visa sponsorship",
        ),
        Question(
            "search.max_required_years_experience",
            "How many years of experience do you have, roughly?",
            int(get("search.max_required_years_experience", 2)),
            "I skip a job only when the posting clearly requires more than this. "
            "'Preferred', a range starting lower, or no number at all all count as fine.",
            kept="'3+ years preferred' — preferred is not required",
            dropped="'Minimum 5 years of experience required'",
            kind="int",
            topic="your years of experience",
        ),
        Question(
            "search.company_rules.hard_exclude",
            "Any companies you never want to apply to?",
            _plain_list(get("search.company_rules.hard_exclude")),
            "These are skipped completely, with the company name as the reason.",
            dropped="any job at a company on this list",
            kind="list",
            topic="the companies to avoid",
        ),
        Question(
            "search.company_rules.hold_pending_user",
            "Any companies I should find but leave for you to decide about?",
            _plain_list(get("search.company_rules.hold_pending_user")),
            "Jobs at these companies appear in your daily summary marked 'waiting for you', "
            "and are never applied to until you say so.",
            kind="list",
            topic="the companies to hold for you",
        ),
        Question(
            "search.recency_days",
            "How far back should I look for openings, in days?",
            int(get("search.recency_days", 21)),
            "Older postings are often already filled; newer ones are always applied to first.",
            kind="int",
            topic="how far back to look",
        ),
        Question(
            "search.sources.greenhouse.boards",
            "Which companies' job pages should I watch? Use the short name from their "
            "careers link, and add ':lever' or ':ashby' if you know they use one of those.",
            _boards_default(data),
            "These are read directly from public pages, with no account and no sign-in. "
            "You can add more at any time.",
            kind="list",
            topic="the company job pages to watch",
        ),
    ]

    for entry in catalog.catalog():
        out.append(
            Question(
                f"enable.{entry.name}",
                f"Switch on '{entry.name}'? {entry.describe()}",
                bool(get(entry.enabled_key, entry.default_on)),
                f"Switching it on adds {entry.adds}."
                + (f" You would need to be signed in to {entry.login}." if entry.login else ""),
                kind="bool",
                topic=f"the '{entry.name}' helper",
            )
        )

    out += [
        Question(
            "identity.digest_email",
            "Where should your daily summary go? (blank means the same address)",
            _plain(get("identity.digest_email")),
            "One short email a day, with what happened and anything that needs you.",
            topic="where your daily summary goes",
        ),
        Question(
            "notifications.digest_time",
            "What time would you like it?",
            _clean_time(str(get("notifications.digest_time") or "08:00")) or "08:00",
            "The daily summary is put together and sent at this time on weekdays.",
            kind="time",
            topic="the time of your daily summary",
        ),
        Question(
            "ui.mode",
            "Would you like plain updates, or all the technical detail? (simple/technical)",
            str(get("ui.mode") or "simple"),
            "Simple keeps every message about progress and results. Technical adds the "
            "inner workings. You can change this whenever you like.",
            topic="how much detail you see",
        ),
    ]
    return out


def followups(data: dict[str, Any]) -> list[Question]:
    """The few questions that only make sense once something is switched on."""
    here = Config(data)
    out: list[Question] = []

    if here.get("plugins.handshake.enabled"):
        out.append(
            Question(
                "plugins.handshake.school_name",
                "Which school's job platform should I use?",
                _plain(here.get("plugins.handshake.school_name")),
                "I look at the version of the jobs board that only your school can see.",
                topic="your school",
            )
        )
    if here.get("plugins.linkedin.enabled"):
        out.append(
            Question(
                "plugins.linkedin.weekly_connect_cap",
                "How many connection requests a week feel comfortable?",
                int(here.get("plugins.linkedin.weekly_connect_cap", 90) or 90),
                "LinkedIn has its own weekly ceiling, and staying under it avoids a restriction.",
                kind="int",
                topic="how many connection requests a week",
            )
        )
    if here.get("plugins.yc.enabled"):
        out.append(
            Question(
                "plugins.yc.weekly_application_cap",
                "How many startup applications a week?",
                int(here.get("plugins.yc.weekly_application_cap", 10) or 10),
                "That platform limits these, and the allowance starts again every Monday.",
                kind="int",
                topic="how many startup applications a week",
            )
        )
    if here.get("models.providers.openai_compatible.enabled"):
        out += [
            Question(
                "models.providers.openai_compatible.base_url",
                "What is the web address of that model service?",
                _plain(here.get("models.providers.openai_compatible.base_url")),
                "I send the job descriptions there to be read.",
                topic="the model service address",
            ),
            Question(
                "models.providers.openai_compatible.model",
                "And which model of theirs should I ask for?",
                _plain(here.get("models.providers.openai_compatible.model")),
                "The name they use for it, exactly as they write it.",
                topic="which model to ask for",
            ),
            Question(
                "models.providers.openai_compatible.api_key_env",
                "What name did you give the key in your computer's environment?",
                _plain(here.get("models.providers.openai_compatible.api_key_env")) or "JOBPILOT_LLM_API_KEY",
                "I read the key from there each time. It is never written into your settings.",
                topic="the name of your key",
            ),
        ]
    return out


# -- the answer bank ------------------------------------------------------
#
# Forms ask the same handful of questions over and over. Writing the answers
# down once is the difference between an application finishing by itself and an
# application stopping to ask. Nothing here is guessed: every answer below comes
# from the person, and a question with no answer on file always stops.

#: Questions that always stop and wait, whatever is written down. A personal
#: identifier is never answered automatically, by anybody, for any reason.
ALWAYS_ASK = (
    "social security",
    "date of birth",
    "driver's license number",
    "passport number",
)


def answer_questions(data: dict[str, Any]) -> list[Question]:
    """The answer bank, asked as plain questions with answers already implied.

    Most of these can be worked out from what the person has already said, so
    they are offered as defaults and usually just confirmed.
    """
    here = Config(data)
    authorized = bool(here.get("work_authorization.authorized_to_work", True))
    sponsorship = bool(here.get("work_authorization.needs_sponsorship_now_or_later", True))
    start = _plain(here.get("timing.earliest_start_date"))

    return [
        Question(
            "answers.work_authorization",
            "Forms ask: are you allowed to work in the country you are applying in?",
            "Yes" if authorized else "No",
            "This exact wording goes into the form. If it is ever not true, say so now — I will "
            "never answer it untruthfully for you.",
            topic="whether you are allowed to work",
        ),
        Question(
            "answers.needs_sponsorship",
            "And: will you need the company to sponsor a visa, now or in future?",
            "Yes" if sponsorship else "No",
            "The honest answer, every time. A posting that accepts the permit you already have is "
            "still a normal job, so this answer does not narrow your search.",
            topic="whether you need sponsorship",
        ),
        Question(
            "answers.relocate",
            "Would you move for the right job?",
            "Yes",
            "Answered as you say it here. 'No' is a perfectly good answer and costs you nothing.",
            topic="whether you would relocate",
        ),
        Question(
            "answers.start_date",
            "What is the earliest date you could start? (like 2027-06-01)",
            start,
            "Typed into the date box. Where a form offers a list instead, I pick the nearest date "
            "after this one and read the choice back.",
            topic="your earliest start date",
        ),
        Question(
            "answers.salary_expectation",
            "If a form insists on a salary expectation, what should I put?",
            "Open, and happy to discuss the range for this role.",
            "Only used where the box cannot be left empty. Give a number if you would rather.",
            topic="what to say about salary",
        ),
        Question(
            "answers.how_did_you_hear",
            "And when they ask how you heard about the job?",
            "Company careers page",
            "I record where each job really came from, so this stays truthful.",
            topic="how you heard about the job",
        ),
    ]


#: The phrases each answer is matched against when a form asks something.
ANSWER_MATCHES: dict[str, list[str]] = {
    "work_authorization": ["authorized to work", "legally authorized", "right to work"],
    "needs_sponsorship": ["sponsorship", "require sponsorship", "visa support"],
    "relocate": ["willing to relocate", "open to relocation"],
    "start_date": ["earliest start", "start date", "available to start"],
    "salary_expectation": ["salary expectation", "compensation expectation", "desired salary"],
    "how_did_you_hear": ["how did you hear", "how did you find"],
}


def answer_bank(data: dict[str, Any]) -> dict[str, Any]:
    """The answer bank as it will be written, from the answers already gathered."""
    answers = []
    for key, phrases in ANSWER_MATCHES.items():
        value = str(Config(data).get(f"answers.{key}", "") or "").strip()
        if not value:
            continue  # no answer means the form stops and asks, which is correct
        answers.append({"id": key, "match": phrases, "answer": value})
    return {"answers": answers, "always_ask": list(ALWAYS_ASK)}


def write_answer_bank(data: dict[str, Any], destination: Path) -> Path:
    """Write ``config/answers.yaml``. Not committed, and never overwritten blindly."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        backup_settings(destination)
    header = (
        "# Your answer bank, written by jobpilot setup.\n"
        "#\n"
        "# A form question is answered ONLY from this file. A question that is not\n"
        "# here stops that application and asks you; nothing is ever guessed.\n"
        "#\n"
        "# 'match' lists wording that may appear in the question. Everything under\n"
        "# 'always_ask' stops and waits for you however this file is edited.\n"
    )
    destination.write_text(
        header + yaml.safe_dump(answer_bank(data), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return destination


def answers_destination(data: dict[str, Any], settings_file: Path | None = None) -> Path:
    """Where the answer bank goes: beside the settings file, never hardcoded.

    Somebody's form answers are as private as their settings, so they live in
    the same folder — which for most people is inside the checkout and
    gitignored, and for anyone using ``JOBPILOT_CONFIG`` is wherever they put
    their settings instead.
    """
    return Config(data, settings_file).user_path("documents.answers") or Path("answers.yaml")


def _plain(value: Any) -> str:
    """Treat a leftover ``{{PLACEHOLDER}}`` from the example file as empty.

    The example file is full of them. Offering ``{{FULL_NAME}}`` as the default
    answer to "what name should go on your applications?" is worse than
    offering nothing: it looks like an answer, and accepting it would type it
    into a form.
    """
    text = str(value or "")
    return "" if _is_placeholder(text) else text


def _plain_list(value: Any) -> list[str]:
    """The same, for a list: ``[{{CITY_1}}, {{CITY_2}}]`` becomes nothing."""
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item) for item in value if item and not _is_placeholder(str(item))]


def strip_placeholders(value: Any) -> Any:
    """Remove every ``{{PLACEHOLDER}}`` the example file left behind.

    A placeholder that survives into real settings is worse than an empty
    value: it looks like an answer, and it would be typed into a form.
    """
    if isinstance(value, dict):
        return {key: strip_placeholders(item) for key, item in value.items()}
    if isinstance(value, list):
        return [strip_placeholders(item) for item in value if not _is_placeholder(item)]
    return "" if _is_placeholder(value) else value


def _is_placeholder(value: Any) -> bool:
    """A value is unusable if it still has a ``{{...}}`` anywhere in it.

    ``config/resumes/{{RESUME_FILE}}`` is not a file; pretending it is one
    would mean trying to attach it to an application.
    """
    return isinstance(value, str) and bool(_PLACEHOLDER_ANYWHERE.search(value))


_PLACEHOLDER_ANYWHERE = re.compile(r"\{\{[^}]*\}\}")


def _boards_default(data: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for family in ("greenhouse", "lever", "ashby"):
        block = Config(data).section(f"search.sources.{family}")
        for board in _plain_list(block.get("boards")):
            out.append(board if family == "greenhouse" else f"{board}:{family}")
    return out


# -- running it ----------------------------------------------------------


@dataclass
class WizardResult:
    data: dict[str, Any]
    saved_to: Path | None = None
    backup: Path | None = None
    confirmed: bool = False
    warnings: list[str] = field(default_factory=list)
    transcript: list[str] = field(default_factory=list)
    #: Where the form answers went. They live in their own file, not in the
    #: settings, and that file is never committed.
    answers_saved_to: Path | None = None


def _assign(data: dict[str, Any], dotted: str, value: Any) -> None:
    node = data
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def _apply_boards(data: dict[str, Any], boards: list[str]) -> None:
    """Spread the one list of company pages across the services they use."""
    grouped: dict[str, list[str]] = {"greenhouse": [], "lever": [], "ashby": []}
    for raw in boards:
        name, _, family = str(raw).partition(":")
        grouped.setdefault(family.strip().lower() or "greenhouse", []).append(name.strip())
    for family in ("greenhouse", "lever", "ashby"):
        names = [n for n in grouped.get(family, []) if n]
        _assign(data, f"search.sources.{family}.boards", names)
        _assign(data, f"search.sources.{family}.enabled", bool(names))


def interview(data: dict[str, Any], asker: Asker, *, only: str = "") -> dict[str, Any]:
    """Ask every question — or just one topic — and fold the answers in.

    With ``only`` set, every other answer is left exactly as it was, which is
    what "change one thing" needs.
    """
    selected: list[str] = []
    asked_about_switches = False
    plan = questions(data) if not only else [*questions(data), *followups(data), *answer_questions(data)]

    for question in plan:
        targeted = (not only) or only in (question.key, question.topic_name)

        if question.key.startswith("enable."):
            name = question.key.split(".", 1)[1]
            if targeted:
                asked_about_switches = True
                value = parse_answer(question, asker.ask(question))
            else:
                value = bool(Config(data).get(_key_for(name), question.default))
            if value:
                selected.append(name)
            continue

        if not targeted:
            continue
        value = parse_answer(question, asker.ask(question))
        if question.key == "search.sources.greenhouse.boards":
            _apply_boards(data, list(value))
            continue
        if question.key == "identity.digest_email" and not value:
            value = Config(data).get("identity.apply_email", "")
        if question.key == "ui.mode":
            value = "technical" if str(value).lower().startswith("t") else "simple"
        _assign(data, question.key, value)

    if asked_about_switches:
        catalog.Selection(chosen=selected).apply_to(data)
        # Now that we know what is on, ask the few things that depend on it.
        for question in followups(data):
            _assign(data, question.key, parse_answer(question, asker.ask(question)))

    if not only:
        # The answer bank, last: these questions read better once the person's
        # situation is already on the table, and most of them are just a yes.
        asker.say("")
        asker.say(
            "Last part. Forms ask the same few questions over and over, so let us write your "
            "answers down once. Anything you leave blank will stop and ask you instead of being "
            "guessed at, and I will never answer a national insurance or date-of-birth question "
            "by myself."
        )
        for question in answer_questions(data):
            _assign(data, question.key, parse_answer(question, asker.ask(question)))

    data.update(strip_placeholders(data))
    return data


def _key_for(name: str) -> str:
    entry = catalog.find(name)
    return entry.enabled_key if entry else f"plugins.{name}.enabled"


def _where_words(config: Config) -> str:
    """"Austin, New York" — or, with no city named, the country instead."""
    cities = _plain_list(config.get("search.locations.preferred"))
    if cities:
        return ", ".join(cities)
    countries = _plain_list(config.get("search.locations.countries")) or ["US"]
    return "anywhere in " + ", ".join(countries)


def summary_prose(data: dict[str, Any]) -> str:
    """The summary the user reads before anything is written. No settings syntax."""
    config = Config(data)
    get = config.get

    def listing(dotted: str, empty: str = "nothing") -> str:
        values = get(dotted) or []
        return ", ".join(str(v) for v in values) if values else empty

    helpers = [e.name for e in catalog.catalog() if e.kind == "helper" and catalog.is_enabled(config, e)]
    models = [e.name for e in catalog.catalog() if e.kind == "model" and catalog.is_enabled(config, e)]
    boards = []
    for family in ("greenhouse", "lever", "ashby"):
        boards += [str(b) for b in config.section(f"search.sources.{family}").get("boards") or []]

    sponsor = get("work_authorization.needs_sponsorship_now_or_later", True)
    lines = [
        "Here is everything, in plain words:",
        "",
        f"You on applications: {get('identity.full_name') or 'no name yet'}"
        f" · {get('identity.apply_email') or 'no email yet'}"
        f" · {get('identity.phone') or 'no phone number yet'}"
        f" · {get('identity.current_location') or 'no location yet'}.",
        f"The CV I will attach: {get('documents.resume') or 'you have not told me where it is yet'}.",
        f"Form answers I will have ready: {_answers_words(data)}.",
        f"Jobs I will go after first: {listing('search.categories.core')}.",
        f"Jobs I will apply to after those: {listing('search.categories.non_core')}.",
        f"Jobs I will never apply to: {listing('search.categories.excluded')}.",
        f"Where: {_where_words(config)}"
        + (", and fully remote jobs count too." if get("search.locations.remote_ok") else ", and not remote jobs."),
        (
            "Work permission: you need a company to sponsor a visa, so I skip a job only when "
            "the posting says it rules you out, and I always keep that sentence."
            if sponsor
            else "Work permission: you do not need sponsorship, so nothing is skipped for visa reasons."
        ),
        f"Experience: I skip a job only if it clearly requires more than "
        f"{plural(int(get('search.max_required_years_experience', 2)), 'year')}.",
        f"Companies I will avoid completely: {listing('search.company_rules.hard_exclude', 'none')}.",
        f"Companies I will hold for your decision: {listing('search.company_rules.hold_pending_user', 'none')}.",
        f"How far back I look: {get('search.recency_days')} days.",
        f"Company job pages I will watch: {', '.join(boards) if boards else 'none yet'}.",
        f"Helpers switched on: {', '.join(helpers) if helpers else 'none'}.",
        f"Models switched on: {', '.join(models) if models else 'none'}.",
        f"Your daily summary: {get('notifications.digest_time', '08:00')} on weekdays, to "
        f"{get('identity.digest_email') or get('identity.apply_email') or 'no address yet'}.",
        f"How much detail you see: {get('ui.mode')}.",
        "",
        "Nothing is sent, submitted or posted until you switch that on separately. "
        "I will never apply to the same job twice, make up an answer on a form, "
        "reset a password, or change one of these settings without asking you.",
    ]
    return "\n".join(lines)


def _answers_words(data: dict[str, Any]) -> str:
    """"four of the six questions forms usually ask" — in plain words."""
    written = answer_bank(data)["answers"]
    if not written:
        return "none yet, so every form question will stop and ask you"
    names = {
        "work_authorization": "whether you may work there",
        "needs_sponsorship": "whether you need sponsorship",
        "relocate": "whether you would move",
        "start_date": "when you could start",
        "salary_expectation": "what to say about salary",
        "how_did_you_hear": "how you heard about the job",
    }
    return ", ".join(names.get(entry["id"], entry["id"]) for entry in written)


def prose_echo(data: dict[str, Any], path: Path) -> str:
    """What was written, read back as sentences rather than as a file."""
    config = Config(data)
    helpers = [e.name for e in catalog.catalog() if e.kind == "helper" and catalog.is_enabled(config, e)]
    return "\n".join(
        [
            "Saved. Your answers are written down, and you can change any of them whenever you like.",
            "In words: I will look for "
            + (", ".join(str(x) for x in config.get("search.categories.core") or []) or "the jobs you listed")
            + " first, skip anything that clearly rules you out and keep the sentence that did it, "
            "and apply to the newest ones first.",
            "Helpers switched on: " + (", ".join(helpers) if helpers else "none") + ".",
            f"You will get one summary a day at {config.get('notifications.digest_time', '08:00')}.",
        ]
    )


def warnings_for(data: dict[str, Any]) -> list[str]:
    """Things worth saying out loud before we finish."""
    config = Config(data)
    out = []
    if not config.get("identity.apply_email"):
        out.append(
            "I do not have an email address for you yet, so I cannot fill in forms until you "
            "tell me one. Say 'change your email address' whenever you like."
        )
    if not any(
        config.section(f"search.sources.{family}").get("boards")
        for family in ("greenhouse", "lever", "ashby")
    ) and not [e for e in catalog.enabled_entries(config) if e.kind == "helper"]:
        out.append(
            "I have nowhere to look yet. Name a few companies whose job pages I should watch, "
            "or switch on one of the helpers."
        )
    resume = str(config.get("documents.resume") or "")
    if not resume:
        out.append(
            "I do not know where your CV is yet. Tell me where it is and I will attach exactly "
            "that file, and never a different version."
        )
    elif not config.user_path("documents.resume").exists():
        out.append(
            "I cannot find your CV where you said it was, so applications that need it will wait. "
            "Say 'change your CV' and give me the right place."
        )
    if not answer_bank(data)["answers"]:
        out.append(
            "I have no answers written down for the questions forms ask, so every one of them "
            "will stop and wait for you."
        )
    if catalog.is_enabled(config, catalog.find("fake")):
        out.append(
            "The practice stand-in is switched on, which makes up its answers. "
            "Switch on a real model before you rely on anything it says."
        )
    return out


def run(
    *,
    asker: Asker,
    base: dict[str, Any] | None = None,
    destination: Path | None = None,
    write: bool = True,
    intro: bool = True,
    max_edits: int = 3,
) -> WizardResult:
    """Hold the conversation, then save only if the user says yes."""
    data = copy.deepcopy(base if base is not None else DEFAULTS)
    if intro:
        asker.say(explain_team(Config(data)))
        asker.say("")
        asker.say(
            "I will ask a short list of questions. Press enter, or say 'use the default', "
            "to take the suggestion each time."
        )
        asker.say("")

    interview(data, asker)

    confirmed = False
    for _ in range(max(1, max_edits)):
        if asker.confirm("\n" + summary_prose(data)):
            confirmed = True
            break
        edit = Question(
            "edit",
            "Which part should I change? (say it the way I said it, like 'the cities you would work in')",
            "",
            "Nothing has been saved yet, so changing your mind costs nothing.",
        )
        topic = parse_answer(edit, asker.ask(edit))
        if not topic:
            break
        interview(data, asker, only=str(topic))

    result = WizardResult(
        data=data,
        confirmed=confirmed,
        warnings=warnings_for(data),
        transcript=list(asker.transcript),
    )
    if not confirmed:
        asker.say("Nothing saved — your settings are exactly as they were.")
        return result

    # The form answers live in their own file, not in the settings: they are a
    # different kind of thing, they are read by a different part of the system,
    # and keeping them separate means the settings file stays something a person
    # can read in one sitting.
    bank = data.pop("answers", None)

    try:
        config = validate(data, destination)
    except ConfigError as exc:
        asker.say("I could not save that yet:")
        asker.say(str(exc))
        return result

    if write and destination is not None:
        destination = Path(destination)
        result.backup = backup_settings(destination)
        write_config(config, destination)
        result.saved_to = destination
        if bank:
            result.answers_saved_to = write_answer_bank(
                {"answers": bank}, answers_destination(data, destination)
            )
            written = answer_bank({"answers": bank})["answers"]
            asker.say(
                f"I have written down {plural(len(written), 'answer')} to the questions forms ask. "
                "Anything not on that list stops and asks you."
            )
        asker.say(prose_echo(data, destination))
        if result.backup:
            asker.say("Your previous answers are kept alongside, in case you want them back.")
    for warning in result.warnings:
        asker.say(f"One thing: {warning}")
    return result
