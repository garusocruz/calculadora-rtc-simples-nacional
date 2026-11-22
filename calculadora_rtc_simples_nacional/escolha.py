"""Escolha do par de alíquotas e avaliação dos campos do ISS (pin a926d5a)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Protocol


class VocabularioRegime(Enum):
    CRT = "CRT"
    NFSE = "NFSE"


class RegraAliquota(Enum):
    DOCUMENTO = "DOCUMENTO"
    ATIVIDADE_NAO_TRIBUTADA = "ATIVIDADE_NAO_TRIBUTADA"
    ANEXO_SEM_ISS = "ANEXO_SEM_ISS"
    ISS_FORA_DO_SIMPLES = "ISS_FORA_DO_SIMPLES"
    ATIVIDADE_SEM_ISS = "ATIVIDADE_SEM_ISS"
    ISS_NAO_INCIDE = "ISS_NAO_INCIDE"
    ISENCAO_MUNICIPAL = "ISENCAO_MUNICIPAL"
    ISS_RETIDO = "ISS_RETIDO"
    PADRAO = "PADRAO"


class TipoAliquota(Enum):
    PAR_UNICO = "PAR_UNICO"
    COM_REDISTRIBUICAO = "COM_REDISTRIBUICAO"
    SEM_REDISTRIBUICAO = "SEM_REDISTRIBUICAO"
    SEM_ALIQUOTA = "SEM_ALIQUOTA"


class MotivoResolucaoAliquota(Enum):
    ATIVIDADE_INADMISSIVEL_NO_DOCUMENTO = "ATIVIDADE_INADMISSIVEL_NO_DOCUMENTO"
    ATIVIDADE_SEM_ANEXO = "ATIVIDADE_SEM_ANEXO"
    FATOR_R_AUSENTE = "FATOR_R_AUSENTE"
    ANEXO_SEM_ALIQUOTA = "ANEXO_SEM_ALIQUOTA"
    RESOLVIDA = "RESOLVIDA"


CAMPO_CRT = "CRT"
CAMPO_REGAPIBSCBSSN = "regApIBSCBSSN"
CAMPO_REGAPTRIBSN = "regApTribSN"
CAMPO_TRIBISSQN = "tribISSQN"
CAMPO_TPRETISSQN = "tpRetISSQN"
CAMPO_TPBM = "tpBM"

_DOMINIO_TRIBISSQN = {1, 2, 3, 4}
_DOMINIO_TPRETISSQN = {1, 2, 3}
_DOMINIO_TPBM = {1, 2, 3, 4}
_TRIBUTAVEL = 1
_ISENCAO = 1
_RETIDO = {2, 3}


@dataclass(frozen=True)
class ParAliquotas:
    aliquota_cbs: Decimal | None
    aliquota_ibs: Decimal | None

    @staticmethod
    def zero() -> ParAliquotas:
        return ParAliquotas(Decimal(0), Decimal(0))


@dataclass(frozen=True)
class AliquotasAnexo:
    par: ParAliquotas | None
    sem_redistribuicao_iss: ParAliquotas | None = None


@dataclass(frozen=True)
class LinhaAliquotas:
    fator_r: bool | None
    impedimento_sublimite: bool
    anexo_i: AliquotasAnexo | None
    anexo_ii: AliquotasAnexo | None
    anexo_iii: AliquotasAnexo | None
    anexo_iv: AliquotasAnexo | None
    anexo_v: AliquotasAnexo | None

    def anexo(self, nome: str) -> AliquotasAnexo | None:
        return {
            "I": self.anexo_i,
            "II": self.anexo_ii,
            "III": self.anexo_iii,
            "IV": self.anexo_iv,
            "V": self.anexo_v,
        }[nome]

    @staticmethod
    def anexo_com_iss(nome: str) -> bool:
        return nome in ("III", "IV", "V")


@dataclass
class AtividadeSimples:
    id: int
    codigo: str
    nao_tributavel: bool = False
    anexo_sem_fator_r: str | None = None
    anexo_com_fator_r: str | None = None
    iss_no_simples: bool = False
    admite_beneficio_municipal: bool = False


@dataclass(frozen=True)
class SituacaoIssParAliquota:
    id: int
    campo: str
    valor: int
    regra: RegraAliquota
    tipo_aliquota: TipoAliquota
    ordem: int


@dataclass(frozen=True)
class CamposIssItem:
    trib_issqn: str | None
    tp_ret_issqn: str | None
    tp_bm: str | None


@dataclass(frozen=True)
class AvaliacaoIssItem:
    trib_issqn: int | None
    tp_ret_issqn: int | None
    tp_bm: int | None
    avisos: tuple[str, ...]


@dataclass(frozen=True)
class EscolhaParAliquotas:
    anexo: str | None
    tipo_aliquota: TipoAliquota | None
    regra: RegraAliquota | None
    par: ParAliquotas | None
    par_sem_redistribuicao_ausente: bool
    caminho_par: str | None
    motivo: MotivoResolucaoAliquota


class ColetorIss(Protocol):
    def add_erro_validacao(self, codigo: str, campo: str, detail: str) -> None: ...

    def has_erros(self) -> bool: ...


class EscolhaParAliquotasService:
    def avaliar_campos_iss(
        self,
        vocabulario: VocabularioRegime,
        atividade: AtividadeSimples,
        campos: CamposIssItem,
        collector: ColetorIss,
    ) -> AvaliacaoIssItem:
        avisos: list[str] = []
        trib_informado = _informado(campos.trib_issqn)
        ret_informado = _informado(campos.tp_ret_issqn)
        bm_informado = _informado(campos.tp_bm)

        if vocabulario is not VocabularioRegime.NFSE:
            desconsiderados = [
                nome
                for nome, ok in (
                    (CAMPO_TRIBISSQN, trib_informado),
                    (CAMPO_TPRETISSQN, ret_informado),
                    (CAMPO_TPBM, bm_informado),
                )
                if ok
            ]
            if desconsiderados:
                avisos.append(
                    f"{', '.join(desconsiderados)} desconsiderado(s): os campos do ISS só valem na NFS-e."
                )
            return AvaliacaoIssItem(None, None, None, tuple(avisos))

        iss_no_simples = atividade.iss_no_simples
        cativ = atividade.codigo

        trib_issqn = _inteiro(campos.trib_issqn)
        if trib_informado and (trib_issqn is None or trib_issqn not in _DOMINIO_TRIBISSQN):
            collector.add_erro_validacao(
                "VSN-036",
                CAMPO_TRIBISSQN,
                f"A tributação do ISSQN (tribISSQN) deve ser 1, 2, 3 ou 4, recebido: '{campos.trib_issqn}'.",
            )
            trib_issqn = None
        elif not trib_informado and iss_no_simples:
            collector.add_erro_validacao(
                "VSN-036",
                CAMPO_TRIBISSQN,
                f"A tributação do ISSQN (tribISSQN) é obrigatória para a atividade {cativ}, "
                "que tem ISS no Simples Nacional.",
            )

        tp_ret_issqn: int | None = None
        if ret_informado and trib_issqn is not None and trib_issqn != _TRIBUTAVEL:
            avisos.append(
                f"tpRetISSQN desconsiderado: não há retenção do ISS com tribISSQN {trib_issqn} "
                "(a NFS-e recusaria a combinação: regra E0580)."
            )
        elif ret_informado:
            tp_ret_issqn = _inteiro(campos.tp_ret_issqn)
            if tp_ret_issqn is None or tp_ret_issqn not in _DOMINIO_TPRETISSQN:
                collector.add_erro_validacao(
                    "VSN-037",
                    CAMPO_TPRETISSQN,
                    f"O tipo de retenção do ISSQN (tpRetISSQN) deve ser 1, 2 ou 3, "
                    f"recebido: '{campos.tp_ret_issqn}'.",
                )
                tp_ret_issqn = None
        elif iss_no_simples and trib_issqn == _TRIBUTAVEL:
            collector.add_erro_validacao(
                "VSN-037",
                CAMPO_TPRETISSQN,
                f"O tipo de retenção do ISSQN (tpRetISSQN) é obrigatório com tribISSQN = 1 "
                f"na atividade {cativ}, que tem ISS no Simples Nacional.",
            )

        tp_bm: int | None = None
        if bm_informado and not atividade.admite_beneficio_municipal:
            avisos.append(
                f"tpBM desconsiderado: a atividade {cativ} não admite benefício municipal do ISS "
                "(regra E0536 da NFS-e: só os subitens 7.02 e 7.05, atividades 12 e 13)."
            )
        elif bm_informado:
            tp_bm = _inteiro(campos.tp_bm)
            if tp_bm is None or tp_bm not in _DOMINIO_TPBM:
                collector.add_erro_validacao(
                    "VSN-038",
                    CAMPO_TPBM,
                    f"O tipo de benefício municipal (tpBM) deve ser 1, 2, 3 ou 4, "
                    f"recebido: '{campos.tp_bm}'.",
                )
                tp_bm = None

        if tp_bm == _ISENCAO and tp_ret_issqn is not None and tp_ret_issqn in _RETIDO:
            avisos.append(
                f"tpBM 1 (isenção) com tpRetISSQN {tp_ret_issqn}: combinação recusada pela NFS-e "
                "(regra E0594); vale a isenção municipal (par sem redistribuição)."
            )
        return AvaliacaoIssItem(trib_issqn, tp_ret_issqn, tp_bm, tuple(avisos))

    def escolher(
        self,
        atividade: AtividadeSimples,
        admissivel: bool,
        linha: LinhaAliquotas,
        fatos: dict[str, int],
        situacoes: list[SituacaoIssParAliquota],
    ) -> EscolhaParAliquotas:
        if not admissivel:
            return EscolhaParAliquotas(
                None,
                None,
                RegraAliquota.DOCUMENTO,
                None,
                False,
                None,
                MotivoResolucaoAliquota.ATIVIDADE_INADMISSIVEL_NO_DOCUMENTO,
            )

        anexo_com_fator_r = atividade.anexo_com_fator_r
        anexo_sem_fator_r = atividade.anexo_sem_fator_r
        if anexo_com_fator_r is None and anexo_sem_fator_r is None:
            return EscolhaParAliquotas(
                None,
                TipoAliquota.SEM_ALIQUOTA,
                RegraAliquota.ATIVIDADE_NAO_TRIBUTADA,
                ParAliquotas.zero(),
                False,
                None,
                MotivoResolucaoAliquota.ATIVIDADE_SEM_ANEXO,
            )

        anexo = anexo_sem_fator_r
        if anexo_com_fator_r is not None:
            if linha.fator_r is None:
                return EscolhaParAliquotas(
                    None, None, None, None, False, None, MotivoResolucaoAliquota.FATOR_R_AUSENTE
                )
            anexo = anexo_com_fator_r if linha.fator_r else anexo_sem_fator_r

        assert anexo is not None
        aliquotas_anexo = linha.anexo(anexo)
        par_do_anexo = aliquotas_anexo.par if aliquotas_anexo else None
        caminho_anexo = f"anexo{anexo}"

        if not LinhaAliquotas.anexo_com_iss(anexo):
            return _escolhido(
                anexo,
                TipoAliquota.PAR_UNICO,
                RegraAliquota.ANEXO_SEM_ISS,
                par_do_anexo,
                False,
                caminho_anexo,
            )

        regra = RegraAliquota.PADRAO
        tipo = TipoAliquota.COM_REDISTRIBUICAO
        situacao: SituacaoIssParAliquota | None
        if linha.impedimento_sublimite:
            regra = RegraAliquota.ISS_FORA_DO_SIMPLES
            tipo = TipoAliquota.SEM_REDISTRIBUICAO
        elif (situacao := _situacao(RegraAliquota.ISS_FORA_DO_SIMPLES, fatos, situacoes)) is not None:
            regra = situacao.regra
            tipo = situacao.tipo_aliquota
        elif not atividade.iss_no_simples:
            regra = RegraAliquota.ATIVIDADE_SEM_ISS
            tipo = TipoAliquota.SEM_REDISTRIBUICAO
        else:
            for candidata in (
                RegraAliquota.ISS_NAO_INCIDE,
                RegraAliquota.ISENCAO_MUNICIPAL,
                RegraAliquota.ISS_RETIDO,
            ):
                situacao = _situacao(candidata, fatos, situacoes)
                if situacao is not None:
                    regra = situacao.regra
                    tipo = situacao.tipo_aliquota
                    break

        if tipo is not TipoAliquota.SEM_REDISTRIBUICAO:
            return _escolhido(anexo, tipo, regra, par_do_anexo, False, caminho_anexo)

        sem = aliquotas_anexo.sem_redistribuicao_iss if aliquotas_anexo else None
        if sem is None:
            return _escolhido(anexo, tipo, regra, par_do_anexo, True, caminho_anexo)
        return _escolhido(anexo, tipo, regra, sem, False, f"{caminho_anexo}/semRedistribuicaoISS")

    @staticmethod
    def aviso_par_sem_redistribuicao_ausente(anexo: str) -> str:
        return (
            f"Par sem redistribuição do ISS ausente no anexo {anexo}; aplicado o par com redistribuição, "
            "igual quando o ISS não passa do teto."
        )


def _escolhido(
    anexo: str,
    tipo: TipoAliquota,
    regra: RegraAliquota,
    par: ParAliquotas | None,
    sem_ausente: bool,
    caminho: str,
) -> EscolhaParAliquotas:
    motivo = (
        MotivoResolucaoAliquota.ANEXO_SEM_ALIQUOTA
        if par is None or par.aliquota_cbs is None
        else MotivoResolucaoAliquota.RESOLVIDA
    )
    return EscolhaParAliquotas(anexo, tipo, regra, par, sem_ausente, caminho, motivo)


def _situacao(
    regra: RegraAliquota, fatos: dict[str, int], situacoes: list[SituacaoIssParAliquota]
) -> SituacaoIssParAliquota | None:
    for situacao in situacoes:
        if situacao.regra is regra and fatos.get(situacao.campo) == situacao.valor:
            return situacao
    return None


def _informado(valor: str | None) -> bool:
    return valor is not None and bool(valor.strip())


def _inteiro(valor: str | None) -> int | None:
    if not _informado(valor):
        return None
    try:
        return int(valor.strip())
    except ValueError:
        return None