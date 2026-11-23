#!/usr/bin/env bash
# Cancel older QUEUED/WORKING/PENDING builds for the same trigger + ref scope.
# Mirrors GitHub Actions concurrency (cancel-in-progress) — see deploy/gcp/ci/triggers.yaml.
set -euo pipefail

env_label="${_ENVIRONMENT:-${_ENV:-}}"
if [[ "${env_label}" == "production" ]]; then
  echo "cancel-superseded-builds: skip (production)"
  exit 0
fi

if [[ "${_CANCEL_SUPERSEDED_BUILDS:-1}" == "0" ]]; then
  echo "cancel-superseded-builds: disabled via _CANCEL_SUPERSEDED_BUILDS=0"
  exit 0
fi

if [[ -z "${TRIGGER_NAME:-}" ]]; then
  echo "cancel-superseded-builds: skip (TRIGGER_NAME unset — manual submit?)"
  exit 0
fi

PROJECT="${PROJECT_ID:?}"
BUILD="${BUILD_ID:?}"
LOCATION="${LOCATION:-${_REGION:-us-central1}}"

scope=()
scope+=("substitutions.TRIGGER_NAME=\"${TRIGGER_NAME}\"")
if [[ -n "${_SERVICE_SUFFIX:-}" ]]; then
  scope+=("substitutions._SERVICE_SUFFIX=\"${_SERVICE_SUFFIX}\"")
elif [[ -n "${_PR_NUMBER:-}" ]]; then
  scope+=("substitutions._PR_NUMBER=\"${_PR_NUMBER}\"")
elif [[ -n "${REF_NAME:-}" ]]; then
  scope+=("substitutions.REF_NAME=\"${REF_NAME}\"")
fi

filter="$(IFS=' AND '; echo "${scope[*]}")"
filter="(${filter}) AND id!=\"${BUILD}\" AND (status=\"WORKING\" OR status=\"QUEUED\" OR status=\"PENDING\")"

echo "cancel-superseded-builds: region=${LOCATION} filter=${filter}"

ids=()
while IFS= read -r line; do
  [[ -n "${line}" ]] && ids+=("${line}")
done < <(
  gcloud builds list \
    --project="${PROJECT}" \
    --region="${LOCATION}" \
    --filter="${filter}" \
    --format='value(id)' \
    --sort-by=createTime 2>/dev/null || true
)

if [[ ${#ids[@]} -eq 0 ]]; then
  echo "cancel-superseded-builds: nothing to cancel"
  exit 0
fi

for id in "${ids[@]}"; do
  echo "cancel-superseded-builds: cancelling ${id}"
  gcloud builds cancel "${id}" --project="${PROJECT}" --region="${LOCATION}" --quiet || true
done

exit 0
