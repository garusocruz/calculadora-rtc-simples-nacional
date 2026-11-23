#!/usr/bin/env bash
# Atualiza o README com o run deste build e abre a pull request para a main.
# Roda antes da tag. O PyPI publica o commit que já contém este README.
# Não imprime o token.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

: "${PROJECT_ID:?}"
: "${BUILD_ID:?}"
: "${COMMIT_SHA:?}"
PYVER="$(awk -F'"' '/^version = /{print $2; exit}' pyproject.toml)"
TAG="${TAG_NAME:-v${PYVER}}"
if [[ ! "${TAG}" =~ ^v([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
  echo "A tag deve ser vX.Y.Z. Veio: ${TAG:-vazio}" >&2
  exit 1
fi
VER="${BASH_REMATCH[1]}"
if [[ "${PYVER}" != "${VER}" ]]; then
  echo "pyproject.toml está em ${PYVER} e a release é ${VER}" >&2
  exit 1
fi
RESUMO="${ROOT}/.ci/steps/equivalencia-resumo.json"
if [[ ! -s "${RESUMO}" ]]; then
  echo "Sem o resumo da equivalência. O README não abre a versão." >&2
  exit 1
fi

REPO="${_GITHUB_REPO:-${GITHUB_REPO:?}}"
OWNER="${_GITHUB_OWNER:-${GITHUB_OWNER:-garusocruz}}"
REGION="${_REGION:-${REGION:-us-central1}}"
MERGE_BUILD="${BUILD_ID}"
MERGE_SHA="${COMMIT_SHA}"
MERGE_URL="https://console.cloud.google.com/cloud-build/builds;region=${REGION}/${BUILD_ID}?project=${PROJECT_ID}"

git fetch origin main
git checkout -B main origin/main

DATE="$(date -u +%Y-%m-%d)"
python3 - README.md "${TAG}" "${MERGE_BUILD}" "${MERGE_URL}" "${DATE}" "${MERGE_SHA}" <<'PY'
import json, pathlib, re, sys
from datetime import datetime, timezone
path, tag, build, url, date, sha = sys.argv[1:]
ver = tag[1:] if tag.startswith("v") else tag
root = pathlib.Path(path).resolve().parent
resumo = json.loads((root / ".ci/steps/equivalencia-resumo.json").read_text(encoding="utf-8"))

def virgula(numero, casas=2):
    return f"{float(numero):.{casas}f}".replace(".", ",")

meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
agora = datetime.now(timezone.utc)
quando = f"{agora.day} de {meses[agora.month - 1]} de {agora.year}"
pytest = f"{resumo['pytest_passaram']} passaram, {resumo['pytest_ignorados']} ignorados, {virgula(resumo['pytest_segundos'])} s"
cob = root / ".ci/steps/cobertura-python.txt"
if cob.is_file():
    stmts, pct = cob.read_text(encoding="utf-8").split()
    cob_py = f"{pct.replace('.', ',')}% de {stmts} sentenças. O mínimo desta lib é 80%"
else:
    raise SystemExit("Sem a cobertura Python. O README não abre a versão.")
if resumo.get("java_linhas") and resumo.get("java_cobertas") is not None:
    linhas = resumo["java_linhas"]
    cobertas = resumo["java_cobertas"]
    pct_java = virgula(100 * cobertas / linhas) if linhas else "0,00"
    cob_java = (
        f"{pct_java}% de {linhas} linhas ({cobertas} cobertas). "
        "JaCoCo do `mvn test` daquele commit, sem a classe `*Application`, como no `pom.xml` oficial. "
        "O workflow oficial exige 80% de linhas"
    )
else:
    raise SystemExit("Sem o JaCoCo. O README não abre a versão.")
bloco = f"""## Última validação

Data: {quando}. Os números abaixo são do Cloud Build [`{build}`]({url}), o run que validou esta versão.

| Checagem | Saída |
| --- | --- |
| Maven test | a suíte Java do pin passou |
| Pytest | {pytest} |
| Cobertura Python | {cob_py} |
| Cobertura Java do pin | {cob_java} |
| Java no corte daquele run | {resumo['java_unitarios']} unitários, {resumo['java_e2e']} e2e |
| Python no relatório | {resumo['python_chaves']} chaves |
| Sem par | {resumo['sem_par']} |
| Resultado diferente | {resumo['diferente']} |
| Frase final | `Equivalência: a mesma suíte passou nas duas.` |"""
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
if bloco:
    ancora = '<a id="ultima-validacao"></a>'
    proxima = '<a id="atualizacao-do-pin"></a>'
    if ancora in text and proxima in text:
        antes, resto = text.split(ancora, 1)
        _, depois = resto.split(proxima, 1)
        text = f"{antes}{ancora}\n\n{bloco.strip()}\n\n{proxima}{depois}"
    else:
        raise SystemExit("README sem a seção de última validação")
pathlib.Path(path).write_text(text, encoding="utf-8")
PY

bash "${ROOT}/deploy/scripts/configure-github-git.sh"
TOKEN_FILE="${CI_GITHUB_TOKEN_FILE:-/workspace/.ci/github_token}"
if [[ ! -s "${TOKEN_FILE}" ]]; then
  echo "Sem token do GitHub para abrir a pull request do README." >&2
  exit 1
fi
TOKEN="$(tr -d '[:space:]' < "${TOKEN_FILE}")"

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
