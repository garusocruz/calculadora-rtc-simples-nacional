#!/usr/bin/env bash
# Publish THIS lib repo to Artifact Registry Python (standalone or workspace checkout).
#
# Usage (from lib repo root):
#   export GCP_PROJECT=lynko-508200
#   ./deploy/scripts/publish-self.sh --env feature --branch feat/foo
#   ./deploy/scripts/publish-self.sh --env rc --branch main
#   ./deploy/scripts/publish-self.sh --env production --tag v0.1.0
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

ENV_NAME=""
PR_NUMBER=""
BRANCH=""
SHA=""
TAG=""
REPO_ID="${PYTHON_ARTIFACT_REPO:-lynko-python}"
DRY_RUN=0
LIB_ID="${LIB_ID:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENV_NAME="$2"; shift 2 ;;
    --pr) PR_NUMBER="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --sha) SHA="$2"; shift 2 ;;
    --tag) TAG="$2"; shift 2 ;;
    --lib-id) LIB_ID="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

: "${GCP_PROJECT:?set GCP_PROJECT}"
: "${ENV_NAME:?--env required}"

# Prefer lib publish SA (least privilege). Cloud Build sets PUBLISH_SA_EMAIL /
# GOOGLE_IMPERSONATE_SERVICE_ACCOUNT after terraform creates the SA.
if [[ -n "${PUBLISH_SA_EMAIL:-}" && -z "${GOOGLE_IMPERSONATE_SERVICE_ACCOUNT:-}" ]]; then
  export GOOGLE_IMPERSONATE_SERVICE_ACCOUNT="${PUBLISH_SA_EMAIL}"
fi
if [[ -n "${GOOGLE_IMPERSONATE_SERVICE_ACCOUNT:-}" ]]; then
  echo "publish identity: impersonating ${GOOGLE_IMPERSONATE_SERVICE_ACCOUNT}"
fi

if [[ -z "${LIB_ID}" ]]; then
  if [[ -f pyproject.toml ]] && grep -q 'name *= *"flow-engine"' pyproject.toml 2>/dev/null; then
    LIB_ID=flow_engine
  elif [[ -f pyproject.toml ]] && grep -q 'name *= *"lynko-buffers"' pyproject.toml 2>/dev/null; then
    LIB_ID=lynkobuffers
  elif [[ -f pyproject.toml ]] && grep -q 'name *= *"fast-flow"' pyproject.toml 2>/dev/null; then
    LIB_ID=fast_flow
  elif [[ -f pyproject.toml ]] && grep -q "name = \"flow-engine\"" pyproject.toml 2>/dev/null; then
    LIB_ID=flow_engine
  else
    # fallback: directory name
    LIB_ID="$(basename "${ROOT}")"
  fi
fi

GCP_REGION="${GCP_REGION:-us-central1}"
if [[ -z "${SHA}" ]]; then
  SHA="$(git rev-parse --short=7 HEAD 2>/dev/null || echo local)"
fi

RESOLVE=("${ROOT}/deploy/scripts/resolve-version.sh" --env "${ENV_NAME}" --sha "${SHA}")
[[ -n "${BRANCH}" ]] && RESOLVE+=(--branch "${BRANCH}")
[[ -n "${PR_NUMBER}" ]] && RESOLVE+=(--pr "${PR_NUMBER}")
[[ -n "${TAG}" ]] && RESOLVE+=(--tag "${TAG}")
PKG_VERSION="$("${RESOLVE[@]}")"
echo "lib=${LIB_ID} version=${PKG_VERSION} env=${ENV_NAME} branch=${BRANCH:--} region=${GCP_REGION} project=${GCP_PROJECT}"

python3 - "${ROOT}/CHANGELOG.md" "${PKG_VERSION}" <<'PY'
import pathlib, sys
path, ver = sys.argv[1], sys.argv[2]
text = pathlib.Path(path).read_text(encoding="utf-8") if pathlib.Path(path).exists() else ""
heading = f"## {ver}"
start = text.find(heading)
if start < 0:
    raise SystemExit(f"CHANGELOG.md não tem a seção {heading}")
rest = text[start + len(heading):]
nxt = rest.find("\n## ")
body = rest if nxt < 0 else rest[:nxt]
print(f"── mudanças da {ver} ──")
print(body.strip())
PY

TWINE_REPO_URL="https://${GCP_REGION}-python.pkg.dev/${GCP_PROJECT}/${REPO_ID}/"

python3 -m pip install -q --upgrade pip build twine keyrings.google-artifactregistry-auth poetry

patch_version_field() {
  python3 - "$1" "$2" <<'PY'
import re, sys
path, ver = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8").read()
text2, n = re.subn(r'(?m)^(version\s*=\s*)(["\'])[^"\']+\2', rf'\1\g<2>{ver}\2', text, count=1)
if n != 1:
    raise SystemExit(f"version field not found in {path}")
open(path, "w", encoding="utf-8").write(text2)
PY
}

# flow-engine is a versioned AR dep in pyproject.toml; poetry build embeds Requires-Dist.
# Do not rewrite METADATA (old path-dep patch pinned == fast-flow's own version and broke consumers).

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
rsync -a --exclude '.git' --exclude '.venv' --exclude 'dist' --exclude 'deploy/terraform/.terraform' \
  --exclude '__pycache__' --exclude '*.egg-info' "${ROOT}/" "${tmp}/src/"
work="${tmp}/src"

echo "==> ${LIB_ID}==${PKG_VERSION}"
case "${LIB_ID}" in
  flow_engine|lynkobuffers)
    patch_version_field "${work}/pyproject.toml" "${PKG_VERSION}"
    (cd "${work}" && python3 -m build --wheel --outdir dist)
    ;;
  fast_flow|calculadora_rtc_regime_regular|calculadora_rtc_simples_nacional)
    patch_version_field "${work}/pyproject.toml" "${PKG_VERSION}" || true
    (cd "${work}" && poetry version "${PKG_VERSION}" && poetry build -f wheel)
    ;;
  *)
    echo "unknown lib_id: ${LIB_ID}" >&2
    exit 1
    ;;
esac

wheel="$(ls -1 "${work}/dist"/*.whl | head -1)"
echo "    wheel=$(basename "${wheel}")"

DIST_NAME="$(python3 - <<'PY'
import re, pathlib
text = pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
m = re.search(r'(?m)^name\s*=\s*["\']([^"\']+)["\']', text)
print(m.group(1) if m else "")
PY
)"
if [[ -z "${DIST_NAME}" ]]; then
  case "${LIB_ID}" in
    flow_engine) DIST_NAME="flow-engine" ;;
    lynkobuffers) DIST_NAME="lynko-buffers" ;;
    fast_flow) DIST_NAME="fast-flow" ;;
    *) DIST_NAME="$(printf '%s' "${LIB_ID}" | tr '_' '-')" ;;
  esac
fi
INDEX_URL="https://${GCP_REGION}-python.pkg.dev/${GCP_PROJECT}/${REPO_ID}/simple/"
SOURCE_NAME="${POETRY_SOURCE_NAME:-lynko-python}"

write_publish_artifacts() {
  local steps_dir="${CI_STEPS_DIR:-}"
  if [[ -z "${steps_dir}" && -d /workspace/.ci ]]; then
    steps_dir="/workspace/.ci/steps"
  fi
  [[ -n "${steps_dir}" ]] || return 0
  mkdir -p "${steps_dir}"
  printf '%s\n' "${PKG_VERSION}" > "${steps_dir}/publish.version"
  printf '%s\n' "${DIST_NAME}" > "${steps_dir}/publish.package"
  printf '%s\n' "${INDEX_URL}" > "${steps_dir}/publish.index-url"
  case "${ENV_NAME}" in
    rc|release-candidate|staging) PUB_HEADING="### Published release candidate" ;;
    production|prod) PUB_HEADING="### Published production package" ;;
    *) PUB_HEADING="### Published package" ;;
  esac
  cat > "${steps_dir}/publish.md" <<EOF
${PUB_HEADING}

| | |
|---|---|
| Package | \`${DIST_NAME}\` |
| Version | \`${PKG_VERSION}\` |
| Index | \`${INDEX_URL}\` |
| Env | \`${ENV_NAME}\` |

#### Install with Poetry

\`\`\`bash
# Auth (once per machine / CI identity)
pip install keyrings.google-artifactregistry-auth
gcloud auth application-default login

# Register Artifact Registry as a supplemental Poetry source
poetry source add --priority=supplemental ${SOURCE_NAME} \\
  ${INDEX_URL}

# Pin this build
poetry add "${DIST_NAME}==${PKG_VERSION}" --source ${SOURCE_NAME}
\`\`\`

Or in \`pyproject.toml\`:

\`\`\`toml
[[tool.poetry.source]]
name = "${SOURCE_NAME}"
url = "${INDEX_URL}"
priority = "supplemental"

[tool.poetry.dependencies]
${DIST_NAME} = { version = "${PKG_VERSION}", source = "${SOURCE_NAME}" }
\`\`\`
EOF
  echo "    wrote publish artifacts → ${steps_dir}/publish.{version,package,index-url,md}"
}

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "    dry-run: skip twine upload"
  write_publish_artifacts
  exit 0
fi
python3 -m twine upload --repository-url "${TWINE_REPO_URL}" "${wheel}"
echo "    uploaded → ${TWINE_REPO_URL}"
echo "Index: ${INDEX_URL}"
write_publish_artifacts
