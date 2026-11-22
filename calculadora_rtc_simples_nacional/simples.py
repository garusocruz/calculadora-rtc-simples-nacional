"""Cálculo do Simples Nacional.

Pin ``a926d5a76095ac0295a6612a9a54db7ffead2396``, ``SimplesNacionalCalculoService``.
O serviço recebe o regime, o tipo de receita e as alíquotas já resolvidos. A
receita bruta, o deslocamento da compra governamental e o destino do valor
seguem as fórmulas desse pin.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from calculadora_rtc_simples_nacional.arredondamento import (
    arredondar_aliquota,
    arredondar_aliquota_publicada,
    arredondar_valor_fiscal,
    multiplicar,
    percentual_para_fracao,
    subtrair,
    totalizar,
)

ZERO = Decimal(0)


class EstadoItem(Enum):
    CALCULADO = "CALCULADO"
    NAO_CALCULADO = "NAO_CALCULADO"


class Destino(Enum):
    DEVIDO = "DEVIDO"
    PENDENTE_SUSPENSO = "PENDENTE_SUSPENSO"
    ZERO = "ZERO"


@dataclass(frozen=True)
class Motivo:
    codigo: str
    descricao: str


REGIME_SOMENTE_RECEITA = Motivo(
    "REGIME_SOMENTE_RECEITA",
    "O optante apura o IBS e a CBS pelo regime regular, fora do Simples Nacional; o item "
    "leva ao Simples apenas a receita bruta.",
)


@dataclass(frozen=True)
class Regime:
    codigo: str
    calcula_tributos: bool
    descricao: str
    gera_ibs: bool
    destino_devido: Destino
    destino_pendente: Destino


@dataclass(frozen=True)
class TipoReceita:
    codigo: int
    descricao: str
    compoe_receita: bool
    fator_receita: Decimal
    pendente_suspenso: bool
    imposto_seletivo_compoe_receita: bool = False
    exige_aliquota: bool = False
    vedado_nao_tributavel: bool = False


@dataclass(frozen=True)
class Insumo:
    regime: Regime
    tipo_receita: TipoReceita
    motivo_nao_calculo: Motivo | None
    base_calculo: Decimal | None
    valor_imposto_seletivo: Decimal | None
    aliquota_ibs: Decimal | None
    aliquota_cbs: Decimal | None
    ente_governamental: int | None
    fator_transicao: Decimal | None
    casas_aliquota: int | None = None


@dataclass(frozen=True)
class ImpostoSeletivo:
    valor: Decimal


@dataclass(frozen=True)
class Memoria:
    cbs: str
    ibs: str | None


@dataclass(frozen=True)
class Tributos:
    receita_bruta: Decimal
    tipo_receita: int
    descricao_tipo_receita: str
    base_calculo: Decimal | None = None
    aliquota_ibs: Decimal | None = None
    valor_ibs: Decimal | None = None
    ibs_pendente: Decimal | None = None
    aliquota_cbs: Decimal | None = None
    valor_cbs: Decimal | None = None
    cbs_pendente: Decimal | None = None
    imposto_seletivo: ImpostoSeletivo | None = None
    total_item: Decimal | None = None
    memoria: Memoria | None = None


@dataclass(frozen=True)
class Resultado:
    estado: EstadoItem
    motivo: Motivo | None
    tributos: Tributos


@dataclass(frozen=True)
class _Par:
    ibs: Decimal | None
    cbs: Decimal | None


@dataclass(frozen=True)
class _Valor:
    devido: Decimal
    pendente: Decimal


def calcular_item(insumo: Insumo) -> Resultado:
    tipo = insumo.tipo_receita
    if tipo.compoe_receita:
        partes = [insumo.base_calculo]
        if tipo.imposto_seletivo_compoe_receita:
            partes.append(insumo.valor_imposto_seletivo)
        receita = arredondar_valor_fiscal(totalizar([parte for parte in partes if parte is not None]))
    else:
        receita = ZERO
    assert receita is not None
    motivo = REGIME_SOMENTE_RECEITA if not insumo.regime.calcula_tributos else insumo.motivo_nao_calculo
    if motivo is not None:
        return Resultado(
            EstadoItem.NAO_CALCULADO,
            motivo,
            Tributos(receita, tipo.codigo, tipo.descricao),
        )
    aliquotas = _arredondar_leiaute(
        _deslocar(
            _Par(insumo.aliquota_ibs, insumo.aliquota_cbs),
            insumo.ente_governamental,
            insumo.fator_transicao,
        ),
        insumo.casas_aliquota,
    )
    fator = tipo.fator_receita
    base = arredondar_valor_fiscal(multiplicar(receita, fator))
    valor_ibs = arredondar_valor_fiscal(_valor_tributo(receita, fator, aliquotas.ibs))
    valor_cbs = arredondar_valor_fiscal(_valor_tributo(receita, fator, aliquotas.cbs))
    assert valor_ibs is not None and valor_cbs is not None
    ibs = _repartir(insumo.regime, valor_ibs, tipo.pendente_suspenso) if insumo.regime.gera_ibs else None
    cbs = _repartir(insumo.regime, valor_cbs, tipo.pendente_suspenso)
    seletivo = insumo.valor_imposto_seletivo
    total = totalizar(
        [parte for parte in (ibs.devido if ibs is not None else None, cbs.devido, seletivo) if parte is not None]
    )
    return Resultado(
        EstadoItem.CALCULADO,
        None,
        Tributos(
            receita,
            tipo.codigo,
            tipo.descricao,
            base,
            arredondar_aliquota_publicada(aliquotas.ibs) if insumo.regime.gera_ibs else None,
            ibs.devido if ibs is not None else None,
            ibs.pendente if ibs is not None else None,
            arredondar_aliquota_publicada(aliquotas.cbs),
            cbs.devido,
            cbs.pendente,
            ImpostoSeletivo(seletivo) if seletivo is not None else None,
            total,
            Memoria(
                _memoria(tipo, receita, base, aliquotas.cbs, cbs),
                _memoria(tipo, receita, base, aliquotas.ibs, ibs) if ibs is not None else None,
            ),
        ),
    )


def _deslocar(aliquotas: _Par, ente: int | None, fator: Decimal | None) -> _Par:
    if ente is None or (aliquotas.ibs is None and aliquotas.cbs is None):
        return aliquotas
    ibs = aliquotas.ibs if aliquotas.ibs is not None else ZERO
    cbs = aliquotas.cbs if aliquotas.cbs is not None else ZERO
    if ente == 1:
        return _Par(ZERO, totalizar([cbs, ibs]))
    if fator is None:
        raise ValueError(f"Fator de transição de compra governamental não resolvido para tpEnteGov {ente}")
    ibs_transformado = totalizar([ibs, multiplicar(fator, cbs)])
    cbs_transformado = multiplicar(subtrair(Decimal(1), fator), cbs)
    return _Par(ibs_transformado, cbs_transformado)


def _arredondar_leiaute(aliquotas: _Par, casas: int | None) -> _Par:
    """``casas`` nulo = precisão integral no cálculo (clássico); publicação via ``formatar_aliquota``."""
    if casas is not None:
        return _Par(arredondar_aliquota(aliquotas.ibs, casas), arredondar_aliquota(aliquotas.cbs, casas))
    return aliquotas


def _valor_tributo(receita: Decimal, fator: Decimal, aliquota: Decimal | None) -> Decimal:
    if aliquota is None or fator == 0:
        return ZERO
    return multiplicar(multiplicar(receita, fator), percentual_para_fracao(aliquota)) or ZERO


def _repartir(regime: Regime, valor: Decimal, pendente: bool) -> _Valor:
    destino = regime.destino_pendente if pendente else regime.destino_devido
    if destino is Destino.DEVIDO:
        return _Valor(valor, ZERO)
    if destino is Destino.PENDENTE_SUSPENSO:
        return _Valor(ZERO, valor)
    return _Valor(ZERO, ZERO)


def _memoria(tipo: TipoReceita, receita: Decimal, base: Decimal | None, aliquota: Decimal | None, valor: _Valor) -> str:
    return (
        f"Receita bruta do Simples Nacional de R$ {_moeda(receita)} ({tipo.descricao}). "
        f"A base de cálculo utilizada é de R$ {_moeda(base)}, com alíquota efetiva de {_percentual(aliquota)}%. "
        f"Valor devido de R$ {_moeda(valor.devido)} e pendente/suspenso de R$ {_moeda(valor.pendente)}."
    )


def _moeda(valor: Decimal | None) -> str:
    numero = arredondar_valor_fiscal(valor if valor is not None else ZERO)
    assert numero is not None
    return _agrupar(numero, 2, 2)


def _percentual(valor: Decimal | None) -> str:
    numero = arredondar_aliquota_publicada(valor if valor is not None else ZERO)
    assert numero is not None
    return _agrupar(numero, 2, 4)


def _agrupar(numero: Decimal, minimo: int, maximo: int) -> str:
    sinal = "-" if numero < 0 else ""
    texto = format(abs(numero), "f")
    inteiro, _, fracao = texto.partition(".")
    fracao = (fracao + ("0" * maximo))[:maximo].rstrip("0")
    if len(fracao) < minimo:
        fracao = fracao.ljust(minimo, "0")
    grupos: list[str] = []
    while inteiro:
        grupos.append(inteiro[-3:])
        inteiro = inteiro[:-3]
    return f"{sinal}{'.'.join(reversed(grupos))},{fracao}"
