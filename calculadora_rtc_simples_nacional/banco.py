"""Abre o mesmo SQLite que a calculadora Java.

O perfil oficial usa
``jdbc:sqlite:file:./calculadora/db/calculadora-pro.db?mode=ro``.
O arquivo é o que o Flyway do regime regular gera. A lib não cria outro banco.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

ARQUIVO = Path("calculadora/db/calculadora-pro.db")


def caminho() -> Path:
    informado = os.environ.get("CALC_DB")
    if informado:
        return Path(informado)
    return ARQUIVO


def conectar() -> sqlite3.Connection:
    arquivo = caminho()
    return sqlite3.connect(f"file:{arquivo}?mode=ro", uri=True)


def tabelas() -> set[str]:
    with conectar() as conexao:
        linhas = conexao.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    return {nome for (nome,) in linhas}
