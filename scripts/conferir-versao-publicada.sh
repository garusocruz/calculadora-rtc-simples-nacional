#!/usr/bin/env bash
# Confere que o README tem o run que validou a versão e que o PyPI já tem o pacote.
# Não publica. A tag usa este script para não publicar de novo.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if ! grep -q "o run que validou esta versão" README.md; then
  echo "O README não tem a última validação do build." >&2
  exit 1
fi

nome="$(awk -F'"' '/^name = /{print $2; exit}' pyproject.toml)"
versao="$(awk -F'"' '/^version = /{print $2; exit}' pyproject.toml)"
tag="${TAG_NAME:-v${versao}}"
tagver="${tag#v}"
if [[ "${tagver}" != "${versao}" ]]; then
  echo "A tag ${tag} não é a versão ${versao}." >&2
  exit 1
fi
if [[ -z "${nome}" || -z "${versao}" ]]; then
  echo "pyproject.toml sem nome ou versão." >&2
  exit 1
fi

codigo=""
for _ in 1 2 3 4 5 6; do
  codigo="$(curl -sS -o /dev/null -w '%{http_code}' "https://pypi.org/pypi/${nome}/${versao}/json" || true)"
  if [[ "${codigo}" == "200" ]]; then
    echo "A versão ${versao} já está no PyPI."
    exit 0
  fi
  sleep 10
done

echo "O PyPI respondeu ${codigo:-sem resposta} para ${nome} ${versao}. Quem publica é a esteira da main." >&2
exit 1
