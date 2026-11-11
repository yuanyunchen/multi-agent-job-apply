# templates/ — the team, ready to import

Seven bot templates. Each one is a folder of plain files you can read, edit and
hand to a bot product, plus a generated `share.json` for importing the whole
thing in one step.

They are **public and generic**. There is nothing in here about any particular
person, employer, mailbox or account: everything specific is asked for in each
bot's first conversation with its new owner and written to that owner's own
settings.

## The roles

| folder | bot | what it does | talks to |
|---|---|---|---|
| [`bots/lead`](bots/lead) | **Job Application Lead** | plans the day, hands work out, checks it, sends one summary a day | **the owner** |
| [`bots/search`](bots/search) | **Job Search Bot** | finds openings and hands them over screened, in one of two focus modes | the Lead |
| [`bots/apply`](bots/apply) | **Job Apply Bot** | fills in forms, in small batches, every job disposed of | the Lead |
| [`bots/mail`](bots/mail) | **Mail Bot** | reads the application mailbox, read-only, and writes outcomes back | the Lead |
| [`bots/linkedin`](bots/linkedin) | **Network Engagement Bot** | visibility on a professional network: notes and comments | the Lead |
| [`bots/handshake`](bots/handshake) | **School Platform Bot** | a school careers platform: employers, student-only postings, events | the Lead |
| [`bots/yc`](bots/yc) | **Startup Platform Bot** | a startup platform where applying happens in-app, under a weekly cap | the Lead |

**Only the Lead talks to the owner.** Everyone else reports to the Lead. That is
not etiquette; it is what stops one person getting six half-informed messages
about the same thing.

**One search role, two focus modes.** A *broad* pass across employers' own
application systems, and a *channel* pass that goes deep on one platform. Run
two copies with different focuses if you like - but they share one set of
screening rules, because two copies of a rule drift and then nobody can say
which answer was right.

## What is in a template

```
bots/<role>/
  bot.yaml                   name, title, description, avatar, services
  PROFILE.md                 role, mission, reporting line, hard rules
  memories.md                generic facts it starts out knowing
  routines.yaml              what it does on a schedule, and the prompt
  getting-started/SKILL.md   its first conversation with a new owner
  skills/<slug>/SKILL.md     one skill per folder, with frontmatter
  share.json                 GENERATED - do not edit
```

Every role has the same two shared skills - `agent-routing` (how to delegate to
provider slots) and `team-protocol` (how the team talks) - plus its own. Those
two live once in [`shared/skills/`](shared/skills) and are copied in, so there
is exactly one source for each.

**`share.json` is generated from the other files.** Never edit it:

```bash
scripts/build_bot_templates.py            # bring every share.json up to date
scripts/build_bot_templates.py --check    # fail if any is stale (this runs in CI)
```

## Importing into a hosted bot product

Two ways, depending on what the product offers.

**Paste the share payload.** Open `bots/<role>/share.json` and give it to the
product's "create a bot from a shared template" flow. It carries the name,
title, description, avatar, memories, skills, routines and the services the bot
expects - and no credentials, because there are none in it.

**Or build it by hand** from the folder, in this order:

1. **Create the bot** with the name, title, description and avatar from
   `bot.yaml`.
2. **Paste `PROFILE.md`** as its instructions or system prompt.
3. **Add the memories** - one per bullet in `memories.md`. (`share.json` has
   them already flattened into one list, if the product takes a list.)
4. **Add each skill** from `skills/<slug>/SKILL.md`, including
   `getting-started/SKILL.md`. The frontmatter holds the name and the
   description the product needs; the rest is the body.
5. **Add the routines** from `routines.yaml` - the cron schedule and the prompt.
   Anything marked `enabled: false` starts switched off; leave it that way.
6. **Connect the services** named in `bot.yaml` under `plugins`. Those are
   names, not keys: you connect them yourself.
7. **Start the bot** and let `getting-started` run. It will ask its questions
   one at a time and write the answers down.

Do the **Lead first**, then the teammates: each teammate's first question is
which Lead to report to.

## Running the same team with a coding agent

You do not need a hosted product. Any agent with a terminal - Claude Code,
Codex, Cursor, or anything similar - can play these roles directly.

```
Read AGENTS.md in https://github.com/yuanyunchen/multi-agent-job-apply and set up my job-application team.
```

[`AGENTS.md`](../AGENTS.md) walks it through installing, building the team from
these templates, running the guided setup, and handing over. The role prompts in
[`agents/`](../agents) are the same behaviour in the shape a coding agent wants;
the templates here are the same behaviour in the shape a bot product wants.

The command line can also read them:

```bash
jobpilot templates list            # the seven roles
jobpilot templates show lead       # what one role is and does
jobpilot templates export lead     # the share payload, to pipe or paste
```

## What every template promises

These hold whichever way you import, and the test suite checks several of them:

- **Nothing is sent, submitted or posted** until the owner switches that
  permission on - and a switched-on permission still has to pass its own check.
- **Only the owner signs in.** No template asks for a password, and none types
  one.
- **No credentials anywhere.** `bot.yaml` names services; it never holds a key,
  a token or an account.
- **Teammates report only to the Lead.**
- **Every skipped job quotes the posting**, and the quote is checked against it.
- **Never apply twice.** A duplicate is worse than a miss.
- **Never invent a form answer.** No answer on file means the application stops
  and the owner is asked.
- **English only.** A scan fails the build on any non-English script, so a
  template cannot quietly become unreadable to half its audience.

## Editing a template

Edit the plain files, then rebuild:

```bash
$EDITOR templates/bots/lead/PROFILE.md
scripts/build_bot_templates.py
JOBPILOT_TEST=1 python -m pytest -q tests/test_templates.py
```

Two rules when editing:

- **Nothing personal.** No names, no email addresses outside the reserved
  example domains, no account handles, no internal identifiers, no machine
  paths. The hygiene scan covers this folder.
- **No vendor names in a skill.** A model or a tool belongs in a provider slot
  in the settings, never written into a skill, a prompt or a routine. That is
  what lets an owner run the same team on whatever they actually have.
