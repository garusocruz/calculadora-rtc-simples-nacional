#!/usr/bin/env bash
# Pattern checks. Usage: check-patterns.sh staged|all
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

MODE="${1:-staged}"
FAIL=0

list_files() {
  if [[ "${MODE}" == "staged" ]]; then
    git diff --cached --name-only --diff-filter=ACMR
  else
    git ls-files
  fi | grep -Ev '(^|/)\.venv/|(^|/)node_modules/|(^|/)\.ci/|(^|/)\.cache/|egg-info/' || true
}

echo "==> patterns (${MODE})"

FORBIDDEN_GREP='(^|/)\.env($|\.)|(^|/)terraform\.tfvars$|\.tfstate($|\.)|credentials\.json$|service[-_]?account.*\.json$|(^|/)id_rsa$|\.pem$'
while IFS= read -r f; do
  [[ -z "${f}" ]] && continue
  case "${f}" in
    *.example|*.sample) continue ;;
  esac
  if echo "${f}" | grep -Eq "${FORBIDDEN_GREP}"; then
    echo "FAIL: forbidden path staged/tracked: ${f}" >&2
    FAIL=1
  fi
done < <(list_files)

SECRET_GREP='(BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})'
while IFS= read -r f; do
  [[ -z "${f}" || ! -f "${f}" ]] && continue
  case "${f}" in
    *.md|docs/*|*.example|*.sample) continue ;;
  esac
  if grep -nE "${SECRET_GREP}" -- "${f}" >/dev/null 2>&1; then
    echo "FAIL: possible secret material in ${f}" >&2
    grep -nE "${SECRET_GREP}" -- "${f}" | head -5 >&2 || true
    FAIL=1
  fi
done < <(list_files)

while IFS= read -r f; do
  [[ -z "${f}" || ! -f "${f}" ]] && continue
  case "${f}" in
    *.sh)
      echo "==> bash -n ${f}"
      if ! bash -n "${f}"; then
        echo "FAIL: bash -n ${f}" >&2
        FAIL=1
      fi
      ;;
  esac
done < <(list_files)

if [[ "${FAIL}" -ne 0 ]]; then
  echo "pattern checks failed" >&2
  exit 1
fi
echo "OK: patterns"
