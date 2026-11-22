"""Espelho de ``MotivoEstadoSimplesControllerTest`` (pin a926d5a7) — serviço, sem HTTP."""

from __future__ import annotations

import os
from dataclasses import replace
import pytest

os.environ.setdefault(
    "CALC_DB",
    "/home/garusotec/projects/lynko/libs/calculadora-rtc-regime-regular/.cache/oficial/java/calculadora/db/calculadora-pro.db",
)

from calculadora_rtc_simples_nacional.arredondamento import formatar_moeda
from calculadora_rtc_simples_nacional.consumo import (
    SimplesNacionalNaoAssistidoService,
    SimplesNacionalObservabilidadeService,
)
from calculadora_rtc_simples_nacional.nao_assistido import (
    AliquotasEfetivas,
    AnexoComIss,
    AnexoUnico,
    OperacaoNaoAssistida,
    ParInformado,
)
from calculadora_rtc_simples_nacional.observabilidade import ItemSimplesClassico, OperacaoSimplesClassica
from calculadora_rtc_simples_nacional.parametro import CodigoRegimeApuracao, banco_disponivel
from calculadora_rtc_simples_nacional.processador import EstadoItemProcessado, ObjetoItem
from calculadora_rtc_simples_nacional.unificado import (
    ErrosCalculoException,
    ItemSimplesUnificadoInput,
    ObservabilidadeSimples,
)

_CLASSNAME = "br.gov.serpro.rtc.testesintegracao.simplesnacional.MotivoEstadoSimplesControllerTest"
_DATA = "2027-03-15"
_BASE_URL = "http://localhost/api"
_SVC_CLASSICO = SimplesNacionalObservabilidadeService()
_SVC_NAO = SimplesNacionalNaoAssistidoService()

_DESCRICAO_AUSENTE = (
    "O código de atividade do Simples Nacional (cAtivSN) não foi informado; sem ele o IBS e a CBS "
    "do item não são calculados (NT 2026.005, §5.3.3)."
)
_DESCRICAO_DESCONHECIDO = (
    "O código de atividade '99' não existe ou não está vigente na data do fato gerador; "
    "o IBS e a CBS do item não são calculados."
)
_DESCRICAO_INADMISSIVEL = (
    "A atividade '07' não é admitida no tipo de documento NF-e (tpDoc 55); "
    "o IBS e a CBS do item não são calculados."
)
_DESCRICAO_SOMENTE_RECEITA = (
    "O optante apura o IBS e a CBS pelo regime regular, fora do Simples Nacional; "
    "o item leva ao Simples apenas a receita bruta."
)

pytestmark = pytest.mark.skipif(not banco_disponivel(), reason="calculadora-pro.db ausente")


def _junit(record_xml_attribute, name: str) -> None:
    record_xml_attribute("classname", _CLASSNAME)
    record_xml_attribute("name", name)


def _par(cbs: str, ibs: str) -> AnexoUnico:
    return AnexoUnico(p_cbssn=cbs, p_ibssn=ibs)


def _anexo_iss(cbs: str, ibs: str, sem: ParInformado | None) -> AnexoComIss:
    return AnexoComIss(p_cbssn=cbs, p_ibssn=ibs, sem_redistribuicao=sem)


def _linha() -> AliquotasEfetivas:
    return AliquotasEfetivas(
        fator_r=True,
        impedimento_sublimite=False,
        anexo_i=_par("1.1612", "0.0129"),
        anexo_ii=_par("1.1184", "0.0121"),
        anexo_iii=_anexo_iss("2.2154", "0.0257", ParInformado("1.99", "0.0231")),
        anexo_iv=_anexo_iss("2.0119", "0.022", ParInformado("1.85", "0.0202")),
        anexo_v=_anexo_iss("3.2534", "0.0363", None),
    )


def _item_classico(numero: int, cativ_sn: str | None) -> ItemSimplesClassico:
    return ItemSimplesClassico(
        numero=numero,
        cativ_sn=cativ_sn,
        class_trib="000001",
        nbs=None,
        ncm=None,
        base_calculo="1000.00",
        valor_imposto_seletivo="0.00",
        p_ibs_sn="0.0129",
        p_cbs_sn="1.1612",
    )


def _operacao_classico(tp_doc: str, *itens: ItemSimplesClassico) -> OperacaoSimplesClassica:
    return OperacaoSimplesClassica(
        id="op-1",
        versao="3.0.0",
        data=_DATA,
        tp_doc=tp_doc,
        crt="1",
        tp_regime_ibscbs=None,
        tp_ente_gov=None,
        itens=list(itens),
    )


def _item_crt(numero: int, cativ: str | None) -> ItemSimplesUnificadoInput:
    return ItemSimplesUnificadoInput(
        numero=numero,
        cativ_sn=cativ,
        class_trib="000001",
        nbs=None,
        ncm=None,
        base_calculo="1000.00",
        valor_imposto_seletivo="0.00",
        trib_issqn=None,
        tp_ret_issqn=None,
        tp_bm=None,
    )


def _crt(
    tp_doc: str,
    crt: str,
    tp_regime: str | None,
    aliquotas: AliquotasEfetivas | None,
    *itens: ItemSimplesUnificadoInput,
) -> OperacaoNaoAssistida:
    return OperacaoNaoAssistida(
        id="op-1",
        versao="3.0.0",
        data=_DATA,
        tp_doc=tp_doc,
        crt=crt,
        tp_regime_ibscbs=tp_regime,
        itens=list(itens),
        aliquotas=aliquotas,
    )


def _nfse_aceita() -> OperacaoNaoAssistida:
    return OperacaoNaoAssistida(
        id="op-1",
        versao="3.0.0",
        data=_DATA,
        tp_doc="91",
        op_simp_nac="3",
        reg_ap_ibscbssn="1",
        reg_ap_trib_sn="1",
        aliquotas=_linha(),
        itens=[
            ItemSimplesUnificadoInput(
                numero=1,
                cativ_sn="07",
                class_trib="000001",
                nbs=None,
                ncm=None,
                base_calculo="1000.00",
                valor_imposto_seletivo=None,
                trib_issqn="1",
                tp_ret_issqn="1",
                tp_bm=None,
            )
        ],
    )


def _enviar_classico(operacao: OperacaoSimplesClassica):
    return _SVC_CLASSICO.processarOperacao(operacao, _BASE_URL)


def _enviar_nao(operacao: OperacaoNaoAssistida) -> ObservabilidadeSimples:
    return _SVC_NAO.processarOperacao(operacao)


def _enviar_erro_classico(operacao: OperacaoSimplesClassica):
    with pytest.raises(ErrosCalculoException) as exc:
        _enviar_classico(operacao)
    return exc.value.erros


def _enviar_erro_nao(operacao: OperacaoNaoAssistida):
    with pytest.raises(ErrosCalculoException) as exc:
        _enviar_nao(operacao)
    return exc.value.erros


def _assert_nao_calculado(obj: ObjetoItem, codigo: str, descricao: str) -> None:
    assert obj.estado is EstadoItemProcessado.NAO_CALCULADO, obj
    assert obj.motivo is not None, obj
    assert obj.motivo.codigo == codigo, obj
    assert obj.motivo.descricao == descricao
    assert obj.erros is None
    assert obj.tributos is not None
    assert formatar_moeda(obj.tributos.receita_bruta) == "1000.00"


def _assert_calculado_sem_motivo(obj: ObjetoItem) -> None:
    assert obj.estado is EstadoItemProcessado.CALCULADO, obj
    assert obj.motivo is None, obj


def _mensagem_vsn015(tp_doc: str) -> str:
    return (
        f"Tipo de documento fiscal (tpDoc) de código {tp_doc} ainda não possui tratamento "
        "implementado no cálculo do Simples Nacional."
    )


# ─── Clássico: motivos de cAtivSN ────────────────────────────────────────────


def test_classico_motivoDoNaoCalculadoPorCAtivSN_eCalculadoSemMotivo(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "classico_motivoDoNaoCalculadoPorCAtivSN_eCalculadoSemMotivo")
    corpo = _enviar_classico(
        _operacao_classico(
            "55",
            _item_classico(1, "01"),
            _item_classico(2, None),
            _item_classico(3, "99"),
            _item_classico(4, "07"),
        )
    )
    _assert_calculado_sem_motivo(corpo.objetos[0])
    _assert_nao_calculado(corpo.objetos[1], "CATIVSN_AUSENTE", _DESCRICAO_AUSENTE)
    _assert_nao_calculado(corpo.objetos[2], "CATIVSN_DESCONHECIDO", _DESCRICAO_DESCONHECIDO)
    _assert_nao_calculado(corpo.objetos[3], "CATIVSN_INADMISSIVEL_NO_DOCUMENTO", _DESCRICAO_INADMISSIVEL)


# ─── Não assistido ───────────────────────────────────────────────────────────


def test_naoAssistido_cAtivSNAusente(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "naoAssistido_cAtivSNAusente")
    corpo = _enviar_nao(
        _crt("55", "1", None, _linha(), _item_crt(1, "01"), _item_crt(2, None))
    )
    _assert_calculado_sem_motivo(corpo.objetos[0])
    _assert_nao_calculado(corpo.objetos[1], "CATIVSN_AUSENTE", _DESCRICAO_AUSENTE)


def test_naoAssistido_cAtivSNDesconhecido(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "naoAssistido_cAtivSNDesconhecido")
    corpo = _enviar_nao(_crt("55", "1", None, _linha(), _item_crt(1, "99")))
    _assert_nao_calculado(corpo.objetos[0], "CATIVSN_DESCONHECIDO", _DESCRICAO_DESCONHECIDO)


def test_naoAssistido_atividadeAdmitidaSoEmOutroDocumento(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "naoAssistido_atividadeAdmitidaSoEmOutroDocumento")
    corpo = _enviar_nao(_crt("55", "1", None, _linha(), _item_crt(1, "07")))
    _assert_nao_calculado(corpo.objetos[0], "CATIVSN_INADMISSIVEL_NO_DOCUMENTO", _DESCRICAO_INADMISSIVEL)


def test_naoAssistido_regimeSomenteReceita_temPrecedenciaSobreOCAtivSN(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "naoAssistido_regimeSomenteReceita_temPrecedenciaSobreOCAtivSN")
    corpo = _enviar_nao(
        _crt(
            "55",
            "1",
            "1",
            None,
            _item_crt(1, "01"),
            _item_crt(2, None),
            _item_crt(3, "99"),
        )
    )
    assert corpo.oper.regime_apuracao is CodigoRegimeApuracao.SOMENTE_RECEITA
    for i in range(3):
        _assert_nao_calculado(corpo.objetos[i], "REGIME_SOMENTE_RECEITA", _DESCRICAO_SOMENTE_RECEITA)


# ─── tpDoc sem tratamento (VSN-015) ──────────────────────────────────────────

_TPDOC_SEM_TRATAMENTO = ("77", "94", "95", "96")


@pytest.mark.parametrize("tp_doc", _TPDOC_SEM_TRATAMENTO)
def test_tpDocSemTratamentoNaCalculadora_vsn015(tp_doc: str, record_xml_attribute) -> None:
    idx = _TPDOC_SEM_TRATAMENTO.index(tp_doc) + 1
    _junit(record_xml_attribute, f"tpDocSemTratamentoNaCalculadora_vsn015(Tipo)[{idx}]")
    mensagem = _mensagem_vsn015(tp_doc)

    erros_nao = _enviar_erro_nao(replace(_crt("55", "1", None, _linha(), _item_crt(1, "01")), tp_doc=tp_doc))
    assert erros_nao[0].code == "VSN-015"
    assert erros_nao[0].pointer == "#/tpDoc"
    assert erros_nao[0].detail == mensagem

    erros_classico = _enviar_erro_classico(
        replace(_operacao_classico("55", _item_classico(1, "01")), tp_doc=tp_doc)
    )
    assert erros_classico[0].code == "VSN-015"
    assert erros_classico[0].detail == mensagem


# ─── tpDoc com tratamento ────────────────────────────────────────────────────

_TPDOC_ACEITO = ("55", "65", "91")


@pytest.mark.parametrize("tp_doc", _TPDOC_ACEITO)
def test_tpDocComTratamentoNaCalculadora_aceito(tp_doc: str, record_xml_attribute) -> None:
    idx = _TPDOC_ACEITO.index(tp_doc) + 1
    _junit(record_xml_attribute, f"tpDocComTratamentoNaCalculadora_aceito(Tipo)[{idx}]")
    if tp_doc == "91":
        operacao = _nfse_aceita()
    else:
        operacao = _crt(tp_doc, "1", None, _linha(), _item_crt(1, "01"))
    corpo = _enviar_nao(operacao)
    _assert_calculado_sem_motivo(corpo.objetos[0])