# A sample session

Every line below is **real output**, recorded by running
`tools/record_sample_session.py`. Nothing here is written by hand.

The recording is sandboxed: no network, no real mailbox, no real browser and no
real model. The job pages come from the synthetic fixtures in `tests/fixtures`
(invented companies), the model answers come from the built-in practice stand-in,
and the data folder is a temporary one that is deleted afterwards.

Lines beginning with **`YOU >`** are what the person typed. In a real session
they are typed one at a time; here they came from a file of answers so that the
document can be regenerated exactly.

Two sessions are recorded:

1. **everything switched on** — all three helpers, plus a model;
2. **nothing switched on** — the core on its own, with the practice stand-in.


## Run 1 — everything switched on

### Setting up

```console
$ jobpilot start
Hello — I look for jobs you would want, apply to them, and tell you how it is going.

Here is what you are getting.

A small team works for you:
- a coordinator, which talks to you, and is the only one that does, so you are not messaged from five places.
- a searcher, which looks for new openings and checks them against what you asked for.
- an applier, which fills in application forms and records every single one, so nothing is applied to twice.
- a mail reader, which checks the inbox you use for applications, read-only, to see which ones arrived.

These models do the thinking:
- reading job descriptions and deciding what is worth applying to: Claude Haiku (quick and cheap)
- reviewing, planning and double-checking its own work: Claude Opus (the careful one)
- working inside a web page, for the helpers that need a browser: Claude Haiku (quick and cheap)

This happens by itself:
- Every morning I look for new jobs that match what you asked for.
- Right after that I read each new job description and decide whether it is worth applying to.
- Every weekday at 8am you get one email with what I did and anything that needs you.
- On weekday mornings I write up any messages worth sending, for you to look over. I send none of them.
- On weekdays between half past nine and six I work through the list and fill in applications.
- Overnight I keep working through the list, so the morning starts with it already shorter.
- Each morning I remind you about any test or interview coming up.
- And again in the evening, so a deadline is never a surprise.
- Through the day I read your mail for replies, tests and interview invitations. I only ever read it.
- Late each morning I check that everything I found in the morning really reached my list.
- Every hour I check that nothing is quietly stuck, and tell you if something needs you.
- Each evening I check your mailbox for confirmations, so we know which applications really arrived.
- At the end of the day I look at how it went, and bring you any suggestion worth making.
- Now and then I tidy away old copies of your records, so they do not fill up your disk.
- Once a week, on Monday morning, I go over the whole week with you and suggest what to change. I never change your settings without asking.
(All times are America/New_York time.)

These are the things only you can do:
- a few details that go on application forms (your name, an email address, a phone number);
- the answers to form questions I do not have, which I always ask about rather than guess;
- saying yes before I send anything, submit anything, or change one of your settings.
- signing in to Claude in the Claude Code tool. Sign in once in that tool; I only ever check that it says you are signed in.

And these are the things I will never do:
- apply to the same job twice.
- make up an answer on a form.
- send a message, post a comment or submit a form without the matching permission switched on.
- reset a password, or follow a password-reset link.
- ask you for a password, or sign in to anything as you.
- change one of your settings without asking you first.

Each thing you have switched on promises more on top of that:
- claude will never sign you out, or copy your sign-in files, or change that tool's own settings.

You can also switch these on later:
- handshake: Uses your school's job platform: finds school-only postings, follows employers, and notes career events. It needs you to be signed in to your school's job platform in your own browser.
- linkedin: Get noticed on LinkedIn: sends connection requests and writes short, relevant comments. It needs you to be signed in to LinkedIn in your own browser.
- yc: Keeps your startup-list profile visible and applies to matching startups with a short note, up to a weekly limit. It needs you to be signed in to the startup jobs platform in your own browser.
- codex: Codex, through its own command-line tool. It needs you to be signed in to the Codex tool.
- openai_compatible: Another model service that you host yourself or already pay for. It needs a key from that service, kept in your computer's environment.
- fake: A stand-in that makes up answers in a fixed, predictable way. It needs no account and no sign-in.

What name should go on your applications?
  … (2 lines of default and consequence omitted)
YOU > Sam Example
Which email address should I use on applications?
  … (2 lines of default and consequence omitted)
YOU > sam@example.test
And a phone number for the forms that ask?
  … (2 lines of default and consequence omitted)
YOU > +1 555 0100 222
Where are you based? (city and state or country)
  … (2 lines of default and consequence omitted)
YOU > Austin, TX
Where is your CV? Give me the path to the file and I will attach exactly that one.
  … (2 lines of default and consequence omitted)
YOU > (use the default)
What kind of jobs do you want most? Give me a few job titles.
  … (4 lines of default and consequence omitted)
YOU > Machine Learning Engineer, AI Engineer
Any jobs you would still take, but are not your first choice?
  … (3 lines of default and consequence omitted)
YOU > Software Engineer, Data Analyst
Anything you never want, even if it matches otherwise?
  … (3 lines of default and consequence omitted)
YOU > Sales, Technician
Which cities would you work in?
  … (2 lines of default and consequence omitted)
YOU > Austin, New York, Remote
Is a job that is fully remote fine?
  … (3 lines of default and consequence omitted)
YOU > yes
Will you need a company to sponsor a work visa, now or later?
  … (4 lines of default and consequence omitted)
YOU > yes
How many years of experience do you have, roughly?
  … (4 lines of default and consequence omitted)
YOU > about 2
Any companies you never want to apply to?
  … (3 lines of default and consequence omitted)
YOU > Umbrella Logistics
Any companies I should find but leave for you to decide about?
  … (2 lines of default and consequence omitted)
YOU > Stark Grid
How far back should I look for openings, in days?
  … (2 lines of default and consequence omitted)
YOU > 30
Which companies' job pages should I watch? Use the short name from their careers link, and add ':lever' or ':ashby' if you know they use one of those.
  … (2 lines of default and consequence omitted)
YOU > acme-robotics, globex-systems:lever, northwind-analytics:ashby
Switch on 'handshake'? Uses your school's job platform: finds school-only postings, follows employers, and notes career events. Runs in the evening. It searches the school view of the jobs board for roles that match what you asked for, including postings only students at your school can see, follows employers you care about, and records career events. It never clicks Apply, never submits an external form, never edits your profile or your documents, and never signs in or out. School-only postings it finds go through exactly the same reading and checking as every other job. If it is allowed to reply to recruiters, every reply is checked before it is sent, and a blocked reply is dropped rather than reworded. It needs you to be signed in to your school's job platform in your own browser. I check by opening the jobs page and telling you which account it sees. It will never apply or submit anything; edit your profile or your documents; sign you in or out; ask for another verification email.
  … (2 lines of default and consequence omitted)
YOU > yes
Switch on 'linkedin'? Get noticed on LinkedIn: sends connection requests and writes short, relevant comments. Runs in the evening. It finds hiring posts and people working in the areas you care about, sends connection requests with a short note, and comments on posts where a comment makes sense. It never sends direct messages, never reads your inbox, never posts anything other than those comments, never edits your profile, and stops immediately if LinkedIn shows a warning, a check, or a limit. Every message is checked before it is sent, and a blocked message is dropped rather than reworded. It needs you to be signed in to LinkedIn in your own browser. I check by opening your feed without changing anything and telling you the account name it sees. It will never sign you in or out; change your password; edit your profile; read or send direct messages.
  … (2 lines of default and consequence omitted)
YOU > yes
Switch on 'yc'? Keeps your startup-list profile visible and applies to matching startups with a short note, up to a weekly limit. Checks that your profile still shows you as looking, finds startups that match what you asked for, and sends an application inside that platform with a short, truthful note — never more than the weekly number you choose. It replies to founders who write back. It never edits your profile text without asking, never goes over the weekly limit, never messages anyone outside the platform, and never attaches your resume unless a founder asks for it. Every note is checked before it is sent, and a blocked note is dropped rather than reworded. It needs you to be signed in to the startup jobs platform in your own browser. I check by opening your profile and telling you whether it shows you as looking. It will never edit your profile text without asking; go over the weekly limit; sign you in or out; attach your resume unless a founder asks.
  … (2 lines of default and consequence omitted)
YOU > yes
Switch on 'claude'? Claude, through the Claude Code command-line tool. Haiku is the quick, cheap one and does the bulk reading; Sonnet is the middle option; Opus is the careful one used for reviewing and planning. It needs you to be signed in to Claude in the Claude Code tool. Sign in once in that tool; I only ever check that it says you are signed in. It will never sign you out; copy your sign-in files; change that tool's own settings.
  … (2 lines of default and consequence omitted)
YOU > yes
Switch on 'codex'? Codex, through its own command-line tool. It needs you to be signed in to the Codex tool. Sign in once in that tool; I only ever check that it says you are signed in. It will never sign you out; copy your sign-in files.
  … (2 lines of default and consequence omitted)
YOU > (use the default)
Switch on 'openai_compatible'? Another model service that you host yourself or already pay for. It needs a key from that service, kept in your computer's environment. Keep the key in your computer's environment and tell me the name you gave it. The key itself is never written into your settings. It will never write your key into a file; show your key in any message.
  … (2 lines of default and consequence omitted)
YOU > (use the default)
Switch on 'fake'? A stand-in that makes up answers in a fixed, predictable way. Useful for a practice run. It is not a real model and should not be left on. It needs no account and no sign-in.
  … (2 lines of default and consequence omitted)
YOU > yes
Where should your daily summary go? (blank means the same address)
  … (2 lines of default and consequence omitted)
YOU > (use the default)
What time would you like it?
  … (2 lines of default and consequence omitted)
YOU > 7:30am
Would you like plain updates, or all the technical detail? (simple/technical)
  … (2 lines of default and consequence omitted)
YOU > simple
Which school's job platform should I use?
  … (2 lines of default and consequence omitted)
YOU > Example University
How many connection requests a week feel comfortable?
  … (2 lines of default and consequence omitted)
YOU > (use the default)
How many startup applications a week?
  … (2 lines of default and consequence omitted)
YOU > (use the default)

Last part. Forms ask the same few questions over and over, so let us write your answers down once. Anything you leave blank will stop and ask you instead of being guessed at, and I will never answer a national insurance or date-of-birth question by myself.
Forms ask: are you allowed to work in the country you are applying in?
  … (2 lines of default and consequence omitted)
YOU > (use the default)
And: will you need the company to sponsor a visa, now or in future?
  … (2 lines of default and consequence omitted)
YOU > (use the default)
Would you move for the right job?
  … (2 lines of default and consequence omitted)
YOU > (use the default)
What is the earliest date you could start? (like 2027-06-01)
  … (2 lines of default and consequence omitted)
YOU > (use the default)
If a form insists on a salary expectation, what should I put?
  … (2 lines of default and consequence omitted)
YOU > (use the default)
And when they ask how you heard about the job?
  … (2 lines of default and consequence omitted)
YOU > (use the default)

Here is everything, in plain words:

You on applications: Sam Example · sam@example.test · +1 555 0100 222 · Austin, TX.
The CV I will attach: you have not told me where it is yet.
Form answers I will have ready: whether you may work there, whether you need sponsorship, whether you would move, what to say about salary, how you heard about the job.
Jobs I will go after first: Machine Learning Engineer, AI Engineer.
Jobs I will apply to after those: Software Engineer, Data Analyst.
Jobs I will never apply to: Sales, Technician.
Where: Austin, New York, Remote, and fully remote jobs count too.
Work permission: you need a company to sponsor a visa, so I skip a job only when the posting says it rules you out, and I always keep that sentence.
Experience: I skip a job only if it clearly requires more than 2 years.
Companies I will avoid completely: Umbrella Logistics.
Companies I will hold for your decision: Stark Grid.
How far back I look: 30 days.
Company job pages I will watch: acme-robotics, globex-systems, northwind-analytics.
Helpers switched on: handshake, linkedin, yc.
Models switched on: claude, fake.
Your daily summary: 07:30 on weekdays, to sam@example.test.
How much detail you see: simple.

Nothing is sent, submitted or posted until you switch that on separately. I will never apply to the same job twice, make up an answer on a form, reset a password, or change one of these settings without asking you.
YOU > yes
I have written down 5 answers to the questions forms ask. Anything not on that list stops and asks you.
Saved. Your answers are written down, and you can change any of them whenever you like.
In words: I will look for Machine Learning Engineer, AI Engineer first, skip anything that clearly rules you out and keep the sentence that did it, and apply to the newest ones first.
Helpers switched on: handshake, linkedin, yc.
You will get one summary a day at 07:30.
One thing: I do not know where your CV is yet. Tell me where it is and I will attach exactly that file, and never a different version.
One thing: The practice stand-in is switched on, which makes up its answers. Switch on a real model before you rely on anything it says.
Now the sign-ins. One at a time, and you are the only one who ever signs in to anything. I never see a password.

The email account you put on applications.
Why I need it: it is how I know which applications really arrived, and how I spot an interview invitation
What you do: open that site in your own browser and sign in as you normally would, then tell me 'done'. I never ask for your password and never sign in as you.
How I check: I read the newest subject lines back to you, and nothing else.
I will never send, reply to, delete or file your mail; follow a password-reset link; write down a verification code.
Tell me 'done' when you are signed in, or press enter to leave it for later.
  … (2 lines of default and consequence omitted)
YOU > done
mailbox: you are signed in, but I have no way to read that mailbox yet, so applications will stay 'sent' rather than 'confirmed'.

Your school's job platform.
Why I need it: it is what 'handshake' works with: Uses your school's job platform: finds school-only postings, follows employers, and notes career events.
What you do: open that site in your own browser and sign in as you normally would, then tell me 'done'. I never ask for your password and never sign in as you.
How I check: I check by opening the jobs page and telling you which account it sees.
I will never apply or submit anything; edit your profile or your documents; sign you in or out; ask for another verification email.
Tell me 'done' when you are signed in, or press enter to leave it for later.
  … (2 lines of default and consequence omitted)
YOU > done
handshake: set up, but I have not watched you sign in, so I will not call it ready. To be sure, i check by opening the jobs page and telling you which account it sees.

LinkedIn.
Why I need it: it is what 'linkedin' works with: Get noticed on LinkedIn: sends connection requests and writes short, relevant comments.
What you do: open that site in your own browser and sign in as you normally would, then tell me 'done'. I never ask for your password and never sign in as you.
How I check: I check by opening your feed without changing anything and telling you the account name it sees.
I will never sign you in or out; change your password; edit your profile; read or send direct messages.
Tell me 'done' when you are signed in, or press enter to leave it for later.
  … (2 lines of default and consequence omitted)
YOU > done
linkedin: set up, but I have not watched you sign in, so I will not call it ready. To be sure, i check by opening your feed without changing anything and telling you the account name it sees.

Startup jobs platform account.
Why I need it: it is what 'yc' works with: Keeps your startup-list profile visible and applies to matching startups with a short note, up to a weekly limit.
What you do: open that site in your own browser and sign in as you normally would, then tell me 'done'. I never ask for your password and never sign in as you.
How I check: I check by opening your profile and telling you whether it shows you as looking.
I will never edit your profile text without asking; go over the weekly limit; sign you in or out; attach your resume unless a founder asks.
Tell me 'done' when you are signed in, or press enter to leave it for later.
  … (2 lines of default and consequence omitted)
YOU > skip
yc: left for later, so its part stays switched off.

your Claude account, in the Claude Code tool.
Why I need it: it is what 'claude' works with: Claude, through the Claude Code command-line tool.
What you do: open that site in your own browser and sign in as you normally would, then tell me 'done'. I never ask for your password and never sign in as you.
How I check: Sign in once in that tool; I only ever check that it says you are signed in.
I will never sign you out; copy your sign-in files; change that tool's own settings.
Tell me 'done' when you are signed in, or press enter to leave it for later.
  … (2 lines of default and consequence omitted)
YOU > done
claude: ready — the tool itself says you are signed in.

Ready: claude.
Still to do, and what stays off until then:
  - mailbox: you are signed in, but I have no way to read that mailbox yet, so applications will stay 'sent' rather than 'confirmed'.
  - handshake: set up, but I have not watched you sign in, so I will not call it ready. To be sure, i check by opening the jobs page and telling you which account it sees.
  - linkedin: set up, but I have not watched you sign in, so I will not call it ready. To be sure, i check by opening your feed without changing anything and telling you the account name it sees.
  - yc: left for later, so its part stays switched off.
```

### Is everything ready?

```console
$ jobpilot doctor
Settings: fine (~/your-folder/preferences.yaml).
My own files: fine (~/.jobpilot).
Your application record: fine (0 jobs on file).
Your answers: fine (5 answers written down).
Your CV: I do not know where it is, so applications needing one will wait.
Model for reading job descriptions: fine (with 2 spares if it is busy).
Model for reviewing and planning: fine (with 2 spares if it is busy).
Model for working in a browser: fine (with 2 spares if it is busy).
Room to work: fine.
Helper 'handshake': on.
Helper 'linkedin': on.
Helper 'yc': on.
Employer sign-ups: nothing waiting for you.
Timetable: 19 routines, all of them ready to run.
Health: nothing looks stuck.
Permissions: nothing may be sent or submitted yet.

Everything checks out.
```

### Looking for jobs (a practice run first)

```console
$ jobpilot run search --dry-run
I looked around and found 7 new jobs worth reading.
This was a practice run, so I did not write anything down.
```

### Looking for jobs, for real

```console
$ jobpilot run search
I looked around and found 7 new jobs worth reading.
I added 7 jobs to my list.
```

### Reading the descriptions

```console
$ jobpilot run screen
I read 7 jobs: 4 look worth applying to and 3 rule you out.
For example, I would apply to: Acme Robotics — Machine Learning Engineer; Globex Systems — Software Engineer, New Grad.
I skipped Acme Robotics — AI Engineer, Perception, because the posting says: "this role is not eligible for visa sponsorship."
```

### Working through the list, sending nothing

```console
$ jobpilot run apply --dry-run
I worked through 1 application, 1 is ready to go whenever you say so.
```

### How is it going?

```console
$ jobpilot status
So far: 0 applications confirmed, 0 waiting for a confirmation, 4 jobs still on my list.

What happens by itself:
- Every morning I look for new jobs that match what you asked for.
- Right after that I read each new job description and decide whether it is worth applying to.
- Every weekday at 7:30am you get one email with what I did and anything that needs you.
- On weekday mornings I write up any messages worth sending, for you to look over. I send none of them.
- On weekdays between half past nine and six I work through the list and fill in applications.
- Overnight I keep working through the list, so the morning starts with it already shorter.
- Each morning I remind you about any test or interview coming up.
- And again in the evening, so a deadline is never a surprise.
- Through the day I read your mail for replies, tests and interview invitations. I only ever read it.
- Late each morning I check that everything I found in the morning really reached my list.
- Every hour I check that nothing is quietly stuck, and tell you if something needs you.
- Each evening I check your mailbox for confirmations, so we know which applications really arrived.
- At the end of the day I look at how it went, and bring you any suggestion worth making.
- Now and then I tidy away old copies of your records, so they do not fill up your disk.
- Once a week, on Monday morning, I go over the whole week with you and suggest what to change. I never change your settings without asking.
- Every evening I check your school's job platform for postings only you can see.
- Every evening I spend a little time making you more visible on LinkedIn.
- Every evening I look at the startup list and, up to your weekly limit, apply with a short note.
- I tell you how many startup applications are left in this week's allowance.
(All times are America/New_York time.)

What is switched on:
- handshake (on): Uses your school's job platform: finds school-only postings, follows employers, and notes career events.
- linkedin (on): Get noticed on LinkedIn: sends connection requests and writes short, relevant comments.
- yc (on): Keeps your startup-list profile visible and applies to matching startups with a short note, up to a weekly limit.
- claude (on): Claude, through the Claude Code command-line tool.
- codex (off): Codex, through its own command-line tool.
- openai_compatible (off): Another model service that you host yourself or already pay for.
- fake (on): A stand-in that makes up answers in a fixed, predictable way.
```

### Today's summary

```console
$ jobpilot digest
Your job search — Tuesday 10 November

Today: 4 new matches found

Still on my list: 4 jobs to apply to.
```

### Changing something in your own words

```console
$ jobpilot ask "also treat data scientist roles as a first choice"
I would also treat data scientist roles as a first choice:
- the jobs I go after first: now Machine Learning Engineer, AI Engineer; would become Machine Learning Engineer, AI Engineer, Data Scientist.

What you would notice: A few more jobs each morning, and they go out before the others.

I have changed nothing yet. Say 'jobpilot approve your-request' and I will.
```

### …and saying yes to it

```console
$ jobpilot approve your-request
Done. Here is what changed:
- the jobs I go after first: was Machine Learning Engineer, AI Engineer; now Machine Learning Engineer, AI Engineer, Data Scientist.
I will use the new setting from the next time I look for jobs.
```

### What the timetable would do, without doing it

```console
$ jobpilot routines run-due --dry-run
(practice) Every morning I look for new jobs that match what you asked for.
(practice) Every weekday at 7:30am you get one email with what I did and anything that needs you.
(practice) Through the day I read your mail for replies, tests and interview invitations. I only ever read it.
(practice) Every hour I check that nothing is quietly stuck, and tell you if something needs you.
(practice) Now and then I tidy away old copies of your records, so they do not fill up your disk.
```

### Letting it run by itself

```console
$ jobpilot routines list --technical
What happens by itself:
- Every morning I look for new jobs that match what you asked for.
- Right after that I read each new job description and decide whether it is worth applying to.
- Every weekday at 7:30am you get one email with what I did and anything that needs you.
- On weekday mornings I write up any messages worth sending, for you to look over. I send none of them.
- On weekdays between half past nine and six I work through the list and fill in applications.
- Overnight I keep working through the list, so the morning starts with it already shorter.
- Each morning I remind you about any test or interview coming up.
- And again in the evening, so a deadline is never a surprise.
- Through the day I read your mail for replies, tests and interview invitations. I only ever read it.
- Late each morning I check that everything I found in the morning really reached my list.
- Every hour I check that nothing is quietly stuck, and tell you if something needs you.
- Each evening I check your mailbox for confirmations, so we know which applications really arrived.
- At the end of the day I look at how it went, and bring you any suggestion worth making.
- Now and then I tidy away old copies of your records, so they do not fill up your disk.
- Once a week, on Monday morning, I go over the whole week with you and suggest what to change. I never change your settings without asking.
- Every evening I check your school's job platform for postings only you can see.
- Every evening I spend a little time making you more visible on LinkedIn.
- Every evening I look at the startup list and, up to your weekly limit, apply with a short note.
- I tell you how many startup applications are left in this week's allowance.
(All times are America/New_York time.)

Due right now: 5 things.

To let this run by itself, add one line to your crontab:
*/10 * * * * cd ~/your-folder && jobpilot routines run-due >> ~/.jobpilot/logs/cron.log 2>&1

Or, with systemd:
# ~/.config/systemd/user/jobpilot.service
[Service]
Type=oneshot
WorkingDirectory=~/your-folder
ExecStart=%h/.local/bin/jobpilot routines run-due

# ~/.config/systemd/user/jobpilot.timer
[Timer]
OnCalendar=*:0/10
Persistent=true
[Install]
WantedBy=timers.target
```

---

## Run 2 — nothing switched on (the core on its own)

### Setting up

```console
$ jobpilot start
Hello — I look for jobs you would want, apply to them, and tell you how it is going.

Here is what you are getting.

A small team works for you:
- a coordinator, which talks to you, and is the only one that does, so you are not messaged from five places.
- a searcher, which looks for new openings and checks them against what you asked for.
- an applier, which fills in application forms and records every single one, so nothing is applied to twice.
- a mail reader, which checks the inbox you use for applications, read-only, to see which ones arrived.

These models do the thinking:
- reading job descriptions and deciding what is worth applying to: Claude Haiku (quick and cheap)
- reviewing, planning and double-checking its own work: Claude Opus (the careful one)
- working inside a web page, for the helpers that need a browser: Claude Haiku (quick and cheap)

This happens by itself:
- Every morning I look for new jobs that match what you asked for.
- Right after that I read each new job description and decide whether it is worth applying to.
- Every weekday at 8am you get one email with what I did and anything that needs you.
- On weekday mornings I write up any messages worth sending, for you to look over. I send none of them.
- On weekdays between half past nine and six I work through the list and fill in applications.
- Overnight I keep working through the list, so the morning starts with it already shorter.
- Each morning I remind you about any test or interview coming up.
- And again in the evening, so a deadline is never a surprise.
- Through the day I read your mail for replies, tests and interview invitations. I only ever read it.
- Late each morning I check that everything I found in the morning really reached my list.
- Every hour I check that nothing is quietly stuck, and tell you if something needs you.
- Each evening I check your mailbox for confirmations, so we know which applications really arrived.
- At the end of the day I look at how it went, and bring you any suggestion worth making.
- Now and then I tidy away old copies of your records, so they do not fill up your disk.
- Once a week, on Monday morning, I go over the whole week with you and suggest what to change. I never change your settings without asking.
(All times are America/New_York time.)

These are the things only you can do:
- a few details that go on application forms (your name, an email address, a phone number);
- the answers to form questions I do not have, which I always ask about rather than guess;
- saying yes before I send anything, submit anything, or change one of your settings.
- signing in to Claude in the Claude Code tool. Sign in once in that tool; I only ever check that it says you are signed in.

And these are the things I will never do:
- apply to the same job twice.
- make up an answer on a form.
- send a message, post a comment or submit a form without the matching permission switched on.
- reset a password, or follow a password-reset link.
- ask you for a password, or sign in to anything as you.
- change one of your settings without asking you first.

Each thing you have switched on promises more on top of that:
- claude will never sign you out, or copy your sign-in files, or change that tool's own settings.

You can also switch these on later:
- handshake: Uses your school's job platform: finds school-only postings, follows employers, and notes career events. It needs you to be signed in to your school's job platform in your own browser.
- linkedin: Get noticed on LinkedIn: sends connection requests and writes short, relevant comments. It needs you to be signed in to LinkedIn in your own browser.
- yc: Keeps your startup-list profile visible and applies to matching startups with a short note, up to a weekly limit. It needs you to be signed in to the startup jobs platform in your own browser.
- codex: Codex, through its own command-line tool. It needs you to be signed in to the Codex tool.
- openai_compatible: Another model service that you host yourself or already pay for. It needs a key from that service, kept in your computer's environment.
- fake: A stand-in that makes up answers in a fixed, predictable way. It needs no account and no sign-in.

What name should go on your applications?
  … (2 lines of default and consequence omitted)
YOU > Alex Sample
Which email address should I use on applications?
  … (2 lines of default and consequence omitted)
YOU > alex@example.test
And a phone number for the forms that ask?
  … (2 lines of default and consequence omitted)
YOU > (use the default)
Where are you based? (city and state or country)
  … (2 lines of default and consequence omitted)
YOU > Chicago, IL
Where is your CV? Give me the path to the file and I will attach exactly that one.
  … (2 lines of default and consequence omitted)
YOU > (use the default)
What kind of jobs do you want most? Give me a few job titles.
  … (4 lines of default and consequence omitted)
YOU > Data Analyst
Any jobs you would still take, but are not your first choice?
  … (3 lines of default and consequence omitted)
YOU > Business Analyst
Anything you never want, even if it matches otherwise?
  … (3 lines of default and consequence omitted)
YOU > Sales
Which cities would you work in?
  … (2 lines of default and consequence omitted)
YOU > Chicago
Is a job that is fully remote fine?
  … (3 lines of default and consequence omitted)
YOU > yes
Will you need a company to sponsor a work visa, now or later?
  … (4 lines of default and consequence omitted)
YOU > no
How many years of experience do you have, roughly?
  … (4 lines of default and consequence omitted)
YOU > 1
Any companies you never want to apply to?
  … (3 lines of default and consequence omitted)
YOU > none
Any companies I should find but leave for you to decide about?
  … (2 lines of default and consequence omitted)
YOU > none
How far back should I look for openings, in days?
  … (2 lines of default and consequence omitted)
YOU > 21
Which companies' job pages should I watch? Use the short name from their careers link, and add ':lever' or ':ashby' if you know they use one of those.
  … (2 lines of default and consequence omitted)
YOU > acme-robotics, globex-systems:lever
Switch on 'handshake'? Uses your school's job platform: finds school-only postings, follows employers, and notes career events. Runs in the evening. It searches the school view of the jobs board for roles that match what you asked for, including postings only students at your school can see, follows employers you care about, and records career events. It never clicks Apply, never submits an external form, never edits your profile or your documents, and never signs in or out. School-only postings it finds go through exactly the same reading and checking as every other job. If it is allowed to reply to recruiters, every reply is checked before it is sent, and a blocked reply is dropped rather than reworded. It needs you to be signed in to your school's job platform in your own browser. I check by opening the jobs page and telling you which account it sees. It will never apply or submit anything; edit your profile or your documents; sign you in or out; ask for another verification email.
  … (2 lines of default and consequence omitted)
YOU > no
Switch on 'linkedin'? Get noticed on LinkedIn: sends connection requests and writes short, relevant comments. Runs in the evening. It finds hiring posts and people working in the areas you care about, sends connection requests with a short note, and comments on posts where a comment makes sense. It never sends direct messages, never reads your inbox, never posts anything other than those comments, never edits your profile, and stops immediately if LinkedIn shows a warning, a check, or a limit. Every message is checked before it is sent, and a blocked message is dropped rather than reworded. It needs you to be signed in to LinkedIn in your own browser. I check by opening your feed without changing anything and telling you the account name it sees. It will never sign you in or out; change your password; edit your profile; read or send direct messages.
  … (2 lines of default and consequence omitted)
YOU > no
Switch on 'yc'? Keeps your startup-list profile visible and applies to matching startups with a short note, up to a weekly limit. Checks that your profile still shows you as looking, finds startups that match what you asked for, and sends an application inside that platform with a short, truthful note — never more than the weekly number you choose. It replies to founders who write back. It never edits your profile text without asking, never goes over the weekly limit, never messages anyone outside the platform, and never attaches your resume unless a founder asks for it. Every note is checked before it is sent, and a blocked note is dropped rather than reworded. It needs you to be signed in to the startup jobs platform in your own browser. I check by opening your profile and telling you whether it shows you as looking. It will never edit your profile text without asking; go over the weekly limit; sign you in or out; attach your resume unless a founder asks.
  … (2 lines of default and consequence omitted)
YOU > no
Switch on 'claude'? Claude, through the Claude Code command-line tool. Haiku is the quick, cheap one and does the bulk reading; Sonnet is the middle option; Opus is the careful one used for reviewing and planning. It needs you to be signed in to Claude in the Claude Code tool. Sign in once in that tool; I only ever check that it says you are signed in. It will never sign you out; copy your sign-in files; change that tool's own settings.
  … (2 lines of default and consequence omitted)
YOU > no
Switch on 'codex'? Codex, through its own command-line tool. It needs you to be signed in to the Codex tool. Sign in once in that tool; I only ever check that it says you are signed in. It will never sign you out; copy your sign-in files.
  … (2 lines of default and consequence omitted)
YOU > (use the default)
Switch on 'openai_compatible'? Another model service that you host yourself or already pay for. It needs a key from that service, kept in your computer's environment. Keep the key in your computer's environment and tell me the name you gave it. The key itself is never written into your settings. It will never write your key into a file; show your key in any message.
  … (2 lines of default and consequence omitted)
YOU > (use the default)
Switch on 'fake'? A stand-in that makes up answers in a fixed, predictable way. Useful for a practice run. It is not a real model and should not be left on. It needs no account and no sign-in.
  … (2 lines of default and consequence omitted)
YOU > yes
Where should your daily summary go? (blank means the same address)
  … (2 lines of default and consequence omitted)
YOU > (use the default)
What time would you like it?
  … (2 lines of default and consequence omitted)
YOU > 8am
Would you like plain updates, or all the technical detail? (simple/technical)
  … (2 lines of default and consequence omitted)
YOU > simple

Last part. Forms ask the same few questions over and over, so let us write your answers down once. Anything you leave blank will stop and ask you instead of being guessed at, and I will never answer a national insurance or date-of-birth question by myself.
Forms ask: are you allowed to work in the country you are applying in?
  … (2 lines of default and consequence omitted)
YOU > (use the default)
And: will you need the company to sponsor a visa, now or in future?
  … (2 lines of default and consequence omitted)
YOU > (use the default)
Would you move for the right job?
  … (2 lines of default and consequence omitted)
YOU > (use the default)
What is the earliest date you could start? (like 2027-06-01)
  … (2 lines of default and consequence omitted)
YOU > (use the default)
If a form insists on a salary expectation, what should I put?
  … (2 lines of default and consequence omitted)
YOU > (use the default)
And when they ask how you heard about the job?
  … (2 lines of default and consequence omitted)
YOU > (use the default)

Here is everything, in plain words:

You on applications: Alex Sample · alex@example.test · no phone number yet · Chicago, IL.
The CV I will attach: you have not told me where it is yet.
Form answers I will have ready: whether you may work there, whether you need sponsorship, whether you would move, what to say about salary, how you heard about the job.
Jobs I will go after first: Data Analyst.
Jobs I will apply to after those: Business Analyst.
Jobs I will never apply to: Sales.
Where: Chicago, and fully remote jobs count too.
Work permission: you do not need sponsorship, so nothing is skipped for visa reasons.
Experience: I skip a job only if it clearly requires more than 1 year.
Companies I will avoid completely: none.
Companies I will hold for your decision: none.
How far back I look: 21 days.
Company job pages I will watch: acme-robotics, globex-systems.
Helpers switched on: none.
Models switched on: fake.
Your daily summary: 08:00 on weekdays, to alex@example.test.
How much detail you see: simple.

Nothing is sent, submitted or posted until you switch that on separately. I will never apply to the same job twice, make up an answer on a form, reset a password, or change one of these settings without asking you.
YOU > yes
I have written down 5 answers to the questions forms ask. Anything not on that list stops and asks you.
Saved. Your answers are written down, and you can change any of them whenever you like.
In words: I will look for Data Analyst first, skip anything that clearly rules you out and keep the sentence that did it, and apply to the newest ones first.
Helpers switched on: none.
You will get one summary a day at 08:00.
One thing: I do not know where your CV is yet. Tell me where it is and I will attach exactly that file, and never a different version.
One thing: The practice stand-in is switched on, which makes up its answers. Switch on a real model before you rely on anything it says.
Now the sign-ins. One at a time, and you are the only one who ever signs in to anything. I never see a password.

The email account you put on applications.
Why I need it: it is how I know which applications really arrived, and how I spot an interview invitation
What you do: open that site in your own browser and sign in as you normally would, then tell me 'done'. I never ask for your password and never sign in as you.
How I check: I read the newest subject lines back to you, and nothing else.
I will never send, reply to, delete or file your mail; follow a password-reset link; write down a verification code.
Tell me 'done' when you are signed in, or press enter to leave it for later.
  … (2 lines of default and consequence omitted)
YOU > done
mailbox: you are signed in, but I have no way to read that mailbox yet, so applications will stay 'sent' rather than 'confirmed'.

Ready: nothing yet.
Still to do, and what stays off until then:
  - mailbox: you are signed in, but I have no way to read that mailbox yet, so applications will stay 'sent' rather than 'confirmed'.
```

### Is everything ready?

```console
$ jobpilot doctor
Settings: fine (~/your-folder/preferences.yaml).
My own files: fine (~/.jobpilot).
Your application record: fine (0 jobs on file).
Your answers: fine (5 answers written down).
Your CV: I do not know where it is, so applications needing one will wait.
Model for reading job descriptions: fine.
Model for reviewing and planning: fine.
Model for working in a browser: fine.
Room to work: fine.
Helper 'handshake': off.
Helper 'linkedin': off.
Helper 'yc': off.
Employer sign-ups: nothing waiting for you.
Timetable: 15 routines, all of them ready to run.
Health: nothing looks stuck.
Permissions: nothing may be sent or submitted yet.

Everything checks out.
```

### Looking for jobs (a practice run first)

```console
$ jobpilot run search --dry-run
I looked around and found 5 new jobs worth reading.
This was a practice run, so I did not write anything down.
```

### Looking for jobs, for real

```console
$ jobpilot run search
I looked around and found 5 new jobs worth reading.
I added 5 jobs to my list.
```

### Reading the descriptions

```console
$ jobpilot run screen
I read 5 jobs: 3 look worth applying to and 2 rule you out.
For example, I would apply to: Acme Robotics — Machine Learning Engineer; Globex Systems — Software Engineer, New Grad.
I skipped Acme Robotics — AI Engineer, Perception, because the posting says: "this role is not eligible for visa sponsorship."
```

### Working through the list, sending nothing

```console
$ jobpilot run apply --dry-run
I worked through 1 application, 1 is ready to go whenever you say so.
```

### How is it going?

```console
$ jobpilot status
So far: 0 applications confirmed, 0 waiting for a confirmation, 3 jobs still on my list.

What happens by itself:
- Every morning I look for new jobs that match what you asked for.
- Right after that I read each new job description and decide whether it is worth applying to.
- Every weekday at 8am you get one email with what I did and anything that needs you.
- On weekday mornings I write up any messages worth sending, for you to look over. I send none of them.
- On weekdays between half past nine and six I work through the list and fill in applications.
- Overnight I keep working through the list, so the morning starts with it already shorter.
- Each morning I remind you about any test or interview coming up.
- And again in the evening, so a deadline is never a surprise.
- Through the day I read your mail for replies, tests and interview invitations. I only ever read it.
- Late each morning I check that everything I found in the morning really reached my list.
- Every hour I check that nothing is quietly stuck, and tell you if something needs you.
- Each evening I check your mailbox for confirmations, so we know which applications really arrived.
- At the end of the day I look at how it went, and bring you any suggestion worth making.
- Now and then I tidy away old copies of your records, so they do not fill up your disk.
- Once a week, on Monday morning, I go over the whole week with you and suggest what to change. I never change your settings without asking.
(All times are America/New_York time.)

What is switched on:
- handshake (off): Uses your school's job platform: finds school-only postings, follows employers, and notes career events.
- linkedin (off): Get noticed on LinkedIn: sends connection requests and writes short, relevant comments.
- yc (off): Keeps your startup-list profile visible and applies to matching startups with a short note, up to a weekly limit.
- claude (off): Claude, through the Claude Code command-line tool.
- codex (off): Codex, through its own command-line tool.
- openai_compatible (off): Another model service that you host yourself or already pay for.
- fake (on): A stand-in that makes up answers in a fixed, predictable way.
```

### Today's summary

```console
$ jobpilot digest
Your job search — Tuesday 10 November

Today: 3 new matches found

Still on my list: 3 jobs to apply to.
```

---

## Regenerating this document

```console
$ python tools/record_sample_session.py
```
