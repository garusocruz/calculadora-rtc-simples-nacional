from decimal import Decimal

from calculadora_rtc_simples_nacional.arredondamento import (
    arredondar_aliquota,
    arredondar_aliquota_publicada,
    arredondar_valor_fiscal,
    dividir,
    formatar_aliquota,
    formatar_moeda,
    formatar_quantidade,
    fracao_para_percentual,
    multiplicar,
    percentual_para_fracao,
    ratear_valor_fiscal,
    subtrair,
    totalizar,
)

CBS_INTEGRAL = Decimal("1.6839379378389463610262954")


def test_multiplicar_e_subtrair_sao_exatos() -> None:
    assert multiplicar(Decimal("0.9"), CBS_INTEGRAL) == Decimal("1.51554414405505172492366586")
    assert subtrair(Decimal(1), Decimal("0.10")) == Decimal("0.90")
    assert multiplicar(None, Decimal(1)) is None
    assert subtrair(Decimal(1), None) is None


def test_conversao_percentual_fracao_e_exata() -> None:
    fracao = percentual_para_fracao(CBS_INTEGRAL)
    assert fracao == Decimal("0.016839379378389463610262954")
    assert fracao_para_percentual(fracao) == CBS_INTEGRAL
    assert percentual_para_fracao(None) is None
    assert fracao_para_percentual(None) is None


def test_valor_fiscal_arredonda_uma_vez_a_duas_casas() -> None:
    assert arredondar_valor_fiscal(Decimal("2.005")) == Decimal("2.00")
    assert arredondar_valor_fiscal(Decimal("2.015")) == Decimal("2.02")
    assert arredondar_valor_fiscal(
        multiplicar(Decimal("987654.32"), percentual_para_fracao(CBS_INTEGRAL))
    ) == Decimal("16631.49")
    assert arredondar_valor_fiscal(None) is None


def test_conta_exata_nao_sobe_quase_empate() -> None:
    exato = multiplicar(
        multiplicar(Decimal("32902.73"), Decimal("0.5")),
        percentual_para_fracao(Decimal("1.3663")),
    )
    assert exato == Decimal("224.774999995")
    assert arredondar_valor_fiscal(exato) == Decimal("224.77")


def test_aliquota_publicada_arredonda_a_quatro_casas() -> None:
    assert arredondar_aliquota_publicada(multiplicar(Decimal("8.8123"), Decimal("0.4"))) == Decimal("3.5249")
    assert arredondar_aliquota_publicada(Decimal("0.12345")) == Decimal("0.1234")
    assert arredondar_aliquota_publicada(Decimal("0.12355")) == Decimal("0.1236")
    assert arredondar_aliquota_publicada(Decimal("8.8")) == Decimal("8.8000")
    assert arredondar_aliquota_publicada(None) is None


def test_aliquota_do_leiaute_usa_as_casas_do_documento() -> None:
    assert arredondar_aliquota(CBS_INTEGRAL, 2) == Decimal("1.68")
    assert arredondar_aliquota(CBS_INTEGRAL, None) == CBS_INTEGRAL
    assert arredondar_aliquota(None, 2) is None


def test_totalizar_soma_exata() -> None:
    assert totalizar([Decimal("2.00"), Decimal("4.41")]) == Decimal("6.41")
    assert totalizar([]) == Decimal(0)


def test_dividir_usa_34_digitos_significativos() -> None:
    terco = dividir(Decimal(1), Decimal(3))
    assert terco is not None
    assert len(terco.as_tuple().digits) == 34
    pequeno = dividir(Decimal("0.0001"), Decimal(3))
    assert pequeno is not None
    assert len(pequeno.as_tuple().digits) == 34
    assert dividir(None, Decimal(1)) is None


def test_ratear_centavos_ao_maior_resto() -> None:
    total = Decimal("1.80")
    extensao = Decimal(33)
    exatas = [dividir(total * Decimal(trecho), extensao) for trecho in ("10", "13", "10")]
    assert ratear_valor_fiscal(exatas) == [Decimal("0.55"), Decimal("0.71"), Decimal("0.54")]
    total_ibs = Decimal("0.20")
    exatas_ibs = [dividir(total_ibs * Decimal(trecho), extensao) for trecho in ("10", "13", "10")]
    assert ratear_valor_fiscal(exatas_ibs) == [Decimal("0.06"), Decimal("0.08"), Decimal("0.06")]


def test_ratear_casos_de_borda() -> None:
    assert ratear_valor_fiscal([]) == []
    assert ratear_valor_fiscal([Decimal(0), Decimal(0)]) == [Decimal("0.00"), Decimal("0.00")]
    assert ratear_valor_fiscal([Decimal("2.005")]) == [Decimal("2.00")]
    terco = Decimal("0.0033333333")
    assert ratear_valor_fiscal([terco, terco, terco]) == [
        Decimal("0.01"),
        Decimal("0.00"),
        Decimal("0.00"),
    ]


def test_formatar_moeda_e_aliquota_e_quantidade() -> None:
    assert formatar_moeda(Decimal("804.37")) == "804.37"
    assert formatar_moeda(Decimal(0)) == "0.00"
    assert formatar_moeda(Decimal("0E-8")) == "0.00"
    assert formatar_aliquota(CBS_INTEGRAL) == "1.6839"
    assert formatar_aliquota(Decimal("0.01867380622521988789135487")) == "0.0187"
    assert formatar_aliquota(Decimal("2.8780")) == "2.878"
    assert formatar_aliquota(Decimal(0)) == "0.00"
    assert formatar_aliquota(Decimal("60.0000")) == "60.00"
    assert formatar_quantidade(Decimal("1000.000")) == "1000"
    assert formatar_quantidade(Decimal("55.55")) == "55.5500"
    assert formatar_quantidade(Decimal("0.0001")) == "0.0001"
