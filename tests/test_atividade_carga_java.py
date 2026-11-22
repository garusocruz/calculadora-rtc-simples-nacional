"""Espelho de ``AtividadeSimplesControllerTest`` (pin a926d5a7) — fachada de serviço, carga real, sem HTTP."""

from __future__ import annotations

import os
from datetime import date

import pytest

os.environ.setdefault(
    "CALC_DB",
    "/home/garusotec/projects/lynko/libs/calculadora-rtc-regime-regular/.cache/oficial/java/calculadora/db/calculadora-pro.db",
)

from calculadora_rtc_simples_nacional.atividade import ErroConsultaAtividade, ModoFatorR
from calculadora_rtc_simples_nacional.consumo import (
    AtividadeSimplesService,
    SimplesNacionalObservabilidadeService,
)
from calculadora_rtc_simples_nacional.observabilidade import ItemSimplesClassico, OperacaoSimplesClassica
from calculadora_rtc_simples_nacional.parametro import banco_disponivel
from calculadora_rtc_simples_nacional.processador import EstadoItemProcessado

DATA_PADRAO = date(2027, 1, 1)
_BASE_URL = "http://localhost/api"

_SVC_ATIV = AtividadeSimplesService()
_SVC_CALC = SimplesNacionalObservabilidadeService()

pytestmark = pytest.mark.skipif(not banco_disponivel(), reason="calculadora-pro.db ausente")


def _idx(lista: list, codigo: str):
    return next(a for a in lista if a.codigo == codigo)


def _map(lista: list):
    return {a.codigo: a for a in lista}


_FQCN_ATIVIDADE = (
    "br.gov.serpro.rtc.testesintegracao.atividadesimples.AtividadeSimplesControllerTest"
)


class TestAtividadeSimplesControllerJava:
  @pytest.fixture(autouse=True)
  def _junit(self, request, record_xml_attribute):
      nome = request.node.name.split("[")[0].removeprefix("test_")
      record_xml_attribute("classname", _FQCN_ATIVIDADE)
      record_xml_attribute("name", nome)

  def test_deveListarAsQuinzeAtividadesSemFiltro(self) -> None:
      lista = _SVC_ATIV.listar(DATA_PADRAO)
      assert len(lista) == 15
      a01 = lista[0]
      assert a01.codigo == "01"
      assert a01.ordem == 1
      assert a01.anexo_sem_fator_r == "I"
      assert a01.anexo_com_fator_r is None
      assert not a01.sujeita_fator_r
      assert a01.rotulo_anexo == "I"
      assert a01.rotulo_curto_anexo == "I"
      assert a01.disponivel
      assert a01.anexos_faltantes == ()
      assert a01.modo_fator_r is ModoFatorR.NAO_APLICAVEL
      assert lista[1].rotulo_anexo == "I, menos ICMS"
      assert lista[1].rotulo_curto_anexo == "I"
      a09 = lista[8]
      assert a09.codigo == "09"
      assert a09.disponivel
      assert a09.anexos_faltantes == ()
      assert a09.modo_fator_r is ModoFatorR.OPCIONAL
      assert lista[13].codigo == "14"
      assert lista[13].ordem == 14
      a90 = lista[14]
      assert a90.codigo == "90"
      assert a90.anexo_sem_fator_r is None
      assert a90.anexo_com_fator_r is None
      assert not a90.sujeita_fator_r
      assert a90.disponivel
      assert a90.anexos_faltantes == ()
      assert a90.modo_fator_r is ModoFatorR.NAO_APLICAVEL

  def test_deveMarcarDisponibilidadeComFiltroDeAnexosIeV(self) -> None:
      lista = _SVC_ATIV.listar(DATA_PADRAO, {"I", "V"})
      assert len(lista) == 15
      a02 = _idx(lista, "02")
      assert a02.disponivel
      assert a02.anexos_faltantes == ()
      assert a02.modo_fator_r is ModoFatorR.NAO_APLICAVEL
      a09 = _idx(lista, "09")
      assert a09.disponivel
      assert a09.anexos_faltantes == ("III",)
      assert a09.modo_fator_r is ModoFatorR.INDISPONIVEL
      a05 = _idx(lista, "05")
      assert not a05.disponivel
      assert a05.anexos_faltantes == ("III",)
      assert a05.modo_fator_r is ModoFatorR.NAO_APLICAVEL

  def test_deveAceitarParametroAnexosRepetido(self) -> None:
      lista = _SVC_ATIV.listar(DATA_PADRAO, {"III", "V"})
      a09 = _idx(lista, "09")
      assert a09.disponivel
      assert a09.anexos_faltantes == ()
      assert a09.modo_fator_r is ModoFatorR.OPCIONAL

  def test_deveMarcarFatorRObrigatorioQuandoSoOAnexoIIIEstaConfigurado(self) -> None:
      lista = _SVC_ATIV.listar(DATA_PADRAO, {"III"})
      a09 = _idx(lista, "09")
      assert a09.disponivel
      assert a09.anexos_faltantes == ("V",)
      assert a09.modo_fator_r is ModoFatorR.OBRIGATORIO

  def test_deveTratarAnexosVazioComoNenhumConfigurado(self) -> None:
      lista = _SVC_ATIV.listar(DATA_PADRAO, set())
      assert len(lista) == 15
      a09 = _idx(lista, "09")
      assert not a09.disponivel
      assert a09.anexos_faltantes == ("III", "V")
      assert a09.modo_fator_r is ModoFatorR.INDISPONIVEL
      a90 = _idx(lista, "90")
      assert a90.disponivel
      assert a90.anexos_faltantes == ()
      assert a90.modo_fator_r is ModoFatorR.NAO_APLICAVEL

  def test_semTpDocDeveDevolverTpDocsAdmissiveisSemAdmissivelNoDocumento(self) -> None:
      lista = _SVC_ATIV.listar(DATA_PADRAO)
      por = _map(lista)
      assert por["01"].tp_docs_admissiveis == ("55", "65")
      assert por["01"].admissivel_no_documento is None
      assert por["01"].disponivel
      assert por["05"].tp_docs_admissiveis == ("57", "63", "67", "93")
      assert por["05"].admissivel_no_documento is None
      assert por["06"].tp_docs_admissiveis == ("62",)
      assert por["09"].tp_docs_admissiveis == ("91",)
      assert por["90"].tp_docs_admissiveis == ("55", "57", "62", "63", "65", "67", "91", "93")

  def test_comTpDoc55DeveMarcarAdmissibilidadeConformeAWhitelist(self) -> None:
      lista = _SVC_ATIV.listar(DATA_PADRAO, None, "55")
      assert len(lista) == 15
      por = _map(lista)
      assert por["01"].admissivel_no_documento is True
      assert por["01"].disponivel
      assert por["05"].admissivel_no_documento is False
      assert not por["05"].disponivel
      assert por["05"].anexos_faltantes == ()
      assert por["09"].admissivel_no_documento is False
      assert not por["09"].disponivel
      assert por["13"].admissivel_no_documento is False
      assert not por["13"].disponivel
      assert por["90"].admissivel_no_documento is True
      assert por["90"].disponivel

  def test_comTpDoc91DeveMarcarVinculadasANfeNfceComoInadmissiveis(self) -> None:
      lista = _SVC_ATIV.listar(DATA_PADRAO, None, "91")
      por = _map(lista)
      assert por["01"].admissivel_no_documento is False
      assert not por["01"].disponivel
      assert por["01"].anexos_faltantes == ()
      assert por["01"].modo_fator_r is ModoFatorR.NAO_APLICAVEL
      assert por["04"].admissivel_no_documento is False
      assert not por["04"].disponivel
      assert por["05"].admissivel_no_documento is False
      assert por["07"].admissivel_no_documento is True
      assert por["07"].disponivel
      assert por["12"].admissivel_no_documento is True
      assert por["13"].admissivel_no_documento is True
      assert por["90"].admissivel_no_documento is True
      assert por["90"].disponivel
      assert por["90"].modo_fator_r is ModoFatorR.NAO_APLICAVEL

  def test_tpDocValidoNaoHabilitadoParaOCalculo_aceitoENenhumaAtividadeAdmissivel(self) -> None:
      lista = _SVC_ATIV.listar(DATA_PADRAO, None, "97")
      assert len(lista) == 15
      for atividade in lista:
          assert atividade.admissivel_no_documento is False
          assert not atividade.disponivel

  def test_deveMarcarOsDoisMotivosQuandoInadmissivelEComAnexosFaltantes(self) -> None:
      lista = _SVC_ATIV.listar(DATA_PADRAO, {"II"}, "91")
      por = _map(lista)
      assert por["01"].admissivel_no_documento is False
      assert por["01"].anexos_faltantes == ("I",)
      assert not por["01"].disponivel
      assert por["13"].admissivel_no_documento is True

  def test_deveRetornar400ParaTpDocMalFormado(self) -> None:
      with pytest.raises(ErroConsultaAtividade, match="abc"):
          _SVC_ATIV.listar(DATA_PADRAO, None, "abc")

  def test_deveRetornar400ParaTpDocSemLinhaNaTipoDfe(self) -> None:
      with pytest.raises(ErroConsultaAtividade, match="99"):
          _SVC_ATIV.listar(DATA_PADRAO, None, "99")

  def test_buscaPorCodigoDeveReceberOMesmoTratamentoDeTpDoc(self) -> None:
      a01_91 = _SVC_ATIV.buscarPorCodigo("01", DATA_PADRAO, "91")
      assert a01_91 is not None
      assert a01_91.tp_docs_admissiveis == ("55", "65")
      assert a01_91.admissivel_no_documento is False
      assert not a01_91.disponivel
      assert a01_91.anexos_faltantes == ()

      a01_55 = _SVC_ATIV.buscarPorCodigo("01", DATA_PADRAO, "55")
      assert a01_55 is not None
      assert a01_55.admissivel_no_documento is True
      assert a01_55.disponivel

      a05 = _SVC_ATIV.buscarPorCodigo("05", DATA_PADRAO)
      assert a05 is not None
      assert a05.tp_docs_admissiveis == ("57", "63", "67", "93")
      assert a05.admissivel_no_documento is None

      with pytest.raises(ErroConsultaAtividade):
          _SVC_ATIV.buscarPorCodigo("01", DATA_PADRAO, "99")

  def test_cClassTribQueDeclaraReceita_marcaSomenteONaoTributavelIndisponivel(self) -> None:
      lista = _SVC_ATIV.listar(DATA_PADRAO, None, None, "000001")
      assert len(lista) == 15
      por = _map(lista)
      assert por["01"].compativel_com_class_trib is True
      assert por["01"].disponivel
      assert por["05"].compativel_com_class_trib is True
      assert por["90"].compativel_com_class_trib is False
      assert not por["90"].disponivel
      assert por["90"].anexos_faltantes == ()

  def test_cClassTribDeTpRBSN0e9_naoMarcaAtividadeAlguma(self) -> None:
      for codigo in ("410001", "010001"):
          lista = _SVC_ATIV.listar(DATA_PADRAO, None, None, codigo)
          assert len(lista) == 15
          for atividade in lista:
              assert atividade.compativel_com_class_trib is True, (
                  f"cClassTrib {codigo} não deveria marcar a atividade {atividade.codigo}"
              )
              assert atividade.disponivel

  def test_motivosDeDocumentoEDeClassificacaoCombinados(self) -> None:
      lista = _SVC_ATIV.listar(DATA_PADRAO, None, "97", "000001")
      por = _map(lista)
      assert por["90"].admissivel_no_documento is False
      assert por["90"].compativel_com_class_trib is False
      assert not por["90"].disponivel
      assert por["01"].admissivel_no_documento is False
      assert por["01"].compativel_com_class_trib is True
      assert not por["01"].disponivel

  def test_cClassTribResolvidoPelaLinhaDaCbsQuandoCodigoColideComImpostoSeletivo(self) -> None:
      lista = _SVC_ATIV.listar(date(2027, 3, 15), None, None, "000001")
      por = _map(lista)
      assert por["90"].compativel_com_class_trib is False
      assert not por["90"].disponivel

  def test_semCClassTrib_respostaNaoTemCampoDeCompatibilidade(self) -> None:
      lista = _SVC_ATIV.listar(DATA_PADRAO)
      for atividade in lista:
          assert atividade.compativel_com_class_trib is None

  def test_deveRetornar400ParaCClassTribInexistente(self) -> None:
      with pytest.raises(ErroConsultaAtividade, match="999999"):
          _SVC_ATIV.listar(DATA_PADRAO, None, None, "999999")

  def test_deveRetornar400ParaCClassTribForaDeVigenciaNaData(self) -> None:
      with pytest.raises(ErroConsultaAtividade):
          _SVC_ATIV.listar(date(2025, 12, 31), None, None, "000001")

  def test_buscaPorCodigoDeveReceberOMesmoTratamentoDeCClassTrib(self) -> None:
      a90 = _SVC_ATIV.buscarPorCodigo("90", DATA_PADRAO, None, "000001")
      assert a90 is not None
      assert a90.compativel_com_class_trib is False
      assert not a90.disponivel

      a01 = _SVC_ATIV.buscarPorCodigo("01", DATA_PADRAO, None, "000001")
      assert a01 is not None
      assert a01.compativel_com_class_trib is True
      assert a01.disponivel

  def test_deveListarVazioParaDataAnteriorATodaVigencia(self) -> None:
      assert _SVC_ATIV.listar(date(2025, 12, 31)) == []

  def test_deveRetornar400ComAnexoForaDoDominio(self) -> None:
      with pytest.raises(ErroConsultaAtividade):
          _SVC_ATIV.listar(DATA_PADRAO, {"I", "X"})

  def test_deveRetornar400ComAnexoMinusculo(self) -> None:
      with pytest.raises(ErroConsultaAtividade):
          _SVC_ATIV.listar(DATA_PADRAO, {"i"})

  def test_deveExporAtividade9SujeitaAFatorR(self) -> None:
      item = _SVC_ATIV.buscarPorCodigo("09", DATA_PADRAO)
      assert item is not None
      assert item.codigo == "09"
      assert item.ordem == 9
      assert item.anexo_sem_fator_r == "V"
      assert item.anexo_com_fator_r == "III"
      assert item.sujeita_fator_r
      assert item.rotulo_anexo == "III ou V"
      assert item.rotulo_curto_anexo == "III ou V"
      assert item.disponivel
      assert item.anexos_faltantes == ()
      assert item.modo_fator_r is ModoFatorR.OPCIONAL

  def test_deveExporLinhaDoCodigo90SemAnexos(self) -> None:
      item = _SVC_ATIV.buscarPorCodigo("90", DATA_PADRAO)
      assert item is not None
      assert item.codigo == "90"
      assert item.ordem == 15
      assert item.descricao == "Operações não Tributáveis"
      assert item.anexo_sem_fator_r is None
      assert item.anexo_com_fator_r is None
      assert not item.sujeita_fator_r
      assert item.rotulo_anexo == "Não tributável"
      assert item.disponivel
      assert item.anexos_faltantes == ()
      assert item.modo_fator_r is ModoFatorR.NAO_APLICAVEL

  def test_deveRetornar404ParaCodigoInexistente(self) -> None:
      assert _SVC_ATIV.buscarPorCodigo("99", DATA_PADRAO) is None

  def test_admissibilidadeCoerenteComOCalculoParaTodaACargaAtual(self) -> None:
      for tp_doc in ("55", "57", "62", "63", "65", "67", "91", "93"):
          atividades = _SVC_ATIV.listar(DATA_PADRAO, None, tp_doc)
          assert len(atividades) == 15

          itens = [
              ItemSimplesClassico(
                  i + 1,
                  atividades[i].codigo,
                  "410999",
                  None,
                  None,
                  "100.00",
                  "0.00",
                  None,
                  None,
              )
              for i in range(len(atividades))
          ]
          operacao = OperacaoSimplesClassica(
              "507f1f77bcf86cd799439011",
              "2.0.0",
              DATA_PADRAO.isoformat(),
              tp_doc,
              "1",
              None,
              None,
              itens,
          )
          resultado = _SVC_CALC.processarOperacao(operacao, _BASE_URL)
          assert len(resultado.objetos) == len(atividades)

          for i, atividade in enumerate(atividades):
              admissivel = atividade.admissivel_no_documento
              assert admissivel is not None
              estado = resultado.objetos[i].estado
              esperado = (
                  EstadoItemProcessado.CALCULADO
                  if admissivel
                  else EstadoItemProcessado.NAO_CALCULADO
              )
              assert estado is esperado, (
                  f"tpDoc {tp_doc}, atividade {atividade.codigo}: "
                  f"admissivel_no_documento={admissivel} diverge do estado {estado.value}"
              )