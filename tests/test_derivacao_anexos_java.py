"""Espelho de ``Teste_DerivacaoAnexosSimples`` (pin a926d5a7), regra pura sem Spring."""

from __future__ import annotations

import pytest

from calculadora_rtc_simples_nacional.atividade import Derivacao, ModoFatorR, derivar_anexos

_CLASSNAME = (
    "br.gov.serpro.rtc.testesunitarios.atividadesimples.Teste_DerivacaoAnexosSimples"
)


def _junit(record_xml_attribute, name: str) -> None:
    record_xml_attribute("classname", _CLASSNAME)
    record_xml_attribute("name", name)


def _atividade9(anexos: set[str] | None) -> Derivacao:
    return derivar_anexos("V", "III", anexos)


def _atividade2(anexos: set[str] | None) -> Derivacao:
    return derivar_anexos("I", None, anexos)


class TesteDerivacaoAnexosSimplesJava:
    def teste_Atividade9_AnexosI_II_IndisponivelFaltandoIIIeV(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "teste_Atividade9_AnexosI_II_IndisponivelFaltandoIIIeV")
        derivacao = _atividade9({"I", "II"})
        assert derivacao.disponivel is False
        assert list(derivacao.anexos_faltantes) == ["III", "V"]
        assert derivacao.modo_fator_r is ModoFatorR.INDISPONIVEL

    def teste_Atividade9_AnexosI_V_DisponivelFatorRIndisponivel(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "teste_Atividade9_AnexosI_V_DisponivelFatorRIndisponivel")
        derivacao = _atividade9({"I", "V"})
        assert derivacao.disponivel is True
        assert list(derivacao.anexos_faltantes) == ["III"]
        assert derivacao.modo_fator_r is ModoFatorR.INDISPONIVEL

    def teste_Atividade9_AnexosI_III_DisponivelFatorRObrigatorio(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "teste_Atividade9_AnexosI_III_DisponivelFatorRObrigatorio")
        derivacao = _atividade9({"I", "III"})
        assert derivacao.disponivel is True
        assert list(derivacao.anexos_faltantes) == ["V"]
        assert derivacao.modo_fator_r is ModoFatorR.OBRIGATORIO

    def teste_Atividade9_AnexosIII_V_DisponivelFatorROpcional(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "teste_Atividade9_AnexosIII_V_DisponivelFatorROpcional")
        derivacao = _atividade9({"III", "V"})
        assert derivacao.disponivel is True
        assert list(derivacao.anexos_faltantes) == []
        assert derivacao.modo_fator_r is ModoFatorR.OPCIONAL

    def teste_Atividade9_SemParametro_DisponivelFatorROpcional(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "teste_Atividade9_SemParametro_DisponivelFatorROpcional")
        derivacao = _atividade9(None)
        assert derivacao.disponivel is True
        assert list(derivacao.anexos_faltantes) == []
        assert derivacao.modo_fator_r is ModoFatorR.OPCIONAL

    def teste_Atividade9_ConjuntoVazio_IndisponivelFaltandoIIIeV(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "teste_Atividade9_ConjuntoVazio_IndisponivelFaltandoIIIeV")
        derivacao = _atividade9(set())
        assert derivacao.disponivel is False
        assert list(derivacao.anexos_faltantes) == ["III", "V"]
        assert derivacao.modo_fator_r is ModoFatorR.INDISPONIVEL

    def teste_Atividade2_AnexosI_II_DisponivelNaoAplicavel(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "teste_Atividade2_AnexosI_II_DisponivelNaoAplicavel")
        derivacao = _atividade2({"I", "II"})
        assert derivacao.disponivel is True
        assert list(derivacao.anexos_faltantes) == []
        assert derivacao.modo_fator_r is ModoFatorR.NAO_APLICAVEL

    def teste_Atividade2_AnexosII_III_IndisponivelFaltandoI(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "teste_Atividade2_AnexosII_III_IndisponivelFaltandoI")
        derivacao = _atividade2({"II", "III"})
        assert derivacao.disponivel is False
        assert list(derivacao.anexos_faltantes) == ["I"]
        assert derivacao.modo_fator_r is ModoFatorR.NAO_APLICAVEL

    def teste_Atividade2_SemParametro_DisponivelNaoAplicavel(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "teste_Atividade2_SemParametro_DisponivelNaoAplicavel")
        derivacao = _atividade2(None)
        assert derivacao.disponivel is True
        assert list(derivacao.anexos_faltantes) == []
        assert derivacao.modo_fator_r is ModoFatorR.NAO_APLICAVEL

    def teste_AtividadeSemAnexo_SemParametro_SempreDisponivel(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "teste_AtividadeSemAnexo_SemParametro_SempreDisponivel")
        derivacao = derivar_anexos(None, None, None)
        assert derivacao.disponivel is True
        assert list(derivacao.anexos_faltantes) == []
        assert derivacao.modo_fator_r is ModoFatorR.NAO_APLICAVEL

    def teste_AtividadeSemAnexo_ConjuntoVazio_SempreDisponivel(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "teste_AtividadeSemAnexo_ConjuntoVazio_SempreDisponivel")
        derivacao = derivar_anexos(None, None, set())
        assert derivacao.disponivel is True
        assert list(derivacao.anexos_faltantes) == []
        assert derivacao.modo_fator_r is ModoFatorR.NAO_APLICAVEL

    def teste_AtividadeSemAnexo_ComAnexosConfigurados_SempreDisponivel(
        self, record_xml_attribute
    ) -> None:
        _junit(
            record_xml_attribute,
            "teste_AtividadeSemAnexo_ComAnexosConfigurados_SempreDisponivel",
        )
        derivacao = derivar_anexos(None, None, {"I", "V"})
        assert derivacao.disponivel is True
        assert list(derivacao.anexos_faltantes) == []
        assert derivacao.modo_fator_r is ModoFatorR.NAO_APLICAVEL

    def teste_Invariante_AnexoComFatorRSemAnexoSemFatorR_LancaExcecao(
        self, record_xml_attribute
    ) -> None:
        _junit(
            record_xml_attribute,
            "teste_Invariante_AnexoComFatorRSemAnexoSemFatorR_LancaExcecao",
        )
        with pytest.raises(ValueError):
            derivar_anexos(None, "III", None)

    def teste_AnexosFaltantes_SempreOrdenadosPorRomano(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "teste_AnexosFaltantes_SempreOrdenadosPorRomano")
        derivacao = derivar_anexos("V", "III", {"IV"})
        assert list(derivacao.anexos_faltantes) == ["III", "V"]