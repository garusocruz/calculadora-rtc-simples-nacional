#!/usr/bin/env bash
# Quality gates — Cloud Build + pre-push.
# Same checks as the other Lynko libs: patterns, pytest+coverage, Trivy.
# These libs do not apply Terraform; the triggers live in lynko-terraform.
#
# Usage:
#   ci-quality-gates.sh        # CB / strict
#   ci-quality-gates.sh local  # laptop
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
export PATH="${HOME}/.asdf/shims:${HOME}/.local/bin:/usr/local/bin:${PATH}"

MODE="${1:-cb}"
FAIL=0
COVERAGE_FAIL_UNDER="${COVERAGE_FAIL_UNDER:-80}"
TRIVY_VERSION="${TRIVY_VERSION:-v0.74.0}"
LIB_NAME="$(awk -F'"' '/^name = /{print $2; exit}' "${ROOT}/pyproject.toml")"

if [[ -n "${CI_STEPS_DIR:-}" ]]; then
  STEPS_DIR="${CI_STEPS_DIR}"
elif [[ -d /workspace && -w /workspace ]]; then
  STEPS_DIR="/workspace/.ci/steps"
else
  STEPS_DIR="${ROOT}/.ci/steps"
fi

SUMMARY_FILE="${QUALITY_SUMMARY_FILE:-${STEPS_DIR}/quality-gates.summary.md}"
LOG_FILE="${QUALITY_LOG_FILE:-${STEPS_DIR}/quality-gates.log}"
mkdir -p "${STEPS_DIR}"
: >"${LOG_FILE}"
: >"${SUMMARY_FILE}"

declare -a GATE_ROWS=()

log() { printf '%s\n' "$*" | tee -a "${LOG_FILE}" >&2; }
fail() { printf 'FAIL: %s\n' "$*" | tee -a "${LOG_FILE}" >&2; FAIL=1; }
record() { GATE_ROWS+=("$1|$2|$3"); }

run_gate() {
  local name="$1"
  shift
  log "==> ${name}"
  set +e
  "$@" >>"${LOG_FILE}" 2>&1
  local rc=$?
  set -e
  if [[ "${rc}" -eq 0 ]]; then
    record "${name}" "pass" "ok"
    log "OK: ${name}"
  else
    record "${name}" "fail" "exit ${rc}"
    fail "${name} (exit ${rc})"
  fi
}

run_selftests() {
  log "==> gate self-tests"
  local ok=1
  local required=(
    cloudbuild.yaml
    cloudbuild-prod.yaml
    trivy.yaml
    .trivyignore.yaml
    trivy-secret.yaml
    docs/quality-gates.md
    scripts/run-trivy-fs.sh
    scripts/ci-quality-gates.sh
    scripts/hooks/check-patterns.sh
    scripts/hooks/pre-commit.sh
    scripts/hooks/pre-push.sh
    scripts/equivalencia.sh
    deploy/scripts/publish-self.sh
    deploy/terraform/main.tf
  )
  local path
  for path in "${required[@]}"; do
    [[ -f "${ROOT}/${path}" ]] || ok=0
  done
  if [[ "${ok}" -eq 1 ]]; then
    record "self-tests" "pass" "ok"
    log "OK: self-tests"
  else
    record "self-tests" "fail" "required files/path checks"
    fail "self-tests"
  fi
}

run_patterns() {
  if [[ ! -f "${ROOT}/scripts/hooks/check-patterns.sh" ]]; then
    record "patterns" "fail" "script missing"
    fail "scripts/hooks/check-patterns.sh missing"
    return
  fi
  run_gate "patterns" bash "${ROOT}/scripts/hooks/check-patterns.sh" all
}

run_fmt() {
  record "terraform fmt" "skip" "esta lib não aplica Terraform"
  log "skip terraform fmt"
}

run_validate() {
  record "terraform validate" "skip" "esta lib não aplica Terraform"
  log "skip terraform validate"
}

PYTEST_COV=""

ensure_pytest_python() {
  if [[ -x "${ROOT}/.venv/bin/python" ]]; then
    printf '%s' "${ROOT}/.venv/bin/python"
    return 0
  fi
  local venv="${PYTEST_VENV:-}"
  if [[ -z "${venv}" ]]; then
    if [[ -d /workspace && -w /workspace ]]; then
      venv="/workspace/.ci/pytest-venv"
    else
      venv="${ROOT}/.ci/pytest-venv"
    fi
  fi
  if [[ ! -x "${venv}/bin/python" ]]; then
    python3 -m venv "${venv}"
  fi
  printf '%s' "${venv}/bin/python"
}

run_pytest() {
  if [[ "${SKIP_PYTEST:-0}" == "1" ]]; then
    record "pytest" "skip" "SKIP_PYTEST=1"
    return
  fi
  local cache_db="${ROOT}/.cache/oficial/java/calculadora/db/calculadora-pro.db"
  if [[ -z "${CALC_DB:-}" && -f "${cache_db}" ]]; then
    export CALC_DB="${cache_db}"
    log "pytest usa o banco da equivalência"
  fi
  log "==> pytest + coverage (fail-under=${COVERAGE_FAIL_UNDER})"
  local py
  if ! py="$(ensure_pytest_python)"; then
    record "pytest" "fail" "venv unavailable"
    fail "pytest venv unavailable"
    return
  fi
  if ! "${py}" -c 'import pytest,pytest_cov' >/dev/null 2>&1; then
    log "==> installing the package, pytest and pytest-cov"
    if ! "${py}" -m pip install -q -e "${ROOT}" 'pytest>=7' 'pytest-cov>=4' >>"${LOG_FILE}" 2>&1; then
      tail -n 30 "${LOG_FILE}" >&2 || true
      record "pytest" "fail" "pip install failed"
      fail "pytest pip install failed"
      return
    fi
  fi
  local out rc=0
  set +e
  out="$("${py}" -m pytest -q 2>&1)"
  rc=$?
  set -e
  printf '%s\n' "${out}" >>"${LOG_FILE}"
  PYTEST_COV="$(printf '%s\n' "${out}" | sed -nE 's/^TOTAL[[:space:]]+[0-9]+[[:space:]]+[0-9]+[[:space:]]+([0-9]+)%/\1/p' | tail -n1)"
  if [[ -n "${PYTEST_COV}" ]]; then
    log "pytest coverage: ${PYTEST_COV}% (fail-under=${COVERAGE_FAIL_UNDER})"
  fi
  if [[ "${rc}" -eq 0 ]]; then
    local detail="ok"
    [[ -n "${PYTEST_COV}" ]] && detail="${PYTEST_COV}% (fail-under ${COVERAGE_FAIL_UNDER})"
    record "pytest" "pass" "${detail}"
    log "OK: pytest"
  else
    local detail="exit ${rc}"
    [[ -n "${PYTEST_COV}" ]] && detail="${PYTEST_COV}% (fail-under ${COVERAGE_FAIL_UNDER})"
    record "pytest" "fail" "${detail}"
    fail "pytest (exit ${rc})"
  fi
}

TRIVY_CMD=()
TRIVY_CRITICAL="" TRIVY_HIGH="" TRIVY_MEDIUM="" TRIVY_LOW="" TRIVY_UNKNOWN="" TRIVY_TOTAL="" TRIVY_COVERAGE=""

ensure_trivy() {
  if [[ ! -x "${ROOT}/scripts/run-trivy-fs.sh" ]]; then
    log "scripts/run-trivy-fs.sh missing"
    return 1
  fi
  TRIVY_CMD=(bash "${ROOT}/scripts/run-trivy-fs.sh" "${ROOT}")
  log "trivy via ${TRIVY_CMD[*]} (image docker.io/aquasec/trivy:${TRIVY_VERSION#v})"
  return 0
}

parse_trivy_json() {
  local json_file="$1"
  [[ -f "${json_file}" ]] || return 1
  local parsed
  parsed="$(python3 -c '
import json,sys
path=sys.argv[1]
with open(path) as f:
    data=json.load(f)
counts={"CRITICAL":0,"HIGH":0,"MEDIUM":0,"LOW":0,"UNKNOWN":0}
for result in data.get("Results") or []:
    for key in ("Vulnerabilities","Misconfigurations","Secrets","Licenses"):
        for item in result.get(key) or []:
            sev=(item.get("Severity") or item.get("severity") or "UNKNOWN").upper()
            if sev not in counts:
                sev="UNKNOWN"
            counts[sev]+=1
total=sum(counts.values())
clean=counts["CRITICAL"]+counts["HIGH"]
cov = 100.0 if clean == 0 else 0.0
print(counts["CRITICAL"], counts["HIGH"], counts["MEDIUM"], counts["LOW"], counts["UNKNOWN"], total, f"{cov:.1f}")
' "${json_file}")" || return 1
  read -r TRIVY_CRITICAL TRIVY_HIGH TRIVY_MEDIUM TRIVY_LOW TRIVY_UNKNOWN TRIVY_TOTAL TRIVY_COVERAGE <<<"${parsed}"
}

write_trivy_report_md() {
  local json_file="$1"
  local md_out="${2:-${STEPS_DIR}/trivy-report.md}"
  local status_icon="✅" status_text="clean (no HIGH/CRITICAL)"
  if [[ -n "${TRIVY_CRITICAL}" && ( "${TRIVY_CRITICAL}" -gt 0 || "${TRIVY_HIGH}" -gt 0 ) ]]; then
    status_icon="❌"
    status_text="failed (HIGH/CRITICAL present)"
  elif [[ ! -f "${json_file}" ]]; then
    status_icon="⏭️"
    status_text="n/a (no report)"
  fi
  {
    echo "### ${status_icon} Trivy report"
    echo
    echo "| | |"
    echo "| --- | --- |"
    echo "| Version pin | \`${TRIVY_VERSION}\` |"
    echo "| Status | **${status_text}** |"
    if [[ -n "${TRIVY_COVERAGE}" ]]; then
      echo "| Clean (HIGH/CRITICAL) | **${TRIVY_COVERAGE}%** |"
      echo "| CRITICAL | ${TRIVY_CRITICAL} |"
      echo "| HIGH | ${TRIVY_HIGH} |"
      echo "| Total findings (reported severities) | ${TRIVY_TOTAL} |"
    fi
    echo
  } >"${md_out}"
  log "wrote Trivy report ${md_out}"
}

run_trivy() {
  if [[ "${SKIP_TRIVY:-0}" == "1" ]]; then
    record "trivy" "skip" "SKIP_TRIVY=1"
    return
  fi
  if ! ensure_trivy; then
    if [[ "${MODE}" == "cb" ]]; then
      record "trivy" "fail" "unavailable"
      fail "trivy unavailable (required: Docker + scripts/run-trivy-fs.sh → aquasec/trivy)"
    else
      record "trivy" "skip" "run-trivy-fs.sh unavailable (Docker required)"
      log "WARN: trivy not installed — skip"
    fi
    return
  fi
  local json_out="${STEPS_DIR}/trivy-report.json"
  local sarif_out="${STEPS_DIR}/trivy-report.sarif"
  local cache_dir="${TRIVY_CACHE_DIR:-}"
  if [[ -z "${cache_dir}" ]]; then
    if [[ -d /workspace && -w /workspace ]]; then
      cache_dir="/workspace/.ci/trivy-cache"
    else
      cache_dir="${ROOT}/.ci/trivy-cache"
    fi
  fi
  mkdir -p "${cache_dir}"
  log "==> trivy fs ${TRIVY_VERSION} via ${TRIVY_CMD[*]}"
  local rc=0 docker_cfg
  docker_cfg="$(mktemp -d)"
  # shellcheck disable=SC2064
  trap 'rm -rf "'"${docker_cfg}"'"' RETURN
  export DOCKER_CONFIG="${docker_cfg}"
  set +e
  "${TRIVY_CMD[@]}" fs \
    --config "${ROOT}/trivy.yaml" \
    --ignorefile "${ROOT}/.trivyignore.yaml" \
    --cache-dir "${cache_dir}" \
    --scanners vuln,secret,misconfig \
    --severity HIGH,CRITICAL \
    --exit-code 1 \
    --format json \
    --output "${json_out}" \
    "${ROOT}" >>"${LOG_FILE}" 2>&1
  rc=$?
  if [[ -f "${json_out}" ]]; then
    "${TRIVY_CMD[@]}" convert --format table "${json_out}" >>"${LOG_FILE}" 2>&1 || true
    "${TRIVY_CMD[@]}" convert --format sarif --output "${sarif_out}" "${json_out}" >>"${LOG_FILE}" 2>&1 || true
  fi
  set -e
  parse_trivy_json "${json_out}" || true
  write_trivy_report_md "${json_out}" "${STEPS_DIR}/trivy-report.md"
  if [[ "${rc}" -eq 0 ]]; then
    local detail="ok"
    [[ -n "${TRIVY_TOTAL}" ]] && detail="HIGH/CRITICAL clean (findings=${TRIVY_TOTAL})"
    record "trivy" "pass" "${detail}"
    log "OK: trivy"
  else
    local detail="exit ${rc}"
    [[ -n "${TRIVY_CRITICAL}" ]] && detail="CRITICAL=${TRIVY_CRITICAL} HIGH=${TRIVY_HIGH}"
    record "trivy" "fail" "${detail}"
    fail "trivy (exit ${rc})"
  fi
}

write_summary() {
  local overall="passed" icon="✅"
  if [[ "${FAIL}" -ne 0 ]]; then
    overall="failed"
    icon="❌"
  fi
  local gates_pass=0 gates_fail=0 gates_skip=0 gates_cov="n/a" row name status detail
  for row in "${GATE_ROWS[@]}"; do
    IFS='|' read -r name status detail <<<"${row}"
    case "${status}" in
      pass) gates_pass=$((gates_pass + 1)) ;;
      fail) gates_fail=$((gates_fail + 1)) ;;
      skip) gates_skip=$((gates_skip + 1)) ;;
    esac
  done
  local gates_denom=$((gates_pass + gates_fail))
  if [[ "${gates_denom}" -gt 0 ]]; then
    gates_cov="$(python3 -c "print(f'{100.0 * ${gates_pass} / ${gates_denom}:.1f}')")"
  fi
  {
    echo "### ${icon} Quality gates ${overall}"
    echo
    echo "#### Coverage"
    echo
    echo "| Metric | Value |"
    echo "| --- | --- |"
    echo "| Gates coverage | **${gates_cov}%** (${gates_pass} passed / ${gates_fail} failed / ${gates_skip} skipped) |"
    if [[ -n "${PYTEST_COV}" ]]; then
      echo "| Pytest line coverage | **${PYTEST_COV}%** (fail-under ${COVERAGE_FAIL_UNDER}) |"
    else
      echo "| Pytest line coverage | _n/a_ |"
    fi
    if [[ -n "${TRIVY_COVERAGE}" ]]; then
      echo "| Trivy clean (HIGH/CRITICAL) | **${TRIVY_COVERAGE}%** (CRITICAL=${TRIVY_CRITICAL} HIGH=${TRIVY_HIGH} total=${TRIVY_TOTAL}) |"
    else
      echo "| Trivy clean (HIGH/CRITICAL) | _n/a_ |"
    fi
    echo
    echo "| Check | Result | Detail |"
    echo "| --- | --- | --- |"
    local badge
    for row in "${GATE_ROWS[@]}"; do
      IFS='|' read -r name status detail <<<"${row}"
      case "${status}" in
        pass) badge="✅ pass" ;;
        fail) badge="❌ fail" ;;
        skip) badge="⏭️ skip" ;;
        *) badge="${status}" ;;
      esac
      echo "| \`${name}\` | ${badge} | ${detail} |"
    done
    echo
    echo "_Mode: \`${MODE}\` · lib: \`${LIB_NAME}\`_"
  } >"${SUMMARY_FILE}"
  log "wrote summary ${SUMMARY_FILE}"
}

log "── quality gates (${MODE}) ──"
run_selftests
run_patterns
run_fmt
run_validate
run_pytest
run_trivy
write_summary

if [[ "${FAIL}" -ne 0 ]]; then
  log "── quality gates FAILED ──"
  exit 1
fi
log "── quality gates OK ──"
