"""Fachada de consumo (espelho dos serviços Java, sem Spring/HTTP)."""

from __future__ import annotations

from datetime import date, timedelta

from calculadora_rtc_simples_nacional import atividade, nao_assistido, observabilidade
from calculadora_rtc_simples_nacional.atividade import AtividadeSimplesDomain, Derivacao
from calculadora_rtc_simples_nacional.nao_assistido import OperacaoNaoAssistida
from calculadora_rtc_simples_nacional.observabilidade import OperacaoSimplesClassica
from calculadora_rtc_simples_nacional.parametro import ParametroCalculo
from calculadora_rtc_simples_nacional.simples import Insumo, Resultado, calcular_item
from calculadora_rtc_simples_nacional import escolha as _escolha
from calculadora_rtc_simples_nacional.unificado import ObservabilidadeSimples
from calculadora_rtc_simples_nacional.versao import (
    ServicoVersaoOffline,
    VersaoOfflineDomain,
)
from calculadora_rtc_simples_nacional.nomenclatura import (
    ModoValidacaoNomenclatura,
    NbsAplicavelService as _NbsAplicavelService,
    NcmAplicavelService as _NcmAplicavelService,
    NomenclaturaService as _NomenclaturaService,
    SiglaDFe,
    ValidacaoNomenclaturaService as _ValidacaoNomenclaturaService,
)


class EscolhaParAliquotasService:
    """``br.gov.serpro.rtc.api.simplesnacional.service.EscolhaParAliquotasService``."""

    def __init__(self) -> None:
        self._inner = _escolha.EscolhaParAliquotasService()

    def escolher(
        self,
        atividade: _escolha.AtividadeSimples,
        admissivel: bool,
        linha: _escolha.LinhaAliquotas,
        fatos: dict[str, int],
        situacoes: list[_escolha.SituacaoIssParAliquota],
    ) -> _escolha.EscolhaParAliquotas:
        return self._inner.escolher(atividade, admissivel, linha, fatos, situacoes)


class SimplesNacionalCalculoService:
    """``br.gov.serpro.rtc.api.simplesnacional.service.SimplesNacionalCalculoService``."""

    def calcularItem(self, insumo: Insumo) -> Resultado:
        return calcular_item(insumo)


class SimplesNacionalObservabilidadeService:
    """``br.gov.serpro.rtc.api.simplesnacional.service.SimplesNacionalObservabilidadeService``."""

    def __init__(
        self,
        parametro: ParametroCalculo | None = None,
    ) -> None:
        self._inner = observabilidade.SimplesNacionalObservabilidadeService(parametro)

    def processarOperacao(
        self, operacao: OperacaoSimplesClassica, base_url: str
    ) -> observabilidade.ObservabilidadeSimplesClassica:
        return self._inner.processar_operacao(operacao, base_url)


class SimplesNacionalNaoAssistidoService:
    """``br.gov.serpro.rtc.api.simplesnacional.service.SimplesNacionalNaoAssistidoService``."""

    def processarOperacao(self, operacao: OperacaoNaoAssistida) -> ObservabilidadeSimples:
        return nao_assistido.processar_operacao(operacao)


class AtividadeSimplesService:
    """``br.gov.serpro.rtc.api.atividadesimples.service.AtividadeSimplesService``."""

    def __init__(self, parametro: ParametroCalculo | None = None) -> None:
        self._inner = atividade.AtividadeSimplesService(parametro)

    def listar(
        self,
        data: date,
        anexos_configurados: set[str] | None = None,
        tp_doc: str | None = None,
        c_class_trib: str | None = None,
    ) -> list[AtividadeSimplesDomain]:
        return self._inner.listar(data, anexos_configurados, tp_doc, c_class_trib)

    def buscarPorCodigo(
        self,
        codigo: str | None,
        data: date,
        tp_doc: str | None = None,
        c_class_trib: str | None = None,
    ) -> AtividadeSimplesDomain | None:
        return self._inner.buscar_por_codigo(codigo, data, tp_doc, c_class_trib)

    @staticmethod
    def derivar(
        anexo_sem_fator_r: str | None,
        anexo_com_fator_r: str | None,
        anexos_configurados: set[str] | None,
    ) -> Derivacao:
        """``DerivacaoAnexosSimples#derivar`` — regra pura de anexos configurados."""
        return atividade.derivar_anexos(
            anexo_sem_fator_r, anexo_com_fator_r, anexos_configurados
        )


class ValidacaoNomenclaturaService:
    """``br.gov.serpro.rtc.domain.service.ValidacaoNomenclaturaService``."""

    def __init__(
        self,
        nomenclatura_service: _NomenclaturaService,
        ncm_aplicavel_service: _NcmAplicavelService,
        nbs_aplicavel_service: _NbsAplicavelService,
    ) -> None:
        self._inner = _ValidacaoNomenclaturaService(
            nomenclatura_service, ncm_aplicavel_service, nbs_aplicavel_service
        )

    def validar(
        self,
        sigla_dfe: SiglaDFe,
        id_classificacao_tributaria: int,
        codigo_classificacao_tributaria: str,
        ncm: str | None,
        nbs: str | None,
        data: date,
        tributos: str,
        modo: ModoValidacaoNomenclatura,
    ) -> None:
        self._inner.validar(
            sigla_dfe,
            id_classificacao_tributaria,
            codigo_classificacao_tributaria,
            ncm,
            nbs,
            data,
            tributos,
            modo,
        )


class VersaoOfflineService:
    """``br.gov.serpro.rtc.api.versao.service.VersaoOfflineService``."""

    def __init__(
        self,
        versao_service: object,
        url_versao_remota: str,
        connect_timeout: timedelta = timedelta(seconds=5),
        read_timeout: timedelta = timedelta(seconds=10),
        intervalo_entre_tentativas: timedelta = timedelta(seconds=2),
    ) -> None:
        self._inner = ServicoVersaoOffline(
            versao_service,
            url_versao_remota,
            connect_timeout,
            read_timeout,
            intervalo_entre_tentativas,
        )

    def verificarVersao(self) -> VersaoOfflineDomain:
        return self._inner.verificar_versao()

    def verificarVersaoNaInicializacao(self) -> None:
        self._inner.verificar_versao_na_inicializacao()