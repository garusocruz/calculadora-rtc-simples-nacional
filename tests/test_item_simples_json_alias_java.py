"""Espelho de ``Teste_ItemSimplesJsonAliasTest`` (pin a926d5a7)."""

from __future__ import annotations

from calculadora_rtc_simples_nacional.json_input import item_simples_unificado_de_json

_CLASSNAME = (
    "br.gov.serpro.rtc.testesunitarios.simplesnacional.Teste_ItemSimplesJsonAliasTest"
)


def _junit(record_xml_attribute, name: str) -> None:
    record_xml_attribute("classname", _CLASSNAME)
    record_xml_attribute("name", name)


def test_aliasMaiusculoNcmContinuaAceitoPorCompatibilidade(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "aliasMaiusculoNcmContinuaAceitoPorCompatibilidade")
    item = item_simples_unificado_de_json(
        """
        {"numero":1,"NCM":"22030000"}
        """
    )
    assert item.numero == 1
    assert item.ncm == "22030000"