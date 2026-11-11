#!/bin/sh
# Prove the project can be cloned somewhere else, under a different name, and
# still work. This is the check that catches a hardcoded folder name, a path
# that only exists on the author's machine, or a file the package forgot to
# ship.
#
# It clones this working tree into a temporary directory with a DIFFERENT
# folder name, builds a fresh virtual environment, installs the project,
# runs the self-check, runs the whole suite, and scans the clone for machine
# paths.
#
# Usage: scripts/migration_check.sh [source-repo] [--keep]
#
#   source-repo   a path or file:// URL; defaults to this checkout
#   --keep        leave the clone behind for inspection
#
# Network: only pip may use it. Set JOBPILOT_PIP_SYSTEM_SITE=1 to build the
# virtual environment with --system-site-packages, which lets the install
# succeed with no network at all when the dependencies are already present.
set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
source=${1:-$here}
keep=${2:-}
case "$source" in --keep) source=$here; keep=--keep ;; esac

python=${PYTHON:-python3}
work=$(mktemp -d 2>/dev/null || mktemp -d -t jobpilot-migration)
# Deliberately not "jobpilot": the printed scheduler line must come from the
# real folder name, never from a guess.
clone="$work/some-other-folder-name"

cleanup() {
    status=$?
    if [ "$keep" = "--keep" ]; then
        echo "Clone left at $clone"
    else
        rm -rf "$work"
    fi
    exit "$status"
}
trap cleanup EXIT INT TERM

step() { printf '\n=== %s\n' "$1"; }

step "1/6 clone $source -> $clone"
git clone --quiet "$source" "$clone"

step "2/6 fresh virtual environment"
if [ "${JOBPILOT_PIP_SYSTEM_SITE:-0}" = "1" ]; then
    "$python" -m venv --system-site-packages "$clone/.venv"
else
    "$python" -m venv "$clone/.venv"
fi
bin="$clone/.venv/bin"

step "3/6 pip install -e .[dev]"
"$bin/python" -m pip install --quiet --disable-pip-version-check -e "$clone[dev]"

step "4/6 jobpilot doctor (offline, example settings, from an unrelated folder)"
# Run from the temporary root, not the clone, to prove nothing depends on the
# current directory.
cd "$work"
JOBPILOT_CONFIG="$clone/config/preferences.example.yaml" \
    JOBPILOT_DATA_DIR="$work/data" \
    JOBPILOT_TEST=1 \
    "$bin/jobpilot" doctor
JOBPILOT_CONFIG="$clone/config/preferences.example.yaml" \
    JOBPILOT_DATA_DIR="$work/data" \
    JOBPILOT_TEST=1 \
    "$bin/jobpilot" routines list --technical | tail -3

step "5/6 the whole test suite, inside the clone"
cd "$clone"
JOBPILOT_TEST=1 "$bin/python" -m pytest -q

step "6/6 sanitize scan of the clone"
"$bin/python" "$clone/scripts/sanitize_scan.py" "$clone"

printf '\nMigration check passed: the clone installs, checks out and tests clean.\n'
