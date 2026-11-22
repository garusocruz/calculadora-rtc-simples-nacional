from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from calculadora_rtc_simples_nacional.escolha import (
    AliquotasAnexo,
    LinhaAliquotas,
    ParAliquotas,
)
from calculadora_rtc_simples_nacional.parametro import (
    CodigoRegimeApuracao,
    ParametroCalculo,
    RegimeApuracao,
    TipoDfeCalculo,
    VocabularioRegime,
)
from calculadora_rtc_simples_nacional.unificado import (
    CalculoSimplesUnificadoService,
    DadosOperacaoSimples,
    ErrosCalculoException,
    ItemSimplesUnificadoInput,
    LinhaAliquotasComOrigem,
    ResolucaoAliquotas,
)

DATA = date(2027, 3, 15)


def _tipo_nfse() -> TipoDfeCalculo:
    return TipoDfeCalculo(910, VocabularioRegime.NFSE, 2, 1, False)


def _regime_sn_pleno() -> RegimeApuracao:
    return RegimeApuracao(
        1,
        CodigoRegimeApuracao.SN_PLENO,
        "SN_PLENO",
        True,
        True,
        None,
        None,
    )


def _parametro_nfse() -> MagicMock:
    parametro = MagicMock(spec=ParametroCalculo)
    parametro.tp_doc_sem_tratamento_calculadora.return_value = False
    parametro.buscar_tipo_dfe_calculo.return_value = _tipo_nfse()
    parametro.buscar_regime_por_campos.return_value = _regime_sn_pleno()
    parametro.buscar_situacoes_iss_par_aliquota.return_value = []
    parametro.buscar_fator_transicao_compra_gov.return_value = None
    return parametro


def _linha_nfse() -> LinhaAliquotasComOrigem:
    par = ParAliquotas(Decimal("2.3874"), Decimal("0.0263"))
    anexo_iii = AliquotasAnexo(par, ParAliquotas(Decimal("2.3874"), Decimal("0.0263")))
    return LinhaAliquotasComOrigem(
        LinhaAliquotas(False, False, None, None, anexo_iii, None, None),
    )


class FonteFake:
    def __init__(self) -> None:
        self.obter_chamado = False
        self._linha = _linha_nfse()

    def obter(self, data: date) -> LinhaAliquotasComOrigem:
        self.obter_chamado = True
        return self._linha

    def montar_resolucao(self, linha, itens, avisos) -> ResolucaoAliquotas:
        return ResolucaoAliquotas(tuple(itens), tuple(avisos))


def _item(**kwargs) -> ItemSimplesUnificadoInput:
    base = dict(
        numero=1,
        cativ_sn="07",
        class_trib="000001",
        nbs=None,
        ncm=None,
        base_calculo="1000.00",
        valor_imposto_seletivo=None,
        trib_issqn="1",
        tp_ret_issqn="1",
        tp_bm=None,
    )
    base.update(kwargs)
    return ItemSimplesUnificadoInput(**base)


def _operacao_nfse(*, itens=None, **kwargs) -> DadosOperacaoSimples:
    campos = dict(
        id="op",
        versao="3.0.0",
        data=DATA.isoformat(),
        tp_doc="91",
        crt=None,
        tp_regime_ibscbs=None,
        op_simp_nac="3",
        reg_ap_ibscbssn="1",
        reg_ap_trib_sn="1",
        tp_ente_gov=None,
        itens=[_item()] if itens is None else itens,
    )
    campos.update(kwargs)
    return DadosOperacaoSimples(**campos)


def test_global_id_ausente_vsn013() -> None:
    svc = CalculoSimplesUnificadoService(parametro=_parametro_nfse())
    with pytest.raises(ErrosCalculoException) as exc:
        svc.processar(_operacao_nfse(id=""), None)
    assert exc.value.erros[0].code == "VSN-013"


def test_data_invalida_vsn012() -> None:
    svc = CalculoSimplesUnificadoService(parametro=_parametro_nfse())
    with pytest.raises(ErrosCalculoException) as exc:
        svc.processar(_operacao_nfse(data="2027-99-01"), None)
    assert exc.value.erros[0].code == "VSN-012"


def test_itens_vazios_vsn011() -> None:
    svc = CalculoSimplesUnificadoService(parametro=_parametro_nfse())
    with pytest.raises(ErrosCalculoException) as exc:
        svc.processar(_operacao_nfse(itens=[]), None)
    assert exc.value.erros[0].code == "VSN-011"


def test_crt_em_nfse_vsn033() -> None:
    svc = CalculoSimplesUnificadoService(parametro=_parametro_nfse())
    with pytest.raises(ErrosCalculoException) as exc:
        svc.processar(_operacao_nfse(crt="1"), None)
    assert exc.value.erros[0].code == "VSN-033"


def test_nfse_mais_de_um_item_vsn034() -> None:
    svc = CalculoSimplesUnificadoService(parametro=_parametro_nfse())
    with pytest.raises(ErrosCalculoException) as exc:
        svc.processar(_operacao_nfse(itens=[_item(), _item()]), None)
    assert exc.value.erros[0].code == "VSN-034"
    assert exc.value.erros[0].pointer == "#/itens"


def test_somente_receita_nao_consulta_fonte() -> None:
    regime = RegimeApuracao(
        5,
        CodigoRegimeApuracao.SOMENTE_RECEITA,
        "SOMENTE_RECEITA",
        False,
        None,
        None,
        None,
    )
    parametro_mock = _parametro_nfse()
    parametro_mock.buscar_regime_por_campos.return_value = regime

    fonte = FonteFake()
    svc = CalculoSimplesUnificadoService(parametro=parametro_mock)
    resultado = svc.processar(_operacao_nfse(), fonte)
    assert not fonte.obter_chamado
    assert resultado.resolucao_aliquotas is None
    assert resultado.oper.regime_apuracao is CodigoRegimeApuracao.SOMENTE_RECEITA


def test_processamento_nfse_integrado() -> None:
    from unittest.mock import patch

    from calculadora_rtc_simples_nacional import parametro

    classificacao = parametro.ClassificacaoTributaria(1, "000001", 1)
    ativ = parametro.AtividadeNacional(7, 7, "x", "07", "III", None, False, True, False)

    patchers = [
        patch.object(parametro, "buscar_classificacoes_vigentes", return_value=[classificacao]),
        patch.object(parametro, "contar_vinculo_classificacao_tpdoc", return_value=1),
        patch.object(parametro, "contar_tratamentos_nao_implementados", return_value=0),
        patch.object(parametro, "buscar_atividades_por_cativsn", return_value=[ativ]),
        patch.object(parametro, "contar_vinculo_atividade_tpdoc", return_value=1),
        patch(
            "calculadora_rtc_simples_nacional.processador.buscar_classificacoes_vigentes",
            return_value=[classificacao],
        ),
        patch(
            "calculadora_rtc_simples_nacional.processador.contar_vinculo_classificacao_tpdoc",
            return_value=1,
        ),
        patch(
            "calculadora_rtc_simples_nacional.processador.contar_tratamentos_nao_implementados",
            return_value=0,
        ),
        patch(
            "calculadora_rtc_simples_nacional.processador.buscar_atividades_por_cativsn",
            return_value=[ativ],
        ),
        patch(
            "calculadora_rtc_simples_nacional.processador.contar_vinculo_atividade_tpdoc",
            return_value=1,
        ),
        patch(
            "calculadora_rtc_simples_nacional.unificado.buscar_atividades_por_cativsn",
            return_value=[ativ],
        ),
        patch(
            "calculadora_rtc_simples_nacional.unificado.buscar_sigla_vigente_por_id",
            return_value="NFSe",
        ),
        patch(
            "calculadora_rtc_simples_nacional.unificado.permite_ncm_zero_vigente_por_id",
            return_value=True,
        ),
    ]
    tipo = _tipo_nfse()
    parametro_mock = _parametro_nfse()
    parametro_mock.buscar_tipo_dfe_calculo.return_value = tipo
    parametro_mock.buscar_tipo_receita_bruta.return_value = parametro.TipoReceitaBruta(
        1,
        "desc",
        True,
        False,
        Decimal(1),
        False,
        True,
        True,
        VocabularioRegime.NFSE,
    )
    for p in patchers:
        p.start()
    try:
        svc = CalculoSimplesUnificadoService(parametro=parametro_mock)
        fonte = FonteFake()
        resultado = svc.processar(_operacao_nfse(), fonte)
        assert resultado.objetos[0].tributos is not None
        assert resultado.objetos[0].tributos.valor_cbs == Decimal("23.90")
        assert resultado.resolucao_aliquotas is not None
        assert resultado.resolucao_aliquotas.itens[0].motivo == "RESOLVIDA"
    finally:
        for p in patchers:
            p.stop()


def test_fora_escopo_mei_nfse_vsn019() -> None:
    parametro = _parametro_nfse()
    parametro.buscar_regime_por_campos.return_value = None
    svc = CalculoSimplesUnificadoService(parametro=parametro)
    with pytest.raises(ErrosCalculoException) as exc:
        svc.processar(
            _operacao_nfse(
                op_simp_nac="2",
                reg_ap_ibscbssn=None,
                reg_ap_trib_sn=None,
            ),
            None,
        )
    assert exc.value.erros[0].code == "VSN-019"