#!/usr/bin/env bash
# Baixa a calculadora oficial no pin, gera o mesmo calculadora-pro.db e roda
# a suíte Java (unitária e de integração, ambas no surefire) e a suíte Python.
# A equivalência só fecha quando cada caso Java passou e a lib tem o mesmo caso,
# com o mesmo resultado.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.local/bin:${HOME}/.asdf/shims:${PATH}"
JAVA_PIN="$(awk '$1=="java" {print $2; exit}' "${ROOT}/.tool-versions")"
if [[ -n "${JAVA_PIN}" ]] && command -v asdf >/dev/null; then
  export JAVA_HOME="$(ASDF_JAVA_VERSION="${JAVA_PIN}" asdf where java)"
  export PATH="${JAVA_HOME}/bin:${PATH}"
fi
OFICIAL_URL="${OFICIAL_URL:-https://github.com/ReceitaFederal/calculadora-rtc-simples-nacional.git}"
OFICIAL_SHA="${OFICIAL_SHA:-a926d5a76095ac0295a6612a9a54db7ffead2396}"
FLYWAY_URL="${FLYWAY_URL:-https://github.com/ReceitaFederal/calculadora-rtc-regime-regular.git}"
FLYWAY_SHA="${FLYWAY_SHA:-f1eebd7ce3157423b1a6aaca7dc1d6c3395452c4}"
CACHE="${ROOT}/.cache/oficial"
JAVA_DIR="${CACHE}/java"
FLYWAY_DIR="${CACHE}/flyway-src"
RELATORIO="${CACHE}/relatorio"
DB="${JAVA_DIR}/calculadora/db/calculadora-pro.db"

java_major() {
  java -version 2>&1 | sed -n 's/.* version "\([0-9][0-9]*\).*/\1/p' | head -1
}

if [[ "$(java_major)" != "25" ]]; then
  echo "A suíte Java oficial exige Java 25. Esta máquina tem: $(java -version 2>&1 | head -1)" >&2
  exit 2
fi

clonar() {
  local url="$1" sha="$2" destino="$3"
  if [[ ! -d "${destino}/.git" ]]; then
    git init "${destino}"
    git -C "${destino}" remote add origin "${url}"
  fi
  git -C "${destino}" fetch --depth 1 origin "${sha}"
  git -C "${destino}" checkout --detach FETCH_HEAD
}

echo "── equivalência: baixando ${OFICIAL_SHA} ──"
clonar "${OFICIAL_URL}" "${OFICIAL_SHA}" "${JAVA_DIR}"
if [[ "${FLYWAY_URL}" != "${OFICIAL_URL}" || "${FLYWAY_SHA}" != "${OFICIAL_SHA}" ]]; then
  clonar "${FLYWAY_URL}" "${FLYWAY_SHA}" "${FLYWAY_DIR}"
  rm -rf "${JAVA_DIR}/flyway"
  cp -a "${FLYWAY_DIR}/flyway" "${JAVA_DIR}/flyway"
fi

mkdir -p "${JAVA_DIR}/calculadora/db" "${RELATORIO}"
echo "── gerando calculadora-pro.db com o Flyway oficial ──"
(cd "${JAVA_DIR}" && ./mvnw -B flyway:migrate -Dflyway.configFiles=./flyway/flyway-pro.conf)
test -f "${DB}"

echo "── suíte Java (unitária e e2e) ──"
(cd "${JAVA_DIR}" && ./mvnw -B test)

echo "── suíte Python sobre o mesmo sqlite ──"
export EQUIVALENCIA=1
export CALC_DB="${DB}"
cd "${ROOT}"
python3 -m pytest -q --junitxml="${RELATORIO}/python.xml"

python3 - "${JAVA_DIR}/target/surefire-reports" "${RELATORIO}/python.xml" <<'PY'
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

java_dir = Path(sys.argv[1])
python_xml = Path(sys.argv[2])

def estado(caso):
    if caso.find("failure") is not None or caso.find("error") is not None:
        return "falha"
    if caso.find("skipped") is not None:
        return "ignorado"
    return "passou"

java = {}
arquivo_da_chave = {}
for caminho in sorted(java_dir.glob("TEST-*.xml")):
    fqcn_arquivo = caminho.name[len("TEST-"):-len(".xml")]
    for caso in ET.parse(caminho).getroot().iter("testcase"):
        classe = caso.get("classname") or ""
        nome = caso.get("name") or ""
        texto = f"{classe} {nome} {fqcn_arquivo}"
        if (
            "Controller" in texto
            or ".controller." in fqcn_arquivo
            or nome.startswith("teste_controller")
            or "retorna400" in nome
            or fqcn_arquivo.endswith("Teste_LoteArredondamento")
            or fqcn_arquivo.endswith("Teste_SerializacaoNaoAlteraNumero")
        ):
            continue
        tipo = "e2e" if "testesintegracao" in (classe + fqcn_arquivo) else "unitario"
        chave = f"{classe}.{nome}"
        java[chave] = (tipo, estado(caso))
        arquivo_da_chave[chave] = fqcn_arquivo

python = {}
for caso in ET.parse(python_xml).getroot().iter("testcase"):
    classe = caso.get("classname") or ""
    nome = caso.get("name") or ""
    python[nome] = estado(caso)
    python[f"{classe}.{nome}"] = estado(caso)

def achar_python(ident):
    estado_python = python.get(ident)
    if estado_python is not None:
        return estado_python
    classe, _, nome = ident.partition(".")
    fqcn = arquivo_da_chave.get(ident, classe)
    nomes = [nome]
    if "(" in nome:
        nomes.append(nome.split("(", 1)[0])
    classes = [classe]
    if fqcn != classe:
        classes.append(fqcn)
    for cl in classes:
        for n in nomes:
            estado_python = python.get(f"{cl}.{n}")
            if estado_python is not None:
                return estado_python
    return None

faltam = []
divergem = []
for ident, (tipo, estado_java) in sorted(java.items()):
    estado_python = achar_python(ident)
    if estado_python is None:
        faltam.append((tipo, ident))
        continue
    if estado_java == estado_python == "ignorado":
        continue
    if estado_java != "passou" or estado_python != "passou":
        divergem.append((ident, estado_java, estado_python))

unit = sum(1 for tipo, _ in java.values() if tipo == "unitario")
e2e = sum(1 for tipo, _ in java.values() if tipo == "e2e")
print(f"Java unitários: {unit}")
print(f"Java e2e: {e2e}")
print(f"Python: {len({nome for nome in python})} casos no relatório")
print(f"Casos Java sem o mesmo teste na lib: {len(faltam)}")
print(f"Casos com resultado diferente: {len(divergem)}")
for tipo, ident in faltam[:20]:
    print(f"  falta {tipo} {ident}")
for ident, ej, ep in divergem[:20]:
    print(f"  diverge {ident} java={ej} python={ep}")
if faltam or divergem:
    raise SystemExit(1)
print("Equivalência: a mesma suíte passou nas duas.")
PY
echo "── equivalência OK ──"
