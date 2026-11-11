#!/bin/sh
# The whole first conversation, answered from a file instead of by a person.
#
# Nothing here touches your own settings or your own records: the answers are
# made up, the settings are written to a throwaway folder, and every command
# runs with the test marker set, which bolts every door to the real world.
#
# Usage: examples/01_setup_dry_run.sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
work=$(mktemp -d 2>/dev/null || mktemp -d -t jobpilot-example)
trap 'rm -rf "$work"' EXIT INT TERM

# Everything this example writes goes in here, and it is thrown away at the end.
export JOBPILOT_CONFIG="$work/preferences.yaml"
export JOBPILOT_DATA_DIR="$work/data"
export JOBPILOT_TEST=1
export PYTHONPATH="$root/src${PYTHONPATH:+:$PYTHONPATH}"

python="${PYTHON:-python3}"
run() { "$python" -m jobpilot "$@"; }

step() { printf '\n== %s\n\n' "$1"; }

cat > "$work/answers.yaml" <<'EOF'
# A made-up person. The friendly key names on the left are aliases; the real
# settings keys work here too.
name: Sam Example
email: sam@example.test
phone: "+1 555 0100"
location: New York, NY
core_roles: [Machine Learning Engineer, AI Engineer]
other_roles: [Software Engineer, Data Engineer]
never_roles: [Sales, Technician]
cities: [New York, Boston]
remote: yes
needs_sponsorship: yes
max_years: 2
never_companies: []
hold_companies: []
recency_days: 21
boards: [acme-robotics, globex-systems:lever]
digest_email: sam@example.test
digest_time: 8am
mode: simple
EOF

step "1. What is installed, and what runs by itself"
run start --explain-only --non-interactive

step "2. The questions, answered from a file"
run setup --answers "$work/answers.yaml" --force

step "3. The sign-ins, read out (nobody is here to answer, so nothing is claimed)"
run logins --non-interactive

step "4. The self-check"
run doctor

step "5. The timetable, in the person's own words"
run routines list

step "6. The timetable with the detail, including the one scheduler line"
run routines list --technical

step "7. A practice run, sending nothing"
run run search --dry-run
run run apply --dry-run

step "8. Today's summary"
run digest

printf '\nAll of that ran offline, wrote only to a throwaway folder, and sent nothing.\n'
printf 'Your own settings and records were never opened.\n'
