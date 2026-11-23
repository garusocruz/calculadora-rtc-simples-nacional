#!/usr/bin/env bash
# Se o PyPI e a tag já têm a versão do pyproject, marca o run para não repetir nada.
# Não publica e não imprime o token.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

: "${PROJECT_ID:?}"
NOME="$(awk -F'"' '/^name = /{print $2; exit}' pyproject.toml)"
VERSAO="$(awk -F'"' '/^version = /{print $2; exit}' pyproject.toml)"
TAG="v${VERSAO}"
REPO="${_GITHUB_REPO:-${GITHUB_REPO:?}}"
OWNER="${_GITHUB_OWNER:-${GITHUB_OWNER:-garusocruz}}"
SKIP="${CI_SKIP_FILE:-/workspace/.ci/skip-build}"

if [[ -z "${NOME}" || ! "${VERSAO}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "pyproject.toml sem nome ou versão X.Y.Z." >&2
  exit 1
fi

codigo="$(curl -sS -o /dev/null -w '%{http_code}' "https://pypi.org/pypi/${NOME}/${VERSAO}/json" || true)"
if [[ "${codigo}" != "200" ]]; then
  echo "A versão ${VERSAO} ainda não está no PyPI. A esteira segue."
  exit 0
fi

bash "${ROOT}/deploy/scripts/configure-github-git.sh"
TOKEN_FILE="${CI_GITHUB_TOKEN_FILE:-/workspace/.ci/github_token}"
if [[ ! -s "${TOKEN_FILE}" ]]; then
  echo "Sem token para ler a tag ${TAG}. A esteira segue."
  exit 0
fi
TOKEN="$(tr -d '[:space:]' < "${TOKEN_FILE}")"
http="$(curl -sS -o /dev/null -w '%{http_code}' \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${OWNER}/${REPO}/releases/tags/${TAG}" || true)"
if [[ "${http}" != "200" ]]; then
  echo "O PyPI tem a ${VERSAO} e a tag ${TAG} ainda não. A esteira segue."
  exit 0
fi

if ! git fetch origin "refs/tags/${TAG}:refs/tags/${TAG}" >/tmp/git-fetch-tag.log 2>&1; then
  sed -E 's#x-access-token:[^@]+#x-access-token:REDACTED#g' /tmp/git-fetch-tag.log >&2 || true
  echo "Não li a tag ${TAG}. A esteira segue."
  exit 0
fi
if [[ "$(git rev-parse "HEAD^{tree}")" != "$(git rev-parse "${TAG}^{tree}")" ]]; then
  echo "A versão ${VERSAO} já está publicada, mas esta árvore não é a da tag. A suíte segue."
  exit 0
fi

mkdir -p "$(dirname "${SKIP}")"
printf 'skip\n' > "${SKIP}"
echo "A versão ${VERSAO} já está no PyPI e esta árvore é a da tag ${TAG}. Este push não faz nada."
