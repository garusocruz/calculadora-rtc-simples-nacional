"""Casos dourados de ``Teste_SimplesNacionalCalculoService`` (pin a926d5a7)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from calculadora_rtc_simples_nacional.consumo import SimplesNacionalCalculoService
from calculadora_rtc_simples_nacional.simples import (
    Destino,
    EstadoItem,
    Insumo,
    Motivo,
    Regime,
    TipoReceita,
)

_CLASSNAME = (
    "br.gov.serpro.rtc.testesunitarios.simplesnacional.Teste_SimplesNacionalCalculoService"
)


@pytest.fixture
def service() -> SimplesNacionalCalculoService:
    return SimplesNacionalCalculoService()


def _tipo(codigo: int, *, seletivo_na_receita: bool = False) -> TipoReceita:
    linhas = {
        0: ("Não é receita bruta", False, "0.0", False, False, False),
        1: ("Receita bruta - interna", True, "1.0", False, True, True),
        2: ("Receita bruta - interna sem cálculo de IBS e CBS", True, "0.0", False, False, True),
        3: ("Receita bruta - exportação direta", True, "0.0", False, False, True),
        4: ("Receita bruta - exportação indireta", True, "1.0", True, True, True),
        5: ("Receita bruta - mercado interno e exportação", True, "0.5", False, True, True),
        9: ("Fornecimento incompatível com SN", True, "0.0", False, False, False),
    }
    descricao, compoe, fator, pendente, exige, vedado = linhas[codigo]
    return TipoReceita(
        codigo,
        descricao,
        compoe,
        Decimal(fator),
        pendente,
        seletivo_na_receita,
        exige,
        vedado,
    )


def _regime_crt1() -> Regime:
    return Regime("SN_PLENO", True, "CRT 1", True, Destino.DEVIDO, Destino.PENDENTE_SUSPENSO)


def _regime_crt2() -> Regime:
    return Regime("SN_SUBLIMITE", True, "CRT 2", False, Destino.DEVIDO, Destino.PENDENTE_SUSPENSO)


def _regime_crt3_tp_regime2() -> Regime:
    return Regime("PENDENTE", True, "CRT 3 + tpRegimeIBSCBS 2", True, Destino.PENDENTE_SUSPENSO, Destino.ZERO)


def _insumo(
    regime: Regime,
    tipo: TipoReceita,
    base: str = "1000.00",
    seletivo: str = "0.00",
    ibs: str | None = "1.25",
    cbs: str | None = "2.75",
    ente: int | None = None,
    fator: str | None = None,
    motivo: Motivo | None = None,
) -> Insumo:
    return Insumo(
        regime,
        tipo,
        motivo,
        Decimal(base),
        Decimal(seletivo),
        Decimal(ibs) if ibs is not None else None,
        Decimal(cbs) if cbs is not None else None,
        ente,
        Decimal(fator) if fator is not None else None,
        None,
    )


def _insumo_padrao(regime: Regime, tp_rbsn: int) -> Insumo:
    return _insumo(regime, _tipo(tp_rbsn))


def _assert_valor(esperado: str, atual: Decimal | None) -> None:
    assert atual is not None
    assert Decimal(esperado).compare(atual) == 0


def _calcular(service: SimplesNacionalCalculoService, insumo: Insumo):
    resultado = service.calcularItem(insumo)
    assert resultado.estado is EstadoItem.CALCULADO
    assert resultado.tributos is not None
    return resultado.tributos


def _junit(record_xml_attribute, name: str) -> None:
    record_xml_attribute("classname", _CLASSNAME)
    record_xml_attribute("name", name)


def test_caso01_crt1_tpRBSN1(service: SimplesNacionalCalculoService, record_xml_attribute) -> None:
    _junit(record_xml_attribute, "caso01_crt1_tpRBSN1")
    trib = _calcular(service, _insumo_padrao(_regime_crt1(), 1))
    _assert_valor("1000.00", trib.receita_bruta)
    assert trib.tipo_receita == 1
    assert trib.descricao_tipo_receita == "Receita bruta - interna"
    _assert_valor("1000.00", trib.base_calculo)
    _assert_valor("12.50", trib.valor_ibs)
    _assert_valor("0.00", trib.ibs_pendente)
    _assert_valor("27.50", trib.valor_cbs)
    _assert_valor("0.00", trib.cbs_pendente)
    _assert_valor("40.00", trib.total_item)


def test_caso02_crt1_tpRBSN1_impostoSeletivoForaDaReceitaBruta(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso02_crt1_tpRBSN1_impostoSeletivoForaDaReceitaBruta")
    trib = _calcular(service, _insumo(_regime_crt1(), _tipo(1), "950.00", "50.00"))
    _assert_valor("950.00", trib.receita_bruta)
    _assert_valor("11.88", trib.valor_ibs)
    _assert_valor("0.00", trib.ibs_pendente)
    _assert_valor("26.12", trib.valor_cbs)
    _assert_valor("0.00", trib.cbs_pendente)
    assert trib.imposto_seletivo is not None
    _assert_valor("50.00", trib.imposto_seletivo.valor)
    _assert_valor("88.00", trib.total_item)


def test_caso02b_crt1_tpRBSN1_impostoSeletivoNaReceitaBrutaQuandoParametrizado(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso02b_crt1_tpRBSN1_impostoSeletivoNaReceitaBrutaQuandoParametrizado")
    trib = _calcular(
        service,
        _insumo(_regime_crt1(), _tipo(1, seletivo_na_receita=True), "950.00", "50.00"),
    )
    _assert_valor("1000.00", trib.receita_bruta)
    _assert_valor("12.50", trib.valor_ibs)
    _assert_valor("0.00", trib.ibs_pendente)
    _assert_valor("27.50", trib.valor_cbs)
    _assert_valor("0.00", trib.cbs_pendente)
    assert trib.imposto_seletivo is not None
    _assert_valor("50.00", trib.imposto_seletivo.valor)
    _assert_valor("90.00", trib.total_item)


def test_caso03_crt1_tpRBSN5_metadeDaReceita(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso03_crt1_tpRBSN5_metadeDaReceita")
    trib = _calcular(service, _insumo_padrao(_regime_crt1(), 5))
    _assert_valor("1000.00", trib.receita_bruta)
    _assert_valor("500.00", trib.base_calculo)
    _assert_valor("6.25", trib.valor_ibs)
    _assert_valor("0.00", trib.ibs_pendente)
    _assert_valor("13.75", trib.valor_cbs)
    _assert_valor("0.00", trib.cbs_pendente)


def test_caso04_crt1_tpRBSN4_exportacaoIndiretaSuspende(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso04_crt1_tpRBSN4_exportacaoIndiretaSuspende")
    trib = _calcular(service, _insumo_padrao(_regime_crt1(), 4))
    _assert_valor("1000.00", trib.receita_bruta)
    _assert_valor("0.00", trib.valor_ibs)
    _assert_valor("12.50", trib.ibs_pendente)
    _assert_valor("0.00", trib.valor_cbs)
    _assert_valor("27.50", trib.cbs_pendente)
    _assert_valor("0.00", trib.total_item)


def test_caso05a07_crt1_tpRBSN2_3_9_tudoZero(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso05a07_crt1_tpRBSN2_3_9_tudoZero")
    for tp_rbsn in (2, 3, 9):
        trib = _calcular(service, _insumo_padrao(_regime_crt1(), tp_rbsn))
        _assert_valor("1000.00", trib.receita_bruta)
        _assert_valor("0.00", trib.base_calculo)
        _assert_valor("0.00", trib.valor_ibs)
        _assert_valor("0.00", trib.ibs_pendente)
        _assert_valor("0.00", trib.valor_cbs)
        _assert_valor("0.00", trib.cbs_pendente)


def test_caso08_crt1_tpRBSN0_receitaBrutaZerada(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso08_crt1_tpRBSN0_receitaBrutaZerada")
    trib = _calcular(service, _insumo(_regime_crt1(), _tipo(0), "1000.00", "50.00"))
    _assert_valor("0.00", trib.receita_bruta)
    assert trib.tipo_receita == 0
    assert trib.descricao_tipo_receita == "Não é receita bruta"
    _assert_valor("0.00", trib.base_calculo)
    _assert_valor("0.00", trib.valor_ibs)
    _assert_valor("0.00", trib.ibs_pendente)
    _assert_valor("0.00", trib.valor_cbs)
    _assert_valor("0.00", trib.cbs_pendente)


def test_caso09_crt2_tpRBSN1_camposDeIbsSuprimidos(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso09_crt2_tpRBSN1_camposDeIbsSuprimidos")
    trib = _calcular(service, _insumo_padrao(_regime_crt2(), 1))
    _assert_valor("1000.00", trib.receita_bruta)
    _assert_valor("1000.00", trib.base_calculo)
    assert trib.aliquota_ibs is None
    assert trib.valor_ibs is None
    assert trib.ibs_pendente is None
    _assert_valor("27.50", trib.valor_cbs)
    _assert_valor("0.00", trib.cbs_pendente)
    _assert_valor("27.50", trib.total_item)


def test_caso10_crt2_tpRBSN4_cbsSuspensa(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso10_crt2_tpRBSN4_cbsSuspensa")
    trib = _calcular(service, _insumo_padrao(_regime_crt2(), 4))
    _assert_valor("1000.00", trib.receita_bruta)
    assert trib.valor_ibs is None
    assert trib.ibs_pendente is None
    _assert_valor("0.00", trib.valor_cbs)
    _assert_valor("27.50", trib.cbs_pendente)


def test_caso11_crt3tpReg2_tpRBSN1_tudoPendenteSuspenso(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso11_crt3tpReg2_tpRBSN1_tudoPendenteSuspenso")
    trib = _calcular(service, _insumo_padrao(_regime_crt3_tp_regime2(), 1))
    _assert_valor("1000.00", trib.receita_bruta)
    _assert_valor("0.00", trib.valor_ibs)
    _assert_valor("12.50", trib.ibs_pendente)
    _assert_valor("0.00", trib.valor_cbs)
    _assert_valor("27.50", trib.cbs_pendente)


def test_caso12_crt3tpReg2_tpRBSN5_metadePendenteSuspensa(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso12_crt3tpReg2_tpRBSN5_metadePendenteSuspensa")
    trib = _calcular(service, _insumo_padrao(_regime_crt3_tp_regime2(), 5))
    _assert_valor("1000.00", trib.receita_bruta)
    _assert_valor("0.00", trib.valor_ibs)
    _assert_valor("6.25", trib.ibs_pendente)
    _assert_valor("0.00", trib.valor_cbs)
    _assert_valor("13.75", trib.cbs_pendente)


def test_caso13_crt3tpReg2_tpRBSN4_tudoZeroLiteralDaNT(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso13_crt3tpReg2_tpRBSN4_tudoZeroLiteralDaNT")
    trib = _calcular(service, _insumo_padrao(_regime_crt3_tp_regime2(), 4))
    _assert_valor("1000.00", trib.receita_bruta)
    _assert_valor("0.00", trib.valor_ibs)
    _assert_valor("0.00", trib.ibs_pendente)
    _assert_valor("0.00", trib.valor_cbs)
    _assert_valor("0.00", trib.cbs_pendente)


def test_caso14_compraGovUniao_deslocaIbsParaCbs(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso14_compraGovUniao_deslocaIbsParaCbs")
    trib = _calcular(service, _insumo(_regime_crt1(), _tipo(1), ente=1))
    _assert_valor("0.00", trib.aliquota_ibs)
    _assert_valor("0.00", trib.valor_ibs)
    _assert_valor("0.00", trib.ibs_pendente)
    _assert_valor("4.00", trib.aliquota_cbs)
    _assert_valor("40.00", trib.valor_cbs)
    _assert_valor("0.00", trib.cbs_pendente)
    _assert_valor("40.00", trib.valor_ibs + trib.valor_cbs)


def test_caso15_compraGovEstado_fator010(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso15_compraGovEstado_fator010")
    trib = _calcular(service, _insumo(_regime_crt1(), _tipo(1), ente=2, fator="0.10"))
    _assert_valor("1.525", trib.aliquota_ibs)
    _assert_valor("15.25", trib.valor_ibs)
    _assert_valor("2.475", trib.aliquota_cbs)
    _assert_valor("24.75", trib.valor_cbs)
    _assert_valor("40.00", trib.valor_ibs + trib.valor_cbs)


def test_caso16_compraGovDf_fator100_transicaoCompleta(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso16_compraGovDf_fator100_transicaoCompleta")
    trib = _calcular(service, _insumo(_regime_crt1(), _tipo(1), ente=3, fator="1.00"))
    _assert_valor("4.00", trib.aliquota_ibs)
    _assert_valor("40.00", trib.valor_ibs)
    _assert_valor("0.00", trib.aliquota_cbs)
    _assert_valor("0.00", trib.valor_cbs)
    _assert_valor("40.00", trib.valor_ibs + trib.valor_cbs)


def test_caso17_compraGovMunicipio_fatorZero_preTransicao(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso17_compraGovMunicipio_fatorZero_preTransicao")
    trib = _calcular(service, _insumo(_regime_crt1(), _tipo(1), ente=4, fator="0.00"))
    _assert_valor("1.25", trib.aliquota_ibs)
    _assert_valor("12.50", trib.valor_ibs)
    _assert_valor("2.75", trib.aliquota_cbs)
    _assert_valor("27.50", trib.valor_cbs)
    _assert_valor("40.00", trib.valor_ibs + trib.valor_cbs)


def test_caso18_cAtivSNInvalido_naoCalculado_somenteReceitaBrutaETipo(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso18_cAtivSNInvalido_naoCalculado_somenteReceitaBrutaETipo")
    motivo = Motivo("CATIVSN_DESCONHECIDO", "99")
    insumo = _insumo(_regime_crt1(), _tipo(1), motivo=motivo)
    resultado = service.calcularItem(insumo)
    assert resultado.estado is EstadoItem.NAO_CALCULADO
    assert resultado.motivo is motivo
    trib = resultado.tributos
    _assert_valor("1000.00", trib.receita_bruta)
    assert trib.tipo_receita == 1
    assert trib.descricao_tipo_receita == "Receita bruta - interna"
    assert trib.base_calculo is None
    assert trib.aliquota_ibs is None
    assert trib.valor_ibs is None
    assert trib.ibs_pendente is None
    assert trib.aliquota_cbs is None
    assert trib.valor_cbs is None
    assert trib.cbs_pendente is None
    assert trib.imposto_seletivo is None
    assert trib.total_item is None


def test_compraGovUniao_crt2_usaPIbsApenasComoInsumoDaTransformacao(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "compraGovUniao_crt2_usaPIbsApenasComoInsumoDaTransformacao")
    trib = _calcular(service, _insumo(_regime_crt2(), _tipo(1), ente=1))
    assert trib.aliquota_ibs is None
    assert trib.valor_ibs is None
    _assert_valor("4.00", trib.aliquota_cbs)
    _assert_valor("40.00", trib.valor_cbs)


def test_compraGovUniao_crt2_semPIbs_trataInsumoComoZero(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "compraGovUniao_crt2_semPIbs_trataInsumoComoZero")
    trib = _calcular(service, _insumo(_regime_crt2(), _tipo(1), ibs=None, ente=1))
    assert trib.aliquota_ibs is None
    _assert_valor("2.75", trib.aliquota_cbs)
    _assert_valor("27.50", trib.valor_cbs)


def test_aliquotasDispensadas_tpRBSN2_calculadoComTudoZero(
    service: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "aliquotasDispensadas_tpRBSN2_calculadoComTudoZero")
    trib = _calcular(service, _insumo(_regime_crt1(), _tipo(2), ibs=None, cbs=None))
    _assert_valor("1000.00", trib.receita_bruta)
    assert trib.aliquota_ibs is None
    assert trib.aliquota_cbs is None
    _assert_valor("0.00", trib.valor_ibs)
    _assert_valor("0.00", trib.valor_cbs)
    _assert_valor("0.00", trib.total_item)