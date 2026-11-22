from datetime import date
from decimal import Decimal

import pytest

from calculadora_rtc_simples_nacional.escolha import (
    AliquotasAnexo,
    AtividadeSimples,
    CamposIssItem,
    EscolhaParAliquotasService,
    LinhaAliquotas,
    MotivoResolucaoAliquota,
    ParAliquotas,
    RegraAliquota,
    SituacaoIssParAliquota,
    TipoAliquota,
    VocabularioRegime,
)


def _situacoes_carga() -> list[SituacaoIssParAliquota]:
    return [
        SituacaoIssParAliquota(1, "CRT", 2, RegraAliquota.ISS_FORA_DO_SIMPLES, TipoAliquota.SEM_REDISTRIBUICAO, 4),
        SituacaoIssParAliquota(2, "regApIBSCBSSN", 2, RegraAliquota.ISS_FORA_DO_SIMPLES, TipoAliquota.SEM_REDISTRIBUICAO, 4),
        SituacaoIssParAliquota(3, "regApTribSN", 2, RegraAliquota.ISS_FORA_DO_SIMPLES, TipoAliquota.SEM_REDISTRIBUICAO, 4),
        SituacaoIssParAliquota(4, "regApTribSN", 3, RegraAliquota.ISS_FORA_DO_SIMPLES, TipoAliquota.SEM_REDISTRIBUICAO, 4),
        SituacaoIssParAliquota(5, "tribISSQN", 2, RegraAliquota.ISS_NAO_INCIDE, TipoAliquota.SEM_REDISTRIBUICAO, 6),
        SituacaoIssParAliquota(6, "tribISSQN", 3, RegraAliquota.ISS_NAO_INCIDE, TipoAliquota.SEM_REDISTRIBUICAO, 6),
        SituacaoIssParAliquota(7, "tribISSQN", 4, RegraAliquota.ISS_NAO_INCIDE, TipoAliquota.SEM_REDISTRIBUICAO, 6),
        SituacaoIssParAliquota(8, "tpBM", 1, RegraAliquota.ISENCAO_MUNICIPAL, TipoAliquota.SEM_REDISTRIBUICAO, 7),
        SituacaoIssParAliquota(9, "tpRetISSQN", 2, RegraAliquota.ISS_RETIDO, TipoAliquota.SEM_REDISTRIBUICAO, 8),
        SituacaoIssParAliquota(10, "tpRetISSQN", 3, RegraAliquota.ISS_RETIDO, TipoAliquota.SEM_REDISTRIBUICAO, 8),
    ]


def atividade(cativ: str) -> AtividadeSimples:
    anexo_sem = None
    anexo_com = None
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


PAR_I = ParAliquotas(Decimal("1.1612"), Decimal("0.0129"))
PAR_III_COM = ParAliquotas(Decimal("2.2154"), Decimal("0.0257"))
PAR_III_SEM = ParAliquotas(Decimal("1.99"), Decimal("0.0231"))
PAR_IV_COM = ParAliquotas(Decimal("2.0119"), Decimal("0.022"))
PAR_IV_SEM = ParAliquotas(Decimal("1.85"), Decimal("0.0202"))
PAR_V_COM = ParAliquotas(Decimal("3.2534"), Decimal("0.0363"))


def linha(fator_r: bool | None, impedimento: bool) -> LinhaAliquotas:
    return LinhaAliquotas(
        fator_r,
        impedimento,
        AliquotasAnexo(PAR_I),
        AliquotasAnexo(ParAliquotas(Decimal("1.1184"), Decimal("0.0121"))),
        AliquotasAnexo(PAR_III_COM, PAR_III_SEM),
        AliquotasAnexo(PAR_IV_COM, PAR_IV_SEM),
        AliquotasAnexo(PAR_V_COM),
    )


escolha = EscolhaParAliquotasService()


def escolher(cativ: str, fatos: dict[str, int]):
    return escolha.escolher(atividade(cativ), True, linha(False, False), fatos, _situacoes_carga())


def assert_escolha(atual, anexo, tipo, regra, par):
    assert atual.anexo == anexo
    assert atual.tipo_aliquota == tipo
    assert atual.regra == regra
    assert atual.par == par


class ColetorTeste:
    def __init__(self) -> None:
        self.erros: list[tuple[str, str, str]] = []

    def add_erro_validacao(self, codigo: str, campo: str, detail: str) -> None:
        self.erros.append((codigo, campo, detail))

    def has_erros(self) -> bool:
        return bool(self.erros)


def test_regra1_documento() -> None:
    atual = escolha.escolher(atividade("07"), False, linha(False, False), {}, _situacoes_carga())
    assert_escolha(atual, None, None, RegraAliquota.DOCUMENTO, None)
    assert atual.motivo is MotivoResolucaoAliquota.ATIVIDADE_INADMISSIVEL_NO_DOCUMENTO


def test_regra2_nao_tributada() -> None:
    atual = escolher("90", {"tpRetISSQN": 2})
    assert_escolha(atual, None, TipoAliquota.SEM_ALIQUOTA, RegraAliquota.ATIVIDADE_NAO_TRIBUTADA, ParAliquotas.zero())


@pytest.mark.parametrize("campo,valor", [("CRT", 2), ("regApIBSCBSSN", 2), ("regApTribSN", 2), ("regApTribSN", 3)])
def test_regra4_campos_documento(campo, valor) -> None:
    assert_escolha(
        escolher("07", {campo: valor}),
        "III",
        TipoAliquota.SEM_REDISTRIBUICAO,
        RegraAliquota.ISS_FORA_DO_SIMPLES,
        PAR_III_SEM,
    )


@pytest.mark.parametrize("cativ", ["05", "06", "08", "11"])
def test_regra5_sem_iss(cativ) -> None:
    assert_escolha(
        escolher(cativ, {}),
        "III",
        TipoAliquota.SEM_REDISTRIBUICAO,
        RegraAliquota.ATIVIDADE_SEM_ISS,
        PAR_III_SEM,
    )


def test_fator_r_ausente_atividade09() -> None:
    atual = escolha.escolher(atividade("09"), True, linha(None, False), {}, _situacoes_carga())
    assert atual.motivo is MotivoResolucaoAliquota.FATOR_R_AUSENTE


def test_campos_iss_vsn036() -> None:
    collector = ColetorTeste()
    escolha.avaliar_campos_iss(VocabularioRegime.NFSE, atividade("07"), CamposIssItem(None, None, None), collector)
    assert [e[0] for e in collector.erros] == ["VSN-036"]