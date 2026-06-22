#!/usr/bin/env bash
#
# ci.sh — run the same gates as .github/workflows/ci.yml, locally.
#
# So you can validate a change with zero dependence on GitHub Actions (e.g. when
# the Actions minute budget is exhausted — see ~/GitHub/LOCAL-FALLBACK.md). The
# four core gates mirror the `check` job; the Playwright e2e smoke (the `e2e`
# job) is opt-in.
#
# Usage:
#   scripts/ci.sh           lint + format-check + types + tests   (the `check` job)
#   scripts/ci.sh --e2e     also run the browser e2e smoke        (the `e2e` job)
#
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

run() { echo "==> $*"; "$@"; }

echo "==> uv sync --frozen"
uv sync --frozen

run uv run ruff check .
run uv run ruff format --check .
run uv run mypy src tests
run uv run pytest -q

if [ "${1:-}" = "--e2e" ]; then
  echo "==> e2e: installing Chromium"
  uv run playwright install --with-deps chromium
  echo "==> e2e: browser smoke"
  ODR_E2E=1 uv run pytest tests/web/test_e2e.py -q
fi

echo "==> All gates passed."
