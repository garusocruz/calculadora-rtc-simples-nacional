"""Consumo Python ↔ testes de serviço Java (Simples, sem HTTP)."""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from calculadora_rtc_simples_nacional import atividade
from calculadora_rtc_simples_nacional.consumo import (
    AtividadeSimplesService,
    SimplesNacionalNaoAssistidoService,
    SimplesNacionalObservabilidadeService,
)
from calculadora_rtc_simples_nacional.nao_assistido import OperacaoNaoAssistida
from calculadora_rtc_simples_nacional.observabilidade import ItemSimplesClassico, OperacaoSimplesClassica
from calculadora_rtc_simples_nacional.parametro import banco_disponivel, ClassificacaoTributaria
from calculadora_rtc_simples_nacional.processador import EstadoItemProcessado
from calculadora_rtc_simples_nacional.unificado import ErrosCalculoException

os.environ.setdefault(
    "CALC_DB",
    "/home/garusotec/projects/lynko/libs/calculadora-rtc-simples-nacional/.cache/oficial/java/calculadora/db/calculadora-pro.db",
)

_FQCN_OBS = "br.gov.serpro.rtc.testesunitarios.simplesnacional.Teste_SimplesNacionalObservabilidadeService"
_FQCN_ATIV = "br.gov.serpro.rtc.testesunitarios.atividadesimples.Teste_AtividadeSimplesService"
_FQCN_NAO = "br.gov.serpro.rtc.api.simplesnacional.service.SimplesNacionalNaoAssistidoService"

BASE_URL = "http://localhost/api"
DATA_PADRAO = "2027-03-15"
DATA_CATALOGO = date(2027, 1, 1)
DATA = date(2027, 3, 15)

pytestmark_db = pytest.mark.skipif(not banco_disponivel(), reason="calculadora-pro.db ausente")


def _java(record_xml_attribute, fqcn: str, method: str) -> None:
    record_xml_attribute("classname", fqcn)
    record_xml_attribute("name", method)


def _item(**kwargs) -> ItemSimplesClassico:
    return ItemSimplesClassico(
        kwargs.get("numero", 1),
        kwargs.get("cativ_sn", "01"),
        kwargs.get("class_trib", "000001"),
        kwargs.get("nbs"),
        kwargs.get("ncm"),
        kwargs.get("base_calculo", "1000.00"),
        kwargs.get("valor_is", "0.00"),
        kwargs.get("pis", "1.25"),
        kwargs.get("pcbs", "2.75"),
    )


def _operacao(**kwargs) -> OperacaoSimplesClassica:
    return OperacaoSimplesClassica(
        kwargs.get("id", "507f1f77bcf86cd799439011"),
        kwargs.get("versao", "2.0.0"),
        kwargs.get("data", DATA_PADRAO),
        kwargs.get("tp_doc", "55"),
        kwargs.get("crt", "1"),
        kwargs.get("tp_regime_ibscbs"),
        kwargs.get("tp_ente_gov"),
        list(kwargs.get("itens") or [_item()]),
    )


def _ativ(id_: int, ordem: int, codigo: str, anexo_sem: str | None) -> atividade._AtividadeVigente:
    return atividade._AtividadeVigente(
        id_,
        ordem,
        f"Atividade {codigo}",
        codigo,
        anexo_sem,
        None,
        anexo_sem or "Não tributável",
        anexo_sem or "Não tributável",
        anexo_sem is None,
    )


# ─── SimplesNacionalObservabilidadeService (integração com banco) ──────────────


@pytestmark_db
def test_caso20_atividadeComVinculoParaOTpDoc_calculadoNormalmente(record_xml_attribute) -> None:
    _java(record_xml_attribute, _FQCN_OBS, "caso20_atividadeComVinculoParaOTpDoc_calculadoNormalmente")
    resultado = SimplesNacionalObservabilidadeService().processarOperacao(_operacao(), BASE_URL)
    objeto = resultado.objetos[0]
    assert objeto.estado is EstadoItemProcessado.CALCULADO
    assert Decimal("12.50") == objeto.tributos.valor_ibs
    assert Decimal("27.50") == objeto.tributos.valor_cbs


@pytestmark_db
def test_caso18_cAtivSNAusente_naoCalculadoEContribuiSoParaVRBSNtot(record_xml_attribute) -> None:
    _java(record_xml_attribute, _FQCN_OBS, "caso18_cAtivSNAusente_naoCalculadoEContribuiSoParaVRBSNtot")
    resultado = SimplesNacionalObservabilidadeService().processarOperacao(
        _operacao(itens=[_item(cativ_sn=None)]), BASE_URL
    )
    objeto = resultado.objetos[0]
    assert objeto.estado is EstadoItemProcessado.NAO_CALCULADO
    assert objeto.tributos is not None
    assert Decimal("1000.00") == objeto.tributos.receita_bruta
    assert objeto.tributos.valor_ibs is None
    assert resultado.total is not None
    assert Decimal("1000.00") == resultado.total.receita_bruta_total
    assert resultado.total.ibs_total is None


# ─── AtividadeSimplesService (espelho unitário com mocks) ─────────────────────


def _vinculo(atividade_id: int, tp_doc: int):
    from calculadora_rtc_simples_nacional.parametro import VinculoTpDocAtividade

    return VinculoTpDocAtividade(atividade_id, tp_doc)


class TesteAtividadeSimplesServiceConsumo:
    def setup_method(self) -> None:
        self.parametro = MagicMock()
        self.servico = AtividadeSimplesService(self.parametro)
        self.patcher_vigentes = patch.object(
            atividade,
            "_buscar_vigentes",
            return_value=[_ativ(1, 1, "01", "I"), _ativ(15, 15, "90", None)],
        )
        self.patcher_contar = patch.object(
            atividade,
            "_contar_tipos_dfe_por_tipo",
            side_effect=lambda t: 1 if t in (55, 65, 91, 57) else 0,
        )
        self.patcher_vigentes.start()
        self.patcher_contar.start()

    def teardown_method(self) -> None:
        self.patcher_vigentes.stop()
        self.patcher_contar.stop()

    def test_semTpDoc_naoValidaNaTipoDfeENaoDevolveAdmissivelNoDocumento(
        self, record_xml_attribute
    ) -> None:
        _java(record_xml_attribute, _FQCN_ATIV, "semTpDoc_naoValidaNaTipoDfeENaoDevolveAdmissivelNoDocumento")
        with patch.object(
            atividade,
            "buscar_vinculos_tpdoc_vigentes",
            return_value=[_vinculo(1, 55), _vinculo(1, 65)],
        ):
            atividades = self.servico.listar(DATA, None, None, None)
        assert atividades[0].tp_docs_admissiveis == ("55", "65")
        assert atividades[0].admissivel_no_documento is None

    def test_buscarPorCodigoRecebeOMesmoTratamentoDosFiltros(self, record_xml_attribute) -> None:
        _java(record_xml_attribute, _FQCN_ATIV, "buscarPorCodigoRecebeOMesmoTratamentoDosFiltros")
        from calculadora_rtc_simples_nacional.parametro import TipoReceitaBruta

        self.parametro.buscar_classificacoes_vigentes = MagicMock(
            return_value=[ClassificacaoTributaria(1, "000001", 1)]
        )
        self.parametro.buscar_tipo_receita_bruta = MagicMock(
            return_value=TipoReceitaBruta(
                1, "R", True, True, Decimal(1), False, True, False, None
            )
        )
        with patch.object(
            atividade,
            "buscar_vinculos_tpdoc_vigentes",
            return_value=[_vinculo(1, 55)],
        ):
            encontrada = self.servico.buscarPorCodigo("01", DATA, "55", "000001")
        assert encontrada is not None
        assert encontrada.codigo == "01"


# ─── SimplesNacionalNaoAssistidoService ───────────────────────────────────────


def test_operacaoSemId_rejeitada(record_xml_attribute) -> None:
    _java(record_xml_attribute, _FQCN_NAO, "operacaoSemId")
    with pytest.raises(ErrosCalculoException) as exc:
        SimplesNacionalNaoAssistidoService().processarOperacao(OperacaoNaoAssistida())
    assert exc.value.erros[0].code == "VSN-013"



