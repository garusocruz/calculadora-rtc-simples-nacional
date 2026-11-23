#!/usr/bin/env bash
# Abre a pull request do commit da tag para a main.
# O merge só devolve o README. A versão já foi publicada neste run.
# Não imprime o token.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

: "${PROJECT_ID:?}"
: "${BUILD_ID:?}"
: "${COMMIT_SHA:?}"
PYVER="$(awk -F'"' '/^version = /{print $2; exit}' pyproject.toml)"
TAG="v${PYVER}"
REPO="${_GITHUB_REPO:-${GITHUB_REPO:?}}"
OWNER="${_GITHUB_OWNER:-${GITHUB_OWNER:-garusocruz}}"
REGION="${_REGION:-${REGION:-us-central1}}"
BRANCH="docs/release-${TAG}"
STEPS="${ROOT}/.ci/steps"
MODE="$(tr -d '[:space:]' < "${STEPS}/publicar.mode" 2>/dev/null || true)"
if [[ "${MODE}" != "publicado" ]]; then
  echo "A versão não foi publicada neste run. Não abre a pull request do README."
  exit 0
fi

bash "${ROOT}/deploy/scripts/configure-github-git.sh"
TOKEN_FILE="${CI_GITHUB_TOKEN_FILE:-/workspace/.ci/github_token}"
if [[ ! -s "${TOKEN_FILE}" ]]; then
  echo "Sem token do GitHub para abrir a pull request do README." >&2
  exit 1
fi
TOKEN="$(tr -d '[:space:]' < "${TOKEN_FILE}")"
MERGE_URL="https://console.cloud.google.com/cloud-build/builds;region=${REGION}/${BUILD_ID}?project=${PROJECT_ID}"

python3 - "${OWNER}" "${REPO}" "${BRANCH}" "${TAG}" "${BUILD_ID}" "${MERGE_URL}" /tmp/gh-readme-pr.json <<'PY'
import json, pathlib, sys
owner, repo, branch, tag, build, url, dest = sys.argv[1:]
body = (
    f"## Summary\n"
    f"- A tag `{tag}` e o PyPI já saíram do run que validou o merge.\n"
    f"- Esta pull request só leva o README dessa versão para a `main`.\n"
    f"- O merge confere que a versão já está publicada e não abre outra tag.\n"
    f"- Build [`{build}`]({url}).\n\n"
    f"## Context\n"
    f"- O README, a tag e o pacote foram gerados na mesma esteira, depois do quality gate.\n"
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
if [[ "${existing}" == "200" ]]; then
  numero="$(python3 -c 'import json; data=json.load(open("/tmp/gh-readme-prs.json")); print(data[0]["number"] if data else "")')"
  if [[ -n "${numero}" ]]; then
    printf '%s\n' "${numero}" > "${STEPS}/readme-pr.number"
    echo "A pull request de ${BRANCH} já está aberta: #${numero}."
    exit 0
  fi
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
numero="$(python3 -c 'import json; print(json.load(open("/tmp/gh-readme-pr-created.json")).get("number") or "")')"
if [[ -z "${numero}" ]]; then
  echo "A pull request de ${BRANCH} abriu sem número." >&2
  exit 1
fi
printf '%s\n' "${numero}" > "${STEPS}/readme-pr.number"
if [[ -f "${STEPS}/publicacao.md" ]]; then
  printf '\nPull request para a `main`: #%s. O merge confere que esta versão já está publicada e não abre outra tag.\n' "${numero}" >> "${STEPS}/publicacao.md"
fi
echo "Pull request #${numero} da release ${TAG} aberta para a main de ${OWNER}/${REPO}."
