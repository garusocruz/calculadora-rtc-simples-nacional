from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from calculadora_rtc_simples_nacional.observabilidade import (
    ItemSimplesClassico,
    OperacaoSimplesClassica,
    SimplesNacionalObservabilidadeService,
    uri_erro,
)
from calculadora_rtc_simples_nacional.parametro import ParametroCalculo, banco_disponivel
from calculadora_rtc_simples_nacional.processador import EstadoItemProcessado
from calculadora_rtc_simples_nacional.unificado import ErrosCalculoException

pytestmark = pytest.mark.skipif(not banco_disponivel(), reason="calculadora-pro.db ausente")

BASE_URL = "http://localhost/api"
DATA_PADRAO = "2027-03-15"


def _item(
    numero: int = 1,
    cativ_sn: str = "01",
    class_trib: str = "000001",
    base: str = "1000.00",
    pis: str = "1.25",
    pcbs: str = "2.75",
    **kwargs,
) -> ItemSimplesClassico:
    return ItemSimplesClassico(
        numero,
        cativ_sn,
        class_trib,
        kwargs.get("nbs"),
        kwargs.get("ncm"),
        base,
        kwargs.get("valor_is", "0.00"),
        pis,
        pcbs,
    )


def _operacao(*, itens=None, **kwargs) -> OperacaoSimplesClassica:
    return OperacaoSimplesClassica(
        kwargs.get("id", "507f1f77bcf86cd799439011"),
        kwargs.get("versao", "2.0.0"),
        kwargs.get("data", DATA_PADRAO),
        kwargs.get("tp_doc", "55"),
        kwargs.get("crt", "1"),
        kwargs.get("tp_regime_ibscbs"),
        kwargs.get("tp_ente_gov"),
        list(itens or [_item()]),
    )


def _codigos_globais(operacao: OperacaoSimplesClassica) -> list[str]:
    service = SimplesNacionalObservabilidadeService()
    with pytest.raises(ErrosCalculoException) as exc:
        service.processar_operacao(operacao, BASE_URL)
    return [e.code for e in exc.value.erros]


def _codigos_item(obj) -> list[str]:
    return [e.code for e in (obj.erros or ())]


def test_atividade_valida_calculado() -> None:
    resultado = SimplesNacionalObservabilidadeService().processar_operacao(
        _operacao(), BASE_URL
    )
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.CALCULADO
    assert obj.tributos is not None
    assert Decimal("12.50") == obj.tributos.valor_ibs
    assert Decimal("27.50") == obj.tributos.valor_cbs


def test_cativsn_ausente_nao_calculado_contribui_só_receita() -> None:
    resultado = SimplesNacionalObservabilidadeService().processar_operacao(
        _operacao(itens=[_item(cativ_sn=None)]), BASE_URL
    )
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.NAO_CALCULADO
    assert obj.tributos is not None
    assert Decimal("1000.00") == obj.tributos.receita_bruta
    assert obj.tributos.valor_ibs is None
    assert resultado.total is not None
    assert Decimal("1000.00") == resultado.total.receita_bruta_total
    assert resultado.total.ibs_total is None


def test_crt4_fora_escopo() -> None:
    assert "VSN-019" in _codigos_globais(_operacao(crt="4"))


def test_tp_regime_1_fora_escopo() -> None:
    assert "VSN-019" in _codigos_globais(_operacao(tp_regime_ibscbs="1"))


def test_crt1_com_tp_regime_2_incompativel() -> None:
    assert "VSN-018" in _codigos_globais(_operacao(tp_regime_ibscbs="2"))


def test_crt3_sem_tp_regime_fora_escopo() -> None:
    assert "VSN-019" in _codigos_globais(_operacao(crt="3"))


def test_tp_doc_nao_suportado() -> None:
    assert "VSN-015" in _codigos_globais(_operacao(tp_doc="77"))


def test_data_invalida_apenas_vsn012() -> None:
    codigos = _codigos_globais(_operacao(data="2027-13-99"))
    assert codigos == ["VSN-012"]


def test_sem_pcbsn_exigida_vsn004() -> None:
    resultado = SimplesNacionalObservabilidadeService().processar_operacao(
        _operacao(itens=[_item(pcbs=None)]), BASE_URL
    )
    assert "VSN-004" in _codigos_item(resultado.objetos[0])


def test_tp_rbsn2_sem_aliquotas_calculado_zero() -> None:
    resultado = SimplesNacionalObservabilidadeService().processar_operacao(
        _operacao(itens=[_item(class_trib="410008", pis=None, pcbs=None)]), BASE_URL
    )
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.CALCULADO
    assert obj.tributos is not None
    assert Decimal(0) == obj.tributos.valor_ibs
    assert Decimal(0) == obj.tributos.valor_cbs


def test_crt2_ibs_nao_exigida() -> None:
    resultado = SimplesNacionalObservabilidadeService().processar_operacao(
        _operacao(crt="2", itens=[_item(pis=None)]), BASE_URL
    )
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.CALCULADO
    assert obj.tributos is not None
    assert obj.tributos.aliquota_ibs is None
    assert Decimal("27.50") == obj.tributos.valor_cbs
    assert resultado.total is not None
    assert resultado.total.ibs_total is None


def test_compra_gov_sem_vigencia_vsn025() -> None:
    parametro = ParametroCalculo()
    parametro.buscar_fator_transicao_compra_gov = lambda _data: None  # type: ignore[method-assign]
    service = SimplesNacionalObservabilidadeService(parametro=parametro)
    with pytest.raises(ErrosCalculoException) as exc:
        service.processar_operacao(_operacao(tp_ente_gov="2"), BASE_URL)
    assert "VSN-025" in [e.code for e in exc.value.erros]


def test_tp_ente_gov_invalido_vsn024() -> None:
    assert "VSN-024" in _codigos_globais(_operacao(tp_ente_gov="5"))


def test_compra_gov_uniao_desloca_aliquotas_todos_itens() -> None:
    resultado = SimplesNacionalObservabilidadeService().processar_operacao(
        _operacao(
            tp_ente_gov="1",
            itens=[_item(numero=1), _item(numero=2)],
        ),
        BASE_URL,
    )
    for obj in resultado.objetos:
        assert obj.estado is EstadoItemProcessado.CALCULADO
        assert obj.tributos is not None
        assert Decimal(0) == obj.tributos.aliquota_ibs
        assert Decimal("4.00") == obj.tributos.aliquota_cbs
        assert Decimal("40.00") == obj.tributos.valor_cbs


def test_c_class_trib_nao_implementado_vsn027() -> None:
    resultado = SimplesNacionalObservabilidadeService().processar_operacao(
        _operacao(itens=[_item(class_trib="620001")]), BASE_URL
    )
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.NAO_IMPLEMENTADO
    assert _codigos_item(obj) == ["VSN-027"]
    assert obj.erros is not None
    assert obj.erros[0].pointer == "#/itens/0/cClassTrib"
    assert uri_erro(BASE_URL, "VSN-027").endswith("codigo=VSN-027")
    assert resultado.total is None


def test_c_class_trib_nao_implementado_nao_contamina_outros() -> None:
    resultado = SimplesNacionalObservabilidadeService().processar_operacao(
        _operacao(
            itens=[
                _item(numero=1, class_trib="620001"),
                _item(numero=2, class_trib="000001"),
            ]
        ),
        BASE_URL,
    )
    assert resultado.objetos[0].estado is EstadoItemProcessado.NAO_IMPLEMENTADO
    assert resultado.objetos[1].estado is EstadoItemProcessado.CALCULADO
    assert resultado.total is not None
    assert Decimal("1000.00") == resultado.total.receita_bruta_total


def test_regime_sem_linha_vigente_global_vsn026() -> None:
    parametro = MagicMock(spec=ParametroCalculo)
    parametro.tp_doc_suportado.return_value = True
    parametro.tp_doc_sem_tratamento_calculadora.return_value = False
    parametro.buscar_regime_apuracao.return_value = None
    service = SimplesNacionalObservabilidadeService(parametro=parametro)
    with pytest.raises(ErrosCalculoException) as exc:
        service.processar_operacao(_operacao(), BASE_URL)
    assert "VSN-026" in [e.code for e in exc.value.erros]


def test_atividade_nao_tributavel_com_receita_vsn023() -> None:
    resultado = SimplesNacionalObservabilidadeService().processar_operacao(
        _operacao(itens=[_item(cativ_sn="90")]), BASE_URL
    )
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    assert "VSN-023" in _codigos_item(obj)


def test_nomenclatura_simultanea_vsn041() -> None:
    resultado = SimplesNacionalObservabilidadeService().processar_operacao(
        _operacao(itens=[_item(ncm="22030000", nbs="114051000")]), BASE_URL
    )
    assert "VSN-041" in _codigos_item(resultado.objetos[0])