#!/usr/bin/env bash
# Constrói o sdist e o wheel e grava os nomes para o README do mesmo run.
# O passo seguinte grava esses nomes. A publicação constrói de novo, já com o README.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

if ! command -v poetry >/dev/null 2>&1; then
  echo "poetry não está no PATH" >&2
  exit 1
fi

chmod +x scripts/copiar-banco.sh
bash scripts/copiar-banco.sh

rm -rf dist
poetry build

mkdir -p "${ROOT}/.ci/steps"
python3 - "${ROOT}/dist" "${ROOT}/.ci/steps/build-lib.txt" "${ROOT}/pyproject.toml" <<'PY'
import pathlib, sys

dist, dest, pyproject = map(pathlib.Path, sys.argv[1:])
version = ""
for line in pyproject.read_text(encoding="utf-8").splitlines():
    if line.startswith("version = "):
        version = line.split('"', 2)[1]
        break
sdists = sorted(dist.glob("*.tar.gz"))
wheels = sorted(dist.glob("*.whl"))
if len(sdists) != 1 or len(wheels) != 1:
    raise SystemExit(f"O build gerou {len(sdists)} sdist e {len(wheels)} wheel.")
if not version:
    raise SystemExit("pyproject.toml sem version")
text = f"version={version}\nsdist={sdists[0].name}\nwheel={wheels[0].name}\n"
dest.write_text(text, encoding="utf-8")
print(text, end="")
PY
