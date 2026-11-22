"""Espelho de ``Teste_EfeitosPorFamiliaSimples`` (pin a926d5a7)."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

import pytest

from calculadora_rtc_simples_nacional.consumo import SimplesNacionalCalculoService
from calculadora_rtc_simples_nacional.escolha import VocabularioRegime
from calculadora_rtc_simples_nacional.parametro import (
    CodigoRegimeApuracao,
    DestinoValor,
    ParametroCalculo,
    RegimeApuracao,
    TipoDfeCalculo,
    TipoReceitaBruta,
)
from calculadora_rtc_simples_nacional.processador import (
    AliquotasItem,
    ContextoItem,
    DadosAliquotas,
    EntradaItem,
    EstadoItemProcessado,
    ItemAProcessar,
    ProcessadorItemSimples,
    RegimeContexto,
    ValidacaoNomenclaturaBasica,
)
from calculadora_rtc_simples_nacional.simples import (
    Destino,
    EstadoItem,
    Insumo,
    Regime,
    TipoReceita,
)
from calculadora_rtc_simples_nacional.unificado import (
    CalculoSimplesUnificadoService,
    DadosOperacaoSimples,
    ErrosCalculoException,
    ItemSimplesUnificadoInput,
)

_CLASSNAME = (
    "br.gov.serpro.rtc.testesunitarios.simplesnacional.Teste_EfeitosPorFamiliaSimples"
)

DATA = date(2027, 3, 15)


def _junit(record_xml_attribute, name: str) -> None:
    record_xml_attribute("classname", _CLASSNAME)
    record_xml_attribute("name", name)


def _assert_valor(esperado: str, atual: Decimal | None) -> None:
    assert atual is not None
    assert Decimal(esperado).compare(atual) == 0


def _tipo_crt(codigo: int) -> TipoReceita:
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
        False,
        exige,
        vedado,
    )


def _tipo_nfse(codigo: int) -> TipoReceita:
    return TipoReceita(
        codigo,
        "desc",
        True,
        Decimal(1 if codigo == 1 else 0),
        False,
        False,
        codigo == 1,
        codigo in {1, 2, 3, 4, 5},
    )


def _tipo_nfse_param(codigo: int) -> TipoReceitaBruta:
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


def _regime_java(codigo: str) -> Regime:
    if codigo == "SN_PLENO":
        return Regime(codigo, True, codigo, True, Destino.DEVIDO, Destino.PENDENTE_SUSPENSO)
    if codigo == "PENDENTE":
        return Regime(codigo, True, codigo, True, Destino.PENDENTE_SUSPENSO, Destino.ZERO)
    if codigo == "PENDENTE_SUBLIMITE":
        return Regime(codigo, True, codigo, False, Destino.PENDENTE_SUSPENSO, Destino.ZERO)
    if codigo == "SOMENTE_RECEITA":
        return Regime(codigo, False, codigo, True, Destino.DEVIDO, Destino.PENDENTE_SUSPENSO)
    raise ValueError(codigo)


def _regime_ctx(codigo: str) -> RegimeContexto:
    gera = None if codigo == "SOMENTE_RECEITA" else codigo != "PENDENTE_SUBLIMITE"
    return RegimeContexto(codigo, codigo != "SOMENTE_RECEITA", gera, codigo)


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


def _calcular_trib(
    service: SimplesNacionalCalculoService,
    regime: Regime,
    tipo: TipoReceita,
    base: str,
    v_is: str | None,
    p_ibs: str,
    p_cbs: str,
    tp_ente: int | None,
    fator: str | None,
    casas: int | None,
):
    resultado = service.calcularItem(
        Insumo(
            regime,
            tipo,
            None,
            Decimal(base),
            Decimal(v_is) if v_is is not None else None,
            Decimal(p_ibs),
            Decimal(p_cbs),
            tp_ente,
            Decimal(fator) if fator is not None else None,
            casas,
        )
    )
    return resultado


def _resolvedor_fixo(_dados: DadosAliquotas, _collector) -> AliquotasItem:
    return AliquotasItem(Decimal("0.0263"), Decimal("2.3874"))


class ParametroTpReceita(ParametroCalculo):
    def buscar_tipo_receita_bruta(
        self, tp_rbsn: int, data: date, vocabulario: VocabularioRegime | None = None
    ) -> TipoReceitaBruta | None:
        return _tipo_nfse_param(tp_rbsn)


@dataclass
class SpyNcmNbs:
    existe_ncm: dict[str, bool] = field(default_factory=dict)
    existe_nbs: dict[str, bool] = field(default_factory=dict)
    chamadas_ncm: list[str] = field(default_factory=list)
    chamadas_nbs: list[str] = field(default_factory=list)

    def ncm(self, codigo: str, data: date) -> bool:
        self.chamadas_ncm.append(codigo)
        if codigo in self.existe_ncm:
            return self.existe_ncm[codigo]
        raise AssertionError(f"existe_ncm inesperado: {codigo}")

    def nbs(self, codigo: str, data: date) -> bool:
        self.chamadas_nbs.append(codigo)
        if codigo in self.existe_nbs:
            return self.existe_nbs[codigo]
        raise AssertionError(f"existe_nbs inesperado: {codigo}")


@dataclass
class SpyValidacaoClassificacao:
    chamadas: list[tuple] = field(default_factory=list)
    erro: BaseException | None = None

    def __call__(self, sigla: str, classificacao, ncm, nbs, data: date) -> None:
        self.chamadas.append((sigla, classificacao.codigo if classificacao else None, ncm, nbs, data))
        if self.erro is not None:
            raise self.erro


def _nomenclatura(spy_ncm: SpyNcmNbs | None = None, spy_val: SpyValidacaoClassificacao | None = None):
    spy_ncm = spy_ncm or SpyNcmNbs()
    spy_val = spy_val or SpyValidacaoClassificacao()
    return ValidacaoNomenclaturaBasica(
        existe_ncm=spy_ncm.ncm if spy_ncm else None,
        existe_nbs=spy_ncm.nbs if spy_ncm else None,
        validar_classificacao=spy_val if spy_val.chamadas is not None or spy_val.erro else None,
    ), spy_ncm, spy_val


@contextmanager
def _patch_processador(tp_rbsn: int = 1):
    from unittest.mock import patch

    from calculadora_rtc_simples_nacional import parametro

    classificacao = parametro.ClassificacaoTributaria(1, "000001", tp_rbsn)

    def fake_vigentes(codigo: str, data: date):
        return [classificacao] if codigo == "000001" else []

    patchers = [
        patch(
            "calculadora_rtc_simples_nacional.processador.buscar_classificacoes_vigentes",
            side_effect=fake_vigentes,
        ),
        patch(
            "calculadora_rtc_simples_nacional.processador.contar_vinculo_classificacao_tpdoc",
            return_value=1,
        ),
        patch(
            "calculadora_rtc_simples_nacional.processador.contar_tratamentos_nao_implementados",
            return_value=0,
        ),
        patch(
            "calculadora_rtc_simples_nacional.processador.buscar_atividades_por_cativsn",
            return_value=[],
        ),
        patch(
            "calculadora_rtc_simples_nacional.processador.contar_vinculo_atividade_tpdoc",
            return_value=0,
        ),
    ]
    for p in patchers:
        p.start()
    try:
        yield classificacao
    finally:
        for p in patchers:
            p.stop()


@pytest.fixture
def calculo() -> SimplesNacionalCalculoService:
    return SimplesNacionalCalculoService()


# ─── Alíquota de 2 casas (NFS-e) ───────────────────────────────────────────


def test_nfse_aliquotaDe2Casas_valorSaiDaBaseVezesAAliquotaArredondada(
    calculo: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "nfse_aliquotaDe2Casas_valorSaiDaBaseVezesAAliquotaArredondada")
    regime = _regime_java("SN_PLENO")
    trib = _calcular_trib(
        calculo, regime, _tipo_nfse(1), "10000.00", None, "0.0263", "2.3874", None, None, 2
    ).tributos
    _assert_valor("2.39", trib.aliquota_cbs)
    _assert_valor("0.03", trib.aliquota_ibs)
    _assert_valor("239.00", trib.valor_cbs)
    _assert_valor("3.00", trib.valor_ibs)
    integral = _calcular_trib(
        calculo, regime, _tipo_nfse(1), "10000.00", None, "0.0263", "2.3874", None, None, None
    ).tributos
    _assert_valor("238.74", integral.valor_cbs)
    _assert_valor("2.63", integral.valor_ibs)


def test_nfse_arredondamentoDepoisDaCompraGovernamental_uniao(
    calculo: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "nfse_arredondamentoDepoisDaCompraGovernamental_uniao")
    trib = _calcular_trib(
        calculo,
        _regime_java("SN_PLENO"),
        _tipo_nfse(1),
        "10000.00",
        None,
        "0.0263",
        "2.3874",
        1,
        None,
        2,
    ).tributos
    _assert_valor("2.41", trib.aliquota_cbs)
    _assert_valor("0.00", trib.aliquota_ibs)
    _assert_valor("241.00", trib.valor_cbs)
    _assert_valor("0.00", trib.valor_ibs)


def test_nfse_arredondamentoDepoisDaCompraGovernamental_enteComFator(
    calculo: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "nfse_arredondamentoDepoisDaCompraGovernamental_enteComFator")
    trib = _calcular_trib(
        calculo,
        _regime_java("SN_PLENO"),
        _tipo_nfse(1),
        "10000.00",
        None,
        "0.0263",
        "2.3874",
        2,
        "0.10",
        2,
    ).tributos
    _assert_valor("2.15", trib.aliquota_cbs)
    _assert_valor("0.27", trib.aliquota_ibs)
    _assert_valor("215.00", trib.valor_cbs)
    _assert_valor("27.00", trib.valor_ibs)


def test_nfse_arredondamentoNoModoDoAdr001_meioParaOPar(
    calculo: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "nfse_arredondamentoNoModoDoAdr001_meioParaOPar")
    par = _calcular_trib(
        calculo, _regime_java("SN_PLENO"), _tipo_nfse(1), "100.00", None, "0.125", "2.385", None, None, 2
    ).tributos
    _assert_valor("2.38", par.aliquota_cbs)
    _assert_valor("0.12", par.aliquota_ibs)
    impar = _calcular_trib(
        calculo, _regime_java("SN_PLENO"), _tipo_nfse(1), "100.00", None, "0.135", "2.395", None, None, 2
    ).tributos
    _assert_valor("2.40", impar.aliquota_cbs)
    _assert_valor("0.14", impar.aliquota_ibs)


# ─── Efeito do tpRBSN na NFS-e ─────────────────────────────────────────────


def test_nfse_tpRBSN4e5_zeradosSemPendenteSuspenso(
    calculo: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "nfse_tpRBSN4e5_zeradosSemPendenteSuspenso")
    regime = _regime_java("SN_PLENO")
    for tp_rbsn in (4, 5):
        trib = _calcular_trib(
            calculo, regime, _tipo_nfse(tp_rbsn), "1000.00", None, "0.0263", "2.3874", None, None, 2
        ).tributos
        _assert_valor("1000.00", trib.receita_bruta)
        _assert_valor("0.00", trib.base_calculo)
        _assert_valor("0.00", trib.valor_cbs)
        _assert_valor("0.00", trib.cbs_pendente)
        _assert_valor("0.00", trib.valor_ibs)
        _assert_valor("0.00", trib.ibs_pendente)
    crt = _calcular_trib(
        calculo, regime, _tipo_crt(4), "1000.00", "0.00", "0.0263", "2.3874", None, None, None
    ).tributos
    _assert_valor("23.87", crt.cbs_pendente)


def test_nfse_pendente_valorVaiParaPendenteSuspenso(
    calculo: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "nfse_pendente_valorVaiParaPendenteSuspenso")
    trib = _calcular_trib(
        calculo,
        _regime_java("PENDENTE"),
        _tipo_nfse(1),
        "1000.00",
        None,
        "0.0263",
        "2.3874",
        None,
        None,
        2,
    ).tributos
    _assert_valor("0.00", trib.valor_cbs)
    _assert_valor("23.90", trib.cbs_pendente)
    _assert_valor("0.30", trib.ibs_pendente)


def test_pendenteSublimite_soACbs_pendenteSuspensa(
    calculo: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "pendenteSublimite_soACbs_pendenteSuspensa")
    trib = _calcular_trib(
        calculo,
        _regime_java("PENDENTE_SUBLIMITE"),
        _tipo_nfse(1),
        "1000.00",
        None,
        "0.0263",
        "2.3874",
        None,
        None,
        2,
    ).tributos
    assert trib.aliquota_ibs is None
    assert trib.valor_ibs is None
    assert trib.ibs_pendente is None
    _assert_valor("23.90", trib.cbs_pendente)
    _assert_valor("0.00", trib.total_item)


# ─── Imposto Seletivo e SOMENTE_RECEITA no cálculo ─────────────────────────


def test_semImpostoSeletivo_grupoISForaDaResposta(
    calculo: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "semImpostoSeletivo_grupoISForaDaResposta")
    trib = _calcular_trib(
        calculo,
        _regime_java("SN_PLENO"),
        _tipo_nfse(1),
        "1000.00",
        None,
        "0.0263",
        "2.3874",
        None,
        None,
        2,
    ).tributos
    assert trib.imposto_seletivo is None
    _assert_valor("24.20", trib.total_item)


def test_somenteReceita_naoCalcula_soAReceitaBruta(
    calculo: SimplesNacionalCalculoService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "somenteReceita_naoCalcula_soAReceitaBruta")
    resultado = calculo.calcularItem(
        Insumo(
            _regime_java("SOMENTE_RECEITA"),
            _tipo_crt(1),
            None,
            Decimal("1000.00"),
            Decimal("0"),
            None,
            None,
            None,
            None,
            None,
        )
    )
    assert resultado.estado is EstadoItem.NAO_CALCULADO
    assert resultado.motivo is not None
    assert resultado.motivo.codigo == "REGIME_SOMENTE_RECEITA"
    _assert_valor("1000.00", resultado.tributos.receita_bruta)
    assert resultado.tributos.tipo_receita == 1
    assert resultado.tributos.base_calculo is None
    assert resultado.tributos.valor_cbs is None


# ─── Processador ───────────────────────────────────────────────────────────


def _processador_com_nomenclatura(spy_ncm: SpyNcmNbs | None, spy_val: SpyValidacaoClassificacao | None):
    nom, spy_ncm, spy_val = _nomenclatura(spy_ncm, spy_val)
    return ProcessadorItemSimples(ParametroTpReceita(), nom), spy_ncm, spy_val


def test_nomenclaturaAusente_eValidadaQuandoClassificacaoExigeCodigo(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "nomenclaturaAusente_eValidadaQuandoClassificacaoExigeCodigo")
    spy_val = SpyValidacaoClassificacao(
        erro=Exception("Nomenclatura obrigatória não informada para a classificação tributária 000001 no documento NFSe")
    )
    proc, _, spy_v = _processador_com_nomenclatura(SpyNcmNbs(), spy_val)
    with _patch_processador():
        item = proc.processar_item(
            EntradaItem(1, "07", "000001", "1000.00", None, None, None),
            0,
            _contexto_nfse(_regime_ctx("SOMENTE_RECEITA")),
            _resolvedor_fixo,
        ).objeto
    assert item.estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    assert item.erros is not None
    assert item.erros[0].code == "VSN-044"
    assert len(spy_v.chamadas) == 1


def test_nomenclaturasSimultaneas_mapeiaPrimeiraFalhaEConservaMensagem(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "nomenclaturasSimultaneas_mapeiaPrimeiraFalhaEConservaMensagem")
    spy_ncm = SpyNcmNbs()
    spy_val = SpyValidacaoClassificacao(erro=AssertionError("validacao não deve ser chamada"))
    proc, spy_n, spy_v = _processador_com_nomenclatura(spy_ncm, spy_val)
    with _patch_processador():
        item = proc.processar_item(
            EntradaItem(1, "07", "000001", "1000.00", None, "22030000", "114051000"),
            0,
            _contexto_nfse(_regime_ctx("SOMENTE_RECEITA")),
            _resolvedor_fixo,
        ).objeto
    assert item.erros is not None
    assert item.erros[0].code == "VSN-041"
    assert item.erros[0].detail == "Não é permitido informar NCM e NBS simultaneamente para um item"
    assert spy_n.chamadas_ncm == []
    assert spy_n.chamadas_nbs == []
    assert spy_v.chamadas == []


def test_nomenclaturaInexistente_mapeiaMensagemDaExcecao(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "nomenclaturaInexistente_mapeiaMensagemDaExcecao")
    spy_ncm = SpyNcmNbs(existe_ncm={"22030000": False})
    spy_val = SpyValidacaoClassificacao()
    proc, _, spy_v = _processador_com_nomenclatura(spy_ncm, spy_val)
    with _patch_processador():
        item = proc.processar_item(
            EntradaItem(1, "07", "000001", "1000.00", None, "22030000", None),
            0,
            _contexto_nfse(_regime_ctx("SOMENTE_RECEITA")),
            _resolvedor_fixo,
        ).objeto
    assert item.erros is not None
    assert item.erros[0].code == "VSN-049"
    assert item.erros[0].detail == f"NCM de código 22030000 não encontrada para a data {DATA}"
    assert spy_v.chamadas == []


def test_nbsInexistente_mapeiaMensagemDaExcecao(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "nbsInexistente_mapeiaMensagemDaExcecao")
    spy_ncm = SpyNcmNbs(existe_nbs={"114051000": False})
    proc, _, spy_v = _processador_com_nomenclatura(spy_ncm, SpyValidacaoClassificacao())
    with _patch_processador():
        item = proc.processar_item(
            EntradaItem(1, "07", "000001", "1000.00", None, None, "114051000"),
            0,
            _contexto_nfse(_regime_ctx("SOMENTE_RECEITA")),
            _resolvedor_fixo,
        ).objeto
    assert item.erros is not None
    assert item.erros[0].code == "VSN-050"
    assert item.erros[0].detail == f"NBS de código 114051000 não encontrada para a data {DATA}"
    assert spy_v.chamadas == []


def test_nomenclaturaValida_eProcessadaSemErro(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "nomenclaturaValida_eProcessadaSemErro")
    spy_ncm = SpyNcmNbs(existe_ncm={"22030000": True})
    spy_val = SpyValidacaoClassificacao()
    proc, _, spy_v = _processador_com_nomenclatura(spy_ncm, spy_val)
    with _patch_processador() as classificacao:
        item = proc.processar_item(
            EntradaItem(1, "07", "000001", "1000.00", None, "22030000", None),
            0,
            _contexto_nfse(_regime_ctx("SOMENTE_RECEITA")),
            _resolvedor_fixo,
        ).objeto
    assert item.estado is EstadoItemProcessado.NAO_CALCULADO
    assert item.erros is None
    assert len(spy_v.chamadas) == 1
    assert spy_v.chamadas[0][2] == "22030000"
    assert classificacao.codigo == "000001"


def test_ncmZeroPermitido_converteSomenteOsDoisCodigosExatosAntesDasDuasValidacoes(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "ncmZeroPermitido_converteSomenteOsDoisCodigosExatosAntesDasDuasValidacoes")
    spy_ncm = SpyNcmNbs(existe_nbs={"001234567": True})
    spy_val = SpyValidacaoClassificacao()
    proc, spy_n, spy_v = _processador_com_nomenclatura(spy_ncm, spy_val)
    ctx = _contexto_nfse(_regime_ctx("SOMENTE_RECEITA"), permite_ncm_zero=True)
    with _patch_processador():
        for recebido in ("00", "00000000"):
            item = proc.processar_item(
                EntradaItem(1, "07", "000001", "1000.00", None, recebido, None),
                0,
                ctx,
                _resolvedor_fixo,
            ).objeto
            assert item.erros is None
        assert len(spy_v.chamadas) == 2
        assert all(c[2] is None for c in spy_v.chamadas)
        com_nbs = proc.processar_item(
            EntradaItem(1, "07", "000001", "1000.00", None, "00", "001234567"),
            0,
            ctx,
            _resolvedor_fixo,
        ).objeto
        assert com_nbs.erros is None
        assert spy_n.chamadas_nbs == ["001234567"]
        assert spy_v.chamadas[-1][3] == "001234567"


def test_ncmZeroNaoPermitidoPreservaLiteraisEValoresQuaseCorrespondentes(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "ncmZeroNaoPermitidoPreservaLiteraisEValoresQuaseCorrespondentes")
    spy_ncm = SpyNcmNbs(existe_ncm={"00000000": True})
    spy_val = SpyValidacaoClassificacao()
    proc, _, spy_v = _processador_com_nomenclatura(spy_ncm, spy_val)
    ctx = _contexto_nfse(_regime_ctx("SOMENTE_RECEITA"), permite_ncm_zero=False)
    with _patch_processador():
        for recebido in ("00000000",):
            item = proc.processar_item(
                EntradaItem(1, "07", "000001", "1000.00", None, recebido, None),
                0,
                ctx,
                _resolvedor_fixo,
            ).objeto
            assert item.erros is None
            assert spy_v.chamadas[-1][2] == recebido
        for recebido in ("00", "000000000", " 00 "):
            item = proc.processar_item(
                EntradaItem(1, "07", "000001", "1000.00", None, recebido, None),
                0,
                ctx,
                _resolvedor_fixo,
            ).objeto
            assert item.erros is not None
            assert item.erros[0].code == "VSN-051"


def test_conversaoDeNcmZeroAindaPodeExigirNomenclatura(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "conversaoDeNcmZeroAindaPodeExigirNomenclatura")
    spy_val = SpyValidacaoClassificacao(
        erro=Exception("Nomenclatura obrigatória não informada para a classificação tributária 000001 no documento NFSe")
    )
    proc, _, spy_v = _processador_com_nomenclatura(SpyNcmNbs(), spy_val)
    with _patch_processador():
        item = proc.processar_item(
            EntradaItem(1, "07", "000001", "1000.00", None, "00", None),
            0,
            _contexto_nfse(_regime_ctx("SOMENTE_RECEITA"), permite_ncm_zero=True),
            _resolvedor_fixo,
        ).objeto
    assert item.erros is not None
    assert item.erros[0].code == "VSN-044"
    assert len(spy_v.chamadas) == 1


def test_valoresAusentesWhitespaceNbsEZerosNbsNaoSaoNormalizados(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "valoresAusentesWhitespaceNbsEZerosNbsNaoSaoNormalizados")
    spy_val = SpyValidacaoClassificacao()
    proc, _, spy_v = _processador_com_nomenclatura(SpyNcmNbs(existe_nbs={"000000000": True}), spy_val)
    ctx = _contexto_nfse(_regime_ctx("SOMENTE_RECEITA"), permite_ncm_zero=True)
    with _patch_processador():
        for ncm in (None, ""):
            item = proc.processar_item(
                EntradaItem(1, "07", "000001", "1000.00", None, ncm, "000000000"),
                0,
                ctx,
                _resolvedor_fixo,
            ).objeto
            assert item.erros is None
            assert spy_v.chamadas[-1][3] == "000000000"
        whitespace = proc.processar_item(
            EntradaItem(1, "07", "000001", "1000.00", None, None, "         "),
            0,
            ctx,
            _resolvedor_fixo,
        ).objeto
        assert whitespace.erros is not None
        assert whitespace.erros[0].code == "VSN-051"


def test_nomenclaturaIncompativel_apontaCampoInformadoEPreservaMensagem(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "nomenclaturaIncompativel_apontaCampoInformadoEPreservaMensagem")
    spy_ncm = SpyNcmNbs(existe_nbs={"114051000": True})
    spy_val = SpyValidacaoClassificacao(
        erro=Exception("NBS não permitida para a Classificação Tributária de código 000001 no tipo de documento NFSe")
    )
    proc, _, _ = _processador_com_nomenclatura(spy_ncm, spy_val)
    with _patch_processador():
        item = proc.processar_item(
            EntradaItem(1, "07", "000001", "1000.00", None, None, "114051000"),
            0,
            _contexto_nfse(_regime_ctx("SOMENTE_RECEITA")),
            _resolvedor_fixo,
        ).objeto
    assert item.erros is not None
    assert item.erros[0].code == "VSN-045"
    assert item.erros[0].pointer == "#/itens/0/nbs"
    assert (
        item.erros[0].detail
        == "NBS não permitida para a Classificação Tributária de código 000001 no tipo de documento NFSe"
    )


def test_prioridadeVsn027_precedeEstruturaNomenclatura(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "prioridadeVsn027_precedeEstruturaNomenclatura")
    from unittest.mock import patch

    spy_ncm = SpyNcmNbs()
    spy_val = SpyValidacaoClassificacao(erro=AssertionError("não deve chamar"))
    proc, spy_n, spy_v = _processador_com_nomenclatura(spy_ncm, spy_val)
    with patch(
        "calculadora_rtc_simples_nacional.processador.contar_tratamentos_nao_implementados",
        return_value=1,
    ):
        item = proc.processar_item(
            EntradaItem(1, "07", "000001", "1000.00", None, "22030000", "114051000"),
            0,
            _contexto_nfse(_regime_ctx("SOMENTE_RECEITA")),
            _resolvedor_fixo,
        ).objeto
    assert item.erros is not None
    assert item.erros[0].code == "VSN-027"
    assert spy_n.chamadas_ncm == []
    assert spy_v.chamadas == []


def test_baseEIsValidamAntesDaEstruturaNomenclatura(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "baseEIsValidamAntesDaEstruturaNomenclatura")
    proc, _, _ = _processador_com_nomenclatura(SpyNcmNbs(), SpyValidacaoClassificacao())
    with _patch_processador():
        item = proc.processar_item(
            EntradaItem(1, "07", "000001", None, None, "22030000", "114051000"),
            0,
            _contexto_nfse(_regime_ctx("SOMENTE_RECEITA")),
            _resolvedor_fixo,
        ).objeto
    assert item.erros is not None
    assert item.erros[0].code == "VSN-001"
    assert item.erros[1].code == "VSN-041"


def test_erroAnteriorSuprimeObrigatoriedadeDeNomenclaturaAusente(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "erroAnteriorSuprimeObrigatoriedadeDeNomenclaturaAusente")
    spy_val = SpyValidacaoClassificacao(erro=AssertionError("não deve chamar validação"))
    proc, _, spy_v = _processador_com_nomenclatura(SpyNcmNbs(), spy_val)
    with _patch_processador():
        item = proc.processar_item(
            EntradaItem(1, "07", "000001", None, None, None, None),
            0,
            _contexto_nfse(_regime_ctx("SOMENTE_RECEITA")),
            _resolvedor_fixo,
        ).objeto
    assert item.erros is not None
    assert item.erros[0].code == "VSN-001"
    assert len(item.erros) == 1
    assert spy_v.chamadas == []


def test_falhaTecnicaEstrutural_ficaNoItemSemInterromperProcessamento(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "falhaTecnicaEstrutural_ficaNoItemSemInterromperProcessamento")

    def ncm_falha(codigo: str, data: date) -> bool:
        if codigo == "22030000":
            raise RuntimeError("banco indisponível")
        return True

    spy_ncm = SpyNcmNbs()
    spy_ncm.ncm = ncm_falha  # type: ignore[method-assign]
    proc, _, _ = _processador_com_nomenclatura(spy_ncm, SpyValidacaoClassificacao())
    with _patch_processador():
        resultados = proc.processar_itens(
            [
                ItemAProcessar(
                    EntradaItem(1, "07", "000001", "1000.00", None, "22030000", None),
                    _resolvedor_fixo,
                ),
                ItemAProcessar(
                    EntradaItem(2, "07", "000001", "1000.00", None, None, None),
                    _resolvedor_fixo,
                ),
            ],
            _contexto_nfse(_regime_ctx("SOMENTE_RECEITA")),
        )
    assert resultados[0].objeto.estado is EstadoItemProcessado.FALHA_TECNICA
    assert resultados[0].objeto.erros is not None
    assert resultados[0].objeto.erros[0].code == "VSN-999"
    assert resultados[1].objeto.estado is EstadoItemProcessado.NAO_CALCULADO


def test_nfse_impostoSeletivoDiferenteDeZero_vsn035(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "nfse_impostoSeletivoDiferenteDeZero_vsn035")
    proc, _, _ = _processador_com_nomenclatura(SpyNcmNbs(), SpyValidacaoClassificacao())
    with _patch_processador():
        objeto = proc.processar_item(
            EntradaItem(1, "07", "000001", "1000.00", "10.00", None, None),
            0,
            _contexto_nfse(_regime_ctx("SN_PLENO")),
            _resolvedor_fixo,
        ).objeto
    assert objeto.estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    assert objeto.erros is not None
    assert objeto.erros[0].code == "VSN-035"
    assert objeto.erros[0].pointer == "#/itens/0/valorImpostoSeletivo"


def test_nfse_impostoSeletivoAusenteOuZero_aceito(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "nfse_impostoSeletivoAusenteOuZero_aceito")
    from unittest.mock import patch

    from calculadora_rtc_simples_nacional import parametro

    ativ = parametro.AtividadeNacional(7, 7, "x", "07", "III", None, False, True, False)
    proc, _, _ = _processador_com_nomenclatura(SpyNcmNbs(), SpyValidacaoClassificacao())
    with _patch_processador(), patch(
        "calculadora_rtc_simples_nacional.processador.buscar_atividades_por_cativsn",
        return_value=[ativ],
    ), patch(
        "calculadora_rtc_simples_nacional.processador.contar_vinculo_atividade_tpdoc",
        return_value=1,
    ):
        for v_is in (None, "0.00"):
            objeto = proc.processar_item(
                EntradaItem(1, "07", "000001", "1000.00", v_is, None, None),
                0,
                _contexto_nfse(_regime_ctx("SN_PLENO")),
                _resolvedor_fixo,
            ).objeto
            assert objeto.estado is EstadoItemProcessado.CALCULADO, f"vIS {v_is}"
            assert objeto.tributos is not None
            assert objeto.tributos.imposto_seletivo is None
            _assert_valor("23.90", objeto.tributos.valor_cbs)


def test_cAtivSNDeUmDigito_completadoComZero(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "cAtivSNDeUmDigito_completadoComZero")
    from unittest.mock import patch

    from calculadora_rtc_simples_nacional import parametro

    ativ = parametro.AtividadeNacional(7, 7, "x", "07", "III", None, False, True, False)
    chamadas: list[str] = []

    def buscar(codigo: str, data: date):
        chamadas.append(codigo)
        return [ativ]

    proc, _, _ = _processador_com_nomenclatura(SpyNcmNbs(), SpyValidacaoClassificacao())
    with _patch_processador(), patch(
        "calculadora_rtc_simples_nacional.processador.buscar_atividades_por_cativsn",
        side_effect=buscar,
    ), patch(
        "calculadora_rtc_simples_nacional.processador.contar_vinculo_atividade_tpdoc",
        return_value=1,
    ):
        objeto = proc.processar_item(
            EntradaItem(1, "7", "000001", "1000.00", None, None, None),
            0,
            _contexto_nfse(_regime_ctx("SN_PLENO")),
            _resolvedor_fixo,
        ).objeto
    assert objeto.estado is EstadoItemProcessado.CALCULADO
    assert chamadas == ["07"]
    assert ProcessadorItemSimples.normalizar_cativ_sn(" 7 ", True) == "07"
    assert ProcessadorItemSimples.normalizar_cativ_sn("7", False) == "7"


def test_somenteReceita_naoConsultaAtividadeNemAliquotas(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "somenteReceita_naoConsultaAtividadeNemAliquotas")
    from unittest.mock import patch

    def atividade_proibida(*_a, **_k):
        raise AssertionError("atividade repository should not be called")

    proc, _, _ = _processador_com_nomenclatura(SpyNcmNbs(), SpyValidacaoClassificacao())
    sem_chamada = lambda *a, **k: (_ for _ in ()).throw(AssertionError("resolvedor"))

    with _patch_processador(), patch(
        "calculadora_rtc_simples_nacional.processador.buscar_atividades_por_cativsn",
        side_effect=atividade_proibida,
    ):
        objeto = proc.processar_item(
            EntradaItem(1, "07", "000001", "1000.00", None, None, None),
            0,
            _contexto_nfse(_regime_ctx("SOMENTE_RECEITA")),
            sem_chamada,
        ).objeto
    assert objeto.estado is EstadoItemProcessado.NAO_CALCULADO
    assert objeto.tributos is not None
    _assert_valor("1000.00", objeto.tributos.receita_bruta)


class _ParametroUnificado:
    def __init__(self) -> None:
        self.sigla_chamado = False
        self.ncm_zero_chamado = False

    def tp_doc_sem_tratamento_calculadora(self, tp_doc: int, data: date) -> bool:
        return False

    def buscar_tipo_dfe_calculo(self, tp_doc: int, data: date) -> TipoDfeCalculo | None:
        return TipoDfeCalculo(910, VocabularioRegime.NFSE, 2, 1, False)

    def buscar_regime_por_campos(
        self,
        vocabulario: VocabularioRegime,
        op_simp_nac: int | None,
        reg_ap_ibscbs: int | None,
        reg_ap_trib_sn: int | None,
        tp_ente_gov: int | None,
        data: date,
    ) -> RegimeApuracao | None:
        return RegimeApuracao(
            5,
            CodigoRegimeApuracao.SOMENTE_RECEITA,
            "SOMENTE_RECEITA",
            False,
            None,
            DestinoValor.DEVIDO,
            DestinoValor.PENDENTE_SUSPENSO,
        )

    def buscar_situacoes_iss_par_aliquota(self, data: date):
        return []

    def buscar_fator_transicao_compra_gov(self, data: date):
        return None

    def buscar_tipo_receita_bruta(
        self, tp_rbsn: int, data: date, vocabulario: VocabularioRegime | None = None
    ) -> TipoReceitaBruta | None:
        return _tipo_nfse_param(tp_rbsn)


def test_nfse_maisDeUmItem_vsn034(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "nfse_maisDeUmItem_vsn034")
    svc = CalculoSimplesUnificadoService(parametro=_ParametroUnificado())  # type: ignore[arg-type]
    item = ItemSimplesUnificadoInput(
        1, "07", "000001", None, None, "1000.00", None, "1", "1", None
    )
    operacao = DadosOperacaoSimples(
        "op",
        "3.0.0",
        DATA.isoformat(),
        "91",
        None,
        None,
        "3",
        "1",
        "1",
        None,
        [item, item],
    )
    with pytest.raises(ErrosCalculoException) as exc:
        svc.processar(operacao, None)
    assert exc.value.erros[0].code == "VSN-034"
    assert exc.value.erros[0].pointer == "#/itens"


def test_naoAssistido_resolveSiglaDaLinhaDeDocumentoSelecionada(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "naoAssistido_resolveSiglaDaLinhaDeDocumentoSelecionada")
    from unittest.mock import patch

    spy_val = SpyValidacaoClassificacao()
    proc = ProcessadorItemSimples(_ParametroUnificado(), _nomenclatura(SpyNcmNbs(), spy_val)[0])  # type: ignore[arg-type]
    chamadas_sigla: list[tuple[int, date]] = []
    chamadas_ncm_zero: list[tuple[int, date]] = []

    def sigla(tipo_id: int, data: date) -> str:
        chamadas_sigla.append((tipo_id, data))
        return "NFSe"

    def ncm_zero(tipo_id: int, data: date) -> bool:
        chamadas_ncm_zero.append((tipo_id, data))
        return True

    item = ItemSimplesUnificadoInput(1, "07", "000001", None, None, "1000.00", None, None, None, None)
    operacao = DadosOperacaoSimples(
        "op",
        "3.0.0",
        DATA.isoformat(),
        "91",
        None,
        None,
        "3",
        "1",
        "1",
        None,
        [item],
    )
    patchers = [
        patch(
            "calculadora_rtc_simples_nacional.processador.buscar_classificacoes_vigentes",
            return_value=[__import__("calculadora_rtc_simples_nacional.parametro", fromlist=["x"]).ClassificacaoTributaria(1, "000001", 1)],
        ),
        patch("calculadora_rtc_simples_nacional.processador.contar_vinculo_classificacao_tpdoc", return_value=1),
        patch("calculadora_rtc_simples_nacional.processador.contar_tratamentos_nao_implementados", return_value=0),
        patch("calculadora_rtc_simples_nacional.unificado.buscar_sigla_vigente_por_id", side_effect=sigla),
        patch("calculadora_rtc_simples_nacional.unificado.permite_ncm_zero_vigente_por_id", side_effect=ncm_zero),
    ]
    for p in patchers:
        p.start()
    try:
        svc = CalculoSimplesUnificadoService(parametro=_ParametroUnificado(), processador=proc)  # type: ignore[arg-type]
        svc.processar(operacao, None)
        assert chamadas_sigla == [(910, DATA)]
        assert chamadas_ncm_zero == [(910, DATA)]
        assert len(spy_val.chamadas) == 1
    finally:
        for p in patchers:
            p.stop()


def test_contextoClassico_comportamentoDeSempre(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "contextoClassico_comportamentoDeSempre")
    classico = ContextoItem.classico(
        DATA,
        91,
        _regime_ctx("SN_PLENO"),
        None,
        None,
        "NFSe",
        False,
    )
    assert classico.vocabulario_tipo_receita is None
    assert classico.casas_aliquota_calculo is None
    assert classico.admite_imposto_seletivo is True
    assert classico.normalizar_cativ_sn is False