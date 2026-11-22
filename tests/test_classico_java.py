"""Espelho de ``SimplesNacionalControllerTest`` (pin a926d5a7) — serviço, sem HTTP."""

from __future__ import annotations

import json
import os
from decimal import Decimal

import pytest

os.environ.setdefault(
    "CALC_DB",
    "/home/garusotec/projects/lynko/libs/calculadora-rtc-regime-regular/.cache/oficial/java/calculadora/db/calculadora-pro.db",
)

from calculadora_rtc_simples_nacional.arredondamento import formatar_aliquota, formatar_moeda
from calculadora_rtc_simples_nacional.consumo import SimplesNacionalObservabilidadeService
from calculadora_rtc_simples_nacional.observabilidade import (
    ItemSimplesClassico,
    ObservabilidadeSimplesClassica,
    OperacaoSimplesClassica,
    uri_erro,
)
from calculadora_rtc_simples_nacional.parametro import banco_disponivel
from calculadora_rtc_simples_nacional.processador import EstadoItemProcessado, ObjetoItem
from calculadora_rtc_simples_nacional.unificado import ErrosCalculoException

_CLASSNAME = "br.gov.serpro.rtc.testesintegracao.simplesnacional.SimplesNacionalControllerTest"
BASE_URL = "http://localhost/api"
_SVC = SimplesNacionalObservabilidadeService()

pytestmark = pytest.mark.skipif(not banco_disponivel(), reason="calculadora-pro.db ausente")


def _junit(record_xml_attribute, name: str) -> None:
    record_xml_attribute("classname", _CLASSNAME)
    record_xml_attribute("name", name)


def _item_json(
    numero: int,
    base: str,
    v_is: str,
    p_ibs: str | None,
    p_cbs: str | None,
    *,
    cativ: str = "01",
    class_trib: str = "000001",
) -> str:
    parts = [
        f'"numero": {numero}',
        f'"cAtivSN": "{cativ}"',
        f'"cClassTrib": "{class_trib}"',
        f'"baseCalculo": "{base}"',
        f'"valorImpostoSeletivo": "{v_is}"',
    ]
    if p_ibs is not None:
        parts.append(f'"pIBSSN": "{p_ibs}"')
    if p_cbs is not None:
        parts.append(f'"pCBSSN": "{p_cbs}"')
    return "{ " + ", ".join(parts) + " }"


def _operacao_json(data: str, itens: str) -> str:
    return (
        '{"id": "507f1f77bcf86cd799439011", "versao": "2.0.0", "data": "'
        f'{data}", "tpDoc": "55", "CRT": "1", "itens": [ {itens} ] }}'
    )


def _operacao_from_json(raw: str) -> OperacaoSimplesClassica:
    doc = json.loads(raw)
    itens: list[ItemSimplesClassico] = []
    for it in doc.get("itens") or []:
        itens.append(
            ItemSimplesClassico(
                it.get("numero"),
                it.get("cAtivSN"),
                it.get("cClassTrib"),
                it.get("nbs"),
                it.get("ncm"),
                it.get("baseCalculo"),
                it.get("valorImpostoSeletivo"),
                it.get("pIBSSN"),
                it.get("pCBSSN"),
            )
        )
    return OperacaoSimplesClassica(
        doc.get("id"),
        doc.get("versao"),
        doc.get("data"),
        doc.get("tpDoc"),
        doc.get("CRT"),
        doc.get("tpRegimeIBSCBS"),
        doc.get("tpEnteGov"),
        itens,
    )


def _enviar(operacao: OperacaoSimplesClassica) -> ObservabilidadeSimplesClassica:
    return _SVC.processarOperacao(operacao, BASE_URL)


def _enviar_json(raw: str) -> ObservabilidadeSimplesClassica:
    return _enviar(_operacao_from_json(raw))


def _codigos_globais(raw: str) -> list[str]:
    with pytest.raises(ErrosCalculoException) as exc:
        _enviar_json(raw)
    return [e.code for e in exc.value.erros]


def _fmt2(val: Decimal | None) -> str:
    assert val is not None
    return formatar_moeda(val)


def _obj(corpo: ObservabilidadeSimplesClassica, i: int = 0) -> ObjetoItem:
    return corpo.objetos[i]


def _trib(corpo: ObservabilidadeSimplesClassica, i: int = 0):
    obj = _obj(corpo, i)
    assert obj.tributos is not None
    return obj.tributos


def _assert_ausente(corpo: ObservabilidadeSimplesClassica, json_path: str) -> None:
    """Espelho de jsonPath ``doesNotExist`` (campo omitido na saída)."""
    if json_path == "$.oper.tpRegimeIBSCBS":
        assert corpo.operacao.tp_regime_ibscbs is None
        return
    if json_path.startswith("$.objetos["):
        idx = int(json_path.split("[")[1].split("]")[0])
        obj = corpo.objetos[idx]
        rest = json_path.split("].", 1)[1]
        if rest == "tribCalc":
            assert obj.tributos is None
            return
        if rest == "erros":
            assert obj.erros is None
            return
        trib = obj.tributos
        if rest == "tribCalc.vBC":
            assert trib is None or trib.base_calculo is None
        elif rest == "tribCalc.vIBSSN":
            assert trib is None or trib.valor_ibs is None
        elif rest == "tribCalc.vCBSSN":
            assert trib is None or trib.valor_cbs is None
        elif rest == "tribCalc.IS":
            assert trib is None or trib.imposto_seletivo is None
        else:
            raise AssertionError(json_path)
        return
    if json_path == "$.total":
        assert corpo.total is None
        return
    if json_path.startswith("$.total."):
        assert corpo.total is not None
        campo = json_path.removeprefix("$.total.")
        mapping = {
            "vBC": "base_calculo_total",
            "vIBSSNtot": "ibs_total",
            "vCBSSNtot": "cbs_total",
            "totalTributos": "total_tributos",
        }
        attr = mapping.get(campo, campo)
        assert getattr(corpo.total, attr, "___") is None
        return
    raise AssertionError(json_path)


# ─── Casos dourados e integração ───────────────────────────────────────────


def test_deveCalcularCaminhoFelizCrt1ComImpostoSeletivoForaDaReceitaBruta(
    record_xml_attribute,
) -> None:
    _junit(record_xml_attribute, "deveCalcularCaminhoFelizCrt1ComImpostoSeletivoForaDaReceitaBruta")
    json_body = """
        {
          "id": "507f1f77bcf86cd799439011",
          "versao": "2.0.0",
          "data": "2027-03-15",
          "tpDoc": "55",
          "CRT": "1",
          "itens": [
            {
              "numero": 1,
              "cAtivSN": "01",
              "cClassTrib": "000001",
              "baseCalculo": "950.00",
              "valorImpostoSeletivo": "50.00",
              "pIBSSN": "1.25",
              "pCBSSN": "2.75"
            }
          ]
        }
        """
    corpo = _enviar_json(json_body)
    assert corpo.operacao.data == "2027-03-15"
    assert corpo.operacao.tp_doc == "55"
    assert corpo.operacao.crt == "1"
    _assert_ausente(corpo, "$.oper.tpRegimeIBSCBS")
    obj = _obj(corpo)
    trib = _trib(corpo)
    assert obj.numero == 1
    assert obj.estado is EstadoItemProcessado.CALCULADO
    assert _fmt2(trib.receita_bruta) == "950.00"
    assert trib.tipo_receita == 1
    assert trib.descricao_tipo_receita == "Receita bruta - interna"
    assert _fmt2(trib.base_calculo) == "950.00"
    assert formatar_aliquota(trib.aliquota_ibs) == "1.25"
    assert _fmt2(trib.valor_ibs) == "11.88"
    assert _fmt2(trib.ibs_pendente) == "0.00"
    assert formatar_aliquota(trib.aliquota_cbs) == "2.75"
    assert _fmt2(trib.valor_cbs) == "26.12"
    assert _fmt2(trib.cbs_pendente) == "0.00"
    assert trib.imposto_seletivo is not None
    assert _fmt2(trib.imposto_seletivo.valor) == "50.00"
    assert _fmt2(trib.total_item) == "88.00"
    tot = corpo.total
    assert tot is not None
    assert _fmt2(tot.receita_bruta_total) == "950.00"
    assert _fmt2(tot.base_calculo_total) == "950.00"
    assert _fmt2(tot.ibs_total) == "11.88"
    assert _fmt2(tot.ibs_pendente_total) == "0.00"
    assert _fmt2(tot.cbs_total) == "26.12"
    assert _fmt2(tot.cbs_pendente_total) == "0.00"
    assert _fmt2(tot.imposto_seletivo_total) == "50.00"
    assert _fmt2(tot.total_tributos) == "88.00"


def test_deveManterImpostoSeletivoForaDaReceitaBrutaTambemAPartirDe2028(
    record_xml_attribute,
) -> None:
    _junit(record_xml_attribute, "deveManterImpostoSeletivoForaDaReceitaBrutaTambemAPartirDe2028")
    json_body = """
        {
          "id": "507f1f77bcf86cd799439011",
          "versao": "2.0.0",
          "data": "2028-03-15",
          "tpDoc": "55",
          "CRT": "1",
          "itens": [
            {
              "numero": 1,
              "cAtivSN": "01",
              "cClassTrib": "000001",
              "baseCalculo": "950.00",
              "valorImpostoSeletivo": "50.00",
              "pIBSSN": "1.25",
              "pCBSSN": "2.75"
            }
          ]
        }
        """
    corpo = _enviar_json(json_body)
    assert corpo.operacao.data == "2028-03-15"
    obj = _obj(corpo)
    trib = _trib(corpo)
    assert obj.numero == 1
    assert obj.estado is EstadoItemProcessado.CALCULADO
    assert _fmt2(trib.receita_bruta) == "950.00"
    assert trib.tipo_receita == 1
    assert trib.descricao_tipo_receita == "Receita bruta - interna"
    assert _fmt2(trib.base_calculo) == "950.00"
    assert formatar_aliquota(trib.aliquota_ibs) == "1.25"
    assert _fmt2(trib.valor_ibs) == "11.88"
    assert _fmt2(trib.ibs_pendente) == "0.00"
    assert formatar_aliquota(trib.aliquota_cbs) == "2.75"
    assert _fmt2(trib.valor_cbs) == "26.12"
    assert _fmt2(trib.cbs_pendente) == "0.00"
    assert trib.imposto_seletivo is not None
    assert _fmt2(trib.imposto_seletivo.valor) == "50.00"
    assert _fmt2(trib.total_item) == "88.00"
    tot = corpo.total
    assert tot is not None
    assert _fmt2(tot.receita_bruta_total) == "950.00"
    assert _fmt2(tot.base_calculo_total) == "950.00"
    assert _fmt2(tot.ibs_total) == "11.88"
    assert _fmt2(tot.ibs_pendente_total) == "0.00"
    assert _fmt2(tot.cbs_total) == "26.12"
    assert _fmt2(tot.cbs_pendente_total) == "0.00"
    assert _fmt2(tot.imposto_seletivo_total) == "50.00"
    assert _fmt2(tot.total_tributos) == "88.00"


def test_deveIgnorarCampoDesconhecidoPRedutorEAplicarApenasODeslocamento(
    record_xml_attribute,
) -> None:
    _junit(record_xml_attribute, "deveIgnorarCampoDesconhecidoPRedutorEAplicarApenasODeslocamento")
    json_body = """
        {
          "id": "507f1f77bcf86cd799439011",
          "versao": "2.0.0",
          "data": "2029-06-01",
          "tpDoc": "55",
          "CRT": "1",
          "tpEnteGov": "2",
          "pRedutor": "0.50",
          "itens": [
            {
              "numero": 1,
              "cAtivSN": "01",
              "cClassTrib": "000001",
              "baseCalculo": "1000.00",
              "valorImpostoSeletivo": "0.00",
              "pIBSSN": "1.25",
              "pCBSSN": "2.75"
            }
          ]
        }
        """
    corpo = _enviar_json(json_body)
    assert corpo.operacao.tp_ente_gov == "2"
    obj = _obj(corpo)
    trib = _trib(corpo)
    assert obj.estado is EstadoItemProcessado.CALCULADO
    assert formatar_aliquota(trib.aliquota_ibs) == "1.525"
    assert _fmt2(trib.valor_ibs) == "15.25"
    assert formatar_aliquota(trib.aliquota_cbs) == "2.475"
    assert _fmt2(trib.valor_cbs) == "24.75"


def test_deveRetornar422ParaTpEnteGovInvalido(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "deveRetornar422ParaTpEnteGovInvalido")
    json_body = """
        {
          "id": "abc",
          "versao": "2.0.0",
          "data": "2027-03-15",
          "tpDoc": "55",
          "CRT": "1",
          "tpEnteGov": "7",
          "itens": [
            {
              "numero": 1,
              "cAtivSN": "01",
              "cClassTrib": "000001",
              "baseCalculo": "1000.00",
              "valorImpostoSeletivo": "0.00",
              "pIBSSN": "1.25",
              "pCBSSN": "2.75"
            }
          ]
        }
        """
    assert _codigos_globais(json_body) == ["VSN-024"]


def test_deveRetornarNaoCalculadoParaCAtivSNSemLinhaNoCatalogo(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "deveRetornarNaoCalculadoParaCAtivSNSemLinhaNoCatalogo")
    json_body = """
        {
          "id": "507f1f77bcf86cd799439011",
          "versao": "2.0.0",
          "data": "2027-03-15",
          "tpDoc": "55",
          "CRT": "1",
          "itens": [
            {
              "numero": 1,
              "cAtivSN": "99",
              "cClassTrib": "000001",
              "baseCalculo": "1000.00",
              "valorImpostoSeletivo": "0.00",
              "pIBSSN": "1.25",
              "pCBSSN": "2.75"
            }
          ]
        }
        """
    corpo = _enviar_json(json_body)
    obj = _obj(corpo)
    trib = obj.tributos
    assert obj.estado is EstadoItemProcessado.NAO_CALCULADO
    assert trib is not None
    assert _fmt2(trib.receita_bruta) == "1000.00"
    assert trib.tipo_receita == 1
    assert trib.descricao_tipo_receita == "Receita bruta - interna"
    assert trib.base_calculo is None
    assert trib.valor_ibs is None
    assert trib.valor_cbs is None
    assert trib.imposto_seletivo is None
    tot = corpo.total
    assert tot is not None
    assert _fmt2(tot.receita_bruta_total) == "1000.00"
    assert tot.base_calculo_total is None
    assert tot.ibs_total is None
    assert tot.total_tributos is None


def test_atividadeSemVinculoAlgum_naoCalculadaEmNenhumDocumentoHabilitado(
    record_xml_attribute,
) -> None:
    _junit(record_xml_attribute, "atividadeSemVinculoAlgum_naoCalculadaEmNenhumDocumentoHabilitado")
    for cativ in ("05", "06"):
        for tp_doc in ("55", "65", "91"):
            json_body = f"""
                {{
                  "id": "507f1f77bcf86cd799439011",
                  "versao": "2.0.0",
                  "data": "2027-03-15",
                  "tpDoc": "{tp_doc}",
                  "CRT": "1",
                  "itens": [
                    {{
                      "numero": 1,
                      "cAtivSN": "{cativ}",
                      "cClassTrib": "000001",
                      "baseCalculo": "1000.00",
                      "valorImpostoSeletivo": "0.00",
                      "pIBSSN": "1.25",
                      "pCBSSN": "2.75"
                    }}
                  ]
                }}
                """
            corpo = _enviar_json(json_body)
            obj = _obj(corpo)
            trib = obj.tributos
            assert obj.estado is EstadoItemProcessado.NAO_CALCULADO, (cativ, tp_doc)
            assert trib is not None
            assert _fmt2(trib.receita_bruta) == "1000.00"
            assert trib.valor_ibs is None
            assert obj.erros is None


def test_atividadeVinculadaCalculaNoDocumentoCertoENaoCalculaNoErrado(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "atividadeVinculadaCalculaNoDocumentoCertoENaoCalculaNoErrado")
    operacao_nfse = """
        {
          "id": "507f1f77bcf86cd799439011",
          "versao": "2.0.0",
          "data": "2027-03-15",
          "tpDoc": "91",
          "CRT": "1",
          "itens": [
            {
              "numero": 1,
              "cAtivSN": "07",
              "cClassTrib": "000001",
              "baseCalculo": "1000.00",
              "valorImpostoSeletivo": "0.00",
              "pIBSSN": "1.25",
              "pCBSSN": "2.75"
            }
          ]
        }
        """
    corpo = _enviar_json(operacao_nfse)
    trib = _trib(corpo)
    assert _obj(corpo).estado is EstadoItemProcessado.CALCULADO
    assert _fmt2(trib.valor_ibs) == "12.50"
    assert _fmt2(trib.valor_cbs) == "27.50"

    corpo_nfe = _enviar_json(operacao_nfse.replace('"tpDoc": "91"', '"tpDoc": "55"'))
    obj = _obj(corpo_nfe)
    assert obj.estado is EstadoItemProcessado.NAO_CALCULADO
    assert obj.erros is None


def test_codigo90CalculaEmNfeNfceENfse(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "codigo90CalculaEmNfeNfceENfse")
    for tp_doc in ("55", "65", "91"):
        json_body = f"""
            {{
              "id": "507f1f77bcf86cd799439011",
              "versao": "2.0.0",
              "data": "2027-03-15",
              "tpDoc": "{tp_doc}",
              "CRT": "1",
              "itens": [
                {{
                  "numero": 1,
                  "cAtivSN": "90",
                  "cClassTrib": "410001",
                  "baseCalculo": "1000.00",
                  "valorImpostoSeletivo": "0.00"
                }}
              ]
            }}
            """
        corpo = _enviar_json(json_body)
        obj = _obj(corpo)
        trib = _trib(corpo)
        assert obj.estado is EstadoItemProcessado.CALCULADO, tp_doc
        assert _fmt2(trib.receita_bruta) == "0.00"
        assert trib.tipo_receita == 0


def test_deveResolverTpRBSNPelaLinhaDaCbsQuandoCodigoColideComImpostoSeletivo(
    record_xml_attribute,
) -> None:
    _junit(record_xml_attribute, "deveResolverTpRBSNPelaLinhaDaCbsQuandoCodigoColideComImpostoSeletivo")
    json_body = """
        {
          "id": "507f1f77bcf86cd799439011",
          "versao": "2.0.0",
          "data": "2027-03-15",
          "tpDoc": "55",
          "CRT": "1",
          "itens": [
            {
              "numero": 1,
              "cAtivSN": "01",
              "cClassTrib": "000001",
              "baseCalculo": "1000.00",
              "valorImpostoSeletivo": "0.00",
              "pIBSSN": "1.25",
              "pCBSSN": "2.75"
            }
          ]
        }
        """
    corpo = _enviar_json(json_body)
    obj = _obj(corpo)
    trib = _trib(corpo)
    assert obj.estado is EstadoItemProcessado.CALCULADO
    assert trib.tipo_receita == 1
    assert _fmt2(trib.valor_ibs) == "12.50"
    assert _fmt2(trib.valor_cbs) == "27.50"


def test_deveCalcularCAtivSN90ComTpRBSN0(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "deveCalcularCAtivSN90ComTpRBSN0")
    json_body = """
        {
          "id": "507f1f77bcf86cd799439011",
          "versao": "2.0.0",
          "data": "2027-03-15",
          "tpDoc": "55",
          "CRT": "1",
          "itens": [
            {
              "numero": 1,
              "cAtivSN": "90",
              "cClassTrib": "410001",
              "baseCalculo": "1000.00",
              "valorImpostoSeletivo": "0.00"
            }
          ]
        }
        """
    corpo = _enviar_json(json_body)
    obj = _obj(corpo)
    trib = _trib(corpo)
    assert obj.estado is EstadoItemProcessado.CALCULADO
    assert _fmt2(trib.receita_bruta) == "0.00"
    assert trib.tipo_receita == 0
    assert trib.descricao_tipo_receita == "Não é receita bruta"
    assert _fmt2(trib.base_calculo) == "0.00"
    assert _fmt2(trib.valor_ibs) == "0.00"
    assert _fmt2(trib.valor_cbs) == "0.00"


def test_deveAcumularErroDeValidacaoNoItemEIgnorarNaTotalizacao(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "deveAcumularErroDeValidacaoNoItemEIgnorarNaTotalizacao")
    json_body = """
        {
          "id": "abc",
          "versao": "2.0.0",
          "data": "2027-03-15",
          "tpDoc": "55",
          "CRT": "1",
          "itens": [
            {
              "numero": 1,
              "cAtivSN": "01",
              "cClassTrib": "000001",
              "baseCalculo": "-10.00",
              "valorImpostoSeletivo": "0.00",
              "pIBSSN": "1.25",
              "pCBSSN": "2.75"
            },
            {
              "numero": 2,
              "cAtivSN": "01",
              "cClassTrib": "000001",
              "baseCalculo": "1000.00",
              "valorImpostoSeletivo": "0.00",
              "pIBSSN": "1.25",
              "pCBSSN": "2.75"
            },
            {
              "numero": 3,
              "cAtivSN": "99",
              "cClassTrib": "000001",
              "baseCalculo": "500.00",
              "valorImpostoSeletivo": "0.00"
            }
          ]
        }
        """
    corpo = _enviar_json(json_body)
    o0, o1, o2 = corpo.objetos[0], corpo.objetos[1], corpo.objetos[2]
    assert o0.numero == 1
    assert o0.estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    assert o0.erros is not None
    assert o0.erros[0].code == "VSN-002"
    assert o0.tributos is None
    assert o1.estado is EstadoItemProcessado.CALCULADO
    assert o2.estado is EstadoItemProcessado.NAO_CALCULADO
    tot = corpo.total
    assert tot is not None
    assert _fmt2(tot.receita_bruta_total) == "1500.00"
    assert _fmt2(tot.base_calculo_total) == "1000.00"
    assert _fmt2(tot.ibs_total) == "12.50"
    assert _fmt2(tot.total_tributos) == "40.00"


def test_deveRetornarNaoImplementadoParaCClassTribComTratamentoSemImplementacao(
    record_xml_attribute,
) -> None:
    _junit(record_xml_attribute, "deveRetornarNaoImplementadoParaCClassTribComTratamentoSemImplementacao")
    json_body = """
        {
          "id": "507f1f77bcf86cd799439011",
          "versao": "2.0.0",
          "data": "2027-03-15",
          "tpDoc": "55",
          "CRT": "1",
          "itens": [
            {
              "numero": 1,
              "cAtivSN": "01",
              "cClassTrib": "620001",
              "baseCalculo": "1000.00",
              "valorImpostoSeletivo": "0.00",
              "pIBSSN": "1.25",
              "pCBSSN": "2.75"
            }
          ]
        }
        """
    corpo = _enviar_json(json_body)
    obj = _obj(corpo)
    assert obj.numero == 1
    assert obj.estado is EstadoItemProcessado.NAO_IMPLEMENTADO
    assert obj.erros is not None
    assert len(obj.erros) == 1
    assert obj.erros[0].code == "VSN-027"
    assert obj.erros[0].pointer == "#/itens/0/cClassTrib"
    assert uri_erro(BASE_URL, "VSN-027").endswith("/calculadora/observabilidade/simples-nacional/erros?codigo=VSN-027")
    assert obj.tributos is None
    assert corpo.total is None


def test_naoImplementadoTemPrioridadeSobreValidacoesDoItemENaoAfetaOsDemais(
    record_xml_attribute,
) -> None:
    _junit(record_xml_attribute, "naoImplementadoTemPrioridadeSobreValidacoesDoItemENaoAfetaOsDemais")
    json_body = """
        {
          "id": "507f1f77bcf86cd799439011",
          "versao": "2.0.0",
          "data": "2027-03-15",
          "tpDoc": "55",
          "CRT": "1",
          "itens": [
            {
              "numero": 1,
              "cAtivSN": "01",
              "cClassTrib": "620001",
              "baseCalculo": "-10.00",
              "valorImpostoSeletivo": "0.00"
            },
            {
              "numero": 2,
              "cAtivSN": "01",
              "cClassTrib": "000001",
              "baseCalculo": "1000.00",
              "valorImpostoSeletivo": "0.00",
              "pIBSSN": "1.25",
              "pCBSSN": "2.75"
            },
            {
              "numero": 3,
              "cAtivSN": "99",
              "cClassTrib": "800001",
              "baseCalculo": "500.00",
              "valorImpostoSeletivo": "0.00"
            }
          ]
        }
        """
    corpo = _enviar_json(json_body)
    o0, o1, o2 = corpo.objetos[0], corpo.objetos[1], corpo.objetos[2]
    assert o0.estado is EstadoItemProcessado.NAO_IMPLEMENTADO
    assert o0.erros is not None and len(o0.erros) == 1 and o0.erros[0].code == "VSN-027"
    assert o0.tributos is None
    assert o1.estado is EstadoItemProcessado.CALCULADO
    assert o2.estado is EstadoItemProcessado.NAO_IMPLEMENTADO
    assert o2.erros is not None
    assert o2.erros[0].code == "VSN-027"
    assert o2.erros[0].pointer == "#/itens/2/cClassTrib"
    tot = corpo.total
    assert tot is not None
    assert _fmt2(tot.receita_bruta_total) == "1000.00"
    assert _fmt2(tot.base_calculo_total) == "1000.00"
    assert _fmt2(tot.ibs_total) == "12.50"
    assert _fmt2(tot.cbs_total) == "27.50"
    assert _fmt2(tot.total_tributos) == "40.00"


def test_tributacaoEmDocumentoEspecificoCalculaEmNfseSemVsn027(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "tributacaoEmDocumentoEspecificoCalculaEmNfseSemVsn027")
    json_body = """
        {
          "id": "507f1f77bcf86cd799439011",
          "versao": "2.0.0",
          "data": "2027-03-15",
          "tpDoc": "91",
          "CRT": "1",
          "itens": [
            {
              "numero": 1,
              "cAtivSN": "07",
              "cClassTrib": "820001",
              "baseCalculo": "1000.00",
              "valorImpostoSeletivo": "0.00",
              "pIBSSN": "1.25",
              "pCBSSN": "2.75"
            }
          ]
        }
        """
    corpo = _enviar_json(json_body)
    obj = _obj(corpo)
    trib = _trib(corpo)
    assert obj.estado is EstadoItemProcessado.CALCULADO
    assert obj.erros is None
    assert _fmt2(trib.receita_bruta) == "1000.00"
    assert trib.tipo_receita == 9
    assert trib.descricao_tipo_receita == "Fornecimento incompatível com SN"
    assert _fmt2(trib.base_calculo) == "0.00"
    assert _fmt2(trib.valor_ibs) == "0.00"
    assert _fmt2(trib.valor_cbs) == "0.00"
    tot = corpo.total
    assert tot is not None
    assert _fmt2(tot.receita_bruta_total) == "1000.00"
    assert _fmt2(tot.base_calculo_total) == "0.00"
    assert _fmt2(tot.ibs_total) == "0.00"
    assert _fmt2(tot.cbs_total) == "0.00"
    assert _fmt2(tot.total_tributos) == "0.00"


def test_naoImplementadoTambemEmNfse(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "naoImplementadoTambemEmNfse")
    json_body = """
        {
          "id": "507f1f77bcf86cd799439011",
          "versao": "2.0.0",
          "data": "2027-03-15",
          "tpDoc": "91",
          "CRT": "1",
          "itens": [
            {
              "numero": 1,
              "cAtivSN": "07",
              "cClassTrib": "800001",
              "baseCalculo": "1000.00",
              "valorImpostoSeletivo": "0.00",
              "pIBSSN": "1.25",
              "pCBSSN": "2.75"
            }
          ]
        }
        """
    corpo = _enviar_json(json_body)
    obj = _obj(corpo)
    assert obj.estado is EstadoItemProcessado.NAO_IMPLEMENTADO
    assert obj.erros is not None
    assert obj.erros[0].code == "VSN-027"
    assert corpo.total is None


def test_cClassTribEncerradoEm2026NaoEhNaoImplementado_ehForaDeVigencia(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "cClassTribEncerradoEm2026NaoEhNaoImplementado_ehForaDeVigencia")
    json_body = """
        {
          "id": "507f1f77bcf86cd799439011",
          "versao": "2.0.0",
          "data": "2027-03-15",
          "tpDoc": "55",
          "CRT": "1",
          "itens": [
            {
              "numero": 1,
              "cAtivSN": "01",
              "cClassTrib": "220001",
              "baseCalculo": "1000.00",
              "valorImpostoSeletivo": "0.00",
              "pIBSSN": "1.25",
              "pCBSSN": "2.75"
            }
          ]
        }
        """
    corpo = _enviar_json(json_body)
    obj = _obj(corpo)
    assert obj.estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    assert obj.erros is not None
    assert obj.erros[0].code == "VSN-021"


def test_deveRetornar422ParaRegimeRegular(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "deveRetornar422ParaRegimeRegular")
    json_body = """
        {
          "id": "abc",
          "versao": "2.0.0",
          "data": "2027-03-15",
          "tpDoc": "55",
          "CRT": "1",
          "tpRegimeIBSCBS": "1",
          "itens": [
            {
              "numero": 1,
              "cAtivSN": "01",
              "cClassTrib": "000001",
              "baseCalculo": "1000.00",
              "valorImpostoSeletivo": "0.00",
              "pIBSSN": "1.25",
              "pCBSSN": "2.75"
            }
          ]
        }
        """
    assert _codigos_globais(json_body) == ["VSN-019"]


def test_deveRetornar422ParaTpDocNaoSuportado(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "deveRetornar422ParaTpDocNaoSuportado")
    for tp_doc in ("97", "83"):
        json_body = f"""
            {{
              "id": "abc",
              "versao": "2.0.0",
              "data": "2027-03-15",
              "tpDoc": "{tp_doc}",
              "CRT": "1",
              "itens": [
                {{
                  "numero": 1,
                  "cClassTrib": "000001",
                  "baseCalculo": "1000.00",
                  "valorImpostoSeletivo": "0.00"
                }}
              ]
            }}
            """
        assert _codigos_globais(json_body) == ["VSN-015"], tp_doc


def test_deveRetornar422ParaTpDocSemTratamento(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "deveRetornar422ParaTpDocSemTratamento")
    for tp_doc in ("77", "94", "95", "96"):
        json_body = f"""
            {{
              "id": "abc",
              "versao": "2.0.0",
              "data": "2027-03-15",
              "tpDoc": "{tp_doc}",
              "CRT": "1",
              "itens": [
                {{
                  "numero": 1,
                  "cAtivSN": "01",
                  "cClassTrib": "000001",
                  "baseCalculo": "1000.00",
                  "valorImpostoSeletivo": "0.00",
                  "pIBSSN": "1.25",
                  "pCBSSN": "2.75"
                }}
              ]
            }}
            """
        with pytest.raises(ErrosCalculoException) as exc:
            _enviar_json(json_body)
        erros = exc.value.erros
        assert erros[0].code == "VSN-015", tp_doc
        assert erros[0].pointer == "#/tpDoc"


def test_deveRetornar422QuandoListaDeItensVazia(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "deveRetornar422QuandoListaDeItensVazia")
    json_body = """
        {
          "id": "abc",
          "versao": "2.0.0",
          "data": "2027-03-15",
          "tpDoc": "55",
          "CRT": "1",
          "itens": []
        }
        """
    assert _codigos_globais(json_body) == ["VSN-011"]


def test_deveRetornar422ParaDataAnteriorATodaVigencia(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "deveRetornar422ParaDataAnteriorATodaVigencia")
    for data in ("2025-06-01", "2025-12-31", "2026-06-01", "2026-12-31"):
        json_body = f"""
            {{
              "id": "abc",
              "versao": "2.0.0",
              "data": "{data}",
              "tpDoc": "55",
              "CRT": "1",
              "itens": [
                {{
                  "numero": 1,
                  "cAtivSN": "01",
                  "cClassTrib": "000001",
                  "baseCalculo": "1000.00",
                  "valorImpostoSeletivo": "0.00",
                  "pIBSSN": "1.25",
                  "pCBSSN": "2.75"
                }}
              ]
            }}
            """
        with pytest.raises(ErrosCalculoException) as exc:
            _enviar_json(json_body)
        erros = exc.value.erros
        assert erros[0].code == "VSN-015", data
        assert erros[0].pointer == "#/tpDoc"


# ─── Precisão ──────────────────────────────────────────────────────────────


def test_aliquotaIntegralNaEntrada_eUsadaComTodasAsCasas_eApresentadaCom4(
    record_xml_attribute,
) -> None:
    _junit(record_xml_attribute, "aliquotaIntegralNaEntrada_eUsadaComTodasAsCasas_eApresentadaCom4")
    json_body = _operacao_json(
        "2027-04-15",
        _item_json(
            1,
            "987654.32",
            "0.00",
            "0.01867380622521988789135487",
            "1.6839379378389463610262954",
        ),
    )
    corpo = _enviar_json(json_body)
    obj = _obj(corpo)
    trib = _trib(corpo)
    assert obj.estado is EstadoItemProcessado.CALCULADO
    assert formatar_aliquota(trib.aliquota_cbs) == "1.6839"
    assert _fmt2(trib.valor_cbs) == "16631.49"
    assert formatar_aliquota(trib.aliquota_ibs) == "0.0187"
    assert _fmt2(trib.valor_ibs) == "184.43"


def test_totaisSaoASomaDosValoresFiscaisDosItens(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "totaisSaoASomaDosValoresFiscaisDosItens")
    itens = ", ".join(
        [
            _item_json(1, "160.40", "0.00", "1.25", "2.75"),
            _item_json(2, "160.40", "0.00", "1.25", "2.75"),
            _item_json(3, "100.01", "0.00", "1.25", "2.75"),
        ]
    )
    corpo = _enviar_json(_operacao_json("2027-04-15", itens))
    assert _fmt2(_trib(corpo, 0).valor_ibs) == "2.00"
    assert _fmt2(_trib(corpo, 0).valor_cbs) == "4.41"
    assert _fmt2(_trib(corpo, 0).total_item) == "6.41"
    assert _fmt2(_trib(corpo, 2).total_item) == "4.00"
    tot = corpo.total
    assert tot is not None
    assert _fmt2(tot.ibs_total) == "5.25"
    assert _fmt2(tot.cbs_total) == "11.57"
    assert _fmt2(tot.total_tributos) == "16.82"


def test_entradaForaDoFormato_eErroDeItem_semConverterNotacaoCientifica(
    record_xml_attribute,
) -> None:
    _junit(record_xml_attribute, "entradaForaDoFormato_eErroDeItem_semConverterNotacaoCientifica")
    ones34 = "1" * 34
    ones35 = "1" * 35
    itens = ", ".join(
        [
            _item_json(1, "1000.00", "0.00", "1.25", "1E+100000000"),
            _item_json(2, "1E+100000000", "0.00", "1.25", "2.75"),
            _item_json(3, "1000.005", "0.00", "1.25", "2.75"),
            _item_json(4, "1000.00", "0.001", "1.25", "2.75"),
            _item_json(5, "1000.00", "0.00", "1234.5", "2.75"),
            _item_json(6, "1000.00", "0.00", "1.25", "-2.75"),
            _item_json(7, "1000.00", "0.00", "1.25", f"2.{ones34}"),
            _item_json(8, "1000.00", "0.00", "1.25", f"2.{ones35}"),
        ]
    )
    corpo = _enviar_json(_operacao_json("2027-04-15", itens))
    esperados = {
        0: ("VSN-005", "sem notação científica"),
        1: ("VSN-002", None),
        2: ("VSN-002", None),
        3: ("VSN-003", None),
        4: ("VSN-007", None),
        5: ("VSN-005", "não pode ser negativo"),
        6: None,
        7: ("VSN-005", None),
    }
    for idx, spec in esperados.items():
        obj = corpo.objetos[idx]
        if spec is None:
            assert obj.estado is EstadoItemProcessado.CALCULADO, idx
            continue
        code, fragment = spec
        assert obj.erros is not None
        assert obj.erros[0].code == code, idx
        if fragment:
            assert fragment in obj.erros[0].detail, idx