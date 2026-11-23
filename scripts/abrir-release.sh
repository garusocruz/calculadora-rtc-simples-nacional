#!/usr/bin/env bash
# Abre a release vX.Y.Z no commit que o build da main validou.
# O corpo guarda o build da main. O PyPI fica para o trigger da release.
# Não imprime o token. Se a release já existe, não troca a tag.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

PYVER="$(awk -F'"' '/^version = /{print $2; exit}' pyproject.toml)"
TAG="${TAG_NAME:-v${PYVER}}"
if [[ ! "${TAG}" =~ ^v([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
  echo "TAG_NAME deve ser vX.Y.Z. Veio: ${TAG:-vazio}" >&2
  exit 1
fi
VER="${BASH_REMATCH[1]}"
if [[ "${PYVER}" != "${VER}" ]]; then
  echo "pyproject.toml está em ${PYVER} e a release é ${VER}" >&2
  exit 1
fi

: "${PROJECT_ID:?}"
: "${BUILD_ID:?}"
: "${COMMIT_SHA:?}"
REPO="${_GITHUB_REPO:-${GITHUB_REPO:?}}"
OWNER="${_GITHUB_OWNER:-${GITHUB_OWNER:-garusocruz}}"
REGION="${_REGION:-${REGION:-us-central1}}"
URL="https://console.cloud.google.com/cloud-build/builds;region=${REGION}/${BUILD_ID}?project=${PROJECT_ID}"

bash "${ROOT}/deploy/scripts/configure-github-git.sh"
TOKEN_FILE="${CI_GITHUB_TOKEN_FILE:-/workspace/.ci/github_token}"
if [[ ! -s "${TOKEN_FILE}" ]]; then
  echo "Sem token do GitHub para abrir a release." >&2
  exit 1
fi
TOKEN="$(tr -d '[:space:]' < "${TOKEN_FILE}")"

http="$(curl -sS -o /tmp/gh-release-get.json -w '%{http_code}' \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${OWNER}/${REPO}/releases/tags/${TAG}")"
if [[ "${http}" == "200" ]]; then
  echo "Release ${TAG} já existe. O build da main não publica de novo."
  exit 0
fi
if [[ "${http}" != "404" ]]; then
  echo "GitHub respondeu ${http} ao ler a release ${TAG}." >&2
  exit 1
fi

python3 - "${TAG}" "${COMMIT_SHA}" "${BUILD_ID}" "${URL}" /tmp/gh-release-create.json <<'PY'
import json, pathlib, sys
tag, sha, build, url, dest = sys.argv[1:]
body = f"Build: {build}\nCommit: {sha}\nURL: {url}\n"
pathlib.Path(dest).write_text(
    json.dumps(
        {
            "tag_name": tag,
            "target_commitish": sha,
            "name": tag,
            "body": body,
        }
    ),
    encoding="utf-8",
)
PY

create="$(curl -sS -o /tmp/gh-release-created.json -w '%{http_code}' \
  -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/gh-release-create.json \
  "https://api.github.com/repos/${OWNER}/${REPO}/releases")"
if [[ "${create}" == "201" ]]; then
  echo "Release ${TAG} aberta em ${COMMIT_SHA} com o build ${BUILD_ID}."
  exit 0
fi
if [[ "${create}" == "422" ]]; then
  echo "Release ${TAG} já estava aberta."
  exit 0
fi
echo "GitHub respondeu ${create} ao abrir a release ${TAG}." >&2
exit 1
