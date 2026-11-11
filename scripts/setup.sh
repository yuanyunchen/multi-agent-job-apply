#!/bin/sh
# Install jobpilot into a virtual environment in this checkout.
#
# Nothing here signs in to anything, sends anything or submits anything. When
# it finishes it tells you the one command that starts the conversation.
#
# Usage: scripts/setup.sh [path-to-virtualenv]
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
venv=${1:-"$root/.venv"}
python=${PYTHON:-python3}

echo "Project folder: $root"
echo "Virtual environment: $venv"

"$python" -m venv "$venv"
"$venv/bin/python" -m pip install --quiet --upgrade pip
"$venv/bin/python" -m pip install --quiet -e "$root[dev]"

echo
echo "Installed. Checking the ground:"
JOBPILOT_CONFIG="$root/config/preferences.example.yaml" "$venv/bin/jobpilot" doctor || true

cat <<'EOF'

Next steps:
  . .venv/bin/activate
  jobpilot setup      # answer the questions; nothing is sent or submitted
  jobpilot logins     # you sign in, in your own browser; it only checks
EOF
