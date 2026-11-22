"""Espelho de ``SimplesNacionalNaoAssistidoControllerTest`` (pin a926d5a7) — serviço, sem HTTP."""

from __future__ import annotations

import os
from dataclasses import replace
from decimal import Decimal

import pytest

os.environ.setdefault(
    "CALC_DB",
    "/home/garusotec/projects/lynko/libs/calculadora-rtc-regime-regular/.cache/oficial/java/calculadora/db/calculadora-pro.db",
)

from calculadora_rtc_simples_nacional.consumo import SimplesNacionalNaoAssistidoService
from calculadora_rtc_simples_nacional.escolha import RegraAliquota, TipoAliquota
from calculadora_rtc_simples_nacional.nao_assistido import (
    AliquotasEfetivas,
    AnexoComIss,
    AnexoUnico,
    OperacaoNaoAssistida,
    ParInformado,
)
from calculadora_rtc_simples_nacional.parametro import CodigoRegimeApuracao, banco_disponivel
from calculadora_rtc_simples_nacional.processador import EstadoItemProcessado
from calculadora_rtc_simples_nacional.unificado import (
    ErrosCalculoException,
    ItemSimplesUnificadoInput,
    ObservabilidadeSimples,
)

_CLASSNAME = (
    "br.gov.serpro.rtc.testesintegracao.simplesnacional.SimplesNacionalNaoAssistidoControllerTest"
)
_DATA = "2027-03-15"
_SVC = SimplesNacionalNaoAssistidoService()

pytestmark = pytest.mark.skipif(not banco_disponivel(), reason="calculadora-pro.db ausente")


def _fmt2(val: Decimal | None) -> str:
    assert val is not None
    return f"{val.quantize(Decimal('0.01')):.2f}"


def _fmt_aliquota_trib(val: Decimal | None) -> str | None:
    if val is None:
        return None
    return _fmt2(val)


def _plain(val: Decimal | None) -> str:
    assert val is not None
    text = format(val.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _par(cbs: str, ibs: str) -> AnexoUnico:
    return AnexoUnico(p_cbssn=cbs, p_ibssn=ibs)


def _anexo_iss(cbs: str, ibs: str, sem: ParInformado | None) -> AnexoComIss:
    return AnexoComIss(p_cbssn=cbs, p_ibssn=ibs, sem_redistribuicao=sem)


def _linha(**patch) -> AliquotasEfetivas:
    base = AliquotasEfetivas(
        fator_r=True,
        impedimento_sublimite=False,
        anexo_i=_par("1.1612", "0.0129"),
        anexo_ii=_par("1.1184", "0.0121"),
        anexo_iii=_anexo_iss("2.2154", "0.0257", ParInformado("1.99", "0.0231")),
        anexo_iv=_anexo_iss("2.0119", "0.022", ParInformado("1.85", "0.0202")),
        anexo_v=_anexo_iss("3.2534", "0.0363", None),
    )
    return replace(base, **patch) if patch else base


def _item(**fields) -> ItemSimplesUnificadoInput:
    base = dict(
        numero=1,
        cativ_sn=None,
        class_trib="000001",
        nbs=None,
        ncm=None,
        base_calculo="10000.00",
        valor_imposto_seletivo=None,
        trib_issqn=None,
        tp_ret_issqn=None,
        tp_bm=None,
    )
    base.update(fields)
    return ItemSimplesUnificadoInput(**base)


def _item_crt(
    numero: int,
    cativ: str | None,
    class_trib: str,
    base: str,
) -> ItemSimplesUnificadoInput:
    return _item(
        numero=numero,
        cativ_sn=cativ,
        class_trib=class_trib,
        base_calculo=base,
        valor_imposto_seletivo="0.00",
    )


def _nfse(
    op_simp: str,
    reg_ap: str,
    reg_trib: str,
    aliquotas: AliquotasEfetivas | None,
    item: ItemSimplesUnificadoInput,
    **extra,
) -> OperacaoNaoAssistida:
    return OperacaoNaoAssistida(
        id="op-1",
        versao="3.0.0",
        data=_DATA,
        tp_doc="91",
        op_simp_nac=op_simp,
        reg_ap_ibscbssn=reg_ap,
        reg_ap_trib_sn=reg_trib,
        itens=[item],
        aliquotas=aliquotas,
        **extra,
    )


def _crt(
    tp_doc: str,
    crt: str | None,
    tp_regime: str | None,
    aliquotas: AliquotasEfetivas | None,
    *itens: ItemSimplesUnificadoInput,
    **extra,
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
        **extra,
    )


def _enviar(operacao: OperacaoNaoAssistida) -> ObservabilidadeSimples:
    return _SVC.processarOperacao(operacao)


def _enviar_erro(operacao: OperacaoNaoAssistida) -> list:
    with pytest.raises(ErrosCalculoException) as exc:
        _SVC.processarOperacao(operacao)
    return exc.value.erros


def _codigos_globais(operacao: OperacaoNaoAssistida) -> list[str]:
    return [e.code for e in _enviar_erro(operacao)]


def _enviar_nfse_padrao(cativ: str, **campos) -> ObservabilidadeSimples:
    return _enviar(_nfse("3", "1", "1", _linha(), _item(cativ_sn=cativ, **campos)))


def _res(corpo: ObservabilidadeSimples, i: int = 0):
    assert corpo.resolucao_aliquotas is not None
    return corpo.resolucao_aliquotas.itens[i]


def _trib(corpo: ObservabilidadeSimples, i: int = 0):
    return corpo.objetos[i].tributos


# ─── Tabela 3.2: família CRT ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "crt,tp_regime,regime",
    [
        ("1", None, "SN_PLENO"),
        ("2", None, "SN_SUBLIMITE"),
        ("1", "1", "SOMENTE_RECEITA"),
        ("2", "1", "SOMENTE_RECEITA"),
        ("3", "2", "PENDENTE"),
    ],
)
def test_tabela32_combinacoesQueLevamAUmRegime(crt: str | None, tp_regime: str | None, regime: str) -> None:
    corpo = _enviar(_crt("55", crt, tp_regime, _linha(), _item_crt(1, "01", "000001", "1000.00")))
    assert corpo.oper.regime_apuracao is CodigoRegimeApuracao(regime)
    assert corpo.oper.crt == crt


@pytest.mark.parametrize(
    "crt,tp_regime,codigo",
    [
        ("1", "2", "VSN-018"),
        ("2", "2", "VSN-018"),
        ("3", None, "VSN-019"),
        ("3", "1", "VSN-018"),
        ("4", None, "VSN-019"),
        ("4", "1", "VSN-018"),
        ("4", "2", "VSN-018"),
        (None, None, "VSN-016"),
        ("5", None, "VSN-016"),
        ("1", "3", "VSN-017"),
    ],
)
def test_tabela32_erros(crt: str | None, tp_regime: str | None, codigo: str) -> None:
    assert _codigos_globais(_crt("55", crt, tp_regime, _linha(), _item_crt(1, "01", "000001", "1000.00"))) == [
        codigo
    ]


def test_tabela32_crt4_mensagemNoVocabularioRecebido() -> None:
    erros = _enviar_erro(_crt("55", "4", None, _linha(), _item_crt(1, "01", "000001", "1000.00")))
    assert erros[0].pointer == "#/CRT"
    assert "MEI (CRT=4)" in erros[0].detail


# ─── Tabela 3.3: família NFS-e ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "op_simp,reg_ap,regime",
    [
        ("3", "1", "SN_PLENO"),
        ("3", "2", "SN_SUBLIMITE"),
        ("3", "3", "SOMENTE_RECEITA"),
        ("4", "1", "PENDENTE"),
        ("4", "2", "PENDENTE_SUBLIMITE"),
        ("4", "3", "SOMENTE_RECEITA"),
    ],
)
def test_tabela33_combinacoesQueLevamAUmRegime(op_simp: str, reg_ap: str, regime: str) -> None:
    corpo = _enviar(
        _nfse(
            op_simp,
            reg_ap,
            "1",
            _linha(),
            _item(cativ_sn="07", trib_issqn="1", tp_ret_issqn="1"),
        )
    )
    assert corpo.oper.regime_apuracao is CodigoRegimeApuracao(regime)
    assert corpo.oper.op_simp_nac == op_simp
    assert corpo.oper.reg_ap_ibscbssn == reg_ap
    assert corpo.oper.reg_ap_trib_sn == "1"


@pytest.mark.parametrize(
    "op_simp,reg_ap,reg_trib,codigo",
    [
        ("1", None, None, "VSN-019"),
        ("2", None, None, "VSN-019"),
        ("1", "1", None, "VSN-031"),
        ("2", "2", None, "VSN-031"),
        ("1", "3", None, "VSN-031"),
        ("3", None, "1", "VSN-031"),
        ("4", None, "1", "VSN-031"),
        ("3", "4", "1", "VSN-031"),
        ("3", "1", None, "VSN-032"),
        ("4", "1", None, "VSN-032"),
        ("1", None, "1", "VSN-032"),
        ("3", "1", "4", "VSN-032"),
        (None, "1", "1", "VSN-030"),
        ("5", "1", "1", "VSN-030"),
    ],
)
def test_tabela33_erros(op_simp: str | None, reg_ap: str | None, reg_trib: str | None, codigo: str) -> None:
    op = OperacaoNaoAssistida(
        id="op-1",
        versao="3.0.0",
        data=_DATA,
        tp_doc="91",
        op_simp_nac=op_simp,
        reg_ap_ibscbssn=reg_ap,
        reg_ap_trib_sn=reg_trib,
        itens=[_item(cativ_sn="07", trib_issqn="1", tp_ret_issqn="1")],
        aliquotas=_linha(),
    )
    assert _codigos_globais(op) == [codigo]


def test_vsn033_campoDeRegimeDoOutroVocabulario() -> None:
    nfse_com_crt = _nfse("3", "1", "1", _linha(), _item(cativ_sn="07"))
    nfse_com_crt = replace(nfse_com_crt, crt="1")
    assert _codigos_globais(nfse_com_crt) == ["VSN-033"]
    assert _enviar_erro(nfse_com_crt)[0].pointer == "#/CRT"

    nfe = _crt("55", "1", None, _linha(), _item_crt(1, "01", "000001", "100.00"))
    nfe = replace(nfe, op_simp_nac="3", reg_ap_trib_sn="1")
    assert _codigos_globais(nfe) == ["VSN-033", "VSN-033"]


# ─── SOMENTE_RECEITA ───────────────────────────────────────────────────────


def test_somenteReceita_nfe_naoCalcula_semAliquotasEfetivas_nemCAtivSN() -> None:
    corpo = _enviar(
        _crt(
            "55",
            "1",
            "1",
            None,
            _item_crt(1, None, "000001", "1000.00"),
            _item_crt(2, "01", "410001", "500.00"),
        )
    )
    assert corpo.oper.regime_apuracao is CodigoRegimeApuracao.SOMENTE_RECEITA
    assert corpo.resolucao_aliquotas is None
    assert corpo.objetos[0].estado is EstadoItemProcessado.NAO_CALCULADO
    trib0 = _trib(corpo, 0)
    assert trib0 is not None
    assert _fmt2(trib0.receita_bruta) == "1000.00"
    assert trib0.tipo_receita == 1
    assert trib0.base_calculo is None
    trib1 = _trib(corpo, 1)
    assert trib1 is not None
    assert _fmt2(trib1.receita_bruta) == "0.00"
    assert corpo.total is not None
    assert _fmt2(corpo.total.receita_bruta_total) == "1000.00"
    assert corpo.total.cbs_total is None


def test_somenteReceita_nfse_semCamposDoIss_eCClassTribObrigatorio() -> None:
    corpo = _enviar(_nfse("4", "3", "1", None, _item(cativ_sn="07")))
    assert corpo.oper.regime_apuracao is CodigoRegimeApuracao.SOMENTE_RECEITA
    assert corpo.objetos[0].estado is EstadoItemProcessado.NAO_CALCULADO
    trib = _trib(corpo)
    assert trib is not None and _fmt2(trib.receita_bruta) == "10000.00"

    sem = _enviar(_nfse("3", "3", "1", None, _item(numero=1, class_trib=None, base_calculo="10.00")))
    assert sem.objetos[0].estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    assert sem.objetos[0].erros is not None
    assert sem.objetos[0].erros[0].code == "VSN-020"


# ─── aliquotasEfetivas e fatorR ────────────────────────────────────────────


def test_vsn039_aliquotasEfetivasAusente() -> None:
    erros = _enviar_erro(
        _nfse("3", "1", "1", None, _item(cativ_sn="07", trib_issqn="1", tp_ret_issqn="1"))
    )
    assert [e.code for e in erros] == ["VSN-039"]
    assert erros[0].pointer == "#/aliquotasEfetivas"


def test_vsn040_fatorRAusenteComAtividade09() -> None:
    sem_fator = _linha()
    sem_fator = replace(sem_fator, fator_r=None)
    corpo = _enviar(
        _nfse("3", "1", "1", sem_fator, _item(cativ_sn="09", trib_issqn="1", tp_ret_issqn="1"))
    )
    assert corpo.objetos[0].erros is not None
    erro = corpo.objetos[0].erros[0]
    assert erro.code == "VSN-040"
    assert erro.pointer == "#/aliquotasEfetivas/fatorR"
    assert _res(corpo).motivo == "FATOR_R_AUSENTE"
    outra = _enviar(
        _nfse("3", "1", "1", sem_fator, _item(cativ_sn="07", trib_issqn="1", tp_ret_issqn="1"))
    )
    assert outra.objetos[0].estado is EstadoItemProcessado.CALCULADO
    assert outra.resolucao_aliquotas is not None
    assert outra.resolucao_aliquotas.fator_r is None


def test_parQueNenhumItemUsa_podeFaltar_masSeVierTemOFormatoValidado() -> None:
    so_anexo_iii = AliquotasEfetivas(
        fator_r=False,
        anexo_iii=_anexo_iss("2.2154", "0.0257", ParInformado("1.99", "0.0231")),
    )
    ok = _enviar(_nfse("3", "1", "1", so_anexo_iii, _item(cativ_sn="07", trib_issqn="1", tp_ret_issqn="1")))
    assert ok.objetos[0].estado is EstadoItemProcessado.CALCULADO

    invalida = _linha()
    invalida = replace(invalida, anexo_v=_anexo_iss("3,25", "-0.03", None))
    erros = _enviar_erro(
        _nfse("3", "1", "1", invalida, _item(cativ_sn="07", trib_issqn="1", tp_ret_issqn="1"))
    )
    assert [e.code for e in erros] == ["VSN-005", "VSN-007"]
    assert erros[0].pointer == "#/aliquotasEfetivas/anexoV/pCBSSN"
    assert "negativo" in erros[1].detail


def test_vsn004e006_valorDoParEscolhidoAusente_ponteiroParaDentroDeAliquotasEfetivas() -> None:
    sem_cbs = _linha()
    sem_cbs = replace(
        sem_cbs,
        anexo_iii=_anexo_iss("2.2154", "0.0257", ParInformado(None, "0.0231")),
    )
    r1 = _enviar(_nfse("3", "1", "1", sem_cbs, _item(cativ_sn="07", trib_issqn="2")))
    assert r1.objetos[0].erros is not None
    assert r1.objetos[0].erros[0].code == "VSN-004"
    assert r1.objetos[0].erros[0].pointer == "#/aliquotasEfetivas/anexoIII/semRedistribuicaoISS/pCBSSN"

    sem_ibs = _linha()
    sem_ibs = replace(sem_ibs, anexo_iii=_anexo_iss("2.2154", None, ParInformado("1.99", "0.0231")))
    r2 = _enviar(
        _nfse("3", "1", "1", sem_ibs, _item(cativ_sn="07", trib_issqn="1", tp_ret_issqn="1"))
    )
    assert r2.objetos[0].erros is not None
    assert r2.objetos[0].erros[0].code == "VSN-006"
    assert r2.objetos[0].erros[0].pointer == "#/aliquotasEfetivas/anexoIII/pIBSSN"

    r3 = _enviar(_nfse("3", "2", "1", sem_ibs, _item(cativ_sn="07", trib_issqn="1", tp_ret_issqn="1")))
    assert r3.objetos[0].estado is EstadoItemProcessado.CALCULADO


# ─── Regras do par de alíquotas ────────────────────────────────────────────


def test_regra1_documento_atividadeNaoAdmitidaNaNfse() -> None:
    corpo = _enviar_nfse_padrao("01")
    assert corpo.objetos[0].estado is EstadoItemProcessado.NAO_CALCULADO
    r = _res(corpo)
    assert r.regra_aliquota is RegraAliquota.DOCUMENTO
    assert r.tipo_aliquota is None
    assert r.motivo == "ATIVIDADE_INADMISSIVEL_NO_DOCUMENTO"


def test_regra2_atividadeNaoTributada_nasDuasFamilias() -> None:
    nfse = _enviar(
        _nfse("3", "1", "1", _linha(), _item(cativ_sn="90", class_trib="200019"))
    )
    r0 = _res(nfse)
    assert r0.tipo_aliquota is TipoAliquota.SEM_ALIQUOTA
    assert r0.regra_aliquota is RegraAliquota.ATIVIDADE_NAO_TRIBUTADA
    assert _plain(r0.aliquota_cbs) == "0"
    assert nfse.objetos[0].estado is EstadoItemProcessado.CALCULADO
    trib = _trib(nfse)
    assert trib is not None and _fmt2(trib.valor_cbs) == "0.00"

    nfe = _enviar(_crt("55", "1", None, _linha(), _item_crt(1, "90", "410001", "100.00")))
    assert _res(nfe).tipo_aliquota is TipoAliquota.SEM_ALIQUOTA


def test_regra3_anexoSemIss_parUnico_familiaCrt() -> None:
    corpo = _enviar(
        _crt(
            "55",
            "1",
            None,
            _linha(),
            _item_crt(1, "01", "000001", "1000.00"),
            _item_crt(2, "03", "000001", "500.00"),
        )
    )
    r0 = _res(corpo, 0)
    assert r0.tipo_aliquota is TipoAliquota.PAR_UNICO
    assert r0.regra_aliquota is RegraAliquota.ANEXO_SEM_ISS
    assert r0.anexo_aplicado == "I"
    assert _plain(r0.aliquota_cbs) == "1.1612"
    trib0 = _trib(corpo, 0)
    assert trib0 is not None
    assert _fmt2(trib0.valor_cbs) == "11.61"
    assert _fmt2(trib0.valor_ibs) == "0.13"
    assert _res(corpo, 1).anexo_aplicado == "II"


@pytest.mark.parametrize("reg_ap,reg_trib", [("1", "2"), ("1", "3"), ("2", "2")])
def test_regra4_issForaDoSimples_nfse(reg_ap: str, reg_trib: str) -> None:
    corpo = _enviar(
        _nfse(
            "3",
            reg_ap,
            reg_trib,
            _linha(),
            _item(cativ_sn="07", trib_issqn="1", tp_ret_issqn="1"),
        )
    )
    r = _res(corpo)
    assert r.regra_aliquota is RegraAliquota.ISS_FORA_DO_SIMPLES
    assert r.tipo_aliquota is TipoAliquota.SEM_REDISTRIBUICAO
    assert _plain(r.aliquota_cbs) == "1.99"
    trib = _trib(corpo)
    assert trib is not None and _fmt2(trib.valor_cbs) == "199.00"


def test_regra4_impedimentoPeloSublimite_daLinha() -> None:
    impedida = replace(_linha(), impedimento_sublimite=True)
    corpo = _enviar(
        _nfse("3", "2", "2", impedida, _item(cativ_sn="07", trib_issqn="1", tp_ret_issqn="1"))
    )
    assert _res(corpo).regra_aliquota is RegraAliquota.ISS_FORA_DO_SIMPLES
    assert corpo.resolucao_aliquotas is not None
    assert corpo.resolucao_aliquotas.ind_sublimite is True
    assert not corpo.resolucao_aliquotas.avisos


def test_regra4_familiaCrt_crt2NoCte() -> None:
    corpo = _enviar(_crt("57", "2", None, _linha(), _item_crt(1, "05", "000001", "1000.00")))
    r = _res(corpo)
    assert r.regra_aliquota is RegraAliquota.ISS_FORA_DO_SIMPLES
    assert r.tipo_aliquota is TipoAliquota.SEM_REDISTRIBUICAO
    trib = _trib(corpo)
    assert trib is not None
    assert _fmt2(trib.valor_cbs) == "19.90"
    assert trib.valor_ibs is None


def test_regra5_atividadeSemIss_nasDuasFamilias() -> None:
    nfse = _enviar_nfse_padrao("11")
    assert _res(nfse).regra_aliquota is RegraAliquota.ATIVIDADE_SEM_ISS
    assert _res(nfse).tipo_aliquota is TipoAliquota.SEM_REDISTRIBUICAO

    nfcom = _enviar(_crt("62", "1", None, _linha(), _item_crt(1, "06", "000001", "1000.00")))
    assert _res(nfcom).regra_aliquota is RegraAliquota.ATIVIDADE_SEM_ISS
    assert _plain(_res(nfcom).aliquota_cbs) == "1.99"


@pytest.mark.parametrize("trib_issqn", ["2", "3", "4"])
def test_regra6_issNaoIncide(trib_issqn: str) -> None:
    corpo = _enviar_nfse_padrao("14", trib_issqn=trib_issqn)
    r = _res(corpo)
    assert r.regra_aliquota is RegraAliquota.ISS_NAO_INCIDE
    assert r.anexo_aplicado == "IV"
    assert _plain(r.aliquota_cbs) == "1.85"


def test_regra7_isencaoMunicipal() -> None:
    corpo = _enviar_nfse_padrao("12", trib_issqn="1", tp_ret_issqn="1", tp_bm="1")
    r = _res(corpo)
    assert r.regra_aliquota is RegraAliquota.ISENCAO_MUNICIPAL
    assert r.tipo_aliquota is TipoAliquota.SEM_REDISTRIBUICAO


@pytest.mark.parametrize("tp_ret", ["2", "3"])
def test_regra8_issRetido(tp_ret: str) -> None:
    corpo = _enviar_nfse_padrao("07", trib_issqn="1", tp_ret_issqn=tp_ret)
    r = _res(corpo)
    assert r.regra_aliquota is RegraAliquota.ISS_RETIDO
    assert r.tipo_aliquota is TipoAliquota.SEM_REDISTRIBUICAO


def test_regra9_padrao_comRedistribuicao() -> None:
    corpo = _enviar_nfse_padrao("13", trib_issqn="1", tp_ret_issqn="1", tp_bm="2")
    r = _res(corpo)
    assert r.regra_aliquota is RegraAliquota.PADRAO
    assert r.tipo_aliquota is TipoAliquota.COM_REDISTRIBUICAO
    assert _plain(r.aliquota_cbs) == "2.0119"
    assert r.motivo == "RESOLVIDA"


def test_parSemNulo_valeOParCom_comAviso() -> None:
    linha_local = replace(_linha(), fator_r=False)
    corpo = _enviar(_nfse("3", "1", "1", linha_local, _item(cativ_sn="09", trib_issqn="2")))
    r = _res(corpo)
    assert r.anexo_aplicado == "V"
    assert r.tipo_aliquota is TipoAliquota.SEM_REDISTRIBUICAO
    assert r.regra_aliquota is RegraAliquota.ISS_NAO_INCIDE
    assert _plain(r.aliquota_cbs) == "3.2534"
    assert any("Par sem redistribuição do ISS ausente" in a for a in r.avisos)
    assert corpo.objetos[0].estado is EstadoItemProcessado.CALCULADO


def test_fatorR_atividade09_anexoIII() -> None:
    corpo = _enviar_nfse_padrao("09", trib_issqn="1", tp_ret_issqn="1")
    assert _res(corpo).anexo_aplicado == "III"
    assert corpo.resolucao_aliquotas is not None
    assert corpo.resolucao_aliquotas.fator_r is True


# ─── Campos do ISS ─────────────────────────────────────────────────────────


def test_camposDoIss_familiaCrt_desconsideradosComAviso() -> None:
    item = _item_crt(1, "01", "000001", "1000.00")
    item = replace(item, trib_issqn="2", tp_ret_issqn="2")
    corpo = _enviar(_crt("55", "1", None, _linha(), item))
    assert corpo.objetos[0].estado is EstadoItemProcessado.CALCULADO
    assert any("tribISSQN, tpRetISSQN" in a for a in _res(corpo).avisos)


def test_vsn036_037_038_camposDoIssNaNfse() -> None:
    sem_trib = _enviar_nfse_padrao("07")
    assert sem_trib.objetos[0].erros is not None
    assert sem_trib.objetos[0].erros[0].code == "VSN-036"
    assert sem_trib.objetos[0].erros[0].pointer == "#/itens/0/tribISSQN"

    sem_ret = _enviar_nfse_padrao("07", trib_issqn="1")
    assert sem_ret.objetos[0].erros is not None
    assert sem_ret.objetos[0].erros[0].code == "VSN-037"

    bm_invalido = _enviar_nfse_padrao("12", trib_issqn="1", tp_ret_issqn="1", tp_bm="7")
    assert bm_invalido.objetos[0].erros is not None
    assert bm_invalido.objetos[0].erros[0].code == "VSN-038"


def test_camposDoIss_desconsideradosNaNfse_comAviso() -> None:
    ret = _enviar_nfse_padrao("07", trib_issqn="2", tp_ret_issqn="2")
    assert _res(ret).regra_aliquota is RegraAliquota.ISS_NAO_INCIDE
    assert any("E0580" in a for a in _res(ret).avisos)

    bm = _enviar_nfse_padrao("07", trib_issqn="1", tp_ret_issqn="1", tp_bm="1")
    assert _res(bm).regra_aliquota is RegraAliquota.PADRAO
    assert any("E0536" in a for a in _res(bm).avisos)

    isencao = _enviar_nfse_padrao("12", trib_issqn="1", tp_ret_issqn="2", tp_bm="1")
    assert _res(isencao).regra_aliquota is RegraAliquota.ISENCAO_MUNICIPAL
    assert any("E0594" in a for a in _res(isencao).avisos)


# ─── NFS-e: 1 item, IS, tpRBSN e alíquota de 2 casas ──────────────────────


def test_vsn034_nfseComMaisDeUmItem() -> None:
    op = _nfse("3", "1", "1", _linha(), _item(cativ_sn="07"))
    op = replace(op, itens=[_item(cativ_sn="07"), _item(numero=2, cativ_sn="07")])
    assert _codigos_globais(op) == ["VSN-034"]


def test_vsn035_impostoSeletivoNaNfse_eGrupoISForaDaResposta() -> None:
    com_is = _enviar_nfse_padrao(
        "07", trib_issqn="1", tp_ret_issqn="1", valor_imposto_seletivo="5.00"
    )
    assert com_is.objetos[0].erros is not None
    assert com_is.objetos[0].erros[0].code == "VSN-035"

    zero = _enviar_nfse_padrao(
        "07", trib_issqn="1", tp_ret_issqn="1", valor_imposto_seletivo="0.00"
    )
    assert zero.objetos[0].estado is EstadoItemProcessado.CALCULADO
    trib = _trib(zero)
    assert trib is not None and trib.imposto_seletivo is None
    assert zero.total is not None and zero.total.imposto_seletivo_total is None


def test_nfse_aliquotaDe2Casas() -> None:
    corpo = _enviar_nfse_padrao("07", trib_issqn="1", tp_ret_issqn="1")
    r = _res(corpo)
    assert _plain(r.aliquota_cbs) == "2.2154"
    trib = _trib(corpo)
    assert trib is not None
    assert _fmt_aliquota_trib(trib.aliquota_cbs) == "2.22"
    assert _fmt_aliquota_trib(trib.aliquota_ibs) == "0.03"
    assert _fmt2(trib.valor_cbs) == "222.00"
    assert _fmt2(trib.valor_ibs) == "3.00"
    assert _fmt2(trib.total_item) == "225.00"
    assert trib.memoria is not None and "2,22%" in trib.memoria.cbs


def test_nfse_aliquotaDe2Casas_depoisDaCompraGovernamental() -> None:
    op = _nfse(
        "3",
        "1",
        "1",
        _linha(),
        _item(cativ_sn="07", trib_issqn="1", tp_ret_issqn="1"),
        tp_ente_gov="1",
    )
    corpo = _enviar(op)
    trib = _trib(corpo)
    assert trib is not None
    assert _fmt_aliquota_trib(trib.aliquota_cbs) == "2.24"
    assert _fmt2(trib.valor_cbs) == "224.00"
    assert _fmt2(trib.valor_ibs) == "0.00"


def test_familiaCrt_precisaoIntegral() -> None:
    linha_local = replace(_linha(), anexo_i=_par("1.16123456789", "0.0129"))
    corpo = _enviar(_crt("55", "1", None, linha_local, _item_crt(1, "01", "000001", "10000.00")))
    trib = _trib(corpo)
    assert trib is not None
    assert _fmt2(trib.valor_cbs) == "116.12"
    assert _plain(trib.aliquota_cbs) == "1.1612"
    assert _plain(_res(corpo).aliquota_cbs) == "1.16123456789"


@pytest.mark.parametrize(
    "class_trib,tp_rbsn,receita",
    [
        ("200019", 0, "0.00"),
        ("410008", 2, "10000.00"),
        ("200001", 3, "10000.00"),
    ],
)
def test_nfse_tpRBSNDiferenteDe1_valoresZerados(class_trib: str, tp_rbsn: int, receita: str) -> None:
    corpo = _enviar_nfse_padrao(
        "07", trib_issqn="1", tp_ret_issqn="1", class_trib=class_trib
    )
    trib = _trib(corpo)
    assert trib is not None
    assert trib.tipo_receita == tp_rbsn
    assert _fmt2(trib.receita_bruta) == receita
    assert _fmt2(trib.valor_cbs) == "0.00"
    assert _fmt2(trib.cbs_pendente) == "0.00"


def test_familiaCrt_tpRBSN4_pendenteSuspenso() -> None:
    corpo = _enviar(_crt("55", "1", None, _linha(), _item_crt(1, "01", "550001", "1000.00")))
    trib = _trib(corpo)
    assert trib is not None
    assert trib.tipo_receita == 4
    assert _fmt2(trib.valor_cbs) == "0.00"
    assert _fmt2(trib.cbs_pendente) == "11.61"


# ─── PENDENTE e PENDENTE_SUBLIMITE ─────────────────────────────────────────


def test_pendente_nfse_valoresPendentesSuspensos() -> None:
    corpo = _enviar(
        _nfse("4", "1", "1", _linha(), _item(cativ_sn="07", trib_issqn="1", tp_ret_issqn="1"))
    )
    assert corpo.oper.regime_apuracao is CodigoRegimeApuracao.PENDENTE
    trib = _trib(corpo)
    assert trib is not None
    assert _fmt2(trib.valor_cbs) == "0.00"
    assert _fmt2(trib.cbs_pendente) == "222.00"
    assert _fmt2(trib.ibs_pendente) == "3.00"
    assert _fmt2(trib.total_item) == "0.00"


def test_pendenteSublimite_nfse_soACbs() -> None:
    corpo = _enviar(
        _nfse("4", "2", "2", _linha(), _item(cativ_sn="07", trib_issqn="1", tp_ret_issqn="1"))
    )
    assert corpo.oper.regime_apuracao is CodigoRegimeApuracao.PENDENTE_SUBLIMITE
    trib = _trib(corpo)
    assert trib is not None
    assert trib.ibs_pendente is None
    assert trib.aliquota_ibs is None
    assert _fmt2(trib.cbs_pendente) == "199.00"
    assert _res(corpo).regra_aliquota is RegraAliquota.ISS_FORA_DO_SIMPLES


# ─── Avisos e saída ────────────────────────────────────────────────────────


def test_avisos_regApIBSCBSSN2ComRegApTribSN1_eDivergenciaComImpedimento() -> None:
    incoerente = _enviar(
        _nfse("3", "2", "1", _linha(), _item(cativ_sn="07", trib_issqn="1", tp_ret_issqn="1"))
    )
    avisos = incoerente.resolucao_aliquotas.avisos if incoerente.resolucao_aliquotas else ()
    assert len(avisos) == 2
    assert "SN_SUBLIMITE" in avisos[0]
    assert "incoerente" in avisos[1]
    assert _res(incoerente).regra_aliquota is RegraAliquota.ISS_FORA_DO_SIMPLES

    impedida = replace(
        _linha(),
        impedimento_sublimite=True,
        anexo_iii=_anexo_iss("2.2154", None, ParInformado("1.99", None)),
    )
    pleno = _enviar(
        _nfse("3", "1", "1", impedida, _item(cativ_sn="07", trib_issqn="1", tp_ret_issqn="1"))
    )
    assert pleno.resolucao_aliquotas is not None
    assert any("SN_PLENO" in a for a in pleno.resolucao_aliquotas.avisos)
    assert pleno.objetos[0].erros is not None
    assert pleno.objetos[0].erros[0].code == "VSN-006"


def test_saida_cabecalhoDoNaoAssistido_eCAtivSNNormalizado() -> None:
    corpo = _enviar_nfse_padrao("7", trib_issqn="1", tp_ret_issqn="1")
    res = corpo.resolucao_aliquotas
    assert res is not None
    assert res.fator_r is True
    assert res.ind_sublimite is False
    assert _res(corpo).cativ_sn == "07"
    assert corpo.objetos[0].estado is EstadoItemProcessado.CALCULADO
    campos = list(corpo.__dataclass_fields__.keys())
    assert campos == ["oper", "resolucao_aliquotas", "objetos", "total"]


def test_itemNaoImplementado_listadoNaResolucao() -> None:
    corpo = _enviar(_crt("55", "1", None, _linha(), _item_crt(1, "01", "620001", "100.00")))
    assert corpo.objetos[0].estado is EstadoItemProcessado.NAO_IMPLEMENTADO
    assert _res(corpo).motivo == "ITEM_NAO_IMPLEMENTADO"


def test_cAtivSNDesconhecido_naoCalculado() -> None:
    corpo = _enviar(_crt("55", "1", None, _linha(), _item_crt(1, "77", "000001", "100.00")))
    assert corpo.objetos[0].estado is EstadoItemProcessado.NAO_CALCULADO
    r = _res(corpo)
    assert r.motivo == "ATIVIDADE_DESCONHECIDA"
    assert r.regra_aliquota is None