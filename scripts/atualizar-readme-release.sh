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
    if not line.startswith(("Build: ", "Commit: ", "URL: ")):
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
import pathlib, re, sys
path, tag, build, url, date, sha = sys.argv[1:]
ver = tag[1:] if tag.startswith("v") else tag
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
text = pre + block + post
text = text.replace(
    "O número deste repositório não vira release no GitHub.",
    f"A release `{tag}` é essa versão no GitHub.",
)
text = re.sub(
    r"(\[!\[PyPI )[0-9]+\.[0-9]+\.[0-9]+(\])",
    rf"\g<1>{ver}\g<2>",
    text,
    count=1,
)
text = re.sub(
    r"(O índice público do PyPI tem a `)[0-9]+\.[0-9]+\.[0-9]+(`)",
    rf"\g<1>{ver}\g<2>",
    text,
    count=1,
)
text = re.sub(
    r"(O pacote público no PyPI é a `)[0-9]+\.[0-9]+\.[0-9]+(`)",
    rf"\g<1>{ver}\g<2>",
    text,
    count=1,
)
pathlib.Path(path).write_text(text, encoding="utf-8")
PY

BRANCH="docs/release-${TAG}"
git checkout -B "${BRANCH}"
git add README.md
if git diff --cached --quiet; then
  echo "README já registra este run"
  exit 0
fi
git -c user.name="Lynko CI" -c user.email="ci@lynko.click" \
  commit -m "docs: registra o run da release ${TAG}"

OUT="$(mktemp)"
if ! git push origin "HEAD:${BRANCH}" >"${OUT}" 2>&1; then
  sed -E 's#x-access-token:[^@]+#x-access-token:REDACTED#g' "${OUT}" >&2
  exit 1
fi

python3 - "${OWNER}" "${REPO}" "${BRANCH}" "${TAG}" "${MERGE_BUILD}" "${MERGE_URL}" /tmp/gh-readme-pr.json <<'PY'
import json, pathlib, sys
owner, repo, branch, tag, build, url, dest = sys.argv[1:]
body = (
    f"## Summary\n"
    f"- A release `{tag}` grava o run no README e aponta a versão pública.\n"
    f"- Build [`{build}`]({url}).\n\n"
    f"## Context\n"
    f"- O trigger da release não escreve na `main`. Esta pull request leva o README.\n"
)
pathlib.Path(dest).write_text(
    json.dumps({"title": f"docs: registra o run da release {tag}", "head": branch, "base": "main", "body": body}),
    encoding="utf-8",
)
PY
existing="$(curl -sS -o /tmp/gh-readme-prs.json -w '%{http_code}' \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/${OWNER}/${REPO}/pulls?head=${OWNER}:${BRANCH}&state=open")"
if [[ "${existing}" == "200" ]] && python3 -c 'import json,sys; sys.exit(0 if json.load(open("/tmp/gh-readme-prs.json")) else 1)'; then
  echo "A pull request de ${BRANCH} já está aberta."
  exit 0
fi
pr="$(curl -sS -o /tmp/gh-readme-pr-created.json -w '%{http_code}' \
  -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/gh-readme-pr.json \
  "https://api.github.com/repos/${OWNER}/${REPO}/pulls")"
if [[ "${pr}" != "201" ]]; then
  echo "GitHub respondeu ${pr} ao abrir a pull request de ${BRANCH}." >&2
  exit 1
fi
echo "Pull request da release ${TAG} aberta para a main de ${OWNER}/${REPO}"
