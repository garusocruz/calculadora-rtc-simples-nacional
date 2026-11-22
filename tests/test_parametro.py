from datetime import date
from decimal import Decimal

import pytest

from calculadora_rtc_simples_nacional.parametro import (
    CodigoRegimeApuracao,
    ParametroCalculo,
    RegimeCalculo,
    VocabularioRegime,
    banco_disponivel,
    buscar_vinculos_tpdoc_vigentes,
    listar_atividades_vigentes,
)

DATA = date(2027, 3, 15)
pytestmark = pytest.mark.skipif(not banco_disponivel(), reason="calculadora-pro.db ausente")


def test_tp_doc_suportado() -> None:
    parametro = ParametroCalculo()
    assert parametro.tp_doc_suportado(55, DATA)
    assert parametro.tp_doc_suportado(91, DATA)
    assert not parametro.tp_doc_suportado(97, DATA)


def test_matriz_tipo_receita_padrao() -> None:
    parametro = ParametroCalculo()
    tipo = parametro.buscar_tipo_receita_bruta(1, DATA)
    assert tipo is not None
    assert tipo.descricao == "Receita bruta - interna"
    assert tipo.compoe_receita
    assert tipo.exige_aliquota


def test_regime_crt1() -> None:
    parametro = ParametroCalculo()
    regime = parametro.buscar_regime_apuracao(RegimeCalculo.CRT_1, DATA)
    assert regime is not None
    assert regime.codigo is CodigoRegimeApuracao.SN_PLENO
    assert regime.gera_ibs


def test_situacoes_iss_dez_linhas() -> None:
    situacoes = ParametroCalculo().buscar_situacoes_iss_par_aliquota(DATA)
    assert len(situacoes) == 10


def test_catalogo_quinze_atividades() -> None:
    atividades = listar_atividades_vigentes(DATA)
    assert len(atividades) == 15
    assert atividades[14].codigo == "90"


def test_fator_transicao_2029() -> None:
    fator = ParametroCalculo().buscar_fator_transicao_compra_gov(date(2029, 6, 1))
    assert fator == Decimal("0.10")


def test_vinculos_associativa() -> None:
    vinculos = buscar_vinculos_tpdoc_vigentes(DATA)
    assert len(vinculos) == 29


def test_nfse_tipo_receita_vocabulario() -> None:
    parametro = ParametroCalculo()
    nfse = parametro.buscar_tipo_receita_bruta(4, DATA, VocabularioRegime.NFSE)
    assert nfse is not None
    assert nfse.pendente_suspenso is False
    assert nfse.fator_receita == Decimal(0)