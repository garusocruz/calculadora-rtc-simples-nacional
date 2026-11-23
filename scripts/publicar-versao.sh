#!/usr/bin/env bash
# Publica a versão no mesmo run que validou o merge.
# Constrói de novo com o README já gravado, publica no PyPI e só então abre a tag.
# Se a versão já está no PyPI e a tag já existe, não faz nada.
# Não imprime o token.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

: "${PROJECT_ID:?}"
: "${BUILD_ID:?}"
: "${COMMIT_SHA:?}"
PYVER="$(awk -F'"' '/^version = /{print $2; exit}' pyproject.toml)"
TAG="v${PYVER}"
if [[ ! "${PYVER}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "A versão do pyproject.toml deve ser X.Y.Z. Veio: ${PYVER:-vazio}" >&2
  exit 1
fi

REPO="${_GITHUB_REPO:-${GITHUB_REPO:?}}"
OWNER="${_GITHUB_OWNER:-${GITHUB_OWNER:-garusocruz}}"
REGION="${_REGION:-${REGION:-us-central1}}"
NOME="$(awk -F'"' '/^name = /{print $2; exit}' pyproject.toml)"
BRANCH="docs/release-${TAG}"
SKIP_FILE="${CI_SKIP_FILE:-/workspace/.ci/skip-build}"
STEPS="${ROOT}/.ci/steps"
mkdir -p "${STEPS}"
MERGE_URL="https://console.cloud.google.com/cloud-build/builds;region=${REGION}/${BUILD_ID}?project=${PROJECT_ID}"

bash "${ROOT}/deploy/scripts/configure-github-git.sh"
TOKEN_FILE="${CI_GITHUB_TOKEN_FILE:-/workspace/.ci/github_token}"
if [[ ! -s "${TOKEN_FILE}" ]]; then
  echo "Sem token do GitHub para publicar a versão." >&2
  exit 1
fi
TOKEN="$(tr -d '[:space:]' < "${TOKEN_FILE}")"

pypi_codigo() {
  curl -sS -o /dev/null -w '%{http_code}' "https://pypi.org/pypi/${NOME}/${PYVER}/json" || true
}

release_codigo() {
  curl -sS -o /tmp/gh-release-get.json -w '%{http_code}' \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/${OWNER}/${REPO}/releases/tags/${TAG}" || true
}

gravar_publicada() {
  local novo="$1"
  local sdist wheel
  sdist="$(awk -F= '/^sdist=/{print $2; exit}' "${STEPS}/build-lib.txt" 2>/dev/null || true)"
  wheel="$(awk -F= '/^wheel=/{print $2; exit}' "${STEPS}/build-lib.txt" 2>/dev/null || true)"
  cat > "${STEPS}/publicacao.md" <<EOF
### Geração e publicação

| | |
| --- | --- |
| Versão | \`${PYVER}\` |
| Tag | \`${TAG}\` |
| Commit validado | \`${COMMIT_SHA}\` |
| Commit da tag | \`${novo}\` |
| Build | [\`${BUILD_ID}\`](${MERGE_URL}) |
| PyPI | https://pypi.org/project/${NOME}/${PYVER}/ |
| sdist | \`${sdist}\` |
| wheel | \`${wheel}\` |

O README, a tag e o pacote no PyPI saíram deste run, depois do quality gate. O pacote foi construído de novo com o README já gravado.
EOF
  printf 'publicado\n' > "${STEPS}/publicar.mode"
  printf '%s\n' "${BRANCH}" > "${STEPS}/readme-branch.txt"
  printf '%s\n' "${novo}" > "${STEPS}/release-sha.txt"
}

gravar_ja_publicada() {
  cat > "${STEPS}/publicacao.md" <<EOF
### Este merge

A versão \`${PYVER}\` já está no PyPI e a tag \`${TAG}\` já existe. Este push não repetiu a publicação, não abriu outra tag e não abriu outra pull request.
EOF
  printf 'ja-publicada\n' > "${STEPS}/publicar.mode"
}

if [[ -f "${SKIP_FILE}" ]]; then
  bash "${ROOT}/scripts/conferir-versao-publicada.sh"
  http="$(release_codigo)"
  if [[ "${http}" != "200" ]]; then
    echo "A versão ${PYVER} não tem a tag ${TAG}. Este merge não publica no lugar da esteira que validou." >&2
    exit 1
  fi
  gravar_ja_publicada
  echo "Versão ${PYVER} já publicada. Este merge não faz nada."
  exit 0
fi

if ! grep -q "o run que validou esta versão" README.md; then
  echo "O README ainda não tem o run que validou esta versão." >&2
  exit 1
fi

pypi="$(pypi_codigo)"
rel="$(release_codigo)"
if [[ "${pypi}" == "200" && "${rel}" == "200" ]]; then
  gravar_ja_publicada
  echo "A versão ${PYVER} já está no PyPI e a tag ${TAG} já existe. Não publica de novo."
  exit 0
fi
if [[ "${pypi}" == "200" && "${rel}" != "200" ]]; then
  fetch_log="$(mktemp)"
  if git fetch origin "${BRANCH}" >"${fetch_log}" 2>&1 \
    && git rev-parse --verify "origin/${BRANCH}" >/dev/null 2>&1; then
    git checkout -f "origin/${BRANCH}"
    if grep -q "o run que validou esta versão" README.md; then
      NOVO="$(git rev-parse HEAD)"
      TARGET_SHA="${NOVO}" bash "${ROOT}/scripts/abrir-release.sh"
      gravar_publicada "${NOVO}"
      echo "A versão ${PYVER} já estava no PyPI. A tag ${TAG} foi aberta em ${NOVO}."
      exit 0
    fi
  fi
  sed -E 's#x-access-token:[^@]+#x-access-token:REDACTED#g' "${fetch_log}" >&2 || true
  echo "O PyPI tem a ${PYVER} e a tag ${TAG} não existe. Não crio a tag em outro commit." >&2
  exit 1
fi
if [[ "${pypi}" != "404" ]]; then
  echo "O PyPI respondeu ${pypi}. Não publica." >&2
  exit 1
fi
if [[ "${rel}" != "404" ]]; then
  echo "O GitHub respondeu ${rel} ao ler a release ${TAG}. Não publica." >&2
  exit 1
fi
if [[ -z "${PYPI_API_TOKEN:-}" ]]; then
  echo "Sem PYPI_API_TOKEN. Não publica." >&2
  exit 1
fi

cp README.md /tmp/readme-release.md
git checkout -f -B "${BRANCH}" HEAD
cp /tmp/readme-release.md README.md
git add README.md
if git diff --cached --quiet; then
  echo "O README não mudou. Não há o que publicar." >&2
  exit 1
fi
git -c user.name="Lynko CI" -c user.email="ci@lynko.click" \
  commit -m "docs: registra o run da release ${TAG}"
NOVO="$(git rev-parse HEAD)"

rm -rf dist
poetry config pypi-token.pypi "${PYPI_API_TOKEN}"
poetry publish --build --no-interaction

OUT="$(mktemp)"
if ! git push origin "HEAD:${BRANCH}" >"${OUT}" 2>&1; then
  sed -E 's#x-access-token:[^@]+#x-access-token:REDACTED#g' "${OUT}" >&2
  exit 1
fi

TARGET_SHA="${NOVO}" bash "${ROOT}/scripts/abrir-release.sh"

gravar_publicada "${NOVO}"
echo "Versão ${PYVER} publicada no PyPI e tag ${TAG} aberta em ${NOVO}."
