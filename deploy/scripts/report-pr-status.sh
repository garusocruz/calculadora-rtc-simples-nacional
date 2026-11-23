#!/bin/bash
# Shared Cloud Build → GitHub PR status comment (success + failure with log tail).
#
# Source of truth (this file). Vendored into lynko-terraform/ci/ and libs/*/deploy/scripts/.
#
# Expected env (Cloud Build substitutions work as env when listed on the step):
#   PROJECT_ID, BUILD_ID, COMMIT_SHA / SHORT_SHA
#   _PR_NUMBER          — empty → resolve from COMMIT_SHA (needed for RC on push→main)
#   _GITHUB_OWNER       — default garusocruz
#   _GITHUB_REPO        — required for comment (e.g. lynko-terraform, flow_engine)
#   _CONTEXT            — pipeline id for upsert marker (e.g. foundation, flow_engine)
#   _REGION / REGION    — Cloud Build region for console + log fetch
#   _ENV / _ENVIRONMENT / _TF_ACTION — optional metadata rows (rc → separate PR comment)
#   GITHUB_CI_TOKEN_SECRET — Secret Manager id (default lynko-github-ci-token)
#   CI_EXIT_FILE         — default /workspace/.ci/exit_code
#   CI_STEPS_DIR         — default /workspace/.ci/steps (*.exit, quality-gates.*, trivy-report.md)
#   LOG_TAIL_LINES       — default 120
#
# Optional artifacts under CI_STEPS_DIR (when quality-gates ran):
#   quality-gates.summary.md  — gate table + coverage
#   quality-gates.log         — full gate log (visible on fail)
#   trivy-report.md           — Trivy counts + HIGH/CRITICAL findings for the PR comment
#   publish.md                — published package version + Poetry install snippet
#   publish.version / publish.package / publish.index-url — machine-readable publish facts
#   deploy.md                 — Cloud Run image (private AR) + Run URL + public URL if any
#
# Preceding steps should use allowFailure: true and record:
#   mkdir -p /workspace/.ci/steps
#   echo "$?" | tee /workspace/.ci/exit_code > /workspace/.ci/steps/<step-id>.exit
#
set -euo pipefail

SECRET_ID="${GITHUB_CI_TOKEN_SECRET:-lynko-github-ci-token}"
EXIT_FILE="${CI_EXIT_FILE:-/workspace/.ci/exit_code}"
STEPS_DIR="${CI_STEPS_DIR:-/workspace/.ci/steps}"
LOG_TAIL_LINES="${LOG_TAIL_LINES:-120}"
MAX_LOG_CHARS="${MAX_LOG_CHARS:-24000}"

PR_NUMBER="${_PR_NUMBER:-${PR_NUMBER:-}}"
OWNER="${_GITHUB_OWNER:-${GITHUB_OWNER:-garusocruz}}"
REPO="${_GITHUB_REPO:-${GITHUB_REPOSITORY_NAME:-${_FOUNDATION_GITHUB_REPO:-}}}"
CONTEXT="${_CONTEXT:-${LYNKO_CB_CONTEXT:-cloudbuild}}"
PROJECT_ID="${PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-}}"
REGION="${_REGION:-${REGION:-${LOCATION:-us-central1}}}"
ENV_NAME="${_ENV:-${_ENVIRONMENT:-${ENVIRONMENT:-}}}"
TF_ACTION="${_TF_ACTION:-}"
BUILD_ID="${BUILD_ID:-}"
COMMIT_SHA="${COMMIT_SHA:-${SHORT_SHA:-}}"

# Separate upsert markers per env so RC (push→main) posts a *new* comment on the
# merged PR instead of overwriting the feature build comment.
normalize_env_label() {
  case "${1:-}" in
    feature|preview) printf 'feature' ;;
    rc|release-candidate|staging) printf 'rc' ;;
    production|prod) printf 'production' ;;
    "") printf '' ;;
    *) printf '%s' "$1" ;;
  esac
}
ENV_LABEL="$(normalize_env_label "${ENV_NAME}")"
if [[ -n "${ENV_LABEL}" && "${ENV_LABEL}" != "feature" ]]; then
  MARKER="<!-- lynko-cloudbuild:${CONTEXT}:${ENV_LABEL} -->"
  COMMENT_SCOPE="${CONTEXT}:${ENV_LABEL}"
else
  MARKER="<!-- lynko-cloudbuild:${CONTEXT} -->"
  COMMENT_SCOPE="${CONTEXT}"
fi

# Some Gen2 triggers leave $_PR_NUMBER empty (push→main RC/teardown). Resolve via API.
# Prefer a merged PR when env is rc/production so the comment lands on the closed PR.
resolve_pr_number_from_commit() {
  local token="$1"
  local prefer_merged=0
  case "${ENV_LABEL}" in
    rc|production) prefer_merged=1 ;;
  esac
  [[ -n "${COMMIT_SHA}" && -n "${OWNER}" && -n "${REPO}" && -n "${token}" ]] || return 1
  curl -fsS \
    -H "Authorization: Bearer ${token}" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/repos/${OWNER}/${REPO}/commits/${COMMIT_SHA}/pulls" \
    | PREFER_MERGED="${prefer_merged}" python3 -c 'import json,os,sys
try:
  data=json.load(sys.stdin)
except Exception:
  sys.exit(1)
if not data:
  sys.exit(1)
prefer = os.environ.get("PREFER_MERGED") == "1"
if prefer:
  for p in data:
    if p.get("merged_at") or p.get("state") == "closed":
      print(p.get("number") or "")
      raise SystemExit(0)
print(data[0].get("number") or "")' 2>/dev/null
}

# Soft-fail steps use allowFailure + *.exit files. report-pr must exit with the
# aggregated code so GitHub Checks stay red when deploy failed but allowFailure
# kept the pipeline going. If deploy-cloud-run never wrote .exit (script crash),
# fail closed when docker-build already passed.
resolve_exit_code() {
  local code=0 f
  local saw_deploy_exit=0
  if [[ -d "${STEPS_DIR}" ]]; then
    for f in "${STEPS_DIR}"/*.exit; do
      [[ -f "${f}" ]] || continue
      local s
      s="$(tr -d '[:space:]' < "${f}" || true)"
      [[ -n "${s}" ]] || continue
      if [[ "$(basename "${f}")" == "deploy-cloud-run.exit" ]]; then
        saw_deploy_exit=1
      fi
      if [[ "${s}" != "0" ]]; then
        code="${s}"
      fi
    done
  fi
  if [[ -f "${EXIT_FILE}" ]]; then
    local e
    e="$(tr -d '[:space:]' < "${EXIT_FILE}" || true)"
    if [[ -n "${e}" && "${e}" != "0" ]]; then
      code="${e}"
    elif [[ "${code}" == "0" && -n "${e}" ]]; then
      code="${e}"
    fi
  fi
  if [[ "${code}" == "0" && "${saw_deploy_exit}" == "0" && -f "${STEPS_DIR}/docker-build.exit" ]]; then
    local db
    db="$(tr -d '[:space:]' < "${STEPS_DIR}/docker-build.exit" || true)"
    if [[ "${db}" == "0" ]]; then
      echo "report-pr-status: WARNING deploy-cloud-run.exit missing after docker-build pass — assuming deploy failed" >&2
      code=1
    fi
  fi
  printf '%s' "${code}"
}

post_commit_status() {
  local token="$1"
  local state description ctx payload http
  local auth=( -H "Authorization: Bearer ${token}" -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28" )
  [[ -n "${COMMIT_SHA}" ]] || return 0
  if [[ "${TF_EXIT}" == "0" ]]; then
    state="success"
    description="Cloud Build ${CONTEXT} succeeded"
  else
    state="failure"
    description="Cloud Build ${CONTEXT} failed (exit ${TF_EXIT})"
  fi
  ctx="lynko/${CONTEXT}"
  [[ -n "${ENV_LABEL}" && "${ENV_LABEL}" != "feature" ]] && ctx="${ctx}/${ENV_LABEL}"
  payload="$(COMMIT_STATE="${state}" COMMIT_DESC="${description}" COMMIT_CTX="${ctx}" BUILD_URL="${BUILD_URL}" python3 -c 'import json,os; print(json.dumps({
    "state": os.environ["COMMIT_STATE"],
    "description": os.environ["COMMIT_DESC"][:140],
    "context": os.environ["COMMIT_CTX"],
    "target_url": os.environ.get("BUILD_URL") or "",
  }))')"
  http="$(curl -sS -o /dev/null -w '%{http_code}' -X POST "${auth[@]}" \
    -H "Content-Type: application/json" \
    -d "${payload}" \
    "${API_BASE}/statuses/${COMMIT_SHA}" || true)"
  if [[ "${http}" != "201" ]]; then
    echo "report-pr-status: commit status HTTP ${http} (context=${ctx})" >&2
  else
    echo "report-pr-status: posted commit status ${state} (${ctx})"
  fi
}

strip_ansi() {
  sed -E 's/\x1b\[[0-9;]*[mK]//g'
}

html_escape() {
  python3 -c 'import sys,html; sys.stdout.write(html.escape(sys.stdin.read()))'
}

fetch_failure_log() {
  local raw=""
  if [[ -z "${BUILD_ID}" || -z "${PROJECT_ID}" ]]; then
    printf '%s\n' "(build log unavailable: BUILD_ID/PROJECT_ID missing)"
    return 0
  fi
  if raw="$(gcloud builds log "${BUILD_ID}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" 2>/dev/null)"; then
    :
  elif raw="$(gcloud builds log "${BUILD_ID}" \
    --project="${PROJECT_ID}" 2>/dev/null)"; then
    :
  else
    printf '%s\n' "(could not fetch Cloud Build log; open the console link)"
    return 0
  fi
  printf '%s\n' "${raw}" | strip_ansi | tail -n "${LOG_TAIL_LINES}" | html_escape
}

mkdir -p "$(dirname "${EXIT_FILE}")"
TF_EXIT="$(resolve_exit_code)"
[[ -n "${TF_EXIT}" ]] || TF_EXIT=0

if [[ -z "${REPO}" ]]; then
  echo "report-pr-status: _GITHUB_REPO unset — skip comment (exit=${TF_EXIT})" >&2
  exit "${TF_EXIT}"
fi

if [[ -z "${PROJECT_ID}" ]]; then
  echo "report-pr-status: PROJECT_ID unset — skip comment (exit=${TF_EXIT})" >&2
  exit "${TF_EXIT}"
fi

if ! GH_TOKEN="$(gcloud secrets versions access latest \
  --secret="${SECRET_ID}" \
  --project="${PROJECT_ID}" 2>/dev/null)"; then
  echo "report-pr-status: secret ${SECRET_ID} missing/unreadable — skip comment (exit=${TF_EXIT})" >&2
  exit "${TF_EXIT}"
fi

# Strip non-digits (payload may leave literal "$(...)" if binding failed)
PR_NUMBER="$(printf '%s' "${PR_NUMBER}" | sed -E 's/[^0-9]//g')"
if [[ -z "${PR_NUMBER}" ]]; then
  if PR_NUMBER="$(resolve_pr_number_from_commit "${GH_TOKEN}")"; then
    PR_NUMBER="$(printf '%s' "${PR_NUMBER}" | sed -E 's/[^0-9]//g')"
    echo "report-pr-status: resolved PR #${PR_NUMBER} from commit ${COMMIT_SHA}"
  fi
fi
if [[ -z "${PR_NUMBER}" ]]; then
  echo "report-pr-status: no PR number — skip comment (exit=${TF_EXIT})"
  exit "${TF_EXIT}"
fi

if [[ "${TF_EXIT}" == "0" ]]; then
  STATUS_ICON="✅"
  case "${ENV_LABEL}" in
    rc) STATUS_TEXT="release candidate succeeded" ;;
    production) STATUS_TEXT="production succeeded" ;;
    *) STATUS_TEXT="succeeded" ;;
  esac
else
  STATUS_ICON="❌"
  case "${ENV_LABEL}" in
    rc) STATUS_TEXT="release candidate failed (exit ${TF_EXIT})" ;;
    production) STATUS_TEXT="production failed (exit ${TF_EXIT})" ;;
    *) STATUS_TEXT="failed (exit ${TF_EXIT})" ;;
  esac
fi

BUILD_URL="https://console.cloud.google.com/cloud-build/builds;region=${REGION}/${BUILD_ID}?project=${PROJECT_ID}"
SHORT_COMMIT="$(printf '%s' "${COMMIT_SHA}" | cut -c1-7)"

META_ROWS=""
META_ROWS+="| Context | \`${CONTEXT}\` |"$'\n'
[[ -n "${ENV_NAME}" ]] && META_ROWS+="| Env | \`${ENV_NAME}\` |"$'\n'
case "${ENV_LABEL}" in
  rc) META_ROWS+="| Channel | \`release-candidate\` |"$'\n' ;;
  production) META_ROWS+="| Channel | \`production\` |"$'\n' ;;
  feature) META_ROWS+="| Channel | \`feature\` |"$'\n' ;;
esac
[[ -n "${TF_ACTION}" ]] && META_ROWS+="| Action | \`${TF_ACTION}\` |"$'\n'
META_ROWS+="| Commit | \`${SHORT_COMMIT}\` |"$'\n'
META_ROWS+="| Build | [\`${BUILD_ID}\`](${BUILD_URL}) |"$'\n'
META_ROWS+="| Region | \`${REGION}\` |"

# Per-step exit table (quality-gates, terraform, …)
STEP_ROWS=""
if [[ -d "${STEPS_DIR}" ]]; then
  for f in "${STEPS_DIR}"/*.exit; do
    [[ -f "${f}" ]] || continue
    step="$(basename "${f}" .exit)"
    code="$(tr -d '[:space:]' < "${f}" || true)"
    [[ -n "${code}" ]] || code="?"
    if [[ "${code}" == "0" ]]; then
      STEP_ROWS+="| \`${step}\` | ✅ pass |"$'\n'
    else
      STEP_ROWS+="| \`${step}\` | ❌ fail (\`${code}\`) |"$'\n'
    fi
  done
fi

QUALITY_SECTION=""
QUALITY_SUMMARY="${STEPS_DIR}/quality-gates.summary.md"
QUALITY_LOG="${STEPS_DIR}/quality-gates.log"
QUALITY_EXIT_FILE="${STEPS_DIR}/quality-gates.exit"
QUALITY_FAILED=0
if [[ -f "${QUALITY_EXIT_FILE}" ]]; then
  qe="$(tr -d '[:space:]' < "${QUALITY_EXIT_FILE}" || true)"
  [[ -n "${qe}" && "${qe}" != "0" ]] && QUALITY_FAILED=1
fi
if [[ -f "${QUALITY_SUMMARY}" ]] && grep -q 'Quality gates failed' "${QUALITY_SUMMARY}" 2>/dev/null; then
  QUALITY_FAILED=1
fi

if [[ -f "${QUALITY_SUMMARY}" ]]; then
  QUALITY_SECTION=$'\n'"$(cat "${QUALITY_SUMMARY}")"$'\n'
fi

if [[ -f "${QUALITY_LOG}" ]]; then
  # Markdown fenced block (not HTML): sanitize fences inside the log.
  Q_TAIL="$(strip_ansi < "${QUALITY_LOG}" | tail -n "${LOG_TAIL_LINES}" | sed 's/```/``ˋ/g')"
  if [[ "${#Q_TAIL}" -gt "${MAX_LOG_CHARS}" ]]; then
    Q_TAIL="$(printf '%s' "${Q_TAIL}" | tail -c "${MAX_LOG_CHARS}")"
    Q_TAIL=$'…(truncated)\n'"${Q_TAIL}"
  fi
  if [[ "${QUALITY_FAILED}" -eq 1 ]]; then
    QUALITY_SECTION+=$(cat <<EOF

### Quality gates error log

\`\`\`text
${Q_TAIL}
\`\`\`
EOF
)
  else
    QUALITY_SECTION+=$(cat <<EOF

<details>
<summary>Quality gates log</summary>

\`\`\`text
${Q_TAIL}
\`\`\`

</details>
EOF
)
  fi
fi

# Trivy markdown report (written by quality-gates when present)
TRIVY_SECTION=""
TRIVY_REPORT_MD="${STEPS_DIR}/trivy-report.md"
if [[ -f "${TRIVY_REPORT_MD}" ]]; then
  TRIVY_BODY="$(cat "${TRIVY_REPORT_MD}")"
  # Older backend gates wrote a bare table — ensure a clear Trivy heading.
  if ! grep -qE '^### .*Trivy' <<<"${TRIVY_BODY}"; then
    TRIVY_BODY=$(cat <<EOF
### Trivy report

${TRIVY_BODY}
EOF
)
  fi
  TRIVY_SECTION=$'\n'"${TRIVY_BODY}"$'\n'
fi

# Cloud Run deploy (backends) — private AR image + Run URL (+ public when unauth)
DEPLOY_SECTION=""
DEPLOY_MD="${STEPS_DIR}/deploy.md"
if [[ ! -f "${DEPLOY_MD}" ]]; then
  # Fallback: synthesize from env when write-cloud-run-deploy-md.sh failed/missing.
  _svc=""
  _img=""
  if [[ -f "${STEPS_DIR}/deploy-cloud-run.exit" ]]; then
    _de="$(tr -d '[:space:]' < "${STEPS_DIR}/deploy-cloud-run.exit" || true)"
    if [[ "${_de}" == "0" ]]; then
      _svc="${_SERVICE_NAME:-${SERVICE_NAME:-}}"
      if [[ -n "${_SERVICE_SUFFIX:-}" && -n "${_svc}" ]]; then
        _svc="${_svc}-${_SERVICE_SUFFIX}"
      elif [[ -n "${_PR_NUMBER:-}" && -n "${_svc}" ]]; then
        _svc="${_svc}-pr-${_PR_NUMBER}"
      fi
      _img="${_REGION:-us-central1}-docker.pkg.dev/${PROJECT_ID}/${_REPO:-lynko}/${_SERVICE_NAME:-service}:${_TAG:-$SHORT_SHA}"
      if [[ -n "${_svc}" && -n "${PROJECT_ID}" ]]; then
        PROJECT_ID="${PROJECT_ID}" REGION="${REGION}" SERVICE_NAME="${_svc}" IMAGE="${_img}" \
          ALLOW_UNAUTH="${_ALLOW_UNAUTH:-0}" PROTOCOL="${_PROTOCOL:-http}" ENVIRONMENT="${ENV_NAME}" \
          DEPLOY_EXIT=0 STEPS_DIR="${STEPS_DIR}" \
          bash "$(dirname "$0")/write-cloud-run-deploy-md.sh" 2>/dev/null \
          || PROJECT_ID="${PROJECT_ID}" REGION="${REGION}" SERVICE_NAME="${_svc}" IMAGE="${_img}" \
            ALLOW_UNAUTH="${_ALLOW_UNAUTH:-0}" PROTOCOL="${_PROTOCOL:-http}" ENVIRONMENT="${ENV_NAME}" \
            DEPLOY_EXIT=0 STEPS_DIR="${STEPS_DIR}" \
            bash /workspace/cloudbuild/write-cloud-run-deploy-md.sh 2>/dev/null \
          || true
      fi
    fi
  fi
fi
if [[ -f "${DEPLOY_MD}" ]]; then
  DEPLOY_SECTION=$'\n'"$(cat "${DEPLOY_MD}")"$'\n'
fi

# Published package + Poetry install (written by publish-self.sh)
PUBLISH_SECTION=""
PUBLISH_MD="${STEPS_DIR}/publish.md"
PUBLISH_VERSION_FILE="${STEPS_DIR}/publish.version"
PUBLISH_PACKAGE_FILE="${STEPS_DIR}/publish.package"
PUBLISH_INDEX_FILE="${STEPS_DIR}/publish.index-url"
PUBLISH_EXIT_FILE="${STEPS_DIR}/publish.exit"
PUBLISH_OK=0
if [[ -f "${PUBLISH_EXIT_FILE}" ]]; then
  pe="$(tr -d '[:space:]' < "${PUBLISH_EXIT_FILE}" || true)"
  [[ "${pe}" == "0" ]] && PUBLISH_OK=1
fi
if [[ -f "${PUBLISH_MD}" ]]; then
  PUBLISH_SECTION=$'\n'"$(cat "${PUBLISH_MD}")"$'\n'
elif [[ "${PUBLISH_OK}" -eq 1 && -f "${PUBLISH_VERSION_FILE}" ]]; then
  PUB_VER="$(tr -d '[:space:]' < "${PUBLISH_VERSION_FILE}")"
  PUB_PKG="$(tr -d '[:space:]' < "${PUBLISH_PACKAGE_FILE}" 2>/dev/null || true)"
  PUB_IDX="$(tr -d '[:space:]' < "${PUBLISH_INDEX_FILE}" 2>/dev/null || true)"
  [[ -n "${PUB_PKG}" ]] || PUB_PKG="${CONTEXT}"
  [[ -n "${PUB_IDX}" ]] || PUB_IDX="(index url unavailable)"
  PUBLISH_SECTION=$(cat <<EOF

### Published package

| | |
|---|---|
| Package | \`${PUB_PKG}\` |
| Version | \`${PUB_VER}\` |
| Index | \`${PUB_IDX}\` |

#### Install with Poetry

\`\`\`bash
pip install keyrings.google-artifactregistry-auth
gcloud auth application-default login
poetry source add --priority=supplemental lynko-python \\
  ${PUB_IDX}
poetry add "${PUB_PKG}==${PUB_VER}" --source lynko-python
\`\`\`
EOF
)
fi

STEPS_SECTION=""
if [[ -n "${STEP_ROWS}" ]]; then
  STEPS_SECTION=$(cat <<EOF

### Cloud Build steps

| Step | Result |
| --- | --- |
${STEP_ROWS}
EOF
)
fi

LOG_SECTION=""
if [[ "${TF_EXIT}" != "0" ]]; then
  LOG_BODY="$(fetch_failure_log)"
  if [[ "${#LOG_BODY}" -gt "${MAX_LOG_CHARS}" ]]; then
    LOG_BODY="$(printf '%s' "${LOG_BODY}" | tail -c "${MAX_LOG_CHARS}")"
    LOG_BODY=$'…(truncated)\n'"${LOG_BODY}"
  fi
  LOG_SECTION=$(cat <<EOF

<details>
<summary>Failure log (last ${LOG_TAIL_LINES} lines)</summary>

<pre><code>${LOG_BODY}</code></pre>

</details>
EOF
)
fi

HEADLINE="Cloud Build ${STATUS_TEXT}"
case "${ENV_LABEL}" in
  rc)
    if [[ "${TF_EXIT}" == "0" ]]; then
      HEADLINE="Release candidate build succeeded"
    else
      HEADLINE="Release candidate build failed (exit ${TF_EXIT})"
    fi
    ;;
  production)
    if [[ "${TF_EXIT}" == "0" ]]; then
      HEADLINE="Production build succeeded"
    else
      HEADLINE="Production build failed (exit ${TF_EXIT})"
    fi
    ;;
esac

# Prefer precise headline: deploy.md → deployed; publish.md → published (libs).
if [[ -f "${DEPLOY_MD}" && "${TF_EXIT}" == "0" ]]; then
  case "${ENV_LABEL}" in
    rc) HEADLINE="Release candidate deployed" ;;
    production) HEADLINE="Production deployed" ;;
    feature|"") HEADLINE="Feature environment deployed" ;;
  esac
elif [[ -f "${PUBLISH_MD}" && "${TF_EXIT}" == "0" ]]; then
  case "${ENV_LABEL}" in
    rc) HEADLINE="Release candidate published" ;;
    production) HEADLINE="Production package published" ;;
  esac
fi

BODY=$(cat <<EOF
${MARKER}
## ${STATUS_ICON} ${HEADLINE}

| | |
|---|---|
${META_ROWS}
${STEPS_SECTION}
${DEPLOY_SECTION}
${PUBLISH_SECTION}
${QUALITY_SECTION}
${TRIVY_SECTION}
${LOG_SECTION}

_Posted by Lynko shared Cloud Build reporter (\`${COMMENT_SCOPE}\`)._
EOF
)
mkdir -p "${STEPS_DIR}"
printf '%s\n' "${BODY}" > "${STEPS_DIR}/pr-comment.md"

API_BASE="https://api.github.com/repos/${OWNER}/${REPO}"
AUTH_HDR=( -H "Authorization: Bearer ${GH_TOKEN}" -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28" )

post_commit_status "${GH_TOKEN}" || true

# Comment upsert must not mask a green (or red) pipeline: PAT missing a private
# repo returns GitHub 404 and curl -f exits 22. Warn and still exit TF_EXIT.
post_pr_comment() {
  local existing_id="" page=1 resp count body_json http
  while [[ "${page}" -le 10 ]]; do
    http="$(curl -sS -o /tmp/lynko-gh-comments.json -w '%{http_code}' "${AUTH_HDR[@]}" \
      "${API_BASE}/issues/${PR_NUMBER}/comments?per_page=100&page=${page}" || true)"
    if [[ "${http}" != "200" ]]; then
      echo "report-pr-status: list comments HTTP ${http} for ${OWNER}/${REPO}#${PR_NUMBER} — skip upsert (check PAT repo access / Issues:Write on secret ${SECRET_ID})" >&2
      return 1
    fi
    resp="$(cat /tmp/lynko-gh-comments.json)"
    count="$(printf '%s' "${resp}" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))' 2>/dev/null || echo 0)"
    [[ "${count}" != "0" ]] || break
    existing_id="$(printf '%s' "${resp}" | python3 -c '
import json,sys
marker=sys.argv[1]
for c in json.load(sys.stdin):
    if marker in (c.get("body") or ""):
        print(c["id"]); break
' "${MARKER}" 2>/dev/null || true)"
    [[ -z "${existing_id}" ]] || break
    [[ "${count}" -lt 100 ]] && break
    page=$((page + 1))
  done

  body_json="$(BODY="${BODY}" python3 -c 'import json,os; print(json.dumps({"body": os.environ["BODY"]}))')"

  if [[ -n "${existing_id}" ]]; then
    http="$(curl -sS -o /dev/null -w '%{http_code}' -X PATCH "${AUTH_HDR[@]}" \
      -H "Content-Type: application/json" \
      -d "${body_json}" \
      "${API_BASE}/issues/comments/${existing_id}" || true)"
    if [[ "${http}" != "200" ]]; then
      echo "report-pr-status: PATCH comment HTTP ${http} on ${OWNER}/${REPO}#${PR_NUMBER} — skip (PAT / Issues:Write?)" >&2
      return 1
    fi
    echo "report-pr-status: updated comment ${existing_id} on ${OWNER}/${REPO}#${PR_NUMBER} (${CONTEXT})"
  else
    http="$(curl -sS -o /dev/null -w '%{http_code}' -X POST "${AUTH_HDR[@]}" \
      -H "Content-Type: application/json" \
      -d "${body_json}" \
      "${API_BASE}/issues/${PR_NUMBER}/comments" || true)"
    if [[ "${http}" != "201" && "${http}" != "200" ]]; then
      echo "report-pr-status: POST comment HTTP ${http} on ${OWNER}/${REPO}#${PR_NUMBER} — skip (PAT must include this repo with Issues: Write)" >&2
      return 1
    fi
    echo "report-pr-status: created comment on ${OWNER}/${REPO}#${PR_NUMBER} (${CONTEXT})"
  fi
  return 0
}

post_pr_comment || true

exit "${TF_EXIT}"
