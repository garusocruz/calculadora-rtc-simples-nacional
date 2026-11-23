#!/usr/bin/env bash
# Abre a release vX.Y.Z no commit do README que já está na main.
# O corpo copia a Última validação e o bloco da release desse README,
# gravados pela esteira do merge que rodou a suíte. Não gera outra tabela.
# O PyPI fica para o trigger da release. Não imprime o token.
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
: "${COMMIT_SHA:?}"
REPO="${_GITHUB_REPO:-${GITHUB_REPO:?}}"
OWNER="${_GITHUB_OWNER:-${GITHUB_OWNER:-garusocruz}}"

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

python3 - "${TAG}" "${COMMIT_SHA}" "${VER}" "${ROOT}/CHANGELOG.md" /tmp/gh-release-create.json <<'PY'
import json, pathlib, sys
tag, sha, ver, notes_path, dest = sys.argv[1:]
readme = pathlib.Path("README.md").read_text(encoding="utf-8")
if "o run que validou esta versão" not in readme:
    raise SystemExit("O README deste commit não tem a validação do merge na main. Não abre a release.")

def entre(texto, inicio, fim, nome):
    if inicio not in texto or fim not in texto:
        raise SystemExit(f"README sem {nome}. Não abre a release.")
    return texto.split(inicio, 1)[1].split(fim, 1)[0].strip()

validacao = entre(readme, '<a id="ultima-validacao"></a>', '<a id="atualizacao-do-pin"></a>', "Última validação")
runs = entre(readme, "<!-- release-runs:start -->", "<!-- release-runs:end -->", "o bloco da release")
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
parts = [part for part in (notes, validacao, runs) if part]
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
  echo "Release ${TAG} aberta em ${COMMIT_SHA}. O corpo é a Última validação do README."
  exit 0
fi
if [[ "${create}" == "422" ]]; then
  echo "Release ${TAG} já estava aberta."
  exit 0
fi
echo "GitHub respondeu ${create} ao abrir a release ${TAG}." >&2
exit 1
