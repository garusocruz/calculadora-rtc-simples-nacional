import os

import pytest

from calculadora_rtc_simples_nacional.banco import tabelas

TABELAS = {
    "ALIQUOTA_PADRAO",
    "ALIQUOTA_REFERENCIA",
    "CLASSIFICACAO_TRIBUTARIA",
    "NCM",
    "NBS",
    "SITUACAO_TRIBUTARIA",
    "TRATAMENTO_TRIBUTARIO",
}


def test_le_as_tabelas_do_sqlite_oficial() -> None:
    if os.environ.get("EQUIVALENCIA") != "1":
        pytest.skip("o pre-push e o CI abrem o calculadora-pro.db oficial")
    assert TABELAS <= tabelas()
