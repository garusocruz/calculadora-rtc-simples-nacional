from decimal import Decimal

import pytest

from calculadora_rtc_simples_nacional.nao_assistido import (
    AliquotasEfetivas,
    AnexoComIss,
    AnexoUnico,
    OperacaoNaoAssistida,
    ParInformado,
    ler_linha_requisicao,
    processar_operacao,
)
from calculadora_rtc_simples_nacional.unificado import ErrosCalculoException


def test_operacao_sem_id_nao_chega_na_linha() -> None:
    with pytest.raises(ErrosCalculoException) as exc:
        processar_operacao(OperacaoNaoAssistida())
    assert exc.value.erros[0].code == "VSN-013"
    assert exc.value.erros[0].pointer.endswith("id") or exc.value.erros[0].pointer == "#/id"


def test_linha_ausente() -> None:
    with pytest.raises(ErrosCalculoException, match="obrigatória") as exc:
        ler_linha_requisicao(None)
    assert exc.value.erros[0].code == "VSN-039"


def test_anexo_i_e_par_sem_iss_do_anexo_iii() -> None:
    linha = ler_linha_requisicao(
        AliquotasEfetivas(
            fator_r=True,
            anexo_i=AnexoUnico("1.5", "2"),
            anexo_iii=AnexoComIss("3", "4", ParInformado("5.25", "6")),
        )
    )
    assert linha.fator_r is True
    assert linha.anexo_i is not None
    assert linha.anexo_i.par == linha.anexo_i.par
    assert linha.anexo_i.par.aliquota_cbs == Decimal("1.5")
    assert linha.anexo_iii is not None
    assert linha.anexo_iii.sem_redistribuicao_iss is not None
    assert linha.anexo_iii.sem_redistribuicao_iss.aliquota_ibs == Decimal("6")


def test_negativo_e_global() -> None:
    with pytest.raises(ErrosCalculoException) as exc:
        ler_linha_requisicao(AliquotasEfetivas(anexo_ii=AnexoUnico("-1", "2")))
    erro = exc.value.erros[0]
    assert erro.code == "VSN-005"
    assert erro.pointer == "#/aliquotasEfetivas/anexoII/pCBSSN"
    assert "negativo" in erro.detail


def test_formato_invalido_do_ibs() -> None:
    with pytest.raises(ErrosCalculoException) as exc:
        ler_linha_requisicao(AliquotasEfetivas(anexo_i=AnexoUnico("1", "1e2")))
    assert exc.value.erros[0].code == "VSN-007"
    assert "decimal válido" in exc.value.erros[0].detail
