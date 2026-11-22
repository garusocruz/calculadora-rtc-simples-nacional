#!/usr/bin/env bash
# pre-push: quality gates (patterns, pytest, Trivy) and the official equivalence suite.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"
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
