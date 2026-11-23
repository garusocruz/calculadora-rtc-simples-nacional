#!/usr/bin/env bash
# pre-push: quality gates (patterns, pytest, Trivy) and the official equivalence suite.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"
set +e
bash "${ROOT}/scripts/hooks/audit-version.sh"
audit_code=$?
set -e
if [[ "${audit_code}" -eq 75 ]]; then
  if [[ "${LYNKO_VERSION_BUMP_PUSH:-}" == 1 ]]; then
    echo "FAIL: o bump de versão entrou em loop." >&2
    exit 1
  fi
  bump_branch="$(git rev-parse --abbrev-ref HEAD)"
  echo "── versão commitada; enviando ${bump_branch} ──"
  LYNKO_VERSION_BUMP_PUSH=1 git push origin "HEAD:${bump_branch}"
  inner_code=$?
  if [[ "${inner_code}" -ne 0 ]]; then
    exit "${inner_code}"
  fi
  echo "OK: a versão nova está em origin/${bump_branch}. O push original para aqui para não rebobinar o commit." >&2
  exit 1
fi
if [[ "${audit_code}" -ne 0 ]]; then
  exit "${audit_code}"
fi
export PATH="${HOME}/.asdf/shims:${HOME}/.local/bin:${PATH}"
CI_STEPS_DIR="$(mktemp -d "${TMPDIR:-/tmp}/calculadora-qg.XXXXXX")"
trap 'rm -rf "${CI_STEPS_DIR}" 2>/dev/null || true' EXIT
export CI_STEPS_DIR
export TRIVY_CACHE_DIR="${CI_STEPS_DIR}/trivy-cache"
export PYTEST_VENV="${CI_STEPS_DIR}/pytest-venv"
echo "── pre-push (calculadora-rtc-simples-nacional) ──"
bash "${ROOT}/scripts/ci-quality-gates.sh" local
bash "${ROOT}/scripts/equivalencia.sh"
echo "── pre-push OK ──"
