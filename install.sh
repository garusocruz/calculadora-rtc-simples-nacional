#!/usr/bin/env bash
# Setup de desenvolvimento: .venv no repositório e dependências do Poetry.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT}"

if [[ ! -x .venv/bin/python || ! -f .venv/bin/activate ]]; then
  rm -rf .venv
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

if [[ -e .git && -f .pre-commit-config.yaml ]]; then
  git config --unset-all core.hooksPath 2>/dev/null || true
  poetry run pre-commit install --hook-type pre-commit --hook-type pre-push --hook-type commit-msg
  echo "OK: pre-commit, pre-push e commit-msg em $(git rev-parse --git-path hooks)"
fi

echo "OK: install complete"
echo "Em outro shell: source ${ROOT}/.venv/bin/activate"
echo "Equivalência: bash scripts/hooks/pre-push.sh"
