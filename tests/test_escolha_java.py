"""Espelho de ``Teste_EscolhaParAliquotasService`` (pin a926d5a7)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from calculadora_rtc_simples_nacional import escolha
from calculadora_rtc_simples_nacional.consumo import EscolhaParAliquotasService
from calculadora_rtc_simples_nacional.escolha import (
    AliquotasAnexo,
    AtividadeSimples,
    CamposIssItem,
    LinhaAliquotas,
    MotivoResolucaoAliquota,
    ParAliquotas,
    RegraAliquota,
    SituacaoIssParAliquota,
    TipoAliquota,
    VocabularioRegime,
)

_CLASSNAME = (
    "br.gov.serpro.rtc.testesunitarios.simplesnacional.Teste_EscolhaParAliquotasService"
)

PAR_I = ParAliquotas(Decimal("1.1612"), Decimal("0.0129"))
PAR_III_COM = ParAliquotas(Decimal("2.2154"), Decimal("0.0257"))
PAR_III_SEM = ParAliquotas(Decimal("1.99"), Decimal("0.0231"))
PAR_IV_COM = ParAliquotas(Decimal("2.0119"), Decimal("0.022"))
PAR_IV_SEM = ParAliquotas(Decimal("1.85"), Decimal("0.0202"))
PAR_V_COM = ParAliquotas(Decimal("3.2534"), Decimal("0.0363"))


def _situacoes_carga() -> list[SituacaoIssParAliquota]:
    return [
        SituacaoIssParAliquota(1, "CRT", 2, RegraAliquota.ISS_FORA_DO_SIMPLES, TipoAliquota.SEM_REDISTRIBUICAO, 4),
        SituacaoIssParAliquota(
            2, "regApIBSCBSSN", 2, RegraAliquota.ISS_FORA_DO_SIMPLES, TipoAliquota.SEM_REDISTRIBUICAO, 4
        ),
        SituacaoIssParAliquota(
            3, "regApTribSN", 2, RegraAliquota.ISS_FORA_DO_SIMPLES, TipoAliquota.SEM_REDISTRIBUICAO, 4
        ),
        SituacaoIssParAliquota(
            4, "regApTribSN", 3, RegraAliquota.ISS_FORA_DO_SIMPLES, TipoAliquota.SEM_REDISTRIBUICAO, 4
        ),
        SituacaoIssParAliquota(5, "tribISSQN", 2, RegraAliquota.ISS_NAO_INCIDE, TipoAliquota.SEM_REDISTRIBUICAO, 6),
        SituacaoIssParAliquota(6, "tribISSQN", 3, RegraAliquota.ISS_NAO_INCIDE, TipoAliquota.SEM_REDISTRIBUICAO, 6),
        SituacaoIssParAliquota(7, "tribISSQN", 4, RegraAliquota.ISS_NAO_INCIDE, TipoAliquota.SEM_REDISTRIBUICAO, 6),
        SituacaoIssParAliquota(8, "tpBM", 1, RegraAliquota.ISENCAO_MUNICIPAL, TipoAliquota.SEM_REDISTRIBUICAO, 7),
        SituacaoIssParAliquota(9, "tpRetISSQN", 2, RegraAliquota.ISS_RETIDO, TipoAliquota.SEM_REDISTRIBUICAO, 8),
        SituacaoIssParAliquota(10, "tpRetISSQN", 3, RegraAliquota.ISS_RETIDO, TipoAliquota.SEM_REDISTRIBUICAO, 8),
    ]


def _atividade(cativ: str) -> AtividadeSimples:
    anexo_sem: str | None = None
    anexo_com: str | None = None
    match cativ:
        case "01" | "02":
            anexo_sem = "I"
        case "03" | "04":
            anexo_sem = "II"
        case "13" | "14":
            anexo_sem = "IV"
        case "09":
            anexo_sem = "V"
            anexo_com = "III"
        case "90":
            pass
        case _:
            anexo_sem = "III"
    return AtividadeSimples(
        int(cativ) if cativ.isdigit() else 90,
        cativ,
        cativ == "90",
        anexo_sem,
        anexo_com,
        cativ in {"07", "09", "10", "12", "13", "14"},
        cativ in {"12", "13"},
    )


def _linha(fator_r: bool | None, impedimento: bool) -> LinhaAliquotas:
    return LinhaAliquotas(
        fator_r,
        impedimento,
        AliquotasAnexo(PAR_I),
        AliquotasAnexo(ParAliquotas(Decimal("1.1184"), Decimal("0.0121"))),
        AliquotasAnexo(PAR_III_COM, PAR_III_SEM),
        AliquotasAnexo(PAR_IV_COM, PAR_IV_SEM),
        AliquotasAnexo(PAR_V_COM),
    )


def _assert_escolha(
    atual: escolha.EscolhaParAliquotas,
    anexo: str | None,
    tipo: TipoAliquota | None,
    regra: RegraAliquota | None,
    par: ParAliquotas | None,
) -> None:
    assert atual.anexo == anexo
    assert atual.tipo_aliquota == tipo
    assert atual.regra == regra
    assert atual.par == par


def _junit(record_xml_attribute, name: str) -> None:
    record_xml_attribute("classname", _CLASSNAME)
    record_xml_attribute("name", name)


@pytest.fixture
def service() -> EscolhaParAliquotasService:
    return EscolhaParAliquotasService()


@pytest.fixture
def iss_service() -> escolha.EscolhaParAliquotasService:
    return escolha.EscolhaParAliquotasService()


def _escolher(service: EscolhaParAliquotasService, cativ: str, fatos: dict[str, int]):
    return service.escolher(_atividade(cativ), True, _linha(False, False), fatos, _situacoes_carga())


@dataclass
class _ErroColetor:
    code: str
    campo: str
    detail: str
    pointer: str


class ItemCollectorSimples:
    def __init__(self, index: int = 0, base_url: str = "http://localhost/api") -> None:
        self._index = index
        self._base_url = base_url
        self.erros: list[_ErroColetor] = []

    def add_erro_validacao(self, codigo: str, campo: str, detail: str) -> None:
        self.erros.append(_ErroColetor(codigo, campo, detail, f"#/itens/{self._index}/{campo}"))

    def has_erros(self) -> bool:
        return bool(self.erros)

    def codigos(self) -> list[str]:
        return [e.code for e in self.erros]


def test_regra1_documento_atividadeNaoAdmitidaNoTpDoc(
    service: EscolhaParAliquotasService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "regra1_documento_atividadeNaoAdmitidaNoTpDoc")
    atual = service.escolher(_atividade("07"), False, _linha(False, False), {}, _situacoes_carga())
    _assert_escolha(atual, None, None, RegraAliquota.DOCUMENTO, None)
    assert atual.motivo is MotivoResolucaoAliquota.ATIVIDADE_INADMISSIVEL_NO_DOCUMENTO


def test_regra2_atividadeNaoTributada_semAliquotaZero(
    service: EscolhaParAliquotasService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "regra2_atividadeNaoTributada_semAliquotaZero")
    atual = _escolher(service, "90", {"tpRetISSQN": 2})
    _assert_escolha(atual, None, TipoAliquota.SEM_ALIQUOTA, RegraAliquota.ATIVIDADE_NAO_TRIBUTADA, ParAliquotas.zero())
    assert atual.motivo is MotivoResolucaoAliquota.ATIVIDADE_SEM_ANEXO


def test_regra3_anexoSemIss_parUnico_mesmoComFatosDoIss(
    service: EscolhaParAliquotasService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "regra3_anexoSemIss_parUnico_mesmoComFatosDoIss")
    atual = _escolher(service, "01", {"CRT": 2})
    _assert_escolha(atual, "I", TipoAliquota.PAR_UNICO, RegraAliquota.ANEXO_SEM_ISS, PAR_I)
    assert atual.motivo is MotivoResolucaoAliquota.RESOLVIDA
    assert atual.caminho_par == "anexoI"


def test_regra4_impedimentoPeloSublimite_vemDaLinha(
    service: EscolhaParAliquotasService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "regra4_impedimentoPeloSublimite_vemDaLinha")
    atual = service.escolher(_atividade("07"), True, _linha(False, True), {}, _situacoes_carga())
    _assert_escolha(atual, "III", TipoAliquota.SEM_REDISTRIBUICAO, RegraAliquota.ISS_FORA_DO_SIMPLES, PAR_III_SEM)
    assert atual.caminho_par == "anexoIII/semRedistribuicaoISS"


@pytest.mark.parametrize(
    "campo,valor,idx",
    [
        ("CRT", 2, 1),
        ("regApIBSCBSSN", 2, 2),
        ("regApTribSN", 2, 3),
        ("regApTribSN", 3, 4),
    ],
)
def test_regra4_issForaDoSimples_pelosCamposDoDocumento(
    service: EscolhaParAliquotasService, record_xml_attribute, campo: str, valor: int, idx: int
) -> None:
    _junit(record_xml_attribute, f"regra4_issForaDoSimples_pelosCamposDoDocumento(String, int)[{idx}]")
    _assert_escolha(
        _escolher(service, "07", {campo: valor}),
        "III",
        TipoAliquota.SEM_REDISTRIBUICAO,
        RegraAliquota.ISS_FORA_DO_SIMPLES,
        PAR_III_SEM,
    )


@pytest.mark.parametrize(
    "cativ,idx",
    [("05", 1), ("06", 2), ("08", 3), ("11", 4)],
)
def test_regra5_atividadeSemIssNoSimples(
    service: EscolhaParAliquotasService, record_xml_attribute, cativ: str, idx: int
) -> None:
    _junit(record_xml_attribute, f"regra5_atividadeSemIssNoSimples(String)[{idx}]")
    _assert_escolha(
        _escolher(service, cativ, {}),
        "III",
        TipoAliquota.SEM_REDISTRIBUICAO,
        RegraAliquota.ATIVIDADE_SEM_ISS,
        PAR_III_SEM,
    )


@pytest.mark.parametrize("trib_issqn,idx", [(2, 1), (3, 2), (4, 3)])
def test_regra6_issNaoIncide(
    service: EscolhaParAliquotasService, record_xml_attribute, trib_issqn: int, idx: int
) -> None:
    _junit(record_xml_attribute, f"regra6_issNaoIncide(int)[{idx}]")
    _assert_escolha(
        _escolher(service, "14", {"tribISSQN": trib_issqn}),
        "IV",
        TipoAliquota.SEM_REDISTRIBUICAO,
        RegraAliquota.ISS_NAO_INCIDE,
        PAR_IV_SEM,
    )


def test_regra7_isencaoMunicipal(service: EscolhaParAliquotasService, record_xml_attribute) -> None:
    _junit(record_xml_attribute, "regra7_isencaoMunicipal")
    _assert_escolha(
        _escolher(service, "12", {"tribISSQN": 1, "tpRetISSQN": 1, "tpBM": 1}),
        "III",
        TipoAliquota.SEM_REDISTRIBUICAO,
        RegraAliquota.ISENCAO_MUNICIPAL,
        PAR_III_SEM,
    )


@pytest.mark.parametrize("tp_ret,idx", [(2, 1), (3, 2)])
def test_regra8_issRetido(
    service: EscolhaParAliquotasService, record_xml_attribute, tp_ret: int, idx: int
) -> None:
    _junit(record_xml_attribute, f"regra8_issRetido(int)[{idx}]")
    _assert_escolha(
        _escolher(service, "07", {"tribISSQN": 1, "tpRetISSQN": tp_ret}),
        "III",
        TipoAliquota.SEM_REDISTRIBUICAO,
        RegraAliquota.ISS_RETIDO,
        PAR_III_SEM,
    )


@pytest.mark.parametrize("tp_bm,idx", [(2, 1), (3, 2), (4, 3)])
def test_regra9_padrao_reducaoDaBaseEAliquotaDiferenciada(
    service: EscolhaParAliquotasService, record_xml_attribute, tp_bm: int, idx: int
) -> None:
    _junit(record_xml_attribute, f"regra9_padrao_reducaoDaBaseEAliquotaDiferenciada(int)[{idx}]")
    _assert_escolha(
        _escolher(service, "13", {"tribISSQN": 1, "tpRetISSQN": 1, "tpBM": tp_bm}),
        "IV",
        TipoAliquota.COM_REDISTRIBUICAO,
        RegraAliquota.PADRAO,
        PAR_IV_COM,
    )


def test_regra9_padrao_semFatosDoIss(service: EscolhaParAliquotasService, record_xml_attribute) -> None:
    _junit(record_xml_attribute, "regra9_padrao_semFatosDoIss")
    atual = _escolher(service, "10", {"tribISSQN": 1, "tpRetISSQN": 1, "regApTribSN": 1})
    _assert_escolha(atual, "III", TipoAliquota.COM_REDISTRIBUICAO, RegraAliquota.PADRAO, PAR_III_COM)
    assert atual.caminho_par == "anexoIII"


def test_ordem_regra4AntesDaRegra5(service: EscolhaParAliquotasService, record_xml_attribute) -> None:
    _junit(record_xml_attribute, "ordem_regra4AntesDaRegra5")
    assert _escolher(service, "11", {"regApTribSN": 3}).regra is RegraAliquota.ISS_FORA_DO_SIMPLES


def test_ordem_regras6a8_formamUmOu_aPrimeiraDecide(
    service: EscolhaParAliquotasService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "ordem_regras6a8_formamUmOu_aPrimeiraDecide")
    atual = _escolher(service, "12", {"tribISSQN": 2, "tpBM": 1, "tpRetISSQN": 2})
    assert atual.regra is RegraAliquota.ISS_NAO_INCIDE
    assert atual.tipo_aliquota is TipoAliquota.SEM_REDISTRIBUICAO
    assert _escolher(service, "12", {"tribISSQN": 1, "tpBM": 1, "tpRetISSQN": 2}).regra is RegraAliquota.ISENCAO_MUNICIPAL


def test_fatorR_atividade09_anexoIIIouV(service: EscolhaParAliquotasService, record_xml_attribute) -> None:
    _junit(record_xml_attribute, "fatorR_atividade09_anexoIIIouV")
    com_fator_r = service.escolher(
        _atividade("09"),
        True,
        _linha(True, False),
        {"tribISSQN": 1, "tpRetISSQN": 1},
        _situacoes_carga(),
    )
    _assert_escolha(com_fator_r, "III", TipoAliquota.COM_REDISTRIBUICAO, RegraAliquota.PADRAO, PAR_III_COM)
    sem_fator_r = service.escolher(
        _atividade("09"),
        True,
        _linha(False, False),
        {"tribISSQN": 1, "tpRetISSQN": 1},
        _situacoes_carga(),
    )
    _assert_escolha(sem_fator_r, "V", TipoAliquota.COM_REDISTRIBUICAO, RegraAliquota.PADRAO, PAR_V_COM)


def test_fatorR_ausente_comAtividade09_semPar(service: EscolhaParAliquotasService, record_xml_attribute) -> None:
    _junit(record_xml_attribute, "fatorR_ausente_comAtividade09_semPar")
    atual = service.escolher(_atividade("09"), True, _linha(None, False), {}, _situacoes_carga())
    assert atual.motivo is MotivoResolucaoAliquota.FATOR_R_AUSENTE
    assert atual.anexo is None
    assert atual.par is None
    assert (
        service.escolher(_atividade("07"), True, _linha(None, False), {}, _situacoes_carga()).motivo
        is MotivoResolucaoAliquota.RESOLVIDA
    )


def test_parSemNulo_valeOParCom_comAviso(service: EscolhaParAliquotasService, record_xml_attribute) -> None:
    _junit(record_xml_attribute, "parSemNulo_valeOParCom_comAviso")
    atual = service.escolher(_atividade("09"), True, _linha(False, False), {"regApTribSN": 2}, _situacoes_carga())
    _assert_escolha(atual, "V", TipoAliquota.SEM_REDISTRIBUICAO, RegraAliquota.ISS_FORA_DO_SIMPLES, PAR_V_COM)
    assert atual.par_sem_redistribuicao_ausente is True
    assert atual.caminho_par == "anexoV"
    assert "aplicado o par com" in escolha.EscolhaParAliquotasService.aviso_par_sem_redistribuicao_ausente("V")


def test_anexoAusenteNaLinha_motivoAnexoSemAliquota(
    service: EscolhaParAliquotasService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "anexoAusenteNaLinha_motivoAnexoSemAliquota")
    sem_anexo_iv = LinhaAliquotas(None, False, None, None, None, None, None)
    atual = service.escolher(
        _atividade("14"), True, sem_anexo_iv, {"tribISSQN": 1, "tpRetISSQN": 1}, _situacoes_carga()
    )
    assert atual.anexo == "IV"
    assert atual.par is None
    assert atual.motivo is MotivoResolucaoAliquota.ANEXO_SEM_ALIQUOTA


def test_camposIss_familiaCrt_desconsideradosComAviso(
    iss_service: escolha.EscolhaParAliquotasService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "camposIss_familiaCrt_desconsideradosComAviso")
    collector = ItemCollectorSimples()
    atual = iss_service.avaliar_campos_iss(
        VocabularioRegime.CRT, _atividade("05"), CamposIssItem("2", "2", "1"), collector
    )
    assert atual.trib_issqn is None
    assert atual.tp_ret_issqn is None
    assert atual.tp_bm is None
    assert len(atual.avisos) == 1
    assert "tribISSQN, tpRetISSQN, tpBM" in atual.avisos[0]
    assert not collector.has_erros()


def test_camposIss_tribIssqnObrigatorioNaAtividadeComIss(
    iss_service: escolha.EscolhaParAliquotasService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "camposIss_tribIssqnObrigatorioNaAtividadeComIss")
    collector = ItemCollectorSimples()
    iss_service.avaliar_campos_iss(VocabularioRegime.NFSE, _atividade("07"), CamposIssItem(None, None, None), collector)
    assert collector.codigos() == ["VSN-036"]
    assert collector.erros[0].pointer == "#/itens/0/tribISSQN"
    sem_iss = ItemCollectorSimples()
    iss_service.avaliar_campos_iss(VocabularioRegime.NFSE, _atividade("11"), CamposIssItem(None, None, None), sem_iss)
    assert not sem_iss.has_erros()


def test_camposIss_foraDoDominio(iss_service: escolha.EscolhaParAliquotasService, record_xml_attribute) -> None:
    _junit(record_xml_attribute, "camposIss_foraDoDominio")
    collector = ItemCollectorSimples()
    iss_service.avaliar_campos_iss(
        VocabularioRegime.NFSE, _atividade("12"), CamposIssItem("5", "4", "9"), collector
    )
    assert collector.codigos() == ["VSN-036", "VSN-037", "VSN-038"]


def test_camposIss_tpRetIssqnObrigatorioComTribIssqn1(
    iss_service: escolha.EscolhaParAliquotasService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "camposIss_tpRetIssqnObrigatorioComTribIssqn1")
    collector = ItemCollectorSimples()
    iss_service.avaliar_campos_iss(VocabularioRegime.NFSE, _atividade("14"), CamposIssItem("1", None, None), collector)
    assert collector.codigos() == ["VSN-037"]


def test_camposIss_tpRetIssqnComImunidade_desconsideradoComAviso(
    iss_service: escolha.EscolhaParAliquotasService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "camposIss_tpRetIssqnComImunidade_desconsideradoComAviso")
    collector = ItemCollectorSimples()
    atual = iss_service.avaliar_campos_iss(
        VocabularioRegime.NFSE, _atividade("07"), CamposIssItem("2", "2", None), collector
    )
    assert not collector.has_erros()
    assert atual.trib_issqn == 2
    assert atual.tp_ret_issqn is None
    assert "E0580" in atual.avisos[0]


def test_camposIss_tpBmAusente_semBeneficio_nuncaErro(
    iss_service: escolha.EscolhaParAliquotasService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "camposIss_tpBmAusente_semBeneficio_nuncaErro")
    collector = ItemCollectorSimples()
    atual = iss_service.avaliar_campos_iss(
        VocabularioRegime.NFSE, _atividade("12"), CamposIssItem("1", "1", None), collector
    )
    assert not collector.has_erros()
    assert atual.tp_bm is None
    assert not atual.avisos


def test_camposIss_tpBmForaDas12e13_desconsideradoComAviso(
    iss_service: escolha.EscolhaParAliquotasService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "camposIss_tpBmForaDas12e13_desconsideradoComAviso")
    collector = ItemCollectorSimples()
    atual = iss_service.avaliar_campos_iss(
        VocabularioRegime.NFSE, _atividade("07"), CamposIssItem("1", "1", "1"), collector
    )
    assert not collector.has_erros()
    assert atual.tp_bm is None
    assert "E0536" in atual.avisos[0]


def test_camposIss_isencaoComRetencao_avisoE0594(
    iss_service: escolha.EscolhaParAliquotasService, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "camposIss_isencaoComRetencao_avisoE0594")
    collector = ItemCollectorSimples()
    atual = iss_service.avaliar_campos_iss(
        VocabularioRegime.NFSE, _atividade("13"), CamposIssItem("1", "2", "1"), collector
    )
    assert not collector.has_erros()
    assert atual.tp_bm == 1
    assert atual.tp_ret_issqn == 2
    assert "E0594" in atual.avisos[0]