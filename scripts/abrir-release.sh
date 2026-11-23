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

python3 - "${TAG}" "${COMMIT_SHA}" "${BUILD_ID}" "${URL}" "${VER}" "${ROOT}/CHANGELOG.md" "${CI_STEPS_DIR:-/workspace/.ci/steps}/pr-comment.md" /tmp/gh-release-create.json <<'PY'
import json, pathlib, sys
from datetime import datetime, timezone
tag, sha, build, url, ver, notes_path, comment_path, dest = sys.argv[1:]
steps = pathlib.Path(comment_path).parent

def virgula(numero, casas=2):
    return f"{float(numero):.{casas}f}".replace(".", ",")

def secao_validacao():
    resumo = steps / "equivalencia-resumo.json"
    if not resumo.is_file():
        return ""
    dados = json.loads(resumo.read_text(encoding="utf-8"))
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    agora = datetime.now(timezone.utc)
    data = f"{agora.day} de {meses[agora.month - 1]} de {agora.year}"
    pytest = f"{dados['pytest_passaram']} passaram, {dados['pytest_ignorados']} ignorados, {virgula(dados['pytest_segundos'])} s"
    cobertura = steps / "cobertura-python.txt"
    if cobertura.is_file():
        stmts, pct = cobertura.read_text(encoding="utf-8").split()
        cob_py = f"{pct.replace('.', ',')}% de {stmts} sentenças. O mínimo desta lib é 80%"
    else:
        cob_py = "o quality gate não gravou a cobertura"
    if dados.get("java_linhas") and dados.get("java_cobertas") is not None:
        linhas = dados["java_linhas"]
        cobertas = dados["java_cobertas"]
        pct_java = virgula(100 * cobertas / linhas) if linhas else "0,00"
        cob_java = (
            f"{pct_java}% de {linhas} linhas ({cobertas} cobertas). "
            "JaCoCo do `mvn test` daquele commit, sem a classe `*Application`, como no `pom.xml` oficial. "
            "O workflow oficial exige 80% de linhas"
        )
    else:
        cob_java = "a suíte Java do pin passou. O JaCoCo não gravou o relatório neste run"
    miolo = f"""## Última validação

Data: {data}. Os números abaixo são do Cloud Build [`{build}`]({url}), o run que validou esta versão.

| Checagem | Saída |
| --- | --- |
| Maven test | a suíte Java do pin passou |
| Pytest | {pytest} |
| Cobertura Python | {cob_py} |
| Cobertura Java do pin | {cob_java} |
| Java no corte daquele run | {dados['java_unitarios']} unitários, {dados['java_e2e']} e2e |
| Python no relatório | {dados['python_chaves']} chaves |
| Sem par | {dados['sem_par']} |
| Resultado diferente | {dados['diferente']} |
| Frase final | `Equivalência: a mesma suíte passou nas duas.` |"""
    return f"<!-- ultima-validacao:start -->\n{miolo.strip()}\n<!-- ultima-validacao:end -->"

notes = ""
changelog = pathlib.Path(notes_path)
if changelog.is_file():
    lines = changelog.read_text(encoding="utf-8").splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith(f"## {ver}"):
            start = i
            break
    if start is not None:
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if lines[j].startswith("## "):
                end = j
                break
        notes = "\n".join(lines[start:end]).strip()
comment = ""
comment_file = pathlib.Path(comment_path)
if comment_file.is_file():
    comment = comment_file.read_text(encoding="utf-8").strip()
validacao = secao_validacao()
parts = [part for part in (notes, validacao, comment) if part]
parts.append(f"Build: {build}\nCommit: {sha}\nURL: {url}")
body = "\n\n".join(parts) + "\n"
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
