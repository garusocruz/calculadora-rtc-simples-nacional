#!/usr/bin/env bash
# Fail Cloud Build when any product step recorded a non-zero exit.
# Run last (no allowFailure). Steps with allowFailure must write .ci/steps/<id>.exit.
#
# Optional: PIPELINE_GATE_STEPS="quality-gates assemble-context docker-build ..."
# Default: every *.exit in CI_STEPS_DIR except cancel-superseded / report-pr / pipeline-gate.
set -euo pipefail

STEPS_DIR="${CI_STEPS_DIR:-/workspace/.ci/steps}"
EXIT_FILE="${CI_EXIT_FILE:-/workspace/.ci/exit_code}"
SKIP_REGEX='^(cancel-superseded-builds|report-pr|pipeline-gate)$'

code=0
steps=()
if [[ -n "${PIPELINE_GATE_STEPS:-}" ]]; then
  # shellcheck disable=SC2206
  steps=(${PIPELINE_GATE_STEPS})
else
  shopt -s nullglob
  for f in "${STEPS_DIR}"/*.exit; do
    step="$(basename "${f}" .exit)"
    [[ "${step}" =~ ${SKIP_REGEX} ]] && continue
    steps+=("${step}")
  done
  shopt -u nullglob
fi

if [[ ${#steps[@]} -eq 0 ]]; then
  echo "pipeline-gate: no steps to check (set PIPELINE_GATE_STEPS or run prior steps)" >&2
  exit 1
fi

for step in "${steps[@]}"; do
  f="${STEPS_DIR}/${step}.exit"
  if [[ ! -f "${f}" ]]; then
    echo "pipeline-gate: missing ${f}" >&2
    code=1
    continue
  fi
  s="$(tr -d '[:space:]' < "${f}" || true)"
  if [[ -z "${s}" || "${s}" != "0" ]]; then
    echo "pipeline-gate: ${step} failed (${s:-?})" >&2
    code=1
  fi
done

if [[ -f "${EXIT_FILE}" ]]; then
  e="$(tr -d '[:space:]' < "${EXIT_FILE}" || true)"
  if [[ -n "${e}" && "${e}" != "0" ]]; then
    code="${e}"
  fi
fi

echo "${code}" > "${EXIT_FILE}"
exit "${code}"
