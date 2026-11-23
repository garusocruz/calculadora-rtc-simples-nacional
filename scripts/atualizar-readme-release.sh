#!/usr/bin/env bash
# Grava este build no README da main.
# O commit de registro não abre outro ciclo. Se a main já tem a release, o build gravado fica.
# Não imprime o token.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

mkdir -p /workspace/.ci

subject="$(git log -1 --format=%s)"
if [[ "${subject}" == "docs: registra o run da release "* ]]; then
  echo "Commit de registro do README. Não grava outro run."
  echo skip >/workspace/.ci/skip-publish
  exit 0
fi

if [[ -z "${TAG_NAME:-}" ]]; then
  TAG_NAME="v$(awk -F'"' '/^version = /{print $2; exit}' pyproject.toml)"
fi

TAG="${TAG_NAME}"
if [[ ! "${TAG}" =~ ^v([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
  echo "TAG_NAME deve ser vX.Y.Z. Veio: ${TAG:-vazio}" >&2
  exit 1
fi
VER="${BASH_REMATCH[1]}"
PYVER="$(awk -F'"' '/^version = /{print $2; exit}' pyproject.toml)"
if [[ "${PYVER}" != "${VER}" ]]; then
  echo "pyproject.toml está em ${PYVER} e a release é ${VER}" >&2
  exit 1
fi

: "${PROJECT_ID:?}"
: "${BUILD_ID:?}"
SHA="${COMMIT_SHA:-$(git rev-parse HEAD)}"
REPO="${_GITHUB_REPO:-${GITHUB_REPO:?}}"
OWNER="${_GITHUB_OWNER:-${GITHUB_OWNER:-garusocruz}}"
REGION="${_REGION:-${REGION:-us-central1}}"

bash "${ROOT}/deploy/scripts/configure-github-git.sh"
git fetch origin main
if git show "origin/main:README.md" | grep -F "Release \`${TAG}\`" >/dev/null; then
  echo "README da main já registra ${TAG}."
  exit 0
fi

URL="https://console.cloud.google.com/cloud-build/builds;region=${REGION}/${BUILD_ID}?project=${PROJECT_ID}"
DATE="$(date -u +%Y-%m-%d)"

python3 - "${ROOT}/README.md" "${TAG}" "${BUILD_ID}" "${URL}" "${DATE}" "${SHA}" <<'PY'
import pathlib, sys
path, tag, build, url, date, sha = sys.argv[1:]
text = pathlib.Path(path).read_text(encoding="utf-8")
start = "<!-- release-runs:start -->"
end = "<!-- release-runs:end -->"
block = (
    f"{start}\n"
    f"Release `{tag}` em {date}. "
    f"Build [`{build}`]({url}) no commit `{sha}`.\n"
    f"{end}"
)
if start not in text or end not in text:
    raise SystemExit("README sem os marcadores release-runs")
pre, rest = text.split(start, 1)
_, post = rest.split(end, 1)
pathlib.Path(path).write_text(pre + block + post, encoding="utf-8")
PY

git add README.md
if git diff --cached --quiet; then
  echo "README já registra este run"
else
  git -c user.name="Lynko CI" -c user.email="ci@lynko.click" \
    commit -m "docs: registra o run da release ${TAG}"
fi

OUT="$(mktemp)"
if ! git push origin HEAD:main >"${OUT}" 2>&1; then
  sed -E 's#x-access-token:[^@]+#x-access-token:REDACTED#g' "${OUT}" >&2
  exit 1
fi
echo "README da release ${TAG} enviado para a main de ${OWNER}/${REPO}"
