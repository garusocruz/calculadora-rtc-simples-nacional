"""Arquitetura da política numérica na lib Python.

Só ``arredondamento.py`` arredonda. O mesmo arquivo, byte a byte, vale para o
regime regular e para o Simples.
"""

from __future__ import annotations

import hashlib
import io
import re
import tokenize
from pathlib import Path

import pytest

_PACOTE = Path(__file__).resolve().parents[1] / "calculadora_rtc_simples_nacional"
_POLITICA = _PACOTE / "arredondamento.py"
_OUTRA = (
    Path(__file__).resolve().parents[2]
    / "calculadora-rtc-regime-regular"
    / "calculadora_rtc_regime_regular"
    / "arredondamento.py"
)
_SHA256 = "6f0defcc9d529267ba8b1c6268bc66ad4a7753392f1778fccb94d58a78b54223"
_FQCN_POLITICA = "br.gov.serpro.rtc.testesunitarios.shared.Teste_ArquiteturaArredondamento"
_FQCN_COPIA = "br.gov.serpro.rtc.testesunitarios.shared.Teste_ArredondamentoUtilsCopiaUnica"

_PROIBIDOS = (
    re.compile(r"\.quantize\s*\("),
    re.compile(r"\bROUND_[A-Z0-9_]+\b"),
    re.compile(r"\blocalcontext\s*\("),
    re.compile(r"\bContext\s*\("),
    re.compile(r"\bgetcontext\s*\("),
)


def _junit(record_xml_attribute, classname: str, name: str) -> None:
    record_xml_attribute("classname", classname)
    record_xml_attribute("name", name)


def _sem_comentarios(codigo: str) -> str:
    saida: list[tokenize.TokenInfo] = []
    for token in tokenize.generate_tokens(io.StringIO(codigo).readline):
        if token.type == tokenize.COMMENT:
            continue
        saida.append(token)
    return tokenize.untokenize(saida)


def _sha256(caminho: Path) -> str:
    texto = caminho.read_text(encoding="utf-8").replace("\r\n", "\n")
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def test_soAClasseDaPoliticaArredonda(record_xml_attribute) -> None:
    _junit(record_xml_attribute, _FQCN_POLITICA, "soAClasseDaPoliticaArredonda")
    arquivos = sorted(_PACOTE.glob("*.py"))
    assert len(arquivos) > 10
    assert _POLITICA in arquivos
    ocorrencias: list[str] = []
    for arquivo in arquivos:
        if arquivo.name == "arredondamento.py":
            continue
        codigo = _sem_comentarios(arquivo.read_text(encoding="utf-8"))
        for proibido in _PROIBIDOS:
            for achado in proibido.finditer(codigo):
                linha = codigo.rfind("\n", 0, achado.start()) + 1
                fim = codigo.find("\n", achado.start())
                trecho = codigo[linha:] if fim < 0 else codigo[linha:fim]
                ocorrencias.append(f"{arquivo.name}: {trecho.strip()}")
    assert ocorrencias == []


def test_asRegrasPegamOQueDevemPegar(record_xml_attribute) -> None:
    _junit(record_xml_attribute, _FQCN_POLITICA, "asRegrasPegamOQueDevemPegar")
    proibido = """
valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
with localcontext(Context(prec=34, rounding=ROUND_DOWN)):
    getcontext()
"""
    achados = sum(len(padrao.findall(proibido)) for padrao in _PROIBIDOS)
    assert achados == 6
    permitido = _sem_comentarios(
        """
# valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
arredondar_valor_fiscal(valor)
"""
    )
    for padrao in _PROIBIDOS:
        assert padrao.findall(permitido) == []


def test_classe_eACopiaUnicaDosDoisProjetos(record_xml_attribute) -> None:
    _junit(record_xml_attribute, _FQCN_COPIA, "classe_eACopiaUnicaDosDoisProjetos")
    assert _sha256(_POLITICA) == _SHA256


def test_testeDaClasse_eACopiaUnicaDosDoisProjetos(record_xml_attribute) -> None:
    if not _OUTRA.is_file():
        pytest.skip("a outra lib não está neste checkout")
    _junit(record_xml_attribute, _FQCN_COPIA, "testeDaClasse_eACopiaUnicaDosDoisProjetos")
    assert _sha256(_OUTRA) == _SHA256
