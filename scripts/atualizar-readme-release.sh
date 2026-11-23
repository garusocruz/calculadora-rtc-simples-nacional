#!/usr/bin/env bash
# Grava no README os insumos do build da lib e os insumos deste run.
# Não commita, não abre tag e não publica. O passo seguinte faz isso na mesma esteira.
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
BUILD_LIB="${ROOT}/.ci/steps/build-lib.txt"
if [[ ! -s "${BUILD_LIB}" ]]; then
  echo "Sem o build da lib. O README não abre a versão." >&2
  exit 1
fi

REGION="${_REGION:-${REGION:-us-central1}}"
MERGE_BUILD="${BUILD_ID}"
MERGE_SHA="${COMMIT_SHA}"
MERGE_URL="https://console.cloud.google.com/cloud-build/builds;region=${REGION}/${BUILD_ID}?project=${PROJECT_ID}"

DATE="$(date -u +%Y-%m-%d)"
python3 - README.md "${TAG}" "${MERGE_BUILD}" "${MERGE_URL}" "${DATE}" "${MERGE_SHA}" <<'PY'
import json, pathlib, re, sys
from datetime import datetime, timezone
path, tag, build, url, date, sha = sys.argv[1:]
ver = tag[1:] if tag.startswith("v") else tag
root = pathlib.Path(path).resolve().parent
resumo = json.loads((root / ".ci/steps/equivalencia-resumo.json").read_text(encoding="utf-8"))
meta = {}
for line in (root / ".ci/steps/build-lib.txt").read_text(encoding="utf-8").splitlines():
    if "=" not in line:
        continue
    chave, valor = line.split("=", 1)
    meta[chave.strip()] = valor.strip()
sdist = meta.get("sdist") or ""
wheel = meta.get("wheel") or ""
if not sdist or not wheel:
    raise SystemExit("O build da lib não gravou o sdist e o wheel.")
if meta.get("version") and meta["version"] != ver:
    raise SystemExit(f"O build da lib é {meta['version']} e a release é {ver}.")

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
| Pacote deste run | `{sdist}` e `{wheel}` |
| Frase final | `Equivalência: a mesma suíte passou nas duas.` |"""
text = pathlib.Path(path).read_text(encoding="utf-8")
start = "<!-- release-runs:start -->"
end = "<!-- release-runs:end -->"
block = (
    f"{start}\n"
    f"Release `{tag}` em {date}. "
    f"Build [`{build}`]({url}) no commit `{sha}`.\n"
    f"Pacote deste run: `{sdist}` e `{wheel}`.\n"
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

echo "README gravado com o build e com o run ${MERGE_BUILD}."
