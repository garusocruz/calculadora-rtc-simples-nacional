from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from calculadora_rtc_simples_nacional.escolha import VocabularioRegime
from calculadora_rtc_simples_nacional.parametro import TipoReceitaBruta
from calculadora_rtc_simples_nacional.processador import (
    AliquotasItem,
    ContextoItem,
    DadosAliquotas,
    EntradaItem,
    EstadoItemProcessado,
    ProcessadorItemSimples,
    RegimeContexto,
    ValidacaoNomenclaturaBasica,
)
DATA = date(2027, 3, 15)


def _regime_sn_pleno() -> RegimeContexto:
    return RegimeContexto("SN_PLENO", True, True, "SN_PLENO")


def _regime_somente_receita() -> RegimeContexto:
    return RegimeContexto("SOMENTE_RECEITA", False, None, "SOMENTE_RECEITA")


def _contexto_nfse(regime: RegimeContexto, *, permite_ncm_zero: bool = False) -> ContextoItem:
    return ContextoItem(
        DATA,
        91,
        regime,
        None,
        None,
        VocabularioRegime.NFSE,
        True,
        False,
        2,
        "NFSe",
        permite_ncm_zero,
    )


def _tipo_nfse(codigo: int) -> TipoReceitaBruta:
    return TipoReceitaBruta(
        codigo,
        "desc",
        True,
        False,
        Decimal(1 if codigo == 1 else 0),
        False,
        codigo == 1,
        codigo in {1, 2, 3, 4, 5},
        VocabularioRegime.NFSE,
    )


def _resolvedor_fixo(_dados: DadosAliquotas, _collector) -> AliquotasItem:
    return AliquotasItem(Decimal("0.0263"), Decimal("2.3874"))


def _stub_classificacao() -> None:
    from calculadora_rtc_simples_nacional import parametro

    classificacao = parametro.ClassificacaoTributaria(1, "000001", 1)

    def fake_vigentes(codigo: str, data: date):
        return [classificacao] if codigo == "000001" else []

    patchers = [
        patch.object(parametro, "buscar_classificacoes_vigentes", side_effect=fake_vigentes),
        patch.object(parametro, "contar_vinculo_classificacao_tpdoc", return_value=1),
        patch.object(parametro, "contar_tratamentos_nao_implementados", return_value=0),
        patch(
            "calculadora_rtc_simples_nacional.processador.contar_tratamentos_nao_implementados",
            return_value=0,
        ),
        patch(
            "calculadora_rtc_simples_nacional.processador.buscar_classificacoes_vigentes",
            side_effect=fake_vigentes,
        ),
        patch(
            "calculadora_rtc_simples_nacional.processador.contar_vinculo_classificacao_tpdoc",
            return_value=1,
        ),
        patch(
            "calculadora_rtc_simples_nacional.processador.buscar_atividades_por_cativsn",
            return_value=[],
        ),
        patch(
            "calculadora_rtc_simples_nacional.processador.contar_vinculo_atividade_tpdoc",
            return_value=0,
        ),
        patch.object(
            parametro.ParametroCalculo,
            "buscar_tipo_receita_bruta",
            return_value=_tipo_nfse(1),
        ),
    ]
    return patchers


@pytest.fixture
def processador() -> ProcessadorItemSimples:
    return ProcessadorItemSimples()


def test_normalizar_cativ_sn() -> None:
    assert ProcessadorItemSimples.normalizar_cativ_sn(" 7 ", True) == "07"
    assert ProcessadorItemSimples.normalizar_cativ_sn("7", False) == "7"


def test_nfse_imposto_seletivo_vsn035(processador: ProcessadorItemSimples) -> None:
    patchers = _stub_classificacao()
    for p in patchers:
        p.start()
    try:
        resultado = processador.processar_item(
            EntradaItem(1, "07", "000001", "1000.00", "10.00", None, None),
            0,
            _contexto_nfse(_regime_sn_pleno()),
            _resolvedor_fixo,
        )
        assert resultado.objeto.estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
        assert resultado.objeto.erros[0].code == "VSN-035"
    finally:
        for p in patchers:
            p.stop()


def test_somente_receita_so_receita_bruta(processador: ProcessadorItemSimples) -> None:
    patchers = _stub_classificacao()
    for p in patchers:
        p.start()
    try:
        sem_chamada = lambda *a, **k: (_ for _ in ()).throw(AssertionError("resolvedor"))
        resultado = processador.processar_item(
            EntradaItem(1, "07", "000001", "1000.00", None, None, None),
            0,
            _contexto_nfse(_regime_somente_receita()),
            sem_chamada,
        )
        assert resultado.objeto.estado is EstadoItemProcessado.NAO_CALCULADO
        assert resultado.objeto.tributos.receita_bruta == Decimal("1000.00")
    finally:
        for p in patchers:
            p.stop()


def test_nomenclatura_simultanea_vsn041() -> None:
    nomenclatura = ValidacaoNomenclaturaBasica()
    processador = ProcessadorItemSimples(nomenclatura=nomenclatura)
    patchers = _stub_classificacao()
    for p in patchers:
        p.start()
    try:
        resultado = processador.processar_item(
            EntradaItem(1, "07", "000001", "1000.00", None, "22030000", "114051000"),
            0,
            _contexto_nfse(_regime_somente_receita()),
            _resolvedor_fixo,
        )
        assert resultado.objeto.erros[0].code == "VSN-041"
    finally:
        for p in patchers:
            p.stop()


def test_prioridade_vsn027(processador: ProcessadorItemSimples) -> None:
    with patch(
        "calculadora_rtc_simples_nacional.processador.contar_tratamentos_nao_implementados",
        return_value=1,
    ):
        resultado = processador.processar_item(
            EntradaItem(1, "07", "000001", "1000.00", None, "22030000", "114051000"),
            0,
            _contexto_nfse(_regime_somente_receita()),
            _resolvedor_fixo,
        )
    assert resultado.objeto.erros[0].code == "VSN-027"


def test_calcular_item_integrado(processador: ProcessadorItemSimples) -> None:
    from calculadora_rtc_simples_nacional import parametro
    ativ_dom = parametro.AtividadeNacional(
        7,
        7,
        "x",
        "07",
        "III",
        None,
        False,
        True,
        False,
    )
    patchers = _stub_classificacao() + [
        patch.object(parametro, "buscar_atividades_por_cativsn", return_value=[ativ_dom]),
        patch.object(parametro, "contar_vinculo_atividade_tpdoc", return_value=1),
        patch(
            "calculadora_rtc_simples_nacional.processador.buscar_atividades_por_cativsn",
            return_value=[ativ_dom],
        ),
        patch(
            "calculadora_rtc_simples_nacional.processador.contar_vinculo_atividade_tpdoc",
            return_value=1,
        ),
    ]
    for p in patchers:
        p.start()
    try:
        resultado = processador.processar_item(
            EntradaItem(1, "7", "000001", "1000.00", None, None, None),
            0,
            _contexto_nfse(_regime_sn_pleno()),
            _resolvedor_fixo,
        )
        assert resultado.objeto.estado is EstadoItemProcessado.CALCULADO
        assert resultado.objeto.tributos.valor_cbs == Decimal("23.90")
    finally:
        for p in patchers:
            p.stop()