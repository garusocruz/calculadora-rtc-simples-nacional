#!/usr/bin/env bash
# Resolve PEP 440 version for this lib repo (standalone).
#
# Scheme (requested) → PEP 440 encoding (public version must be numeric first):
#   feature  → fb.{branch}.{version}  ⇒  {version}+fb.{branch}.{sha}
#   rc       → rc.{branch}.{version}  ⇒  {version}+rc.{branch}.{sha}
#   production → {version}            ⇒  X.Y.Z (from tag or base)
#
# Looks for VERSION in repo root, else pyproject version base, else 0.1.0.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_NAME=""
PR_NUMBER=""
BRANCH=""
SHA=""
TAG=""
BASE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENV_NAME="$2"; shift 2 ;;
    --pr) PR_NUMBER="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --sha) SHA="$2"; shift 2 ;;
    --tag) TAG="$2"; shift 2 ;;
    --base) BASE="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "${BASE}" ]]; then
  if [[ -f "${ROOT}/VERSION" ]]; then
    BASE="$(grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' "${ROOT}/VERSION" | tail -1 | tr -d '[:space:]')"
  elif [[ -f "${ROOT}/../../VERSION" ]]; then
    BASE="$(grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' "${ROOT}/../../VERSION" | tail -1 | tr -d '[:space:]')"
  else
    BASE="$(python3 - <<PY
import re, pathlib
p = pathlib.Path("${ROOT}/pyproject.toml")
text = p.read_text(encoding="utf-8") if p.exists() else ""
m = re.search(r'(?m)^version\s*=\s*["\']([0-9]+\.[0-9]+\.[0-9]+)', text)
print(m.group(1) if m else "0.1.0")
PY
)"
  fi
fi
BASE="${BASE#v}"
if [[ ! "${BASE}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "base version must be X.Y.Z, got: ${BASE}" >&2
  exit 1
fi

SHA="${SHA:-unknown}"
SHA="${SHA:0:7}"
SHA_SAFE="$(printf '%s' "${SHA}" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+//g')"
[[ -n "${SHA_SAFE}" ]] || SHA_SAFE="unknown"

# PEP 440 local version labels: alphanumeric segments separated by dots.
sanitize_branch() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/./g; s/^\.+//; s/\.+$//; s/\.{2,}/./g'
}

resolve_branch_safe() {
  local raw="${BRANCH}"
  if [[ -z "${raw}" && -n "${PR_NUMBER}" ]]; then
    raw="pr${PR_NUMBER}"
  fi
  if [[ -z "${raw}" ]]; then
    echo ""
    return 0
  fi
  sanitize_branch "${raw}"
}

case "${ENV_NAME}" in
  feature|preview)
    BRANCH_SAFE="$(resolve_branch_safe)"
    if [[ -z "${BRANCH_SAFE}" ]]; then
      echo "--branch required for feature (or --pr as fallback name)" >&2
      exit 1
    fi
    # fb.{branch}.{version} → {version}+fb.{branch}.{sha}
    printf '%s+fb.%s.%s\n' "${BASE}" "${BRANCH_SAFE}" "${SHA_SAFE}"
    ;;
  rc|release-candidate|staging)
    if [[ -z "${BRANCH}" ]]; then
      BRANCH="main"
    fi
    BRANCH_SAFE="$(sanitize_branch "${BRANCH}")"
    if [[ -z "${BRANCH_SAFE}" ]]; then
      echo "--branch resolved empty for rc" >&2
      exit 1
    fi
    # rc.{branch}.{version} → {version}+rc.{branch}.{sha}
    printf '%s+rc.%s.%s\n' "${BASE}" "${BRANCH_SAFE}" "${SHA_SAFE}"
    ;;
  production|prod)
    if [[ -n "${TAG}" ]]; then BASE="${TAG#v}"; fi
    if [[ ! "${BASE}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
      echo "production version must be X.Y.Z" >&2
      exit 1
    fi
    printf '%s\n' "${BASE}"
    ;;
  *)
    echo "Usage: $0 --env feature|rc|production [--branch NAME] [--pr N] [--sha SHA] [--tag vX.Y.Z]" >&2
    exit 1
    ;;
esac
