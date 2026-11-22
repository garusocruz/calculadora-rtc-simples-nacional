#!/usr/bin/env bash
# pre-push: baixa a calculadora oficial e exige a mesma suíte em Java e Python.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
echo "── pre-push (calculadora-rtc-simples-nacional) ──"
bash "${ROOT}/scripts/equivalencia.sh"
echo "── pre-push OK ──"
