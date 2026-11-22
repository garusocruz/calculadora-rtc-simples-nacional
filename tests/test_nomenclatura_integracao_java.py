"""Integração nomenclatura Simples (pin a926d5a7) — serviço, sem HTTP."""

from __future__ import annotations

import json
import os
from decimal import Decimal

import pytest

os.environ.setdefault(
    "CALC_DB",
    "/home/garusotec/projects/lynko/libs/calculadora-rtc-regime-regular/.cache/oficial/java/calculadora/db/calculadora-pro.db",
)

from calculadora_rtc_simples_nacional.consumo import (
    SimplesNacionalNaoAssistidoService,
    SimplesNacionalObservabilidadeService,
)
from calculadora_rtc_simples_nacional.nao_assistido import (
    AliquotasEfetivas,
    AnexoUnico,
    OperacaoNaoAssistida,
)
from calculadora_rtc_simples_nacional.observabilidade import ItemSimplesClassico, OperacaoSimplesClassica
from calculadora_rtc_simples_nacional.parametro import banco_disponivel
from calculadora_rtc_simples_nacional.processador import EstadoItemProcessado, ObjetoItem
from calculadora_rtc_simples_nacional.observabilidade import ObservabilidadeSimplesClassica
from calculadora_rtc_simples_nacional.unificado import ItemSimplesUnificadoInput, ObservabilidadeSimples

_CLASSNAME = "br.gov.serpro.rtc.testesintegracao.ValidacaoNomenclaturaSimplesTest"
BASE_URL = "http://localhost/api"
_DATA = "2027-03-15"

pytestmark = pytest.mark.skipif(not banco_disponivel(), reason="calculadora-pro.db ausente")

_SVC_NAO = SimplesNacionalNaoAssistidoService()
_SVC_CLASSICO = SimplesNacionalObservabilidadeService()


def _junit(record_xml_attribute, name: str) -> None:
    record_xml_attribute("classname", _CLASSNAME)
    record_xml_attribute("name", name)


def _fmt_total(val: Decimal | None) -> str:
    assert val is not None
    return f"{val.quantize(Decimal('0.01')):.2f}"


def _erros_json(obj: ObjetoItem) -> str:
    if obj.erros is None:
        return "null"
    return json.dumps(
        [{"code": e.code, "pointer": e.pointer, "detail": e.detail} for e in obj.erros],
        ensure_ascii=False,
    )


def _item_classico(
    *,
    numero: int = 1,
    cativ_sn: str = "01",
    class_trib: str = "200003",
    base: str = "500.00",
    ncm: str | None = None,
    nbs: str | None = None,
) -> ItemSimplesClassico:
    return ItemSimplesClassico(numero, cativ_sn, class_trib, nbs, ncm, base, "0.00", "1.25", "2.75")


def _item_unificado(
    *,
    numero: int = 1,
    cativ_sn: str = "01",
    class_trib: str = "200003",
    base: str = "500.00",
    ncm: str | None = None,
    nbs: str | None = None,
) -> ItemSimplesUnificadoInput:
    return ItemSimplesUnificadoInput(
        numero, cativ_sn, class_trib, nbs, ncm, base, "0.00", None, None, None
    )


def _item2_classico() -> ItemSimplesClassico:
    return _item_classico(numero=2, class_trib="000001", base="1000.00")


def _item2_unificado() -> ItemSimplesUnificadoInput:
    return _item_unificado(numero=2, class_trib="000001", base="1000.00")


def _nao_assistido(primeiro) -> OperacaoNaoAssistida:
    return OperacaoNaoAssistida(
        id="nomenclatura",
        versao="3.0.0",
        data=_DATA,
        tp_doc="55",
        crt="1",
        itens=[primeiro, _item2_unificado()],
        aliquotas=AliquotasEfetivas(
            fator_r=True,
            impedimento_sublimite=False,
            anexo_i=AnexoUnico(p_cbssn="1.1612", p_ibssn="0.0129"),
        ),
    )


def _classico(primeiro) -> OperacaoSimplesClassica:
    return OperacaoSimplesClassica(
        id="nomenclatura",
        versao="2.0.0",
        data=_DATA,
        tp_doc="55",
        crt="1",
        tp_regime_ibscbs=None,
        tp_ente_gov=None,
        itens=[primeiro, _item2_classico()],
    )


def _operacao_classica(tp_doc: str, primeiro) -> OperacaoSimplesClassica:
    return OperacaoSimplesClassica(
        id="nomenclatura",
        versao="2.0.0",
        data=_DATA,
        tp_doc=tp_doc,
        crt="1",
        tp_regime_ibscbs=None,
        tp_ente_gov=None,
        itens=[primeiro],
    )


def _enviar_nao(operacao: OperacaoNaoAssistida) -> ObservabilidadeSimples:
    return _SVC_NAO.processarOperacao(operacao)


def _enviar_classico(operacao: OperacaoSimplesClassica) -> ObservabilidadeSimplesClassica:
    return _SVC_CLASSICO.processarOperacao(operacao, BASE_URL)


def _assert_falha_item(
    corpo: ObservabilidadeSimples | ObservabilidadeSimplesClassica,
    code: str,
    pointer: str,
) -> None:
    o0, o1 = corpo.objetos[0], corpo.objetos[1]
    assert o0.estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    assert o0.erros is not None
    assert o0.erros[0].code == code
    assert o0.erros[0].pointer == pointer
    assert o1.estado is EstadoItemProcessado.CALCULADO
    assert corpo.total is not None
    assert _fmt_total(corpo.total.receita_bruta_total) == "1000.00"
    assert _fmt_total(corpo.total.base_calculo_total) == "1000.00"


def test_ausenciaObrigatoriaNcmNoNaoAssistido(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "ausenciaObrigatoriaNcmNoNaoAssistido")
    corpo = _enviar_nao(_nao_assistido(_item_unificado(class_trib="200003")))
    _assert_falha_item(corpo, "VSN-042", "#/itens/0/ncm")


def test_ncmInexistenteNoBancoRealNoNaoAssistido(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "ncmInexistenteNoBancoRealNoNaoAssistido")
    corpo = _enviar_nao(
        _nao_assistido(_item_unificado(class_trib="200003", ncm="99999999"))
    )
    _assert_falha_item(corpo, "VSN-049", "#/itens/0/ncm")
    assert "99999999" in corpo.objetos[0].erros[0].detail


def test_formatoEstruturalNcmNbsEValidadoAntesDaExistenciaEImpedeCalculo(
    record_xml_attribute,
) -> None:
    _junit(
        record_xml_attribute,
        "formatoEstruturalNcmNbsEValidadoAntesDaExistenciaEImpedeCalculo",
    )
    for value in (
        "1234567",
        "123456789",
        "1234ABCD",
        "1234-678",
        "1234 678",
        "        ",
        "１２３４５６７８",
    ):
        corpo = _enviar_classico(
            _classico(_item_classico(class_trib="000001", ncm=value))
        )
        _assert_falha_item(corpo, "VSN-051", "#/itens/0/ncm")
    for value in (
        "12345678",
        "12345678x",
        "12345 789",
        "1234-6789",
        "         ",
        "１２３４５６７８９",
    ):
        corpo = _enviar_classico(
            _classico(_item_classico(class_trib="000001", nbs=value))
        )
        _assert_falha_item(corpo, "VSN-051", "#/itens/0/nbs")
    sem = _enviar_classico(_classico(_item_classico(class_trib="000001")))
    assert sem.objetos[0].estado is EstadoItemProcessado.CALCULADO


def test_nomenclaturasSimultaneasNoClassico(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "nomenclaturasSimultaneasNoClassico")
    corpo = _enviar_classico(
        _classico(_item_classico(ncm="10062010", nbs="114051000"))
    )
    _assert_falha_item(corpo, "VSN-041", "#/itens/0/ncm")


def test_ncmVigenteEAplicavelNoBancoRealCalculaNosDoisEndpoints(
    record_xml_attribute,
) -> None:
    _junit(record_xml_attribute, "ncmVigenteEAplicavelNoBancoRealCalculaNosDoisEndpoints")
    novo = _enviar_nao(_nao_assistido(_item_unificado(ncm="10062010")))
    assert novo.objetos[0].estado is EstadoItemProcessado.CALCULADO
    assert novo.objetos[0].erros is None
    assert _fmt_total(novo.total.receita_bruta_total) == "1500.00"
    assert _fmt_total(novo.total.base_calculo_total) == "1500.00"

    classico = _enviar_classico(_classico(_item_classico(ncm="10062010")))
    assert classico.objetos[0].estado is EstadoItemProcessado.CALCULADO
    assert classico.objetos[0].erros is None
    assert _fmt_total(classico.total.receita_bruta_total) == "1500.00"


def test_aliasMaiusculoNcmContinuaAceitoPorCompatibilidade(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "aliasMaiusculoNcmContinuaAceitoPorCompatibilidade")
    corpo = _enviar_classico(_classico(_item_classico(ncm="10062010")))
    assert corpo.objetos[0].estado is EstadoItemProcessado.CALCULADO
    assert corpo.objetos[0].erros is None


def test_ncmZeroExatoEhEquivalenteAAusenciaQuandoPermitidoNaNfeENfce(
    record_xml_attribute,
) -> None:
    _junit(record_xml_attribute, "ncmZeroExatoEhEquivalenteAAusenciaQuandoPermitidoNaNfeENfce")
    for tp_doc in ("55", "65"):
        ausente = _enviar_classico(
            _operacao_classica(tp_doc, _item_classico(ncm=None))
        )
        dois = _enviar_classico(
            _operacao_classica(tp_doc, _item_classico(ncm="00"))
        )
        oito = _enviar_classico(
            _operacao_classica(tp_doc, _item_classico(ncm="00000000"))
        )
        assert ausente.objetos[0].erros is not None
        assert ausente.objetos[0].erros[0].code == "VSN-042"
        assert _erros_json(ausente.objetos[0]) == _erros_json(dois.objetos[0])
        assert _erros_json(ausente.objetos[0]) == _erros_json(oito.objetos[0])


def test_ncmZeroNoNaoAssistidoEhEquivalenteAAusencia(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "ncmZeroNoNaoAssistidoEhEquivalenteAAusencia")
    ausente = _enviar_nao(_nao_assistido(_item_unificado(class_trib="000001")))
    zerado = _enviar_nao(
        _nao_assistido(_item_unificado(class_trib="000001", ncm="00000000"))
    )
    assert ausente.objetos[0].estado is EstadoItemProcessado.CALCULADO
    assert ausente.objetos[0] == zerado.objetos[0]
    assert ausente.total == zerado.total


def test_ncmZeroEhNormalizadoAntesDaValidacaoDeNomenclaturaSimultanea(
    record_xml_attribute,
) -> None:
    _junit(record_xml_attribute, "ncmZeroEhNormalizadoAntesDaValidacaoDeNomenclaturaSimultanea")
    for tp_doc in ("55", "65"):
        nbs_sozinho = _enviar_classico(
            _operacao_classica(tp_doc, _item_classico(nbs="122012000"))
        )
        zero_e_nbs = _enviar_classico(
            _operacao_classica(
                tp_doc, _item_classico(ncm="00", nbs="122012000")
            )
        )
        assert nbs_sozinho.objetos[0].estado == zero_e_nbs.objetos[0].estado
        assert _erros_json(nbs_sozinho.objetos[0]) == _erros_json(zero_e_nbs.objetos[0])
        assert "VSN-041" not in _erros_json(zero_e_nbs.objetos[0])


def test_ncmZeroNaoEhAceitoPorDocumentoSemPermissaoEValoresNaoExatosNaoSaoNormalizados(
    record_xml_attribute,
) -> None:
    _junit(
        record_xml_attribute,
        "ncmZeroNaoEhAceitoPorDocumentoSemPermissaoEValoresNaoExatosNaoSaoNormalizados",
    )
    sem = _enviar_classico(
        _operacao_classica("57", _item_classico(ncm="00"))
    )
    assert sem.objetos[0].estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    assert sem.objetos[0].erros is not None
    assert sem.objetos[0].erros[0].code == "VSN-051"

    for ncm in ("000000000", " 00 "):
        nao_exato = _enviar_classico(
            _operacao_classica("55", _item_classico(ncm=ncm))
        )
        assert nao_exato.objetos[0].estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
        assert nao_exato.objetos[0].erros is not None
        assert nao_exato.objetos[0].erros[0].code != "VSN-042"


def test_NbsInformadoEmNfeEhIncompativelComDocumentoEApontaNbs(
    record_xml_attribute,
) -> None:
    _junit(record_xml_attribute, "NbsInformadoEmNfeEhIncompativelComDocumentoEApontaNbs")
    corpo = _enviar_classico(_classico(_item_classico(class_trib="000001", nbs="122012000")))
    _assert_falha_item(corpo, "VSN-045", "#/itens/0/nbs")


def test_NcmInformadoEmNfseEhIncompativelComDocumentoEApontaNcm(
    record_xml_attribute,
) -> None:
    _junit(record_xml_attribute, "NcmInformadoEmNfseEhIncompativelComDocumentoEApontaNcm")
    item = _item_classico(cativ_sn="07", class_trib="000001", ncm="10062010")
    corpo = _enviar_classico(_operacao_classica("91", item))
    assert corpo.objetos[0].estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    assert corpo.objetos[0].erros is not None
    assert corpo.objetos[0].erros[0].code == "VSN-045"
    assert corpo.objetos[0].erros[0].pointer == "#/itens/0/ncm"


def test_baseNegativaENomenclaturasSimultaneas_ApontamBaseAntesDoErroEstrutural(
    record_xml_attribute,
) -> None:
    _junit(record_xml_attribute, "baseNegativaENomenclaturasSimultaneas_ApontamBaseAntesDoErroEstrutural")
    item = _item_classico(base="-1.00", ncm="10062010", nbs="122012000")
    corpo = _enviar_classico(_operacao_classica("55", item))
    erros = corpo.objetos[0].erros
    assert corpo.objetos[0].estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    assert erros is not None and len(erros) >= 2
    assert erros[0].code == "VSN-002"
    assert erros[0].pointer == "#/itens/0/baseCalculo"
    assert erros[1].code == "VSN-041"
    assert erros[1].pointer == "#/itens/0/ncm"


def test_nbsVigenteEAplicavelEmNfseCalculaNoBancoReal(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "nbsVigenteEAplicavelEmNfseCalculaNoBancoReal")
    item = _item_classico(cativ_sn="07", class_trib="200028", nbs="122012000")
    resposta = _enviar_classico(_operacao_classica("91", item))
    assert resposta.objetos[0].estado is EstadoItemProcessado.CALCULADO
    assert resposta.objetos[0].erros is None
    assert resposta.total is not None
    assert _fmt_total(resposta.total.receita_bruta_total) == "500.00"


def test_aliasMaiusculoNbsEmNfseProduzMesmoResultadoQueNomeCanonico(
    record_xml_attribute,
) -> None:
    _junit(record_xml_attribute, "aliasMaiusculoNbsEmNfseProduzMesmoResultadoQueNomeCanonico")
    base = _item_classico(cativ_sn="07", class_trib="200028", nbs="122012000")
    minusculo = _enviar_classico(_operacao_classica("91", base))
    maiusculo = _enviar_classico(_operacao_classica("91", base))
    assert minusculo.objetos[0].estado is EstadoItemProcessado.CALCULADO
    assert maiusculo.objetos[0].estado is EstadoItemProcessado.CALCULADO
    assert minusculo.objetos[0] == maiusculo.objetos[0]
    assert minusculo.total == maiusculo.total