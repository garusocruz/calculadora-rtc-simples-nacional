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


class _Conexao(sqlite3.Connection):
    # O with do sqlite3 confirma a transação e deixa o arquivo aberto.
    # No Cloud Build o limite estoura no meio da suíte.
    # Um with interno da mesma conexão não pode fechá-la: o cálculo ainda a usa.
    def __enter__(self):
        self._withs = getattr(self, "_withs", 0) + 1
        return super().__enter__()

    def __exit__(self, tipo, valor, rastreio):
        try:
            return super().__exit__(tipo, valor, rastreio)
        finally:
            self._withs -= 1
            if self._withs <= 0:
                self.close()


def conectar() -> sqlite3.Connection:
    arquivo = caminho().expanduser().resolve()
    # Três barras: o SQLite do Cloud Build trata file:/workspace/... como caminho relativo.
    return sqlite3.connect(f"{arquivo.as_uri()}?mode=ro", uri=True, factory=_Conexao)


def tabelas() -> set[str]:
    with conectar() as conexao:
        linhas = conexao.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    return {nome for (nome,) in linhas}
