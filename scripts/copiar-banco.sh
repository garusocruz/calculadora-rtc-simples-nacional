#!/usr/bin/env bash
# Copia o sqlite da equivalência para dentro do pacote, antes do build.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORIGEM="${ROOT}/.cache/oficial/java/calculadora/db/calculadora-pro.db"
DESTINO="${ROOT}/calculadora_rtc_simples_nacional/data/calculadora-pro.db"

if [[ ! -f "${ORIGEM}" ]]; then
  echo "A equivalência não deixou ${ORIGEM}." >&2
  exit 1
fi

mkdir -p "$(dirname "${DESTINO}")"
cp -f "${ORIGEM}" "${DESTINO}"
echo "banco copiado para ${DESTINO}"
