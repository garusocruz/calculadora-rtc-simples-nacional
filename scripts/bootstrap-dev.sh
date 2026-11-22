#!/usr/bin/env bash
# One-time (or after clone) dev setup: .venv + Poetry + pre-commit hooks.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if [[ ! -d .venv ]]; then
  if command -v cenv >/dev/null 2>&1; then
    cenv
  else
    python3 -m venv .venv
  fi
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [[ ! -f poetry.toml ]]; then
  poetry config virtualenvs.in-project true --local
fi

poetry install --with dev --no-ansi
git config --unset-all core.hooksPath 2>/dev/null || true

if [[ -f .pre-commit-config.yaml ]]; then
  poetry run pre-commit install --hook-type pre-commit --hook-type pre-push --hook-type commit-msg
  echo "OK: pre-commit + pre-push + commit-msg in $(git rev-parse --git-dir)/hooks"
  echo "Verify: poetry run pre-commit run --all-files"
else
  echo "WARN: no .pre-commit-config.yaml — add template before pushing CI changes" >&2
  exit 1
fi

echo "OK: bootstrap complete — use 'venv' (or source .venv/bin/activate) in new shells"
echo ""
echo "GATE: before git commit — VIRTUAL_ENV must be ${ROOT}/.venv"
echo "      git commit must trigger .git/hooks/pre-commit (never --no-verify; see lynko-git-commit-push-gate)"
