#!/usr/bin/env bash
# Abre a release vX.Y.Z no commit que este build validou.
# Não imprime o token. Se a release já existe, não troca a tag.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if [[ -f /workspace/.ci/skip-publish ]]; then
  echo "Commit de registro. Não abre outra release."
  exit 0
fi

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

: "${COMMIT_SHA:?}"
REPO="${_GITHUB_REPO:-${GITHUB_REPO:?}}"
OWNER="${_GITHUB_OWNER:-${GITHUB_OWNER:-garusocruz}}"

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
  echo "Release ${TAG} já existe."
  exit 0
fi
if [[ "${http}" != "404" ]]; then
  echo "GitHub respondeu ${http} ao ler a release ${TAG}." >&2
  exit 1
fi

create="$(curl -sS -o /tmp/gh-release-create.json -w '%{http_code}' \
  -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  "https://api.github.com/repos/${OWNER}/${REPO}/releases" \
  -d "{\"tag_name\":\"${TAG}\",\"target_commitish\":\"${COMMIT_SHA}\",\"name\":\"${TAG}\"}")"
if [[ "${create}" == "201" ]]; then
  echo "Release ${TAG} aberta em ${COMMIT_SHA}."
  exit 0
fi
if [[ "${create}" == "422" ]]; then
  echo "Release ${TAG} já estava aberta."
  exit 0
fi
echo "GitHub respondeu ${create} ao abrir a release ${TAG}." >&2
exit 1
