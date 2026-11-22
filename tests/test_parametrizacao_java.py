"""Espelho de ``ParametrizacaoSimplesNacionalTest`` (pin a926d5a7), carga via ParametroCalculo."""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

import pytest

os.environ.setdefault(
    "CALC_DB",
    "/home/garusotec/projects/lynko/libs/calculadora-rtc-simples-nacional/.cache/oficial/java/calculadora/db/calculadora-pro.db",
)

from calculadora_rtc_simples_nacional.escolha import RegraAliquota, TipoAliquota, VocabularioRegime
from calculadora_rtc_simples_nacional.parametro import (
    CodigoRegimeApuracao,
    DestinoValor,
    ParametroCalculo,
    RegimeCalculo,
    banco_disponivel,
    buscar_vinculos_tpdoc_vigentes,
    contar_tratamentos_nao_implementados,
    listar_atividades_vigentes,
    listar_transicao_compra_gov,
)

_CLASSNAME = "br.gov.serpro.rtc.testesintegracao.simplesnacional.ParametrizacaoSimplesNacionalTest"
DATA_PADRAO = date(2027, 3, 15)

pytestmark = pytest.mark.skipif(not banco_disponivel(), reason="calculadora-pro.db ausente")


def _junit(record_xml_attribute, name: str) -> None:
    record_xml_attribute("classname", _CLASSNAME)
    record_xml_attribute("name", name)


def _assert_tipo_receita(
    parametro: ParametroCalculo,
    data: date,
    is_compoe_receita: bool,
    codigo: int,
    descricao: str,
    compoe_receita: bool,
    fator_receita: str,
    pendente_suspenso: bool,
    exige_aliquota: bool,
    vedado_nao_tributavel: bool,
) -> None:
    tipo = parametro.buscar_tipo_receita_bruta(codigo, data)
    assert tipo is not None, f"tpRBSN {codigo} deveria ter linha vigente em {data}"
    assert tipo.descricao == descricao
    assert tipo.compoe_receita == compoe_receita
    assert tipo.imposto_seletivo_compoe_receita == is_compoe_receita
    assert tipo.fator_receita == Decimal(fator_receita)
    assert tipo.pendente_suspenso == pendente_suspenso
    assert tipo.exige_aliquota == exige_aliquota
    assert tipo.vedado_nao_tributavel == vedado_nao_tributavel


def _assert_matriz_tipos_receita(parametro: ParametroCalculo, data: date, is_compoe_receita: bool) -> None:
    _assert_tipo_receita(
        parametro, data, is_compoe_receita, 0, "Não é receita bruta", False, "0", False, False, False
    )
    _assert_tipo_receita(
        parametro, data, is_compoe_receita, 1, "Receita bruta - interna", True, "1", False, True, True
    )
    _assert_tipo_receita(
        parametro,
        data,
        is_compoe_receita,
        2,
        "Receita bruta - interna sem cálculo de IBS e CBS",
        True,
        "0",
        False,
        False,
        True,
    )
    _assert_tipo_receita(
        parametro,
        data,
        is_compoe_receita,
        3,
        "Receita bruta - exportação direta",
        True,
        "0",
        False,
        False,
        True,
    )
    _assert_tipo_receita(
        parametro,
        data,
        is_compoe_receita,
        4,
        "Receita bruta - exportação indireta",
        True,
        "1",
        True,
        True,
        True,
    )
    _assert_tipo_receita(
        parametro,
        data,
        is_compoe_receita,
        5,
        "Receita bruta - mercado interno e exportação",
        True,
        "0.5",
        False,
        True,
        True,
    )
    _assert_tipo_receita(
        parametro,
        data,
        is_compoe_receita,
        9,
        "Fornecimento incompatível com SN",
        True,
        "0",
        False,
        False,
        False,
    )


@pytest.fixture
def parametro() -> ParametroCalculo:
    return ParametroCalculo()


class TesteParametrizacaoSimplesNacional:
    def test_classificacoesSemTratamentoImplementado_conformeACargaVigente(
        self, parametro: ParametroCalculo, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "classificacoesSemTratamentoImplementado_conformeACargaVigente")
        for codigo in (
            "550023",
            "620001",
            "620002",
            "620006",
            "620007",
            "800001",
            "800002",
            "810001",
            "811001",
            "811003",
            "830001",
            "221002",
            "221004",
        ):
            assert contar_tratamentos_nao_implementados(codigo, DATA_PADRAO) > 0
        for codigo in ("820001", "820005", "820008", "820009"):
            assert contar_tratamentos_nao_implementados(codigo, DATA_PADRAO) == 0
        for codigo in (
            "000001",
            "410001",
            "010001",
            "222001",
            "820001",
            "820002",
            "820003",
            "820004",
            "820005",
            "820006",
            "820007",
            "820008",
            "820009",
            "999999",
        ):
            assert contar_tratamentos_nao_implementados(codigo, DATA_PADRAO) == 0

    def test_classificacaoSemImplementacaoEncerradaEm2026_naoContaEm2027(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "classificacaoSemImplementacaoEncerradaEm2026_naoContaEm2027")
        for codigo in ("220001", "220002", "220003"):
            assert contar_tratamentos_nao_implementados(codigo, date(2026, 1, 1)) > 0
            assert contar_tratamentos_nao_implementados(codigo, DATA_PADRAO) == 0

    def test_tiposDeDocumentoSuportados_conformeACargaVigente(
        self, parametro: ParametroCalculo, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "tiposDeDocumentoSuportados_conformeACargaVigente")
        for tp_doc in (55, 65, 91, 57, 67, 63, 93, 62):
            assert parametro.tp_doc_suportado(tp_doc, DATA_PADRAO)
        assert not parametro.tp_doc_suportado(97, DATA_PADRAO)
        assert not parametro.tp_doc_suportado(83, DATA_PADRAO)

    def test_tiposDeReceitaBruta_cargaConformeAMatrizDaNt(
        self, parametro: ParametroCalculo, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "tiposDeReceitaBruta_cargaConformeAMatrizDaNt")
        for data in (DATA_PADRAO, date(2028, 6, 15), date(2033, 6, 15)):
            _assert_matriz_tipos_receita(parametro, data, False)

    def test_matrizDeRegime_cargaConformeANt(self, parametro: ParametroCalculo, record_xml_attribute) -> None:
        _junit(record_xml_attribute, "matrizDeRegime_cargaConformeANt")

        def assert_regime(
            regime: RegimeCalculo,
            gera_ibs: bool,
            destino_devido: DestinoValor,
            destino_pendente: DestinoValor,
        ) -> None:
            vigente = parametro.buscar_regime_apuracao(regime, DATA_PADRAO)
            assert vigente is not None
            assert vigente.gera_ibs == gera_ibs
            assert vigente.destino_devido == destino_devido
            assert vigente.destino_pendente == destino_pendente

        assert_regime(RegimeCalculo.CRT_1, True, DestinoValor.DEVIDO, DestinoValor.PENDENTE_SUSPENSO)
        assert_regime(RegimeCalculo.CRT_2, False, DestinoValor.DEVIDO, DestinoValor.PENDENTE_SUSPENSO)
        assert_regime(
            RegimeCalculo.CRT_3_TPREGIME_2, True, DestinoValor.PENDENTE_SUSPENSO, DestinoValor.ZERO
        )

    def test_tiposDeDocumento_caracteristicasDoCalculoPorDocumento(
        self, parametro: ParametroCalculo, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "tiposDeDocumento_caracteristicasDoCalculoPorDocumento")
        for tp_doc in (55, 65, 57, 67, 63, 93, 62):
            documento = parametro.buscar_tipo_dfe_calculo(tp_doc, DATA_PADRAO)
            assert documento is not None
            assert documento.vocabulario_regime == VocabularioRegime.CRT
            assert documento.casas_aliquota_calculo is None
            assert documento.maximo_itens is None
            assert documento.admite_imposto_seletivo is True
        nfse = parametro.buscar_tipo_dfe_calculo(91, DATA_PADRAO)
        assert nfse is not None
        assert nfse.vocabulario_regime == VocabularioRegime.NFSE
        assert nfse.casas_aliquota_calculo == 2
        assert nfse.maximo_itens == 1
        assert nfse.admite_imposto_seletivo is False
        assert parametro.buscar_tipo_dfe_calculo(97, DATA_PADRAO) is None

    def _enquadramento_crt(self, parametro: ParametroCalculo, crt: int, tp_regime: int | None):
        return parametro.buscar_regime_por_campos(
            VocabularioRegime.CRT, crt, tp_regime, None, None, DATA_PADRAO
        )

    def _enquadramento_nfse(self, parametro: ParametroCalculo, op_simp_nac: int, reg_ap: int):
        return parametro.buscar_regime_por_campos(
            VocabularioRegime.NFSE, None, None, op_simp_nac, reg_ap, DATA_PADRAO
        )

    def test_enquadramentoDoRegime_onzeCombinacoesQueLevamAUmRegime(
        self, parametro: ParametroCalculo, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "enquadramentoDoRegime_onzeCombinacoesQueLevamAUmRegime")
        assert self._enquadramento_crt(parametro, 1, None).codigo == CodigoRegimeApuracao.SN_PLENO
        assert self._enquadramento_crt(parametro, 2, None).codigo == CodigoRegimeApuracao.SN_SUBLIMITE
        assert self._enquadramento_crt(parametro, 1, 1).codigo == CodigoRegimeApuracao.SOMENTE_RECEITA
        assert self._enquadramento_crt(parametro, 2, 1).codigo == CodigoRegimeApuracao.SOMENTE_RECEITA
        assert self._enquadramento_crt(parametro, 3, 2).codigo == CodigoRegimeApuracao.PENDENTE
        assert self._enquadramento_nfse(parametro, 3, 1).codigo == CodigoRegimeApuracao.SN_PLENO
        assert self._enquadramento_nfse(parametro, 3, 2).codigo == CodigoRegimeApuracao.SN_SUBLIMITE
        assert self._enquadramento_nfse(parametro, 3, 3).codigo == CodigoRegimeApuracao.SOMENTE_RECEITA
        assert self._enquadramento_nfse(parametro, 4, 1).codigo == CodigoRegimeApuracao.PENDENTE
        assert self._enquadramento_nfse(parametro, 4, 2).codigo == CodigoRegimeApuracao.PENDENTE_SUBLIMITE
        assert self._enquadramento_nfse(parametro, 4, 3).codigo == CodigoRegimeApuracao.SOMENTE_RECEITA

    def test_enquadramentoDoRegime_combinacoesValidasSemLinha_foraDoEscopo(
        self, parametro: ParametroCalculo, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "enquadramentoDoRegime_combinacoesValidasSemLinha_foraDoEscopo")
        assert self._enquadramento_crt(parametro, 3, None) is None
        assert self._enquadramento_crt(parametro, 4, None) is None
        for op_simp_nac in (1, 2):
            for reg_ap in (1, 2, 3):
                assert self._enquadramento_nfse(parametro, op_simp_nac, reg_ap) is None
        assert (
            parametro.buscar_regime_por_campos(
                VocabularioRegime.CRT, None, None, 3, 1, DATA_PADRAO
            )
            is None
        )

    def test_regimesDeApuracao_comportamentoPorCodigoNeutro(
        self, parametro: ParametroCalculo, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "regimesDeApuracao_comportamentoPorCodigoNeutro")
        pendente_sublimite = self._enquadramento_nfse(parametro, 4, 2)
        assert pendente_sublimite is not None
        assert pendente_sublimite.codigo == CodigoRegimeApuracao.PENDENTE_SUBLIMITE
        assert pendente_sublimite.calcula_tributos is True
        assert pendente_sublimite.gera_ibs is False
        assert pendente_sublimite.destino_devido == DestinoValor.PENDENTE_SUSPENSO
        assert pendente_sublimite.destino_pendente == DestinoValor.ZERO

        somente_receita = self._enquadramento_crt(parametro, 1, 1)
        assert somente_receita is not None
        assert somente_receita.codigo == CodigoRegimeApuracao.SOMENTE_RECEITA
        assert somente_receita.calcula_tributos is False
        assert somente_receita.gera_ibs is None
        assert somente_receita.destino_devido is None
        assert somente_receita.destino_pendente is None

        sn_pleno = self._enquadramento_crt(parametro, 1, None)
        assert sn_pleno is not None
        assert sn_pleno.codigo == CodigoRegimeApuracao.SN_PLENO
        assert sn_pleno.calcula_tributos is True
        assert sn_pleno.gera_ibs is True
        assert sn_pleno.destino_devido == DestinoValor.DEVIDO
        assert sn_pleno.destino_pendente == DestinoValor.PENDENTE_SUSPENSO
        assert sn_pleno.id == 1
        assert self._enquadramento_crt(parametro, 2, None).id == 2
        assert self._enquadramento_crt(parametro, 3, 2).id == 3
        assert self._enquadramento_crt(parametro, 2, None).id == self._enquadramento_nfse(parametro, 3, 2).id

    def test_tiposDeReceitaBruta_linhasDaNfse(
        self, parametro: ParametroCalculo, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "tiposDeReceitaBruta_linhasDaNfse")
        for codigo in (0, 1, 2, 3, 4, 5, 9):
            padrao = parametro.buscar_tipo_receita_bruta(codigo, DATA_PADRAO)
            nfse = parametro.buscar_tipo_receita_bruta(codigo, DATA_PADRAO, VocabularioRegime.NFSE)
            assert padrao is not None and nfse is not None
            assert padrao.vocabulario_regime is None
            assert nfse.vocabulario_regime == VocabularioRegime.NFSE
            assert padrao.descricao == nfse.descricao
            assert padrao.compoe_receita == nfse.compoe_receita
            assert padrao.vedado_nao_tributavel == nfse.vedado_nao_tributavel
            assert nfse.imposto_seletivo_compoe_receita is False
            assert nfse.pendente_suspenso is False
            assert nfse.fator_receita == Decimal("1" if codigo == 1 else "0")
            assert nfse.exige_aliquota == (codigo == 1)
        crt_linha = parametro.buscar_tipo_receita_bruta(4, DATA_PADRAO, VocabularioRegime.CRT)
        assert crt_linha is not None
        assert crt_linha.vocabulario_regime is None

    def test_catalogoDeAtividades_indicadoresDeIss(self, record_xml_attribute) -> None:
        _junit(record_xml_attribute, "catalogoDeAtividades_indicadoresDeIss")
        por_codigo = {a.codigo: a for a in listar_atividades_vigentes(DATA_PADRAO)}
        com_iss = {"07", "09", "10", "12", "13", "14"}
        com_beneficio = {"12", "13"}
        for codigo, atividade in por_codigo.items():
            assert atividade.iss_no_simples == (codigo in com_iss)
            assert atividade.admite_beneficio_municipal == (codigo in com_beneficio)

    def test_situacoesDoIss_cargaConformeASecao6(
        self, parametro: ParametroCalculo, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "situacoesDoIss_cargaConformeASecao6")
        situacoes = parametro.buscar_situacoes_iss_par_aliquota(DATA_PADRAO)
        assert len(situacoes) == 10
        por_regra: dict[str, list[str]] = defaultdict(list)
        for situacao in situacoes:
            por_regra[situacao.regra.value].append(f"{situacao.campo}={situacao.valor}")
        assert por_regra[RegraAliquota.ISS_FORA_DO_SIMPLES.value] == [
            "CRT=2",
            "regApIBSCBSSN=2",
            "regApTribSN=2",
            "regApTribSN=3",
        ]
        assert por_regra[RegraAliquota.ISS_NAO_INCIDE.value] == [
            "tribISSQN=2",
            "tribISSQN=3",
            "tribISSQN=4",
        ]
        assert por_regra[RegraAliquota.ISENCAO_MUNICIPAL.value] == ["tpBM=1"]
        assert por_regra[RegraAliquota.ISS_RETIDO.value] == ["tpRetISSQN=2", "tpRetISSQN=3"]
        for situacao in situacoes:
            assert situacao.tipo_aliquota == TipoAliquota.SEM_REDISTRIBUICAO
            assert situacao.ordem == list(RegraAliquota).index(situacao.regra) + 1

    def test_transicaoCompraGov_vigenciasContiguasESemSobreposicaoDe2027a2035(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "transicaoCompraGov_vigenciasContiguasESemSobreposicaoDe2027a2035")
        linhas = listar_transicao_compra_gov()
        assert len(linhas) == 6
        data = date(2027, 1, 1)
        fim = date(2035, 12, 31)
        while data <= fim:
            vigentes = sum(
                1
                for t in linhas
                if data >= t.inicio_vigencia and (t.fim_vigencia is None or data <= t.fim_vigencia)
            )
            assert vigentes == 1, f"data {data} deveria ter exatamente uma vigência, encontrou {vigentes}"
            data += timedelta(days=1)

    def test_transicaoCompraGov_dataAnteriorATodaVigencia_retornaVazio(
        self, parametro: ParametroCalculo, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "transicaoCompraGov_dataAnteriorATodaVigencia_retornaVazio")
        assert parametro.buscar_fator_transicao_compra_gov(date(2025, 12, 31)) is None

    def test_transicaoCompraGov_fatoresConformeANt(
        self, parametro: ParametroCalculo, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "transicaoCompraGov_fatoresConformeANt")
        casos = (
            ("0.00", date(2027, 1, 1)),
            ("0.00", date(2028, 12, 31)),
            ("0.10", date(2029, 6, 1)),
            ("0.20", date(2030, 6, 1)),
            ("0.30", date(2031, 6, 1)),
            ("0.40", date(2032, 6, 1)),
            ("1.00", date(2033, 1, 1)),
            ("1.00", date(2099, 12, 31)),
        )
        for esperado, data in casos:
            fator = parametro.buscar_fator_transicao_compra_gov(data)
            assert fator is not None, f"sem vigência para {data}"
            assert fator == Decimal(esperado)

    def test_catalogoDeAtividades_quinzeLinhasComCodigosOficiaisEIndicadorNaoTributavel(
        self, record_xml_attribute
    ) -> None:
        _junit(
            record_xml_attribute,
            "catalogoDeAtividades_quinzeLinhasComCodigosOficiaisEIndicadorNaoTributavel",
        )
        atividades = listar_atividades_vigentes(DATA_PADRAO)
        assert len(atividades) == 15
        por_ordem = {a.ordem: a for a in atividades}
        for ordem in range(1, 15):
            atividade = por_ordem[ordem]
            assert atividade is not None
            assert atividade.codigo == f"{ordem:02d}"
            assert atividade.nao_tributavel is False
        nao_tributavel = por_ordem[15]
        assert nao_tributavel.codigo == "90"
        assert nao_tributavel.nao_tributavel is True
        assert nao_tributavel.anexo_sem_fator_r is None
        assert nao_tributavel.anexo_com_fator_r is None
        assert por_ordem[9].anexo_sem_fator_r == "V"
        assert por_ordem[9].anexo_com_fator_r == "III"
        for ordem in range(1, 15):
            if ordem != 9:
                assert por_ordem[ordem].anexo_com_fator_r is None
        assert "7.02 e 7.05" in por_ordem[12].descricao
        assert "7.02 e 7.05" in por_ordem[13].descricao
        assert "ferroviário" in por_ordem[10].descricao
        assert "16.01" in por_ordem[10].descricao

    def test_associativaDeAtividades_vinculosVigentesConformeACarga(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, "associativaDeAtividades_vinculosVigentesConformeACarga")
        atividades = listar_atividades_vigentes(DATA_PADRAO)
        por_id = {a.id: a for a in atividades}
        vinculos = buscar_vinculos_tpdoc_vigentes(DATA_PADRAO)
        assert len(vinculos) == 29
        tp_docs_por_codigo: dict[str, list[int]] = defaultdict(list)
        for v in vinculos:
            codigo = por_id[v.atividade_id].codigo
            tp_docs_por_codigo[codigo].append(v.tp_doc)
        for codigo in tp_docs_por_codigo:
            tp_docs_por_codigo[codigo].sort()
        for codigo in ("01", "02", "03", "04"):
            assert tp_docs_por_codigo[codigo] == [55, 65]
        for codigo in ("07", "08", "09", "10", "11", "12", "13", "14"):
            assert tp_docs_por_codigo[codigo] == [91]
        assert tp_docs_por_codigo["05"] == [57, 63, 67, 93]
        assert tp_docs_por_codigo["06"] == [62]
        assert tp_docs_por_codigo["90"] == [55, 57, 62, 63, 65, 67, 91, 93]