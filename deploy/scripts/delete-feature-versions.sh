#!/usr/bin/env bash
# Delete feature-build versions of a Python package from Artifact Registry.
#
# Matches PEP 440 local / pre labels produced by resolve-version.sh:
#   {base}+fb.{branch}.{sha}
#   {base}.dev0+pr{N}.{sha}   (legacy)
#
# Usage:
#   ./deploy/scripts/delete-feature-versions.sh \
#     --package fast-flow --pr 1 [--branch feat/foo]
#
# Env defaults (Cloud Build):
#   GCP_PROJECT / PROJECT_ID, GCP_REGION / _REGION, PYTHON_ARTIFACT_REPO / _PYTHON_REPO
set -euo pipefail

PACKAGE=""
PR_NUMBER=""
BRANCH=""
PROJECT="${GCP_PROJECT:-${PROJECT_ID:-}}"
REGION="${GCP_REGION:-${_REGION:-us-central1}}"
REPO_ID="${PYTHON_ARTIFACT_REPO:-${_PYTHON_REPO:-lynko-python}}"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --package) PACKAGE="$2"; shift 2 ;;
    --pr) PR_NUMBER="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --project) PROJECT="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --repository) REPO_ID="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

: "${PACKAGE:?--package required}"
: "${PROJECT:?set GCP_PROJECT/PROJECT_ID or --project}"
PR_NUMBER="$(printf '%s' "${PR_NUMBER}" | sed -E 's/[^0-9]//g')"
[[ -n "${PR_NUMBER}" ]] || { echo "--pr required (digits)" >&2; exit 1; }

sanitize_branch() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/./g; s/^\.+//; s/\.+$//; s/\.{2,}/./g'
}

BRANCH_SAFE=""
if [[ -n "${BRANCH}" ]]; then
  BRANCH_SAFE="$(sanitize_branch "${BRANCH}")"
fi
PR_BRANCH_SAFE="$(sanitize_branch "pr${PR_NUMBER}")"

echo "delete-feature-versions: package=${PACKAGE} pr=${PR_NUMBER} branch=${BRANCH:--} branch_safe=${BRANCH_SAFE:--} project=${PROJECT} region=${REGION} repo=${REPO_ID}"

mapfile -t VERSIONS < <(
  gcloud artifacts versions list \
    --package="${PACKAGE}" \
    --repository="${REPO_ID}" \
    --location="${REGION}" \
    --project="${PROJECT}" \
    --format='value(name.basename())' 2>/dev/null || true
)

if [[ "${#VERSIONS[@]}" -eq 0 || -z "${VERSIONS[0]:-}" ]]; then
  echo "No versions listed for ${PACKAGE} (nothing to delete)"
  exit 0
fi

should_delete() {
  local ver="$1"
  # Legacy: 0.1.0.dev0+prN.sha  (require '.' after N so pr1 ≠ pr10)
  if [[ "${ver}" =~ \.dev0\+pr${PR_NUMBER}\. ]]; then
    return 0
  fi
  # Fallback branch label prN: 0.1.0+fb.prN.sha
  if [[ "${ver}" =~ \+fb\.pr${PR_NUMBER}\. ]]; then
    return 0
  fi
  # Named feature branch: 0.1.0+fb.{branch}.sha (fixed-string contains)
  if [[ -n "${BRANCH_SAFE}" && "${BRANCH_SAFE}" != "${PR_BRANCH_SAFE}" ]]; then
    local needle="+fb.${BRANCH_SAFE}."
    if [[ "${ver}" == *"${needle}"* ]]; then
      return 0
    fi
  fi
  return 1
}

DELETED=0
SKIPPED=0
for ver in "${VERSIONS[@]}"; do
  [[ -n "${ver}" ]] || continue
  if ! should_delete "${ver}"; then
    SKIPPED=$((SKIPPED + 1))
    continue
  fi
  if [[ "${DRY_RUN}" == "1" ]]; then
    echo "dry-run: would delete ${PACKAGE}==${ver}"
    DELETED=$((DELETED + 1))
    continue
  fi
  echo "Deleting ${PACKAGE}==${ver}"
  gcloud artifacts versions delete "${ver}" \
    --package="${PACKAGE}" \
    --repository="${REPO_ID}" \
    --location="${REGION}" \
    --project="${PROJECT}" \
    --delete-tags \
    --quiet
  DELETED=$((DELETED + 1))
done

echo "delete-feature-versions: deleted=${DELETED} skipped=${SKIPPED} total_listed=${#VERSIONS[@]}"
