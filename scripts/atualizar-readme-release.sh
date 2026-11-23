#!/usr/bin/env bash
# Grava o run desta release no README e envia o commit para a main.
# Não imprime o token. Só corre com TAG_NAME=vX.Y.Z igual ao pyproject.toml.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

TAG="${TAG_NAME:-}"
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
REPO="${_GITHUB_REPO:-${GITHUB_REPO:?}}"
OWNER="${_GITHUB_OWNER:-${GITHUB_OWNER:-garusocruz}}"
REGION="${_REGION:-${REGION:-us-central1}}"
URL="https://console.cloud.google.com/cloud-build/builds;region=${REGION}/${BUILD_ID}?project=${PROJECT_ID}"
DATE="$(date -u +%Y-%m-%d)"

python3 - "${ROOT}/README.md" "${TAG}" "${BUILD_ID}" "${URL}" "${DATE}" <<'PY'
import pathlib, sys
path, tag, build, url, date = sys.argv[1:]
text = pathlib.Path(path).read_text(encoding="utf-8")
start = "<!-- release-runs:start -->"
end = "<!-- release-runs:end -->"
block = (
    f"{start}\n"
    f"Release `{tag}` em {date}. "
    f"Build [`{build}`]({url}).\n"
    f"{end}"
)
if start not in text or end not in text:
    raise SystemExit("README sem os marcadores release-runs")
pre, rest = text.split(start, 1)
_, post = rest.split(end, 1)
pathlib.Path(path).write_text(pre + block + post, encoding="utf-8")
PY

bash "${ROOT}/deploy/scripts/configure-github-git.sh"
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
