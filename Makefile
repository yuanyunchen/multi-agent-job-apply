# Developer shortcuts. Everything here is offline and sends nothing.
#
# make setup      create a virtual environment and install in editable mode
# make test       run the whole suite with the test marker set
# make sanitize   check nothing personal or machine-specific is committed
# make doctor     run the self-check against the example settings
# make migration-check  clone, install and test this tree in a fresh folder
# make examples   run every example script offline

PYTHON ?= python3
VENV   ?= .venv
BIN     = $(VENV)/bin

.DEFAULT_GOAL := help
.PHONY: help setup test sanitize lint doctor migration-check examples clean

help:
	@grep -E '^# make ' Makefile | sed 's/^# //'

setup:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -e ".[dev]"
	@echo "Done. Next: $(BIN)/jobpilot setup"

test:
	JOBPILOT_TEST=1 $(BIN)/python -m pytest -q

# "lint-ish": the repository-hygiene scan. It is the check that matters here —
# no personal data, no machine paths, no leftover placeholders.
sanitize lint:
	$(PYTHON) scripts/sanitize_scan.py

doctor:
	JOBPILOT_CONFIG=config/preferences.example.yaml $(BIN)/jobpilot doctor

migration-check:
	scripts/migration_check.sh

examples:
	@set -e; for script in examples/*.py; do echo "== $$script"; $(BIN)/python "$$script" >/dev/null; done
	@set -e; for script in examples/*.sh; do echo "== $$script"; sh "$$script" >/dev/null; done
	@echo "All examples ran offline."

clean:
	rm -rf build dist src/*.egg-info .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
