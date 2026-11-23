"""Implementação independente, em Python, do cálculo de CBS e IBS do Simples Nacional.

Não é produto oficial, homologado ou certificado da Receita Federal.
O pin é o CalculadorTributo 1.0.2, commit a926d5a76095ac0295a6612a9a54db7ffead2396.
O Flyway do banco é o do regime regular 1.7.2, commit f1eebd7ce3157423b1a6aaca7dc1d6c3395452c4.
"""

from calculadora_rtc_simples_nacional.simples import calcular_item

PIN_OFICIAL_VERSAO = "1.0.2"
PIN_OFICIAL_COMMIT = "a926d5a76095ac0295a6612a9a54db7ffead2396"
PIN_OFICIAL_DATA = "2026-11-20"
PIN_FLYWAY_VERSAO = "1.7.2"
PIN_FLYWAY_COMMIT = "f1eebd7ce3157423b1a6aaca7dc1d6c3395452c4"

__all__ = [
    "PIN_FLYWAY_COMMIT",
    "PIN_FLYWAY_VERSAO",
    "PIN_OFICIAL_COMMIT",
    "PIN_OFICIAL_DATA",
    "PIN_OFICIAL_VERSAO",
    "calcular_item",
]
