"""Endpoint clássico de observabilidade do Simples Nacional (pin a926d5a)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from calculadora_rtc_simples_nacional import banco
from calculadora_rtc_simples_nacional.escolha import _inteiro
from calculadora_rtc_simples_nacional.nomenclatura import (
    ValidacaoNomenclaturaAdapter,
    montar_validacao_nomenclatura,
)
from calculadora_rtc_simples_nacional.parametro import ParametroCalculo, RegimeCalculo
from calculadora_rtc_simples_nacional.processador import (
    AliquotasItem,
    ColetorItem,
    ContextoItem,
    DadosAliquotas,
    EntradaItem,
    ItemAProcessar,
    ObjetoItem,
    ProcessadorItemSimples,
    RegimeContexto,
    ResolvedorAliquotas,
)
from calculadora_rtc_simples_nacional.unificado import (
    ErroDetalhe,
    ErrosCalculoException,
    TotalSimples,
    _totalizar_objetos,
    buscar_sigla_vigente_por_id,
    permite_ncm_zero_vigente_por_id,
)

_CAMPO_TPDOC = "tpDoc"
_CAMPO_CRT = "CRT"
_CAMPO_TPREGIMEIBSCBS = "tpRegimeIBSCBS"
_CAMPO_TPENTEGOV = "tpEnteGov"


@dataclass(frozen=True)
class ItemSimplesClassico:
    numero: int | None
    cativ_sn: str | None
    class_trib: str | None
    nbs: str | None
    ncm: str | None
    base_calculo: str | None
    valor_imposto_seletivo: str | None
    p_ibs_sn: str | None
    p_cbs_sn: str | None


@dataclass(frozen=True)
class OperacaoSimplesClassica:
    id: str | None
    versao: str | None
    data: str | None
    tp_doc: str | None
    crt: str | None
    tp_regime_ibscbs: str | None
    tp_ente_gov: str | None
    itens: list[ItemSimplesClassico]


@dataclass(frozen=True)
class OperacaoClassicaEco:
    data: str
    tp_doc: str
    crt: str | None
    tp_regime_ibscbs: str | None
    tp_ente_gov: str | None


@dataclass(frozen=True)
class ObservabilidadeSimplesClassica:
    operacao: OperacaoClassicaEco
    objetos: tuple[ObjetoItem, ...]
    total: TotalSimples | None


class SimplesNacionalObservabilidadeService:
    """Processamento clássico: validação global, itens em sequência, totalização."""

    def __init__(
        self,
        parametro: ParametroCalculo | None = None,
        processador: ProcessadorItemSimples | None = None,
        nomenclatura: ValidacaoNomenclaturaAdapter | None = None,
    ) -> None:
        self._parametro = parametro or ParametroCalculo()
        self._nomenclatura = nomenclatura or montar_validacao_nomenclatura()
        self._processador = processador or ProcessadorItemSimples(
            self._parametro, self._nomenclatura
        )

    def processar_operacao(
        self, operacao: OperacaoSimplesClassica, base_url: str
    ) -> ObservabilidadeSimplesClassica:
      erros = _validar_campos_globais(operacao, base_url, self._parametro)
      if erros:
          raise ErrosCalculoException(erros)

      assert operacao.data is not None
      data = date.fromisoformat(operacao.data.strip())
      tp_doc = int(operacao.tp_doc.strip())  # type: ignore[union-attr]

      regime_enum = _resolver_regime(operacao)
      regime_row = self._parametro.buscar_regime_apuracao(regime_enum, data)
      if regime_row is None:
          raise ErrosCalculoException(
              [
                  _erro_global(
                      "VSN-026",
                      _CAMPO_CRT,
                      f"Não há parametrização de regime de apuração do Simples Nacional vigente "
                      f"para CRT={operacao.crt} e tpRegimeIBSCBS={operacao.tp_regime_ibscbs} na data '{data}'.",
                      base_url,
                  )
              ]
          )

      tp_ente_gov = _inteiro(operacao.tp_ente_gov)
      fator_transicao: Decimal | None = None
      if tp_ente_gov is not None and tp_ente_gov != 1:
          fator_transicao = self._parametro.buscar_fator_transicao_compra_gov(data)
          if fator_transicao is None:
              raise ErrosCalculoException(
                  [
                      _erro_global(
                          "VSN-025",
                          _CAMPO_TPENTEGOV,
                          f"Não há parametrização de transição de compra governamental vigente "
                          f"para a data '{data}'.",
                          base_url,
                      )
                  ]
              )

      tipo_dfe_id = _buscar_tipo_dfe_id(tp_doc, data)
      sigla = (
          buscar_sigla_vigente_por_id(tipo_dfe_id, data) if tipo_dfe_id is not None else None
      )
      permite_ncm_zero = (
          permite_ncm_zero_vigente_por_id(tipo_dfe_id, data)
          if tipo_dfe_id is not None
          else False
      )

      regime_ctx = RegimeContexto(
          regime_row.codigo.value,
          regime_row.calcula_tributos,
          regime_row.gera_ibs,
          regime_row.descricao,
      )
      contexto = ContextoItem.classico(
          data, tp_doc, regime_ctx, tp_ente_gov, fator_transicao, sigla or "", permite_ncm_zero
      )

      itens = [
          ItemAProcessar(
              EntradaItem(
                  item.numero,
                  item.cativ_sn,
                  item.class_trib,
                  item.base_calculo,
                  item.valor_imposto_seletivo,
                  item.ncm,
                  item.nbs,
              ),
              _aliquotas_classico(item),
          )
          for item in operacao.itens
      ]

      processados = self._processador.processar_itens(itens, contexto)
      objetos = sorted(
          (p.objeto for p in processados),
          key=lambda o: (o.numero is None, o.numero if o.numero is not None else 0),
      )
      return ObservabilidadeSimplesClassica(
          OperacaoClassicaEco(
              operacao.data,
              operacao.tp_doc or "",
              operacao.crt,
              operacao.tp_regime_ibscbs,
              operacao.tp_ente_gov,
          ),
          tuple(objetos),
          _totalizar_objetos(tuple(objetos)),
      )


def _buscar_tipo_dfe_id(tp_doc: int, data: date) -> int | None:
    sql = """
        SELECT t.TDCS_TPDF_ID
        FROM TIPO_DFE_CALCULO_SIMPLES_NACIONAL t
        JOIN TIPO_DFE td ON td.TPDF_ID = t.TDCS_TPDF_ID
        WHERE td.TPDF_TIPO = ?
          AND ? BETWEEN t.TDCS_INICIO_VIGENCIA AND COALESCE(t.TDCS_FIM_VIGENCIA, ?)
          AND ? BETWEEN td.TPDF_INICIO_VIGENCIA AND COALESCE(td.TPDF_FIM_VIGENCIA, ?)
        ORDER BY t.TDCS_INICIO_VIGENCIA DESC
        LIMIT 1
    """
    iso = data.isoformat()
    with banco.conectar() as conexao:
        row = conexao.execute(sql, (tp_doc, iso, iso, iso, iso)).fetchone()
    return int(row[0]) if row else None


def _aliquotas_classico(item: ItemSimplesClassico) -> ResolvedorAliquotas:
    def resolver(dados: DadosAliquotas, collector: ColetorItem) -> AliquotasItem:
        p_cbs = ProcessadorItemSimples.validar_aliquota(
            item.p_cbs_sn,
            dados.cbs_exigida,
            collector,
            "pCBSSN",
            "VSN-004",
            "VSN-005",
        )
        p_ibs = ProcessadorItemSimples.validar_aliquota(
            item.p_ibs_sn,
            dados.ibs_exigida,
            collector,
            "pIBSSN",
            "VSN-006",
            "VSN-007",
        )
        return AliquotasItem(p_ibs, p_cbs, False)

    return resolver


def _resolver_regime(operacao: OperacaoSimplesClassica) -> RegimeCalculo:
    crt = int(operacao.crt.strip())  # type: ignore[union-attr]
    if crt == 1:
        return RegimeCalculo.CRT_1
    if crt == 2:
        return RegimeCalculo.CRT_2
    return RegimeCalculo.CRT_3_TPREGIME_2


def _erro_global(codigo: str, campo: str, detail: str, base_url: str) -> ErroDetalhe:
    # base_url entra só na URI de erro (espelho do Java buildErroGlobal / ItemCollector).
    _ = f"{base_url}/calculadora/observabilidade/simples-nacional/erros?codigo={codigo}"
    return ErroDetalhe(codigo, f"#/{campo}", detail)


def _validar_campos_globais(
    operacao: OperacaoSimplesClassica, base_url: str, parametro: ParametroCalculo
) -> list[ErroDetalhe]:
    erros: list[ErroDetalhe] = []
    if operacao.id is None or not str(operacao.id).strip():
        erros.append(
            _erro_global(
                "VSN-013", "id", "O identificador da operação (id) é obrigatório.", base_url
            )
        )
    if operacao.versao is None or not str(operacao.versao).strip():
        erros.append(
            _erro_global(
                "VSN-013", "versao", "A versão do payload (versao) é obrigatória.", base_url
            )
        )

    data: date | None = None
    if operacao.data is None or not str(operacao.data).strip():
        erros.append(
            _erro_global(
                "VSN-012", "data", "A data do fato gerador é obrigatória.", base_url
            )
        )
    else:
        try:
            data = date.fromisoformat(operacao.data.strip())
        except ValueError:
            erros.append(
                _erro_global(
                    "VSN-012",
                    "data",
                    f"Data inválida, recebido: '{operacao.data}' (esperado YYYY-MM-DD).",
                    base_url,
                )
            )

    _validar_escopo(operacao, data, erros, base_url, parametro)
    _validar_tp_ente_gov(operacao.tp_ente_gov, erros, base_url)

    if operacao.itens is None or not operacao.itens:
        erros.append(
            _erro_global(
                "VSN-011",
                "itens",
                "A lista de itens é obrigatória e não pode estar vazia.",
                base_url,
            )
        )
    return erros


def _validar_escopo(
    operacao: OperacaoSimplesClassica,
    data: date | None,
    erros: list[ErroDetalhe],
    base_url: str,
    parametro: ParametroCalculo,
) -> None:
    if operacao.tp_doc is None or not str(operacao.tp_doc).strip():
        erros.append(
            _erro_global(
                "VSN-014",
                _CAMPO_TPDOC,
                "O tipo de documento fiscal (tpDoc) é obrigatório e não foi informado.",
                base_url,
            )
        )
    else:
        tp_doc = _inteiro(operacao.tp_doc)
        if tp_doc is None:
            erros.append(
                _erro_global(
                    "VSN-015",
                    _CAMPO_TPDOC,
                    f"Tipo de documento não suportado pelo cálculo do Simples Nacional, "
                    f"recebido: '{operacao.tp_doc}'.",
                    base_url,
                )
            )
        elif data is not None and parametro.tp_doc_sem_tratamento_calculadora(tp_doc, data):
            erros.append(
                _erro_global(
                    "VSN-015",
                    _CAMPO_TPDOC,
                    f"Tipo de documento fiscal (tpDoc) de código {tp_doc} ainda não possui "
                    "tratamento implementado no cálculo do Simples Nacional.",
                    base_url,
                )
            )
        elif data is not None and not parametro.tp_doc_suportado(tp_doc, data):
            erros.append(
                _erro_global(
                    "VSN-015",
                    _CAMPO_TPDOC,
                    f"Tipo de documento não suportado pelo cálculo do Simples Nacional, "
                    f"recebido: '{operacao.tp_doc}'.",
                    base_url,
                )
            )

    crt = _inteiro(operacao.crt)
    if crt is None or crt < 1 or crt > 4:
        erros.append(
            _erro_global(
                "VSN-016",
                _CAMPO_CRT,
                f"O Código de Regime Tributário (CRT) é obrigatório e deve ser 1, 2, 3 ou 4, "
                f"recebido: '{operacao.crt}'.",
                base_url,
            )
        )
        return

    tp_regime_informado = (
        operacao.tp_regime_ibscbs is not None and str(operacao.tp_regime_ibscbs).strip() != ""
    )
    tp_regime = None
    if tp_regime_informado:
        tp_regime = _inteiro(operacao.tp_regime_ibscbs)
        if tp_regime is None or tp_regime not in (1, 2):
            erros.append(
                _erro_global(
                    "VSN-017",
                    _CAMPO_TPREGIMEIBSCBS,
                    f"Tipo de regime de apuração do IBS/CBS inválido, recebido: "
                    f"'{operacao.tp_regime_ibscbs}' (esperado 1 ou 2).",
                    base_url,
                )
            )
            return

    if crt == 4 and tp_regime_informado:
        erros.append(
            _erro_global(
                "VSN-018",
                _CAMPO_TPREGIMEIBSCBS,
                "CRT=4 (MEI) não admite tpRegimeIBSCBS algum (regra C21a-30 da NT 2026.005).",
                base_url,
            )
        )
    elif crt in (1, 2) and tp_regime == 2:
        erros.append(
            _erro_global(
                "VSN-018",
                _CAMPO_TPREGIMEIBSCBS,
                f"CRT={crt} não admite tpRegimeIBSCBS=2 (regra C21a-10 da NT 2026.005).",
                base_url,
            )
        )
    elif crt == 3 and tp_regime == 1:
        erros.append(
            _erro_global(
                "VSN-018",
                _CAMPO_TPREGIMEIBSCBS,
                "CRT=3 não admite tpRegimeIBSCBS=1 (regra C21a-20 da NT 2026.005).",
                base_url,
            )
        )

    if crt == 4:
        erros.append(
            _erro_global(
                "VSN-019",
                _CAMPO_CRT,
                "Operação fora do escopo do cálculo do Simples Nacional: MEI (CRT=4) "
                "está fora do Evento de Tributação do Simples Nacional.",
                base_url,
            )
        )
    if tp_regime == 1:
        erros.append(
            _erro_global(
                "VSN-019",
                _CAMPO_TPREGIMEIBSCBS,
                "Operação fora do escopo do cálculo do Simples Nacional: optante pelo regime "
                "regular do IBS/CBS (tpRegimeIBSCBS=1) tem a tributação calculada pelo regime "
                "regular, não por este endpoint.",
                base_url,
            )
        )
    if crt == 3 and not tp_regime_informado:
        erros.append(
            _erro_global(
                "VSN-019",
                _CAMPO_CRT,
                "Operação fora do escopo do cálculo do Simples Nacional: CRT=3 sem "
                "tpRegimeIBSCBS=2 (regime normal puro) não é Simples Nacional.",
                base_url,
            )
        )


def _validar_tp_ente_gov(
    tp_ente_gov: str | None, erros: list[ErroDetalhe], base_url: str
) -> None:
    if tp_ente_gov is None or not str(tp_ente_gov).strip():
        return
    valor = _inteiro(tp_ente_gov)
    if valor is None or valor < 1 or valor > 4:
        erros.append(
            _erro_global(
                "VSN-024",
                _CAMPO_TPENTEGOV,
                f"Tipo de ente governamental inválido, recebido: '{tp_ente_gov}' "
                "(esperado 1, 2, 3 ou 4).",
                base_url,
            )
        )


def uri_erro(base_url: str, codigo: str) -> str:
    return f"{base_url}/calculadora/observabilidade/simples-nacional/erros?codigo={codigo}"