#!/bin/sh
# Run the unit suite. Engine modules need only the standard library.
# Browser modules need playwright plus a chromium build:
#   python3 -m pip install -r requirements-test.txt
#   python3 -m playwright install chromium
# Usage: ./run_checks.sh              all modules
#        ./run_checks.sh test_app     one module
set -eu
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
exec "$PYTHON" -m unittest "$@" -v
