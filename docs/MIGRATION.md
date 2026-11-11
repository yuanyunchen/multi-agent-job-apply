# Migration and portability

Everything here answers one question: **can somebody else clone this and run
it?** The honest way to find out is to clone it into a folder with a different
name, on a machine that knows nothing about the author, and watch what breaks.
That is what `scripts/migration_check.sh` does, and what the GitHub Actions
workflow (`.github/workflows/ci.yml`) does on every push and every pull
request.

---

## 1. Moving in

```bash
git clone https://github.com/yuanyunchen/multi-agent-job-apply my-job-search
cd my-job-search
python3 -m venv .venv && . .venv/bin/activate     # Python 3.10 or newer
pip install -e ".[dev]"
jobpilot setup           # the questions; nothing is sent or submitted
jobpilot logins          # you sign in, in your own browser
jobpilot doctor          # the self-check
```

The folder is called `my-job-search` above on purpose. Nothing in the project
cares what it is called:

- the project directory is found by looking **upward from the package** for the
  directory holding `pyproject.toml` and `config/` (`config.repo_root()`);
- `JOBPILOT_HOME` overrides that, for an installed copy whose files live
  somewhere else;
- the scheduler line is **generated** from that directory and your own data
  folder, so `jobpilot routines list --technical` prints a line that works;
- no command depends on the current working directory. `jobpilot doctor` run
  from anywhere at all is covered by a test.

## 2. Where your things live

Three kinds of file, in three places, for three different reasons.

| what | where | committed? |
|---|---|---|
| **Your settings** | `config/preferences.yaml`, or wherever `JOBPILOT_CONFIG` points | no, gitignored |
| **Your form answers, notes** | beside your settings (`answers.yaml`, `background.md`) | no, gitignored |
| **Your CV** | wherever you keep it; only the path is stored | never touched |
| **Your record of applications** | `paths.data_dir` (`~/.jobpilot` by default), or `JOBPILOT_DATA_DIR` | no, outside the checkout |
| **The project itself** | the checkout | yes |

Two rules behind that table:

- A relative path under `documents:` resolves **next to your settings file**,
  not next to the project. So moving your settings with `JOBPILOT_CONFIG`
  genuinely moves everything private, instead of leaving your answers inside a
  git checkout.
- Your record of applications lives **outside** the checkout by default, so
  deleting, re-cloning or updating the project cannot touch it.

```bash
export JOBPILOT_CONFIG=~/private/jobpilot/preferences.yaml
export JOBPILOT_DATA_DIR=~/private/jobpilot/data
# your answers are now at ~/private/jobpilot/answers.yaml
```

## 3. Changes from earlier layouts

If you have a checkout from before the restructure:

| was | is now | what to do |
|---|---|---|
| `jobpilot/` at the top level | `src/jobpilot/` | nothing — reinstall with `pip install -e .` |
| `config/routines.yaml` | `routines/routines.yaml` | nothing; the old location is still read |
| `documents.answers: config/answers.yaml` | `documents.answers: answers.yaml` | nothing; a leading `config/` next to a settings file already inside `config/` is understood |
| `apply.waves`, `tracker.tidy` in the timetable | `apply.pass`, `records.tidy` | only if you edited `routines.yaml` yourself |
| a hand-written cron line | `jobpilot routines list --technical` | re-copy the line; it now names your real folder |

Nothing in your record of applications changes. The statuses, the evidence
fields and the never-re-apply guard are all unchanged, and the writer has
always refused a status it does not recognise rather than guessing.

## 4. Running the check yourself

```bash
scripts/migration_check.sh              # this working tree
scripts/migration_check.sh /path/to/repo --keep   # another one, kept for a look
```

It does six things, and fails on any of them:

1. `git clone` into a temporary directory with a **different folder name**;
2. build a fresh virtual environment;
3. `pip install -e ".[dev]"` inside the clone;
4. `jobpilot doctor` **from an unrelated directory**, against the example
   settings, offline;
5. the whole test suite, inside the clone;
6. `scripts/sanitize_scan.py` over the clone — no machine paths, no personal
   data, no address outside the reserved example domains.

**If pip has no network**, set `JOBPILOT_PIP_SYSTEM_SITE=1`. The virtual
environment is then built with `--system-site-packages`, so an already-present
PyYAML and pytest are enough and pip has nothing to fetch. The check is
otherwise identical: the point is the clone, the folder name and the working
directory, not the download.

## 5. What would break portability

Things to avoid in a change, each of which this project checks for:

| mistake | what catches it |
|---|---|
| An absolute path in committed code or docs | `scripts/sanitize_scan.py`, `tests/test_repo_hygiene.py` |
| Assuming the folder is called anything | `test_the_cron_line_names_the_real_folder_not_a_guessed_one` |
| Assuming the current directory | `test_doctor_works_from_an_arbitrary_working_directory` |
| A file the package forgot to ship | the migration check installs the clone and runs its tests |
| A real email address or a personal word | the sanitize scan, in the suite and in CI |
| A template placeholder treated as a value | `config.has_placeholder`, and the scan |
| A timetable entry with nothing behind it | `test_every_routine_in_the_file_has_something_wired_up_to_do_it` |
| An example that quietly stopped working | `tests/test_examples.py` |

## 6. Taking your data with you

There is nothing to migrate but your own files, and they are all plain text:

```bash
cp -r ~/.jobpilot            ~/backup/      # your record, its copies, the logs
cp config/preferences.yaml   ~/backup/      # your settings
cp config/answers.yaml       ~/backup/      # your form answers
```

Your record is a JSON file. Point `JOBPILOT_DATA_DIR` at a folder containing it
and the new installation picks it up as it stands — including every piece of
evidence behind every decision, which is the reason it is kept in the first
place.
