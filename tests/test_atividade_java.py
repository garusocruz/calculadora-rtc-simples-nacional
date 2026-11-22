"""Espelho de ``Teste_AtividadeSimplesService`` (pin a926d5a7), chamada de serviço sem Spring."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from calculadora_rtc_simples_nacional import atividade
from calculadora_rtc_simples_nacional.atividade import ErroConsultaAtividade, ModoFatorR
from calculadora_rtc_simples_nacional.consumo import AtividadeSimplesService
from calculadora_rtc_simples_nacional.parametro import ClassificacaoTributaria, TipoReceitaBruta, VinculoTpDocAtividade

_CLASSNAME = "br.gov.serpro.rtc.testesunitarios.atividadesimples.Teste_AtividadeSimplesService"
DATA = date(2027, 3, 15)


def _junit(record_xml_attribute, name: str) -> None:
    record_xml_attribute("classname", _CLASSNAME)
    record_xml_attribute("name", name)


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


def _vinculo(atividade_id: int, tp_doc: int) -> VinculoTpDocAtividade:
    return VinculoTpDocAtividade(atividade_id, tp_doc)


def _tipo_receita(tp_rbsn: int, vedado_nao_tributavel: bool) -> TipoReceitaBruta:
    return TipoReceitaBruta(
        tp_rbsn, "R", True, True, Decimal(1), False, True, vedado_nao_tributavel, None
    )


class TesteAtividadeSimplesServiceJava:
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

    def _stub_class_trib(self, codigo: str, tp_rbsn: int, vedado_nao_tributavel: bool):
        self.parametro.buscar_tipo_receita_bruta = MagicMock(
            return_value=_tipo_receita(tp_rbsn, vedado_nao_tributavel)
        )
        return patch.object(
            atividade,
            "buscar_classificacoes_vigentes",
            return_value=[ClassificacaoTributaria(1, codigo, tp_rbsn)],
        )

    def test_tpDocEmBrancoEquivaleAAusente(self, record_xml_attribute) -> None:
        _junit(record_xml_attribute, "tpDocEmBrancoEquivaleAAusente")
        with patch.object(atividade, "buscar_vinculos_tpdoc_vigentes", return_value=[]):
            vinculada = self.servico.listar(DATA, None, "  ", None)[0]
        assert vinculada.admissivel_no_documento is None

    def test_atividadeComVinculoParaOTpDoc_admissivelEDisponivelPelosAnexos(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "atividadeComVinculoParaOTpDoc_admissivelEDisponivelPelosAnexos")
        with patch.object(
            atividade,
            "buscar_vinculos_tpdoc_vigentes",
            return_value=[_vinculo(1, 55), _vinculo(1, 65)],
        ):
            vinculada = self.servico.listar(DATA, None, "55", None)[0]
        assert vinculada.admissivel_no_documento is True
        assert vinculada.disponivel is True
        assert vinculada.tp_docs_admissiveis == ("55", "65")

    def test_atividadeSemVinculoParaOTpDoc_inadmissivelEIndisponivelMesmoComAnexosOk(
        self, record_xml_attribute
    ) -> None:
        _junit(
            record_xml_attribute,
            "atividadeSemVinculoParaOTpDoc_inadmissivelEIndisponivelMesmoComAnexosOk",
        )
        with patch.object(
            atividade,
            "buscar_vinculos_tpdoc_vigentes",
            return_value=[_vinculo(1, 55), _vinculo(1, 65)],
        ):
            vinculada = self.servico.listar(DATA, None, "91", None)[0]
        assert vinculada.admissivel_no_documento is False
        assert vinculada.disponivel is False
        assert vinculada.anexos_faltantes == ()
        assert vinculada.modo_fator_r is ModoFatorR.NAO_APLICAVEL

    def test_atividadeSemVinculoAlgum_inadmissivelEmQualquerTpDoc(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "atividadeSemVinculoAlgum_inadmissivelEmQualquerTpDoc")
        with patch.object(
            atividade,
            "buscar_vinculos_tpdoc_vigentes",
            return_value=[_vinculo(15, 55)],
        ):
            sem_vinculo = self.servico.listar(DATA, None, "57", None)[0]
        assert sem_vinculo.tp_docs_admissiveis == ()
        assert sem_vinculo.admissivel_no_documento is False
        assert sem_vinculo.disponivel is False

    def test_doisMotivosSimultaneos_inadmissivelEComAnexosFaltantes(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "doisMotivosSimultaneos_inadmissivelEComAnexosFaltantes")
        with patch.object(
            atividade,
            "buscar_vinculos_tpdoc_vigentes",
            return_value=[_vinculo(1, 55)],
        ):
            vinculada = self.servico.listar(DATA, {"II"}, "91", None)[0]
        assert vinculada.admissivel_no_documento is False
        assert vinculada.anexos_faltantes == ("I",)
        assert vinculada.disponivel is False

    def test_vinculoForaDeVigenciaIgnorado_atividadeFicaSemDocumentoAlgum(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "vinculoForaDeVigenciaIgnorado_atividadeFicaSemDocumentoAlgum")
        with patch.object(atividade, "buscar_vinculos_tpdoc_vigentes", return_value=[]):
            ativ = self.servico.listar(DATA, None, "91", None)[0]
        assert ativ.tp_docs_admissiveis == ()
        assert ativ.admissivel_no_documento is False
        assert ativ.disponivel is False

    def test_tpDocMalFormado_retorna400(self, record_xml_attribute) -> None:
        _junit(record_xml_attribute, "tpDocMalFormado_retorna400")
        with pytest.raises(ErroConsultaAtividade):
            self.servico.listar(DATA, None, "abc", None)

    def test_tpDocSemLinhaNaTipoDfe_retorna400(self, record_xml_attribute) -> None:
        _junit(record_xml_attribute, "tpDocSemLinhaNaTipoDfe_retorna400")
        with pytest.raises(ErroConsultaAtividade):
            self.servico.listar(DATA, None, "99", None)

    def test_tpDocComZeroAEsquerda_canonizadoAntesDaComparacao(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "tpDocComZeroAEsquerda_canonizadoAntesDaComparacao")
        with patch.object(
            atividade,
            "buscar_vinculos_tpdoc_vigentes",
            return_value=[_vinculo(1, 55)],
        ):
            vinculada = self.servico.listar(DATA, None, "055", None)[0]
        assert vinculada.admissivel_no_documento is True

    def test_semCClassTrib_naoResolveTpRBSNENaoDevolveCompativelComClassTrib(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "semCClassTrib_naoResolveTpRBSNENaoDevolveCompativelComClassTrib")
        mock_class = MagicMock(return_value=[])
        with (
            patch.object(atividade, "buscar_vinculos_tpdoc_vigentes", return_value=[]),
            patch.object(atividade, "buscar_classificacoes_vigentes", mock_class),
        ):
            atividades = self.servico.listar(DATA, None, None, None)
        assert atividades[0].compativel_com_class_trib is None
        assert atividades[1].compativel_com_class_trib is None
        mock_class.assert_not_called()

    def test_cClassTribVedadoParaNaoTributavel_marcaSomenteAAtividadeNaoTributavel(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "cClassTribVedadoParaNaoTributavel_marcaSomenteAAtividadeNaoTributavel")
        with (
            patch.object(atividade, "buscar_vinculos_tpdoc_vigentes", return_value=[]),
            self._stub_class_trib("000001", 1, True),
        ):
            atividades = self.servico.listar(DATA, None, None, "000001")
        comum = atividades[0]
        assert comum.compativel_com_class_trib is True
        assert comum.disponivel is True
        nao_tributavel = atividades[1]
        assert nao_tributavel.compativel_com_class_trib is False
        assert nao_tributavel.disponivel is False
        assert nao_tributavel.anexos_faltantes == ()

    def test_cClassTribNaoVedado_naoMarcaAtividadeAlguma(self, record_xml_attribute) -> None:
        _junit(record_xml_attribute, "cClassTribNaoVedado_naoMarcaAtividadeAlguma")
        with (
            patch.object(atividade, "buscar_vinculos_tpdoc_vigentes", return_value=[]),
            self._stub_class_trib("410001", 0, False),
        ):
            atividades = self.servico.listar(DATA, None, None, "410001")
        assert atividades[0].compativel_com_class_trib is True
        assert atividades[1].compativel_com_class_trib is True

    def test_cClassTribDesconhecidoOuForaDeVigencia_retorna400(self, record_xml_attribute) -> None:
        _junit(record_xml_attribute, "cClassTribDesconhecidoOuForaDeVigencia_retorna400")
        with patch.object(atividade, "buscar_classificacoes_vigentes", return_value=[]):
            with pytest.raises(ErroConsultaAtividade):
                self.servico.listar(DATA, None, None, "999999")

    def test_cClassTribSemEfeitoVigenteDoTpRBSN_retorna400(self, record_xml_attribute) -> None:
        _junit(record_xml_attribute, "cClassTribSemEfeitoVigenteDoTpRBSN_retorna400")
        self.parametro.buscar_tipo_receita_bruta = MagicMock(return_value=None)
        with patch.object(
            atividade,
            "buscar_classificacoes_vigentes",
            return_value=[ClassificacaoTributaria(1, "000001", 1)],
        ):
            with pytest.raises(ErroConsultaAtividade):
                self.servico.listar(DATA, None, None, "000001")

    def test_motivosDeDocumentoEDeClassificacaoCombinados(self, record_xml_attribute) -> None:
        _junit(record_xml_attribute, "motivosDeDocumentoEDeClassificacaoCombinados")
        with (
            patch.object(
                atividade,
                "buscar_vinculos_tpdoc_vigentes",
                return_value=[_vinculo(1, 55)],
            ),
            self._stub_class_trib("000001", 1, True),
        ):
            nao_tributavel = self.servico.listar(DATA, None, "55", "000001")[1]
        assert nao_tributavel.admissivel_no_documento is False
        assert nao_tributavel.compativel_com_class_trib is False
        assert nao_tributavel.disponivel is False