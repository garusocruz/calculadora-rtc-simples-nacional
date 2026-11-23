"""Desserialização JSON dos modelos de entrada (aliases Jackson do pin a926d5a)."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from calculadora_rtc_simples_nacional.unificado import ItemSimplesUnificadoInput

_CAMPOS_ITEM = (
    ("numero", ("numero",)),
    ("cativ_sn", ("cAtivSN",)),
    ("class_trib", ("cClassTrib",)),
    ("nbs", ("nbs", "NBS")),
    ("ncm", ("ncm", "NCM")),
    ("base_calculo", ("baseCalculo",)),
    ("valor_imposto_seletivo", ("valorImpostoSeletivo",)),
    ("trib_issqn", ("tribISSQN",)),
    ("tp_ret_issqn", ("tpRetISSQN",)),
    ("tp_bm", ("tpBM",)),
)


def _primeiro(obj: dict[str, Any], chaves: tuple[str, ...]) -> Any:
    for chave in chaves:
        if chave in obj:
            return obj[chave]
    return None


def item_simples_unificado_de_json(obj: str | dict[str, Any]) -> ItemSimplesUnificadoInput:
    """``ItemSimplesUnificadoInput`` a partir de JSON (``@JsonProperty`` + ``@JsonAlias``)."""
    if isinstance(obj, str):
        dados = json.loads(obj, parse_float=Decimal)
    else:
        dados = obj
    kwargs = {
        destino: _primeiro(dados, chaves_json)
        for destino, chaves_json in _CAMPOS_ITEM
    }
    if kwargs["numero"] is not None and not isinstance(kwargs["numero"], int):
        kwargs["numero"] = int(kwargs["numero"])
    for campo in (
        "cativ_sn",
        "class_trib",
        "nbs",
        "ncm",
        "base_calculo",
        "valor_imposto_seletivo",
        "trib_issqn",
        "tp_ret_issqn",
        "tp_bm",
    ):
        valor = kwargs[campo]
        if isinstance(valor, Decimal):
            kwargs[campo] = format(valor, "f")
        elif valor is not None and not isinstance(valor, str):
            kwargs[campo] = str(valor)
    return ItemSimplesUnificadoInput(**kwargs)