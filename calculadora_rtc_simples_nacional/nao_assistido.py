"""Linha de alíquotas do cálculo não assistido (pin a926d5a).

Transcrição de ``SimplesNacionalNaoAssistidoService`` sem Spring. A linha
entra no corpo e só é lida quando o regime calcula tributos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from calculadora_rtc_simples_nacional.escolha import AliquotasAnexo, LinhaAliquotas, ParAliquotas
from calculadora_rtc_simples_nacional.unificado import (
    CalculoSimplesUnificadoService,
    DadosOperacaoSimples,
    ErroDetalhe,
    ErrosCalculoException,
    ItemSimplesUnificadoInput,
    LinhaAliquotasComOrigem,
    ObservabilidadeSimples,
    OrigemLinhaAliquotas,
    ResolucaoAliquotaItem,
    ResolucaoAliquotas,
)

_RAIZ = "aliquotasEfetivas"
_FORMATO = re.compile(r"\d{1,3}(\.\d{1,34})?")
_DESCRICAO = (
    "até 3 dígitos inteiros e até 34 casas decimais, sem notação científica (ex.: 1.6839)"
)
_CBS = "VSN-005"
_IBS = "VSN-007"
_AUSENTE = "VSN-039"


@dataclass(frozen=True)
class ParInformado:
    p_cbssn: str | None = None
    p_ibssn: str | None = None


@dataclass(frozen=True)
class AnexoUnico:
    p_cbssn: str | None = None
    p_ibssn: str | None = None


@dataclass(frozen=True)
class AnexoComIss:
    p_cbssn: str | None = None
    p_ibssn: str | None = None
    sem_redistribuicao: ParInformado | None = None


@dataclass(frozen=True)
class AliquotasEfetivas:
    fator_r: bool | None = None
    impedimento_sublimite: bool | None = None
    anexo_i: AnexoUnico | None = None
    anexo_ii: AnexoUnico | None = None
    anexo_iii: AnexoComIss | None = None
    anexo_iv: AnexoComIss | None = None
    anexo_v: AnexoComIss | None = None


def _informado(valor: str | None) -> bool:
    return valor is not None and valor.strip() != ""


def _aliquota(
    valor: str | None,
    caminho: str,
    codigo: str,
    erros: list[ErroDetalhe],
) -> Decimal | None:
    if not _informado(valor):
        return None
    assert valor is not None
    texto = valor.strip()
    if _FORMATO.fullmatch(texto):
        return Decimal(texto)
    negativo = texto.startswith("-") and _FORMATO.fullmatch(texto[1:]) is not None
    detalhe = (
        f"O valor não pode ser negativo, recebido: '{valor}'."
        if negativo
        else (
            f"O valor não é um número decimal válido, recebido: '{valor}'. Informe {_DESCRICAO}."
        )
    )
    erros.append(ErroDetalhe(codigo, f"#/{_RAIZ}/{caminho}", detalhe))
    return None


def _par(
    p_cbssn: str | None,
    p_ibssn: str | None,
    caminho: str,
    erros: list[ErroDetalhe],
) -> ParAliquotas:
    return ParAliquotas(
        _aliquota(p_cbssn, f"{caminho}/pCBSSN", _CBS, erros),
        _aliquota(p_ibssn, f"{caminho}/pIBSSN", _IBS, erros),
    )


def _anexo_unico(anexo: AnexoUnico | None, caminho: str, erros: list[ErroDetalhe]) -> AliquotasAnexo | None:
    if anexo is None:
        return None
    return AliquotasAnexo(_par(anexo.p_cbssn, anexo.p_ibssn, caminho, erros))


def _anexo_iss(anexo: AnexoComIss | None, caminho: str, erros: list[ErroDetalhe]) -> AliquotasAnexo | None:
    if anexo is None:
        return None
    sem = anexo.sem_redistribuicao
    sem_informado = sem is not None and (_informado(sem.p_cbssn) or _informado(sem.p_ibssn))
    return AliquotasAnexo(
        _par(anexo.p_cbssn, anexo.p_ibssn, caminho, erros),
        _par(sem.p_cbssn, sem.p_ibssn, f"{caminho}/semRedistribuicaoISS", erros) if sem_informado and sem else None,
    )


def ler_linha_requisicao(aliquotas: AliquotasEfetivas | None) -> LinhaAliquotas:
    if aliquotas is None:
        raise ErrosCalculoException(
            [
                ErroDetalhe(
                    _AUSENTE,
                    f"#/{_RAIZ}",
                    "A linha de alíquotas efetivas do contribuinte (aliquotasEfetivas) é obrigatória no cálculo "
                    "não assistido quando o regime calcula tributos.",
                )
            ]
        )
    erros: list[ErroDetalhe] = []
    linha = LinhaAliquotas(
        aliquotas.fator_r,
        bool(aliquotas.impedimento_sublimite),
        _anexo_unico(aliquotas.anexo_i, "anexoI", erros),
        _anexo_unico(aliquotas.anexo_ii, "anexoII", erros),
        _anexo_iss(aliquotas.anexo_iii, "anexoIII", erros),
        _anexo_iss(aliquotas.anexo_iv, "anexoIV", erros),
        _anexo_iss(aliquotas.anexo_v, "anexoV", erros),
    )
    if erros:
        raise ErrosCalculoException(erros)
    return linha


@dataclass
class OperacaoNaoAssistida:
    id: str | None = None
    versao: str | None = None
    data: str | None = None
    tp_doc: str | None = None
    crt: str | None = None
    tp_regime_ibscbs: str | None = None
    op_simp_nac: str | None = None
    reg_ap_ibscbssn: str | None = None
    reg_ap_trib_sn: str | None = None
    tp_ente_gov: str | None = None
    itens: list[ItemSimplesUnificadoInput] = field(default_factory=list)
    aliquotas: AliquotasEfetivas | None = None


def processar_operacao(operacao: OperacaoNaoAssistida) -> ObservabilidadeSimples:
    """Núcleo do não assistido: a linha do corpo entra em ``CalculoSimplesUnificadoService``."""
    dados = DadosOperacaoSimples(
        operacao.id,
        operacao.versao,
        operacao.data,
        operacao.tp_doc,
        operacao.crt,
        operacao.tp_regime_ibscbs,
        operacao.op_simp_nac,
        operacao.reg_ap_ibscbssn,
        operacao.reg_ap_trib_sn,
        operacao.tp_ente_gov,
        operacao.itens,
    )
    return CalculoSimplesUnificadoService().processar(dados, FonteRequisicao(operacao.aliquotas))


class FonteRequisicao:
    def __init__(self, aliquotas: AliquotasEfetivas | None) -> None:
        self._aliquotas = aliquotas

    def obter(self, data: date) -> LinhaAliquotasComOrigem:
        del data
        return LinhaAliquotasComOrigem(ler_linha_requisicao(self._aliquotas), OrigemLinhaAliquotas.REQUISICAO)

    def montar_resolucao(
        self,
        linha: LinhaAliquotasComOrigem,
        itens: list[ResolucaoAliquotaItem],
        avisos: list[str],
    ) -> ResolucaoAliquotas:
        eff = linha.linha
        return ResolucaoAliquotas(
            tuple(itens),
            tuple(avisos),
            eff.fator_r,
            eff.impedimento_sublimite,
        )
