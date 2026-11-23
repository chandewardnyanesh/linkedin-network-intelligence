#!/bin/sh
# Everything that has to pass before a release.
set -e
cd "$(dirname "$0")/.."

echo "== frontmatter =="
python3 scripts/check_frontmatter.py

echo
echo "== secrets and personal data =="
python3 scripts/check_no_secrets.py

echo
echo "== configuration =="
python3 -m lni config-check > /dev/null && echo "configuration loads"

echo
echo "== tests =="
python3 -m pytest -q

echo
echo "== evaluation cases =="
python3 -m evals.run_evals --quiet | tail -2
