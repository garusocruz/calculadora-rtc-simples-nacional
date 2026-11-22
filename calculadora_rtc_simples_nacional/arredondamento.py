"""Numeric policy shared by the two official calculators.

Pin ``f1eebd7ce3157423b1a6aaca7dc1d6c3395452c4``, class
``br.gov.serpro.rtc.shared.util.ArredondamentoUtils``. Addition, subtraction,
multiplication and percent/fraction conversion stay exact. Division is the only
internal rounding, at 34 significant digits, half-even. A published amount is
rounded once.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Context, Decimal, localcontext

MODO = ROUND_HALF_EVEN
ESCALA_VALOR_FISCAL = 2
ESCALA_ALIQUOTA_MIN = 2
ESCALA_ALIQUOTA_MAX = 4
ESCALA_QUANTIDADE = 4
CONTEXTO_DIVISAO = Context(prec=34, rounding=MODO)
CENTAVO = Decimal("0.01")


def multiplicar(v1: Decimal | None, v2: Decimal | None) -> Decimal | None:
    if v1 is None or v2 is None:
        return None
    return v1 * v2


def subtrair(v1: Decimal | None, v2: Decimal | None) -> Decimal | None:
    if v1 is None or v2 is None:
        return None
    return v1 - v2


def dividir(dividendo: Decimal | None, divisor: Decimal | None) -> Decimal | None:
    if dividendo is None or divisor is None:
        return None
    with localcontext(CONTEXTO_DIVISAO):
        return CONTEXTO_DIVISAO.divide(dividendo, divisor)


def totalizar(valores: list[Decimal]) -> Decimal:
    total = Decimal(0)
    for valor in valores:
        total += valor
    return total


def percentual_para_fracao(percentual: Decimal | None) -> Decimal | None:
    if percentual is None:
        return None
    return percentual.scaleb(-2)


def fracao_para_percentual(fracao: Decimal | None) -> Decimal | None:
    if fracao is None:
        return None
    return fracao.scaleb(2)


def arredondar_valor_fiscal(valor: Decimal | None) -> Decimal | None:
    if valor is None:
        return None
    return valor.quantize(CENTAVO, rounding=MODO)


def arredondar_aliquota_publicada(aliquota: Decimal | None) -> Decimal | None:
    if aliquota is None:
        return None
    return aliquota.quantize(Decimal("0.0001"), rounding=MODO)


def arredondar_aliquota(aliquota: Decimal | None, casas: int | None) -> Decimal | None:
    if aliquota is None or casas is None:
        return aliquota
    return aliquota.quantize(Decimal(1).scaleb(-casas), rounding=MODO)


def ratear_valor_fiscal(parcelas_exatas: list[Decimal]) -> list[Decimal]:
    total = arredondar_valor_fiscal(totalizar(parcelas_exatas))
    assert total is not None
    parcelas: list[Decimal] = []
    restos: list[Decimal] = []
    distribuido = Decimal(0)
    for exata in parcelas_exatas:
        truncada = exata.quantize(CENTAVO, rounding=ROUND_DOWN)
        parcelas.append(truncada)
        restos.append(exata - truncada)
        distribuido += truncada
    ordem = sorted(range(len(parcelas_exatas)), key=lambda index: restos[index], reverse=True)
    faltam = int((total - distribuido).scaleb(ESCALA_VALOR_FISCAL))
    for passo in range(faltam):
        posicao = ordem[passo % len(ordem)]
        parcelas[posicao] = parcelas[posicao] + CENTAVO
    return parcelas


def formatar_moeda(valor: Decimal) -> str:
    return format(valor.quantize(CENTAVO, rounding=MODO), "f")


def formatar_aliquota(valor: Decimal) -> str:
    scaled = valor.quantize(Decimal("0.0001"), rounding=MODO)
    stripped = _sem_zeros_a_direita(scaled)
    if _casas(stripped) < ESCALA_ALIQUOTA_MIN:
        stripped = stripped.quantize(CENTAVO)
    return format(stripped, "f")


def formatar_quantidade(valor: Decimal) -> str:
    stripped = _sem_zeros_a_direita(valor)
    if _casas(stripped) <= 0:
        return str(int(valor))
    return format(valor.quantize(Decimal("0.0001"), rounding=MODO), "f")


def _casas(valor: Decimal) -> int:
    expoente = valor.as_tuple().exponent
    if not isinstance(expoente, int):
        return 0
    return -expoente


def _sem_zeros_a_direita(valor: Decimal) -> Decimal:
    texto = format(valor, "f")
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".") or "0"
    return Decimal(texto)
