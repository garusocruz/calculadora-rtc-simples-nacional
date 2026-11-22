"""Sentido das dependências do núcleo, na lib Python.

A escolha da alíquota não importa o cálculo. A atividade não importa a escolha
da alíquota. O cálculo pode usar os dois.
"""

from __future__ import annotations

import ast
from pathlib import Path

_PACOTE = Path(__file__).resolve().parents[1] / "calculadora_rtc_simples_nacional"
_PREFIXO = "calculadora_rtc_simples_nacional"
_FQCN = "br.gov.serpro.rtc.testesunitarios.arquitetura.Teste_DependenciasNucleo"
_CALCULO = frozenset(
    {"simples", "processador", "unificado", "nao_assistido", "observabilidade", "consumo"}
)


def _junit(record_xml_attribute, name: str) -> None:
    record_xml_attribute("classname", _FQCN)
    record_xml_attribute("name", name)


def _importa(arquivo: Path) -> set[str]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    modulos: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and no.module and no.module.startswith(_PREFIXO):
            resto = no.module.removeprefix(_PREFIXO).strip(".")
            if resto:
                modulos.add(resto.split(".", 1)[0])
        elif isinstance(no, ast.Import):
            for apelido in no.names:
                if apelido.name.startswith(_PREFIXO):
                    resto = apelido.name.removeprefix(_PREFIXO).strip(".")
                    if resto:
                        modulos.add(resto.split(".", 1)[0])
    return modulos


def test_aliquotasNaoDependemDoCalculo(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "aliquotasNaoDependemDoCalculo")
    violacoes = sorted(_importa(_PACOTE / "escolha.py") & _CALCULO)
    assert violacoes == []


def test_atividadesNaoDependemDasAliquotas(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "atividadesNaoDependemDasAliquotas")
    violacoes = sorted(_importa(_PACOTE / "atividade.py") & {"escolha"})
    assert violacoes == []
