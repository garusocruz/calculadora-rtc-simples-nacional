from decimal import Decimal

import pytest

from calculadora_rtc_simples_nacional.simples import (
    REGIME_SOMENTE_RECEITA,
    Destino,
    EstadoItem,
    Insumo,
    Motivo,
    Regime,
    TipoReceita,
    calcular_item,
)


def _tipo(codigo: int, *, seletivo_na_receita: bool = False) -> TipoReceita:
    linhas = {
        0: ("Não é receita bruta", False, "0.0", False, False, False),
        1: ("Receita bruta - interna", True, "1.0", False, True, True),
        2: ("Receita bruta - interna sem cálculo de IBS e CBS", True, "0.0", False, False, True),
        3: ("Receita bruta - exportação direta", True, "0.0", False, False, True),
        4: ("Receita bruta - exportação indireta", True, "1.0", True, True, True),
        5: ("Receita bruta - mercado interno e exportação", True, "0.5", False, True, True),
        9: ("Fornecimento incompatível com SN", True, "0.0", False, False, False),
    }
    descricao, compoe, fator, pendente, exige, vedado = linhas[codigo]
    return TipoReceita(
        codigo,
        descricao,
        compoe,
        Decimal(fator),
        pendente,
        seletivo_na_receita,
        exige,
        vedado,
    )


def _regime(crt: int, gera_ibs: bool, devido: Destino, pendente: Destino) -> Regime:
    codigo = {1: "SN_PLENO", 2: "SN_SUBLIMITE"}.get(crt, "PENDENTE")
    return Regime(codigo, True, f"CRT {crt}", gera_ibs, devido, pendente)


def _crt1() -> Regime:
    return _regime(1, True, Destino.DEVIDO, Destino.PENDENTE_SUSPENSO)


def _crt2() -> Regime:
    return _regime(2, False, Destino.DEVIDO, Destino.PENDENTE_SUSPENSO)


def _crt3() -> Regime:
    return _regime(3, True, Destino.PENDENTE_SUSPENSO, Destino.ZERO)


def _insumo(
    regime: Regime,
    tipo: TipoReceita,
    base: str = "1000.00",
    seletivo: str = "0.00",
    ibs: str | None = "1.25",
    cbs: str | None = "2.75",
    ente: int | None = None,
    fator: str | None = None,
    motivo: Motivo | None = None,
    casas: int | None = None,
) -> Insumo:
    return Insumo(
        regime,
        tipo,
        motivo,
        Decimal(base),
        Decimal(seletivo),
        Decimal(ibs) if ibs is not None else None,
        Decimal(cbs) if cbs is not None else None,
        ente,
        Decimal(fator) if fator is not None else None,
        casas,
    )


def _calculado(insumo: Insumo):
    resultado = calcular_item(insumo)
    assert resultado.estado is EstadoItem.CALCULADO
    assert resultado.motivo is None
    return resultado.tributos


def test_crt1_receita_interna() -> None:
    tributos = _calculado(_insumo(_crt1(), _tipo(1)))
    assert tributos.receita_bruta == Decimal("1000.00")
    assert tributos.tipo_receita == 1
    assert tributos.descricao_tipo_receita == "Receita bruta - interna"
    assert tributos.base_calculo == Decimal("1000.00")
    assert tributos.valor_ibs == Decimal("12.50")
    assert tributos.ibs_pendente == Decimal("0.00")
    assert tributos.valor_cbs == Decimal("27.50")
    assert tributos.cbs_pendente == Decimal("0.00")
    assert tributos.total_item == Decimal("40.00")
    assert tributos.memoria is not None
    assert tributos.memoria.cbs == (
        "Receita bruta do Simples Nacional de R$ 1.000,00 (Receita bruta - interna). "
        "A base de cálculo utilizada é de R$ 1.000,00, com alíquota efetiva de 2,75%. "
        "Valor devido de R$ 27,50 e pendente/suspenso de R$ 0,00."
    )


def test_seletivo_fica_fora_da_receita_bruta() -> None:
    tributos = _calculado(_insumo(_crt1(), _tipo(1), "950.00", "50.00"))
    assert tributos.receita_bruta == Decimal("950.00")
    assert tributos.valor_ibs == Decimal("11.88")
    assert tributos.ibs_pendente == Decimal("0.00")
    assert tributos.valor_cbs == Decimal("26.12")
    assert tributos.cbs_pendente == Decimal("0.00")
    assert tributos.imposto_seletivo is not None
    assert tributos.imposto_seletivo.valor == Decimal("50.00")
    assert tributos.total_item == Decimal("88.00")


def test_seletivo_entra_na_receita_quando_a_linha_manda() -> None:
    tributos = _calculado(_insumo(_crt1(), _tipo(1, seletivo_na_receita=True), "950.00", "50.00"))
    assert tributos.receita_bruta == Decimal("1000.00")
    assert tributos.valor_ibs == Decimal("12.50")
    assert tributos.valor_cbs == Decimal("27.50")
    assert tributos.imposto_seletivo is not None
    assert tributos.imposto_seletivo.valor == Decimal("50.00")
    assert tributos.total_item == Decimal("90.00")


def test_metade_da_receita() -> None:
    tributos = _calculado(_insumo(_crt1(), _tipo(5)))
    assert tributos.receita_bruta == Decimal("1000.00")
    assert tributos.base_calculo == Decimal("500.00")
    assert tributos.valor_ibs == Decimal("6.25")
    assert tributos.ibs_pendente == Decimal("0.00")
    assert tributos.valor_cbs == Decimal("13.75")
    assert tributos.cbs_pendente == Decimal("0.00")


def test_exportacao_indireta_suspende() -> None:
    tributos = _calculado(_insumo(_crt1(), _tipo(4)))
    assert tributos.valor_ibs == Decimal("0.00")
    assert tributos.ibs_pendente == Decimal("12.50")
    assert tributos.valor_cbs == Decimal("0.00")
    assert tributos.cbs_pendente == Decimal("27.50")
    assert tributos.total_item == Decimal("0.00")


def test_fator_zero_mantem_a_receita_e_zera_o_tributo() -> None:
    for codigo in (2, 3, 9):
        tributos = _calculado(_insumo(_crt1(), _tipo(codigo)))
        assert tributos.receita_bruta == Decimal("1000.00")
        assert tributos.base_calculo == Decimal("0.00")
        assert tributos.valor_ibs == Decimal("0.00")
        assert tributos.valor_cbs == Decimal("0.00")


def test_tipo_zero_zera_a_receita_bruta() -> None:
    tributos = _calculado(_insumo(_crt1(), _tipo(0), "1000.00", "50.00"))
    assert tributos.receita_bruta == Decimal("0.00")
    assert tributos.tipo_receita == 0
    assert tributos.descricao_tipo_receita == "Não é receita bruta"
    assert tributos.base_calculo == Decimal("0.00")
    assert tributos.valor_ibs == Decimal("0.00")
    assert tributos.valor_cbs == Decimal("0.00")


def test_crt2_suprime_o_ibs() -> None:
    tributos = _calculado(_insumo(_crt2(), _tipo(1)))
    assert tributos.base_calculo == Decimal("1000.00")
    assert tributos.aliquota_ibs is None
    assert tributos.valor_ibs is None
    assert tributos.ibs_pendente is None
    assert tributos.valor_cbs == Decimal("27.50")
    assert tributos.cbs_pendente == Decimal("0.00")
    assert tributos.total_item == Decimal("27.50")


def test_crt2_exportacao_indireta_suspende_so_a_cbs() -> None:
    tributos = _calculado(_insumo(_crt2(), _tipo(4)))
    assert tributos.valor_ibs is None
    assert tributos.ibs_pendente is None
    assert tributos.valor_cbs == Decimal("0.00")
    assert tributos.cbs_pendente == Decimal("27.50")


def test_crt3_devido_vai_para_pendente() -> None:
    tributos = _calculado(_insumo(_crt3(), _tipo(1)))
    assert tributos.valor_ibs == Decimal("0.00")
    assert tributos.ibs_pendente == Decimal("12.50")
    assert tributos.valor_cbs == Decimal("0.00")
    assert tributos.cbs_pendente == Decimal("27.50")


def test_crt3_metade_tambem_fica_pendente() -> None:
    tributos = _calculado(_insumo(_crt3(), _tipo(5)))
    assert tributos.valor_ibs == Decimal("0.00")
    assert tributos.ibs_pendente == Decimal("6.25")
    assert tributos.valor_cbs == Decimal("0.00")
    assert tributos.cbs_pendente == Decimal("13.75")


def test_crt3_exportacao_indireta_zera_os_dois_destinos() -> None:
    tributos = _calculado(_insumo(_crt3(), _tipo(4)))
    assert tributos.valor_ibs == Decimal("0.00")
    assert tributos.ibs_pendente == Decimal("0.00")
    assert tributos.valor_cbs == Decimal("0.00")
    assert tributos.cbs_pendente == Decimal("0.00")


def test_uniao_desloca_o_ibs_para_a_cbs() -> None:
    tributos = _calculado(_insumo(_crt1(), _tipo(1), ente=1))
    assert tributos.aliquota_ibs == Decimal("0.00")
    assert tributos.valor_ibs == Decimal("0.00")
    assert tributos.ibs_pendente == Decimal("0.00")
    assert tributos.aliquota_cbs == Decimal("4.00")
    assert tributos.valor_cbs == Decimal("40.00")
    assert tributos.cbs_pendente == Decimal("0.00")
    assert tributos.valor_ibs + tributos.valor_cbs == Decimal("40.00")


def test_estado_aplica_fator_de_transicao() -> None:
    tributos = _calculado(_insumo(_crt1(), _tipo(1), ente=2, fator="0.10"))
    assert tributos.aliquota_ibs == Decimal("1.525")
    assert tributos.valor_ibs == Decimal("15.25")
    assert tributos.aliquota_cbs == Decimal("2.475")
    assert tributos.valor_cbs == Decimal("24.75")
    assert tributos.valor_ibs + tributos.valor_cbs == Decimal("40.00")


def test_distrito_federal_completa_a_transicao() -> None:
    tributos = _calculado(_insumo(_crt1(), _tipo(1), ente=3, fator="1.00"))
    assert tributos.aliquota_ibs == Decimal("4.00")
    assert tributos.valor_ibs == Decimal("40.00")
    assert tributos.aliquota_cbs == Decimal("0.00")
    assert tributos.valor_cbs == Decimal("0.00")
    assert tributos.valor_ibs + tributos.valor_cbs == Decimal("40.00")


def test_municipio_antes_da_transicao_nao_desloca() -> None:
    tributos = _calculado(_insumo(_crt1(), _tipo(1), ente=4, fator="0.00"))
    assert tributos.aliquota_ibs == Decimal("1.25")
    assert tributos.valor_ibs == Decimal("12.50")
    assert tributos.aliquota_cbs == Decimal("2.75")
    assert tributos.valor_cbs == Decimal("27.50")
    assert tributos.valor_ibs + tributos.valor_cbs == Decimal("40.00")


def test_atividade_invalida_nao_calcula() -> None:
    motivo = Motivo("CATIVSN_DESCONHECIDO", "O código de atividade '99' não existe ou não está vigente na data do fato gerador; o IBS e a CBS do item não são calculados.")
    resultado = calcular_item(_insumo(_crt1(), _tipo(1), motivo=motivo))
    assert resultado.estado is EstadoItem.NAO_CALCULADO
    assert resultado.motivo is motivo
    tributos = resultado.tributos
    assert tributos.receita_bruta == Decimal("1000.00")
    assert tributos.tipo_receita == 1
    assert tributos.descricao_tipo_receita == "Receita bruta - interna"
    assert tributos.base_calculo is None
    assert tributos.aliquota_ibs is None
    assert tributos.valor_ibs is None
    assert tributos.aliquota_cbs is None
    assert tributos.valor_cbs is None
    assert tributos.imposto_seletivo is None
    assert tributos.total_item is None


def test_crt2_na_uniao_usa_o_ibs_so_para_deslocar_a_cbs() -> None:
    tributos = _calculado(_insumo(_crt2(), _tipo(1), ente=1))
    assert tributos.aliquota_ibs is None
    assert tributos.valor_ibs is None
    assert tributos.aliquota_cbs == Decimal("4.00")
    assert tributos.valor_cbs == Decimal("40.00")


def test_crt2_na_uniao_sem_ibs_trata_o_insumo_como_zero() -> None:
    tributos = _calculado(_insumo(_crt2(), _tipo(1), ibs=None, ente=1))
    assert tributos.aliquota_ibs is None
    assert tributos.aliquota_cbs == Decimal("2.75")
    assert tributos.valor_cbs == Decimal("27.50")


def test_aliquotas_dispensadas_calculam_zero() -> None:
    tributos = _calculado(_insumo(_crt1(), _tipo(2), ibs=None, cbs=None))
    assert tributos.receita_bruta == Decimal("1000.00")
    assert tributos.aliquota_ibs is None
    assert tributos.aliquota_cbs is None
    assert tributos.valor_ibs == Decimal("0.00")
    assert tributos.valor_cbs == Decimal("0.00")
    assert tributos.total_item == Decimal("0.00")


def test_ente_sem_fator_nao_desloca() -> None:
    with pytest.raises(ValueError, match="tpEnteGov 2"):
        calcular_item(_insumo(_crt1(), _tipo(1), ente=2))


def test_nfse_arredonda_a_aliquota_a_duas_casas_depois_do_deslocamento() -> None:
    tributos = _calculado(_insumo(_crt1(), _tipo(1), ente=2, fator="0.10", casas=2))
    assert tributos.aliquota_ibs == Decimal("1.52")
    assert tributos.valor_ibs == Decimal("15.20")
    assert tributos.aliquota_cbs == Decimal("2.48")
    assert tributos.valor_cbs == Decimal("24.80")


def test_regime_somente_receita_nao_calcula() -> None:
    regime = Regime("SN_PLENO", False, "CRT 1", True, Destino.DEVIDO, Destino.PENDENTE_SUSPENSO)
    resultado = calcular_item(_insumo(regime, _tipo(1)))
    assert resultado.estado is EstadoItem.NAO_CALCULADO
    assert resultado.motivo == REGIME_SOMENTE_RECEITA
    assert resultado.tributos.receita_bruta == Decimal("1000.00")
    assert resultado.tributos.base_calculo is None
