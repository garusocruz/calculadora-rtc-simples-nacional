from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from calculadora_rtc_simples_nacional import atividade
from calculadora_rtc_simples_nacional.atividade import (
    AtividadeSimplesService,
    ErroConsultaAtividade,
    ModoFatorR,
    derivar_anexos,
)
from calculadora_rtc_simples_nacional.parametro import (
    ClassificacaoTributaria,
    TipoReceitaBruta,
    VocabularioRegime,
    banco_disponivel,
)

DATA = date(2027, 3, 15)
DATA_CATALOGO = date(2027, 1, 1)
pytestmark_integracao = pytest.mark.skipif(not banco_disponivel(), reason="calculadora-pro.db ausente")


def _ativ(
    id_: int, ordem: int, codigo: str, anexo_sem: str | None
) -> atividade._AtividadeVigente:
    return atividade._AtividadeVigente(
        id_,
        ordem,
        f"Atividade {codigo}",
        codigo,
        anexo_sem,
        None,
        anexo_sem or "Não tributável",
        anexo_sem or "Não tributável",
        anexo_sem is None,
    )


def _vinculo(atividade_id: int, tp_doc: int):
    from calculadora_rtc_simples_nacional.parametro import VinculoTpDocAtividade

    return VinculoTpDocAtividade(atividade_id, tp_doc)


# ─── DerivacaoAnexosSimples ───────────────────────────────────────────────────


def test_atividade9_anexos_i_v() -> None:
    d = derivar_anexos("V", "III", {"I", "V"})
    assert d.disponivel
    assert d.anexos_faltantes == ("III",)
    assert d.modo_fator_r is ModoFatorR.INDISPONIVEL


def test_atividade9_sem_parametro_opcional() -> None:
    d = derivar_anexos("V", "III", None)
    assert d.disponivel
    assert d.anexos_faltantes == ()
    assert d.modo_fator_r is ModoFatorR.OPCIONAL


def test_atividade90_sem_anexo_sempre_disponivel() -> None:
    d = derivar_anexos(None, None, set())
    assert d.disponivel
    assert d.modo_fator_r is ModoFatorR.NAO_APLICAVEL


# ─── Unitários (espelho Teste_AtividadeSimplesService) ──────────────────────────


class TesteAtividadeSimplesService:
    def setup_method(self) -> None:
        self.parametro = MagicMock()
        self.servico = AtividadeSimplesService(self.parametro)
        self.patcher_vigentes = patch.object(
            atividade, "_buscar_vigentes", return_value=[_ativ(1, 1, "01", "I"), _ativ(15, 15, "90", None)]
        )
        self.patcher_contar = patch.object(
            atividade,
            "_contar_tipos_dfe_por_tipo",
            side_effect=lambda t: 1 if t in (55, 65, 91, 57) else 0,
        )
        self.patcher_vigentes.start()
        self.patcher_contar.start()

    def teardown_method(self) -> None:
        self.patcher_vigentes.stop()
        self.patcher_contar.stop()

    def test_sem_tp_doc(self) -> None:
        with patch.object(
            atividade, "buscar_vinculos_tpdoc_vigentes", return_value=[_vinculo(1, 55), _vinculo(1, 65)]
        ):
            lista = self.servico.listar(DATA, None, None, None)
        assert lista[0].tp_docs_admissiveis == ("55", "65")
        assert lista[0].admissivel_no_documento is None
        assert lista[0].disponivel
        assert lista[1].tp_docs_admissiveis == ()

    def test_tp_doc_em_branco(self) -> None:
        with patch.object(atividade, "buscar_vinculos_tpdoc_vigentes", return_value=[]):
            assert self.servico.listar(DATA, None, "  ", None)[0].admissivel_no_documento is None

    def test_admissivel_no_tp_doc(self) -> None:
        with patch.object(
            atividade, "buscar_vinculos_tpdoc_vigentes", return_value=[_vinculo(1, 55), _vinculo(1, 65)]
        ):
            v = self.servico.listar(DATA, None, "55", None)[0]
        assert v.admissivel_no_documento is True
        assert v.disponivel

    def test_inadmissivel_no_tp_doc(self) -> None:
        with patch.object(
            atividade, "buscar_vinculos_tpdoc_vigentes", return_value=[_vinculo(1, 55), _vinculo(1, 65)]
        ):
            v = self.servico.listar(DATA, None, "91", None)[0]
        assert v.admissivel_no_documento is False
        assert not v.disponivel
        assert v.anexos_faltantes == ()

    def test_tp_doc_57_aceito(self) -> None:
        with patch.object(atividade, "buscar_vinculos_tpdoc_vigentes", return_value=[_vinculo(15, 55)]):
            v = self.servico.listar(DATA, None, "57", None)[0]
        assert v.admissivel_no_documento is False

    def test_tp_doc_mal_formado(self) -> None:
        with pytest.raises(ErroConsultaAtividade, match="abc"):
            self.servico.listar(DATA, None, "abc", None)

    def test_tp_doc_desconhecido(self) -> None:
        with pytest.raises(ErroConsultaAtividade, match="99"):
            self.servico.listar(DATA, None, "99", None)

    def test_tp_doc_zero_a_esquerda(self) -> None:
        with patch.object(atividade, "buscar_vinculos_tpdoc_vigentes", return_value=[_vinculo(1, 55)]):
            assert self.servico.listar(DATA, None, "055", None)[0].admissivel_no_documento is True

    def test_c_class_trib_ausente(self) -> None:
        with patch.object(atividade, "buscar_vinculos_tpdoc_vigentes", return_value=[]):
            lista = self.servico.listar(DATA, None, None, None)
        assert lista[0].compativel_com_class_trib is None

    def test_c_class_trib_vedado_marca_90(self) -> None:
        with patch.object(atividade, "buscar_vinculos_tpdoc_vigentes", return_value=[]):
            with patch.object(
                atividade,
                "buscar_classificacoes_vigentes",
                return_value=[ClassificacaoTributaria(1, "000001", 1)],
            ):
                self.parametro.buscar_tipo_receita_bruta.return_value = TipoReceitaBruta(
                    1, "x", True, False, Decimal("1"), False, True, True, VocabularioRegime.NFSE
                )
                lista = self.servico.listar(DATA, None, None, "000001")
        assert lista[0].compativel_com_class_trib is True
        assert lista[1].compativel_com_class_trib is False
        assert not lista[1].disponivel

    def test_c_class_trib_desconhecido(self) -> None:
        with patch.object(atividade, "buscar_classificacoes_vigentes", return_value=[]):
            with pytest.raises(ErroConsultaAtividade, match="999999"):
                self.servico.listar(DATA, None, None, "999999")

    def test_c_class_trib_sem_efeito_tp_rbsn(self) -> None:
        with patch.object(
            atividade,
            "buscar_classificacoes_vigentes",
            return_value=[ClassificacaoTributaria(1, "000001", 1)],
        ):
            self.parametro.buscar_tipo_receita_bruta.return_value = None
            with pytest.raises(ErroConsultaAtividade, match="tpRBSN=1"):
                self.servico.listar(DATA, None, None, "000001")

    def test_buscar_por_codigo(self) -> None:
        with patch.object(
            atividade, "buscar_vinculos_tpdoc_vigentes", return_value=[_vinculo(1, 55), _vinculo(1, 65)]
        ):
            item = self.servico.buscar_por_codigo("01", DATA, "91", None)
        assert item is not None
        assert item.admissivel_no_documento is False

# ─── Integração (carga oficial) ───────────────────────────────────────────────


@pytestmark_integracao
def test_lista_quinze_atividades() -> None:
    lista = AtividadeSimplesService().listar(DATA_CATALOGO)
    assert len(lista) == 15
    assert lista[0].codigo == "01"
    assert lista[8].codigo == "09"
    assert lista[8].modo_fator_r is ModoFatorR.OPCIONAL
    assert lista[14].codigo == "90"
    assert lista[14].anexo_sem_fator_r is None
    assert lista[14].disponivel


@pytestmark_integracao
def test_filtro_anexos_i_e_v() -> None:
    lista = AtividadeSimplesService().listar(DATA_CATALOGO, {"I", "V"})
    a09 = next(a for a in lista if a.codigo == "09")
    assert a09.disponivel
    assert a09.anexos_faltantes == ("III",)
    assert a09.modo_fator_r is ModoFatorR.INDISPONIVEL
    a05 = next(a for a in lista if a.codigo == "05")
    assert not a05.disponivel


@pytestmark_integracao
def test_tp_doc_55_admissibilidade() -> None:
    lista = AtividadeSimplesService().listar(DATA_CATALOGO, None, "55")
    por_codigo = {a.codigo: a for a in lista}
    assert por_codigo["01"].admissivel_no_documento is True
    assert por_codigo["05"].admissivel_no_documento is False
    assert por_codigo["09"].admissivel_no_documento is False
    assert por_codigo["90"].admissivel_no_documento is True


@pytestmark_integracao
def test_tp_doc_57_aceito_pela_listagem() -> None:
    lista = AtividadeSimplesService().listar(DATA_CATALOGO, None, "57")
    assert len(lista) == 15
    a05 = next(a for a in lista if a.codigo == "05")
    assert a05.admissivel_no_documento is True


@pytestmark_integracao
def test_c_class_trib_000001_marca_90() -> None:
    lista = AtividadeSimplesService().listar(DATA_CATALOGO, None, None, "000001")
    por_codigo = {a.codigo: a for a in lista}
    assert por_codigo["01"].compativel_com_class_trib is True
    assert por_codigo["90"].compativel_com_class_trib is False
    assert not por_codigo["90"].disponivel


@pytestmark_integracao
def test_c_class_trib_fora_vigencia() -> None:
    with pytest.raises(ErroConsultaAtividade):
        AtividadeSimplesService().listar(date(2025, 12, 31), None, None, "000001")


@pytestmark_integracao
def test_buscar_por_codigo_09() -> None:
    item = AtividadeSimplesService().buscar_por_codigo("09", DATA_CATALOGO)
    assert item is not None
    assert item.anexo_sem_fator_r == "V"
    assert item.anexo_com_fator_r == "III"
    assert item.sujeita_fator_r
    assert item.disponivel
    assert item.anexos_faltantes == ()


@pytestmark_integracao
def test_buscar_por_codigo_inexistente() -> None:
    assert AtividadeSimplesService().buscar_por_codigo("99", DATA_CATALOGO) is None


@pytestmark_integracao
def test_lista_vazia_antes_da_vigencia() -> None:
    assert AtividadeSimplesService().listar(date(2025, 12, 31)) == []