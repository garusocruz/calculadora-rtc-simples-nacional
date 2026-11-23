#!/usr/bin/env bash
# Grava no README o build da main que abriu a release.
# Não usa o build deste trigger. Não imprime o token.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

: "${TAG_NAME:?}"
TAG="${TAG_NAME}"
if [[ ! "${TAG}" =~ ^v([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
  echo "TAG_NAME deve ser vX.Y.Z. Veio: ${TAG}" >&2
  exit 1
fi
VER="${BASH_REMATCH[1]}"
PYVER="$(awk -F'"' '/^version = /{print $2; exit}' pyproject.toml)"
if [[ "${PYVER}" != "${VER}" ]]; then
  echo "pyproject.toml está em ${PYVER} e a release é ${VER}" >&2
  exit 1
fi

REPO="${_GITHUB_REPO:-${GITHUB_REPO:?}}"
OWNER="${_GITHUB_OWNER:-${GITHUB_OWNER:-garusocruz}}"

bash "${ROOT}/deploy/scripts/configure-github-git.sh"
TOKEN_FILE="${CI_GITHUB_TOKEN_FILE:-/workspace/.ci/github_token}"
if [[ ! -s "${TOKEN_FILE}" ]]; then
  echo "Sem token do GitHub para ler a release." >&2
  exit 1
fi
TOKEN="$(tr -d '[:space:]' < "${TOKEN_FILE}")"

http="$(curl -sS -o /tmp/gh-release-get.json -w '%{http_code}' \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${OWNER}/${REPO}/releases/tags/${TAG}")"
if [[ "${http}" != "200" ]]; then
  echo "GitHub respondeu ${http} ao ler a release ${TAG}." >&2
  exit 1
fi

eval "$(python3 - /tmp/gh-release-get.json <<'PY'
import json, shlex, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
fields = {}
for line in (data.get("body") or "").splitlines():
    if ": " not in line:
        continue
    key, value = line.split(": ", 1)
    fields[key] = value.strip()
for key in ("Build", "Commit", "URL"):
    if not fields.get(key):
        raise SystemExit(f"release sem {key} do build da main")
print(f"MERGE_BUILD={shlex.quote(fields['Build'])}")
print(f"MERGE_SHA={shlex.quote(fields['Commit'])}")
print(f"MERGE_URL={shlex.quote(fields['URL'])}")
PY
)"

git fetch origin main
git checkout -B main origin/main
if grep -F "${MERGE_BUILD}" README.md >/dev/null; then
  echo "README da main já registra o build ${MERGE_BUILD}."
  exit 0
fi

DATE="$(date -u +%Y-%m-%d)"
python3 - README.md "${TAG}" "${MERGE_BUILD}" "${MERGE_URL}" "${DATE}" "${MERGE_SHA}" <<'PY'
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
