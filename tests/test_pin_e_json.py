"""O pin oficial fica no pacote, e o JSON não perde dígito no float."""

from decimal import Decimal

from calculadora_rtc_simples_nacional import (
    PIN_FLYWAY_COMMIT,
    PIN_FLYWAY_VERSAO,
    PIN_OFICIAL_COMMIT,
    PIN_OFICIAL_DATA,
    PIN_OFICIAL_VERSAO,
)
from calculadora_rtc_simples_nacional.json_input import item_simples_unificado_de_json


def test_pin_oficial_e_o_calculador_1_0_2() -> None:
    assert PIN_OFICIAL_VERSAO == "1.0.2"
    assert PIN_OFICIAL_COMMIT == "a926d5a76095ac0295a6612a9a54db7ffead2396"
    assert PIN_OFICIAL_DATA == "2026-11-20"
    assert PIN_FLYWAY_VERSAO == "1.7.2"
    assert PIN_FLYWAY_COMMIT == "f1eebd7ce3157423b1a6aaca7dc1d6c3395452c4"


def test_json_preserva_decimal_que_o_float_perde() -> None:
    item = item_simples_unificado_de_json('{"baseCalculo": 1234567890123456789.25}')
    assert item.base_calculo == "1234567890123456789.25"
    assert Decimal(item.base_calculo) == Decimal("1234567890123456789.25")
