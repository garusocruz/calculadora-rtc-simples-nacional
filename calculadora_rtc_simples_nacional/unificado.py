"""Núcleo dos endpoints não assistido e assistido do Simples Nacional (pin a926d5a)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Protocol

from calculadora_rtc_simples_nacional import banco
from calculadora_rtc_simples_nacional.arredondamento import totalizar
from calculadora_rtc_simples_nacional.escolha import (
    CAMPO_CRT,
    CAMPO_REGAPIBSCBSSN,
    CAMPO_REGAPTRIBSN,
    CAMPO_TPBM,
    CAMPO_TPRETISSQN,
    CAMPO_TRIBISSQN,
    AtividadeSimples,
    CamposIssItem,
    EscolhaParAliquotasService,
    LinhaAliquotas,
    MotivoResolucaoAliquota,
    RegraAliquota,
    TipoAliquota,
    VocabularioRegime,
    _inteiro,
)
from calculadora_rtc_simples_nacional.parametro import (
    CodigoRegimeApuracao,
    ParametroCalculo,
    RegimeApuracao,
    TipoDfeCalculo,
    buscar_atividades_por_cativsn,
)
from calculadora_rtc_simples_nacional.nomenclatura import montar_validacao_nomenclatura
from calculadora_rtc_simples_nacional.processador import (
    AliquotasItem,
    ColetorItem,
    ContextoItem,
    DadosAliquotas,
    EntradaItem,
    EstadoItemProcessado,
    ErroItem,
    ItemAProcessar,
    ObjetoItem,
    ProcessadorItemSimples,
    RegimeContexto,
    ResolvedorAliquotas,
)

_CAMPO_TPDOC = "tpDoc"
_CAMPO_CRT = "CRT"
_CAMPO_TPREGIMEIBSCBS = "tpRegimeIBSCBS"
_CAMPO_OPSIMPNAC = "opSimpNac"
_CAMPO_REGAPIBSCBSSN = "regApIBSCBSSN"
_CAMPO_REGAPTRIBSN = "regApTribSN"
_CAMPO_TPENTEGOV = "tpEnteGov"
_OPTANTES = {3, 4}


class OrigemLinhaAliquotas(Enum):
    REQUISICAO = "REQUISICAO"
    TABELA_ALIQUOTAS_EFETIVAS = "TABELA_ALIQUOTAS_EFETIVAS"


@dataclass(frozen=True)
class LinhaAliquotasComOrigem:
    linha: LinhaAliquotas
    origem: OrigemLinhaAliquotas = OrigemLinhaAliquotas.REQUISICAO


@dataclass(frozen=True)
class ErroDetalhe:
    code: str
    pointer: str
    detail: str


class ErrosCalculoException(Exception):
    def __init__(self, erros: list[ErroDetalhe]) -> None:
        self.erros = erros
        super().__init__(erros[0].detail if erros else "erro de cálculo")


@dataclass(frozen=True)
class ItemSimplesUnificadoInput:
    numero: int | None
    cativ_sn: str | None
    class_trib: str | None
    nbs: str | None
    ncm: str | None
    base_calculo: str | None
    valor_imposto_seletivo: str | None
    trib_issqn: str | None
    tp_ret_issqn: str | None
    tp_bm: str | None


@dataclass(frozen=True)
class DadosOperacaoSimples:
    id: str | None
    versao: str | None
    data: str | None
    tp_doc: str | None
    crt: str | None
    tp_regime_ibscbs: str | None
    op_simp_nac: str | None
    reg_ap_ibscbssn: str | None
    reg_ap_trib_sn: str | None
    tp_ente_gov: str | None
    itens: list[ItemSimplesUnificadoInput]


@dataclass(frozen=True)
class ResolucaoAliquotaItem:
    numero: int | None
    cativ_sn: str | None
    anexo_aplicado: str | None
    tipo_aliquota: TipoAliquota | None
    regra_aliquota: RegraAliquota | None
    aliquota_ibs: Decimal | None
    aliquota_cbs: Decimal | None
    motivo: str
    avisos: tuple[str, ...]


@dataclass(frozen=True)
class ResolucaoAliquotas:
    itens: tuple[ResolucaoAliquotaItem, ...]
    avisos: tuple[str, ...]
    fator_r: bool | None = None
    ind_sublimite: bool | None = None


@dataclass(frozen=True)
class OperacaoSimples:
    data: str
    tp_doc: str
    crt: str | None
    tp_regime_ibscbs: str | None
    op_simp_nac: str | None
    reg_ap_ibscbssn: str | None
    reg_ap_trib_sn: str | None
    tp_ente_gov: str | None
    regime_apuracao: CodigoRegimeApuracao


@dataclass(frozen=True)
class TotalSimples:
    receita_bruta_total: Decimal | None
    base_calculo_total: Decimal | None
    ibs_total: Decimal | None
    ibs_pendente_total: Decimal | None
    cbs_total: Decimal | None
    cbs_pendente_total: Decimal | None
    imposto_seletivo_total: Decimal | None
    total_tributos: Decimal | None


@dataclass(frozen=True)
class ObservabilidadeSimples:
    oper: OperacaoSimples
    resolucao_aliquotas: ResolucaoAliquotas | None
    objetos: tuple[ObjetoItem, ...]
    total: TotalSimples | None


class FonteLinhaAliquotasSimples(Protocol):
    def obter(self, data: date) -> LinhaAliquotasComOrigem: ...

    def montar_resolucao(
        self,
        linha: LinhaAliquotasComOrigem,
        itens: list[ResolucaoAliquotaItem],
        avisos: list[str],
    ) -> ResolucaoAliquotas: ...


@dataclass(frozen=True)
class RegimeInformado:
    crt: int | None
    tp_regime_ibscbs: int | None
    op_simp_nac: int | None
    reg_ap_ibscbssn: int | None
    reg_ap_trib_sn: int | None


def _erro_global(codigo: str, campo: str, detail: str) -> ErroDetalhe:
    return ErroDetalhe(codigo, f"#/{campo}", detail)


def _conectar() -> sqlite3.Connection:
    return banco.conectar()


def buscar_sigla_vigente_por_id(tipo_dfe_id: int, data: date) -> str | None:
    sql = """
        SELECT td.TPDF_SIGLA
        FROM TIPO_DFE td
        WHERE td.TPDF_ID = ?
          AND ? BETWEEN td.TPDF_INICIO_VIGENCIA AND COALESCE(td.TPDF_FIM_VIGENCIA, ?)
    """
    iso = data.isoformat()
    with _conectar() as conexao:
        row = conexao.execute(sql, (tipo_dfe_id, iso, iso)).fetchone()
    return str(row[0]) if row else None


def permite_ncm_zero_vigente_por_id(tipo_dfe_id: int, data: date) -> bool:
    sql = """
        SELECT td.TPDF_B_PERMITE_NCM_ZERO
        FROM TIPO_DFE td
        WHERE td.TPDF_ID = ?
          AND ? BETWEEN td.TPDF_INICIO_VIGENCIA AND COALESCE(td.TPDF_FIM_VIGENCIA, ?)
    """
    iso = data.isoformat()
    with _conectar() as conexao:
        row = conexao.execute(sql, (tipo_dfe_id, iso, iso)).fetchone()
    return bool(int(row[0])) if row else False


def _sem_aliquotas(_dados: DadosAliquotas, _collector: ColetorItem) -> AliquotasItem:
    return AliquotasItem(None, None, False)


class CalculoSimplesUnificadoService:
    def __init__(
        self,
        parametro: ParametroCalculo | None = None,
        processador: ProcessadorItemSimples | None = None,
        escolha: EscolhaParAliquotasService | None = None,
    ) -> None:
        self._parametro = parametro or ParametroCalculo()
        self._processador = processador or ProcessadorItemSimples(
            self._parametro, montar_validacao_nomenclatura()
        )
        self._escolha = escolha or EscolhaParAliquotasService()

    def processar(
        self,
        operacao: DadosOperacaoSimples,
        fonte: FonteLinhaAliquotasSimples | None,
    ) -> ObservabilidadeSimples:
        erros: list[ErroDetalhe] = []
        data = _validar_campos_globais(operacao, erros)
        documento = _validar_documento(operacao, data, erros, self._parametro)
        if documento is not None:
            _validar_regime(operacao, documento.vocabulario_regime, erros)
            _validar_quantidade_itens(operacao, documento, erros)
        if erros:
            raise ErrosCalculoException(erros)

        assert data is not None and documento is not None
        vocabulario = documento.vocabulario_regime
        sigla_dfe = buscar_sigla_vigente_por_id(documento.tipo_dfe_id, data)
        permite_ncm_zero = permite_ncm_zero_vigente_por_id(documento.tipo_dfe_id, data)
        informado = _converter_regime(operacao)

        regime = self._parametro.buscar_regime_por_campos(
            vocabulario,
            informado.crt,
            informado.tp_regime_ibscbs,
            informado.op_simp_nac,
            informado.reg_ap_ibscbssn,
            data,
        )
        if regime is None:
            raise ErrosCalculoException([_erro_fora_do_escopo(vocabulario, informado, data)])

        calcula_tributos = regime.calcula_tributos
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
                        )
                    ]
                )

        linha_com_origem: LinhaAliquotasComOrigem | None = None
        if calcula_tributos:
            if fonte is None:
                raise ErrosCalculoException(
                    [
                        _erro_global(
                            "VSN-039",
                            "aliquotasEfetivas",
                            "A linha de alíquotas efetivas do contribuinte (aliquotasEfetivas) é obrigatória no "
                            "cálculo não assistido quando o regime calcula tributos.",
                        )
                    ]
                )
            linha_com_origem = fonte.obter(data)
        situacoes = (
            self._parametro.buscar_situacoes_iss_par_aliquota(data) if calcula_tributos else []
        )
        avisos = _avisos_da_operacao(vocabulario, regime, informado, linha_com_origem)

        regime_ctx = RegimeContexto(
            regime.codigo.value,
            regime.calcula_tributos,
            regime.gera_ibs,
            regime.descricao,
        )
        contexto = ContextoItem(
            data,
            int(operacao.tp_doc.strip()),
            regime_ctx,
            tp_ente_gov,
            fator_transicao,
            vocabulario,
            True,
            documento.admite_imposto_seletivo,
            documento.casas_aliquota_calculo,
            sigla_dfe,
            permite_ncm_zero,
        )
        fatos = _fatos_da_operacao(informado)
        resolucoes: list[ResolucaoAliquotaItem | None] = [None] * len(operacao.itens)
        itens_processar: list[ItemAProcessar] = []
        for indice, item in enumerate(operacao.itens):
            seguro = _item_seguro(item)
            resolvedor: ResolvedorAliquotas
            if calcula_tributos:
                assert linha_com_origem is not None
                resolvedor = self._criar_resolvedor(
                    seguro,
                    vocabulario,
                    linha_com_origem,
                    fatos,
                    situacoes,
                    resolucoes,
                    indice,
                    data,
                )
            else:
                resolvedor = _sem_aliquotas
            itens_processar.append(
                ItemAProcessar(
                    EntradaItem(
                        seguro.numero,
                        seguro.cativ_sn,
                        seguro.class_trib,
                        seguro.base_calculo,
                        seguro.valor_imposto_seletivo,
                        seguro.ncm,
                        seguro.nbs,
                    ),
                    resolvedor,
                )
            )

        processados = self._processador.processar_itens(itens_processar, contexto)
        objetos = sorted(
            (p.objeto for p in processados),
            key=lambda o: (o.numero is None, o.numero if o.numero is not None else 0),
        )
        resolucao_itens = _completar_resolucoes(processados, operacao.itens, resolucoes, calcula_tributos)
        resolucao = (
            fonte.montar_resolucao(linha_com_origem, resolucao_itens, avisos)
            if calcula_tributos and fonte is not None and linha_com_origem is not None
            else None
        )
        return ObservabilidadeSimples(
            OperacaoSimples(
                operacao.data or "",
                operacao.tp_doc or "",
                operacao.crt,
                operacao.tp_regime_ibscbs,
                operacao.op_simp_nac,
                operacao.reg_ap_ibscbssn,
                operacao.reg_ap_trib_sn,
                operacao.tp_ente_gov,
                regime.codigo,
            ),
            resolucao,
            tuple(objetos),
            _totalizar_objetos(objetos),
        )

    def _criar_resolvedor(
        self,
        item: ItemSimplesUnificadoInput,
        vocabulario: VocabularioRegime,
        linha_com_origem: LinhaAliquotasComOrigem,
        fatos_da_operacao: dict[str, int],
        situacoes: list,
        resolucoes: list[ResolucaoAliquotaItem | None],
        indice: int,
        data: date,
    ) -> ResolvedorAliquotas:
        linha = linha_com_origem.linha
        origem = linha_com_origem.origem
        escolha = self._escolha

        def resolver(dados: DadosAliquotas, collector: ColetorItem) -> AliquotasItem:
            cativ = dados.atividade.codigo
            if dados.atividade.atividade_id is None:
                res = _sem_par(item, cativ, "ATIVIDADE_DESCONHECIDA", ())
                resolucoes[indice] = res
                return AliquotasItem(None, None, False)

            vigentes = buscar_atividades_por_cativsn(cativ or "", data)
            row = next((r for r in vigentes if r.id == dados.atividade.atividade_id), None)
            atividade_dom = (
                AtividadeSimples(
                    row.id,
                    row.codigo,
                    row.nao_tributavel,
                    row.anexo_sem_fator_r,
                    row.anexo_com_fator_r,
                    row.iss_no_simples,
                    row.admite_beneficio_municipal,
                )
                if row
                else None
            )
            avisos: list[str] = []
            fatos = dict(fatos_da_operacao)
            if dados.atividade.admissivel and atividade_dom is not None:
                iss = escolha.avaliar_campos_iss(
                    vocabulario,
                    atividade_dom,
                    CamposIssItem(item.trib_issqn, item.tp_ret_issqn, item.tp_bm),
                    collector,
                )
                avisos.extend(iss.avisos)
                _colocar(fatos, CAMPO_TRIBISSQN, iss.trib_issqn)
                _colocar(fatos, CAMPO_TPRETISSQN, iss.tp_ret_issqn)
                _colocar(fatos, CAMPO_TPBM, iss.tp_bm)
            elif atividade_dom is None:
                res = _sem_par(item, cativ, "ATIVIDADE_DESCONHECIDA", ())
                resolucoes[indice] = res
                return AliquotasItem(None, None, False)

            assert atividade_dom is not None
            escolha_par = escolha.escolher(
                atividade_dom, dados.atividade.admissivel, linha, fatos, situacoes
            )
            if escolha_par.motivo is MotivoResolucaoAliquota.FATOR_R_AUSENTE:
                _erro_no_ponteiro(
                    collector,
                    "VSN-040",
                    _ponteiro_linha(origem, collector, "fatorR"),
                    f'O fatorR é exigido: a atividade {cativ} é sujeita ao fator "r" (Anexo III ou V).',
                )
            if escolha_par.par_sem_redistribuicao_ausente:
                avisos.append(EscolhaParAliquotasService.aviso_par_sem_redistribuicao_ausente(escolha_par.anexo or ""))

            par = escolha_par.par
            p_cbs = par.aliquota_cbs if par else None
            p_ibs = par.aliquota_ibs if par else None
            nao_calcular = False
            if escolha_par.caminho_par is not None:
                if origem is OrigemLinhaAliquotas.TABELA_ALIQUOTAS_EFETIVAS and p_cbs is None:
                    nao_calcular = True
                else:
                    _exigir(
                        dados.cbs_exigida,
                        p_cbs,
                        "VSN-004",
                        "pCBSSN",
                        escolha_par,
                        origem,
                        collector,
                    )
                    _exigir(
                        dados.ibs_exigida,
                        p_ibs,
                        "VSN-006",
                        "pIBSSN",
                        escolha_par,
                        origem,
                        collector,
                    )

            resolucao = ResolucaoAliquotaItem(
                item.numero,
                cativ,
                escolha_par.anexo,
                escolha_par.tipo_aliquota,
                escolha_par.regra,
                p_ibs,
                p_cbs,
                escolha_par.motivo.value,
                tuple(avisos),
            )
            resolucoes[indice] = resolucao
            return AliquotasItem(p_ibs, p_cbs, nao_calcular)

        return resolver


def _completar_resolucoes(
    processados,
    itens_entrada: list[ItemSimplesUnificadoInput],
    resolucoes: list[ResolucaoAliquotaItem | None],
    calcula_tributos: bool,
) -> list[ResolucaoAliquotaItem]:
    if not calcula_tributos:
        return []
    resultado: list[ResolucaoAliquotaItem] = []
    for index, proc in enumerate(processados):
        if resolucoes[index] is not None:
            resultado.append(resolucoes[index])  # type: ignore[arg-type]
            continue
        if proc.objeto.estado is EstadoItemProcessado.NAO_IMPLEMENTADO:
            item = _item_seguro(itens_entrada[index])
            codigo = ProcessadorItemSimples.normalizar_cativ_sn(item.cativ_sn, True)
            resultado.append(
                ResolucaoAliquotaItem(
                    item.numero,
                    codigo,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "ITEM_NAO_IMPLEMENTADO",
                    (),
                )
            )
        else:
            item = _item_seguro(itens_entrada[index])
            resultado.append(
                ResolucaoAliquotaItem(
                    item.numero,
                    ProcessadorItemSimples.normalizar_cativ_sn(item.cativ_sn, True),
                    None,
                    None,
                    None,
                    None,
                    None,
                    "ATIVIDADE_DESCONHECIDA",
                    (),
                )
            )
    return resultado


def _totalizar_objetos(objetos: tuple[ObjetoItem, ...]) -> TotalSimples | None:
    com_trib = [o for o in objetos if o.tributos is not None]
    if not com_trib:
        return None

    def somar(campo) -> Decimal | None:
        valores = [campo(t.tributos) for t in com_trib if t.tributos is not None]
        valores = [v for v in valores if v is not None]
        return totalizar(valores) if valores else None

    v_ibs = somar(lambda t: t.valor_ibs)
    v_cbs = somar(lambda t: t.valor_cbs)
    v_is = somar(lambda t: t.imposto_seletivo.valor if t.imposto_seletivo else None)
    partes = [v for v in (v_ibs, v_cbs, v_is) if v is not None]
    total_tributos = totalizar(partes) if partes else None
    return TotalSimples(
        somar(lambda t: t.receita_bruta),
        somar(lambda t: t.base_calculo),
        v_ibs,
        somar(lambda t: t.ibs_pendente),
        v_cbs,
        somar(lambda t: t.cbs_pendente),
        v_is,
        total_tributos,
    )


def _sem_par(
    item: ItemSimplesUnificadoInput, cativ: str | None, motivo: str, avisos: tuple[str, ...]
) -> ResolucaoAliquotaItem:
    return ResolucaoAliquotaItem(
        item.numero, cativ, None, None, None, None, None, motivo, avisos
    )


def _erro_no_ponteiro(collector: ColetorItem, codigo: str, pointer: str, detail: str) -> None:
    if collector.estado is EstadoItemProcessado.CALCULADO:
        collector.estado = EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    collector.erros.append(ErroItem(codigo, pointer, detail))


def _ponteiro_linha(origem: OrigemLinhaAliquotas, collector: ColetorItem, caminho: str) -> str:
    if origem is OrigemLinhaAliquotas.REQUISICAO:
        return f"#/aliquotasEfetivas/{caminho}"
    return f"#/itens/{collector.index}/cAtivSN"


def _exigir(
    exigida: bool,
    aliquota: Decimal | None,
    codigo: str,
    campo: str,
    escolha,
    origem: OrigemLinhaAliquotas,
    collector: ColetorItem,
) -> None:
    if not exigida or aliquota is not None:
        return
    par = (
        "sem"
        if escolha.tipo_aliquota is TipoAliquota.SEM_REDISTRIBUICAO
        and not escolha.par_sem_redistribuicao_ausente
        else "com"
    )
    if escolha.tipo_aliquota is TipoAliquota.PAR_UNICO:
        detalhe = (
            f"A alíquota {campo} do anexo {escolha.anexo} é exigida para o cálculo do item e não está na "
            "linha de alíquotas."
        )
    else:
        detalhe = (
            f"A alíquota {campo} do anexo {escolha.anexo} (par {par} redistribuição do ISS, regra "
            f"{escolha.regra.value if escolha.regra else escolha.regra}) é exigida para o cálculo do item "
            "e não está na linha de alíquotas."
        )
    _erro_no_ponteiro(
        collector,
        codigo,
        _ponteiro_linha(origem, collector, f"{escolha.caminho_par}/{campo}"),
        detalhe,
    )


def _colocar(fatos: dict[str, int], campo: str, valor: int | None) -> None:
    if valor is not None:
        fatos[campo] = valor


def _fatos_da_operacao(informado: RegimeInformado) -> dict[str, int]:
    fatos: dict[str, int] = {}
    _colocar(fatos, CAMPO_CRT, informado.crt)
    _colocar(fatos, CAMPO_REGAPIBSCBSSN, informado.reg_ap_ibscbssn)
    _colocar(fatos, CAMPO_REGAPTRIBSN, informado.reg_ap_trib_sn)
    return dict(fatos)


def _item_seguro(item: ItemSimplesUnificadoInput | None) -> ItemSimplesUnificadoInput:
    if item is not None:
        return item
    return ItemSimplesUnificadoInput(None, None, None, None, None, None, None, None, None, None)


def _avisos_da_operacao(
    vocabulario: VocabularioRegime,
    regime: RegimeApuracao,
    informado: RegimeInformado,
    linha: LinhaAliquotasComOrigem | None,
) -> list[str]:
    avisos: list[str] = []
    if linha is not None:
        gera_ibs = bool(regime.gera_ibs)
        if gera_ibs == linha.linha.impedimento_sublimite:
            avisos.append(
                f"Regime de apuração {regime.codigo.value} ({_descrever_regime(vocabulario, informado)}) diverge "
                f"do indicador de impedimento por sublimite da linha de alíquotas "
                f"({linha.linha.impedimento_sublimite})"
            )
    if informado.reg_ap_ibscbssn == 2 and informado.reg_ap_trib_sn == 1:
        avisos.append(
            "regApIBSCBSSN 2 (excesso de sublimite) com regApTribSN 1: incoerente — quem excede o "
            "sublimite tem o ISS fora do Simples Nacional"
        )
    return avisos


def _descrever_regime(vocabulario: VocabularioRegime, informado: RegimeInformado) -> str:
    if vocabulario is VocabularioRegime.NFSE:
        return f"opSimpNac={informado.op_simp_nac}, regApIBSCBSSN={informado.reg_ap_ibscbssn}"
    if informado.tp_regime_ibscbs is None:
        return f"CRT={informado.crt}"
    return f"CRT={informado.crt}, tpRegimeIBSCBS={informado.tp_regime_ibscbs}"


def _validar_campos_globais(operacao: DadosOperacaoSimples, erros: list[ErroDetalhe]) -> date | None:
    if operacao.id is None or not str(operacao.id).strip():
        erros.append(_erro_global("VSN-013", "id", "O identificador da operação (id) é obrigatório."))
    if operacao.versao is None or not str(operacao.versao).strip():
        erros.append(_erro_global("VSN-013", "versao", "A versão do payload (versao) é obrigatória."))
    data: date | None = None
    if operacao.data is None or not str(operacao.data).strip():
        erros.append(_erro_global("VSN-012", "data", "A data do fato gerador é obrigatória."))
    else:
        try:
            data = date.fromisoformat(operacao.data.strip())
        except ValueError:
            erros.append(
                _erro_global(
                    "VSN-012",
                    "data",
                    f"Data inválida, recebido: '{operacao.data}' (esperado YYYY-MM-DD).",
                )
            )
    if operacao.tp_ente_gov is not None and str(operacao.tp_ente_gov).strip():
        tp = _inteiro(operacao.tp_ente_gov)
        if tp is None or tp < 1 or tp > 4:
            erros.append(
                _erro_global(
                    "VSN-024",
                    _CAMPO_TPENTEGOV,
                    f"Tipo de ente governamental inválido, recebido: '{operacao.tp_ente_gov}' "
                    "(esperado 1, 2, 3 ou 4).",
                )
            )
    if operacao.itens is None or not operacao.itens:
        erros.append(
            _erro_global("VSN-011", "itens", "A lista de itens é obrigatória e não pode estar vazia.")
        )
    return data


def _validar_documento(
    operacao: DadosOperacaoSimples,
    data: date | None,
    erros: list[ErroDetalhe],
    parametro: ParametroCalculo,
) -> TipoDfeCalculo | None:
    if operacao.tp_doc is None or not str(operacao.tp_doc).strip():
        erros.append(
            _erro_global(
                "VSN-014",
                _CAMPO_TPDOC,
                "O tipo de documento fiscal (tpDoc) é obrigatório e não foi informado.",
            )
        )
        return None
    tp_doc = _inteiro(operacao.tp_doc)
    if tp_doc is not None and data is not None and parametro.tp_doc_sem_tratamento_calculadora(tp_doc, data):
        erros.append(
            _erro_global(
                "VSN-015",
                _CAMPO_TPDOC,
                f"Tipo de documento fiscal (tpDoc) de código {tp_doc} ainda não possui tratamento "
                "implementado no cálculo do Simples Nacional.",
            )
        )
        return None
    if tp_doc is None or data is None:
        if tp_doc is None:
            erros.append(
                _erro_global(
                    "VSN-015",
                    _CAMPO_TPDOC,
                    f"Tipo de documento não suportado pelo cálculo do Simples Nacional, recebido: "
                    f"'{operacao.tp_doc}'.",
                )
            )
        return None
    documento = parametro.buscar_tipo_dfe_calculo(tp_doc, data)
    if documento is None:
        erros.append(
            _erro_global(
                "VSN-015",
                _CAMPO_TPDOC,
                f"Tipo de documento não suportado pelo cálculo do Simples Nacional, recebido: "
                f"'{operacao.tp_doc}'.",
            )
        )
    return documento


def _validar_quantidade_itens(
    operacao: DadosOperacaoSimples, documento: TipoDfeCalculo, erros: list[ErroDetalhe]
) -> None:
    maximo = documento.maximo_itens
    if maximo is not None and operacao.itens is not None and len(operacao.itens) > maximo:
        texto = "exatamente 1 item" if maximo == 1 else f"no máximo {maximo} itens"
        erros.append(
            _erro_global(
                "VSN-034",
                "itens",
                f"O documento {operacao.tp_doc.strip()} admite {texto}, recebidos {len(operacao.itens)}.",
            )
        )


def _validar_regime(
    operacao: DadosOperacaoSimples, vocabulario: VocabularioRegime, erros: list[ErroDetalhe]
) -> None:
    if vocabulario is VocabularioRegime.NFSE:
        _proibido(operacao.crt, _CAMPO_CRT, "NFS-e", erros)
        _proibido(operacao.tp_regime_ibscbs, _CAMPO_TPREGIMEIBSCBS, "NFS-e", erros)
        _validar_regime_nfse(operacao, erros)
    else:
        _proibido(operacao.op_simp_nac, _CAMPO_OPSIMPNAC, "documento com CRT", erros)
        _proibido(operacao.reg_ap_ibscbssn, _CAMPO_REGAPIBSCBSSN, "documento com CRT", erros)
        _proibido(operacao.reg_ap_trib_sn, _CAMPO_REGAPTRIBSN, "documento com CRT", erros)
        _validar_regime_crt(operacao, erros)


def _proibido(valor: str | None, campo: str, documento: str, erros: list[ErroDetalhe]) -> None:
    if valor is not None and str(valor).strip():
        erros.append(
            _erro_global(
                "VSN-033",
                campo,
                f"O campo {campo} não pertence ao vocabulário de regime do {documento}, recebido: '{valor}'.",
            )
        )


def _validar_regime_crt(operacao: DadosOperacaoSimples, erros: list[ErroDetalhe]) -> None:
    crt = _inteiro(operacao.crt)
    if crt is None or crt < 1 or crt > 4:
        erros.append(
            _erro_global(
                "VSN-016",
                _CAMPO_CRT,
                f"O Código de Regime Tributário (CRT) é obrigatório e deve ser 1, 2, 3 ou 4, "
                f"recebido: '{operacao.crt}'.",
            )
        )
        return
    if operacao.tp_regime_ibscbs is None or not str(operacao.tp_regime_ibscbs).strip():
        return
    tp_regime = _inteiro(operacao.tp_regime_ibscbs)
    if tp_regime is None or tp_regime not in (1, 2):
        erros.append(
            _erro_global(
                "VSN-017",
                _CAMPO_TPREGIMEIBSCBS,
                f"Tipo de regime de apuração do IBS/CBS inválido, recebido: '{operacao.tp_regime_ibscbs}' "
                "(esperado 1 ou 2).",
            )
        )
        return
    if crt == 4:
        msg = (
            "CRT=4 (MEI) não admite tpRegimeIBSCBS algum (regras C21a-10 e C21a-30 da NT 2026.005)."
            if tp_regime == 2
            else "CRT=4 (MEI) não admite tpRegimeIBSCBS algum (regra C21a-30 da NT 2026.005)."
        )
        erros.append(_erro_global("VSN-018", _CAMPO_TPREGIMEIBSCBS, msg))
    elif crt in (1, 2) and tp_regime == 2:
        erros.append(
            _erro_global(
                "VSN-018",
                _CAMPO_TPREGIMEIBSCBS,
                f"CRT={crt} não admite tpRegimeIBSCBS=2 (regra C21a-10 da NT 2026.005).",
            )
        )
    elif crt == 3 and tp_regime == 1:
        erros.append(
            _erro_global(
                "VSN-018",
                _CAMPO_TPREGIMEIBSCBS,
                "CRT=3 não admite tpRegimeIBSCBS=1 (regra C21a-20 da NT 2026.005).",
            )
        )


def _validar_regime_nfse(operacao: DadosOperacaoSimples, erros: list[ErroDetalhe]) -> None:
    op = _inteiro(operacao.op_simp_nac)
    if op is None or op < 1 or op > 4:
        erros.append(
            _erro_global(
                "VSN-030",
                _CAMPO_OPSIMPNAC,
                f"A situação perante o Simples Nacional (opSimpNac) é obrigatória na NFS-e e deve ser "
                f"1, 2, 3 ou 4, recebido: '{operacao.op_simp_nac}'.",
            )
        )
        return
    _validar_campo_nfse(
        operacao.reg_ap_ibscbssn,
        _CAMPO_REGAPIBSCBSSN,
        op,
        "VSN-031",
        "regra 313 da NFS-e",
        erros,
    )
    _validar_campo_nfse(
        operacao.reg_ap_trib_sn,
        _CAMPO_REGAPTRIBSN,
        op,
        "VSN-032",
        "regra E0166 da NFS-e, estendida pela NT 009",
        erros,
    )


def _validar_campo_nfse(
    valor: str | None,
    campo: str,
    op_simp_nac: int,
    codigo: str,
    regra_obrigatorio: str,
    erros: list[ErroDetalhe],
) -> None:
    informado = valor is not None and str(valor).strip()
    if informado:
        convertido = _inteiro(valor)
        if convertido is None or convertido < 1 or convertido > 3:
            erros.append(
                _erro_global(codigo, campo, f"O {campo} deve ser 1, 2 ou 3, recebido: '{valor}'.")
            )
        elif op_simp_nac not in _OPTANTES:
            sufixo = " (regra E0162 da NFS-e)" if campo == _CAMPO_REGAPTRIBSN else ""
            erros.append(
                _erro_global(
                    codigo,
                    campo,
                    f"O {campo} não pode ser informado com opSimpNac={op_simp_nac} "
                    f"(não optante ou MEI){sufixo}.",
                )
            )
    elif op_simp_nac in _OPTANTES:
        erros.append(
            _erro_global(
                codigo, campo, f"O {campo} é obrigatório com opSimpNac={op_simp_nac} ({regra_obrigatorio})."
            )
        )


def _converter_regime(operacao: DadosOperacaoSimples) -> RegimeInformado:
    return RegimeInformado(
        _inteiro(operacao.crt),
        _inteiro(operacao.tp_regime_ibscbs),
        _inteiro(operacao.op_simp_nac),
        _inteiro(operacao.reg_ap_ibscbssn),
        _inteiro(operacao.reg_ap_trib_sn),
    )


def _erro_fora_do_escopo(
    vocabulario: VocabularioRegime, informado: RegimeInformado, data: date
) -> ErroDetalhe:
    if vocabulario is VocabularioRegime.NFSE:
        campo = _CAMPO_OPSIMPNAC
        if informado.op_simp_nac == 1:
            motivo = "prestador não optante pelo Simples Nacional (opSimpNac=1)"
        elif informado.op_simp_nac == 2:
            motivo = "MEI (opSimpNac=2) está fora do cálculo do IBS e da CBS pelo Simples Nacional"
        else:
            motivo = (
                f"não há enquadramento vigente na data '{data}' para opSimpNac={informado.op_simp_nac} e "
                f"regApIBSCBSSN={informado.reg_ap_ibscbssn}"
            )
    else:
        campo = _CAMPO_CRT
        if informado.crt == 4:
            motivo = "MEI (CRT=4) está fora do Evento de Tributação do Simples Nacional"
        elif informado.crt == 3 and informado.tp_regime_ibscbs is None:
            motivo = "CRT=3 sem tpRegimeIBSCBS=2 (regime normal puro) não é Simples Nacional"
        else:
            motivo = f"não há enquadramento vigente na data '{data}' para {_descrever_regime(vocabulario, informado)}"
    return _erro_global(
        "VSN-019",
        campo,
        f"Operação fora do escopo do cálculo do Simples Nacional: {motivo}.",
    )