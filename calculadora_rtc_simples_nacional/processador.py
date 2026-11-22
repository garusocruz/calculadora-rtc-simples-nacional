"""Processamento por item do Simples Nacional (pin a926d5a)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Callable, Protocol

from calculadora_rtc_simples_nacional.escolha import VocabularioRegime
from calculadora_rtc_simples_nacional.parametro import (
    ClassificacaoTributaria,
    ParametroCalculo,
    TipoReceitaBruta,
    buscar_atividades_por_cativsn,
    buscar_classificacoes_vigentes,
    contar_tratamentos_nao_implementados,
    contar_vinculo_atividade_tpdoc,
    contar_vinculo_classificacao_tpdoc,
    regime_para_calculo,
    tipo_receita_para_calculo,
)
from calculadora_rtc_simples_nacional.simples import EstadoItem, Insumo, Motivo, Resultado, Tributos, calcular_item

_DIGITOS_INTEIROS_ALIQUOTA = 3
_CASAS_ALIQUOTA_ENTRADA = 34
_DIGITOS_INTEIROS_VALOR = 13
_ESCALA_VALOR = 2

_FORMATO_ALIQUOTA = re.compile(
    rf"\d{{1,{_DIGITOS_INTEIROS_ALIQUOTA}}}(\.\d{{1,{_CASAS_ALIQUOTA_ENTRADA}}})?"
)
_FORMATO_VALOR = re.compile(rf"\d{{1,{_DIGITOS_INTEIROS_VALOR}}}(\.\d{{1,{_ESCALA_VALOR}}})?")
_UM_DIGITO = re.compile(r"\d")
_DESCRICAO_FORMATO_ALIQUOTA = (
    f"até {_DIGITOS_INTEIROS_ALIQUOTA} dígitos inteiros e até {_CASAS_ALIQUOTA_ENTRADA} casas decimais, "
    "sem notação científica (ex.: 1.6839)"
)
_DESCRICAO_FORMATO_VALOR = (
    f"até {_DIGITOS_INTEIROS_VALOR} dígitos inteiros e até {_ESCALA_VALOR} casas decimais, "
    "sem notação científica (ex.: 1000.00)"
)

_CAMPO_CCLASSTRIB = "cClassTrib"


class EstadoItemProcessado(Enum):
    CALCULADO = "CALCULADO"
    NAO_CALCULADO = "NAO_CALCULADO"
    INCONSISTENCIA_ENTRADA = "INCONSISTENCIA_ENTRADA"
    NAO_IMPLEMENTADO = "NAO_IMPLEMENTADO"
    FALHA_TECNICA = "FALHA_TECNICA"


@dataclass(frozen=True)
class ErroItem:
    code: str
    pointer: str
    detail: str


@dataclass
class ColetorItem:
    index: int
    estado: EstadoItemProcessado = EstadoItemProcessado.CALCULADO
    erros: list[ErroItem] = field(default_factory=list)

    def add_erro_validacao(self, codigo: str, campo: str, detail: str) -> None:
        if self.estado is EstadoItemProcessado.CALCULADO:
            self.estado = EstadoItemProcessado.INCONSISTENCIA_ENTRADA
        self.erros.append(ErroItem(codigo, _ponteiro(self.index, campo), detail))

    def add_nao_implementado(self, codigo: str, campo: str, detail: str) -> None:
        self.estado = EstadoItemProcessado.NAO_IMPLEMENTADO
        self.erros.append(ErroItem(codigo, _ponteiro(self.index, campo), detail))

    def add_falha_tecnica(self, ex: BaseException) -> None:
        self.estado = EstadoItemProcessado.FALHA_TECNICA
        self.erros.append(ErroItem("VSN-999", f"#/itens/{self.index}", str(ex)))

    def has_erros(self) -> bool:
        return bool(self.erros)


@dataclass(frozen=True)
class EntradaItem:
    numero: int | None
    cativ_sn: str | None
    class_trib: str | None
    base_calculo: str | None
    valor_imposto_seletivo: str | None
    ncm: str | None
    nbs: str | None


@dataclass(frozen=True)
class RegimeContexto:
    codigo: str
    calcula_tributos: bool
    gera_ibs: bool | None
    descricao: str


@dataclass(frozen=True)
class ContextoItem:
    data: date
    tp_doc: int
    regime: RegimeContexto
    tp_ente_gov: int | None
    fator_transicao_compra_gov: Decimal | None
    vocabulario_tipo_receita: VocabularioRegime | None
    normalizar_cativ_sn: bool
    admite_imposto_seletivo: bool
    casas_aliquota_calculo: int | None
    sigla_dfe: str | None
    permite_ncm_zero: bool

    @staticmethod
    def classico(
        data: date,
        tp_doc: int,
        regime: RegimeContexto,
        tp_ente_gov: int | None,
        fator_transicao: Decimal | None,
        sigla_dfe: str,
        permite_ncm_zero: bool,
    ) -> ContextoItem:
        return ContextoItem(
            data,
            tp_doc,
            regime,
            tp_ente_gov,
            fator_transicao,
            None,
            False,
            True,
            None,
            sigla_dfe,
            permite_ncm_zero,
        )


@dataclass(frozen=True)
class AtividadeItem:
    codigo: str | None
    atividade_id: int | None
    nao_tributavel: bool | None
    admissivel: bool

    def valida(self) -> bool:
        return self.atividade_id is not None and self.admissivel


@dataclass(frozen=True)
class ResolucaoClassificacao:
    classificacao: ClassificacaoTributaria
    tipo_receita: TipoReceitaBruta


@dataclass(frozen=True)
class AliquotasItem:
    aliquota_ibs: Decimal | None
    aliquota_cbs: Decimal | None
    nao_calcular: bool = False


@dataclass(frozen=True)
class DadosAliquotas:
    index: int
    atividade: AtividadeItem
    tipo_receita: TipoReceitaBruta | None
    cbs_exigida: bool
    ibs_exigida: bool


@dataclass(frozen=True)
class ObjetoItem:
    numero: int
    estado: EstadoItemProcessado
    motivo: Motivo | None
    tributos: Tributos | None
    erros: tuple[ErroItem, ...] | None


@dataclass(frozen=True)
class ItemProcessado:
    objeto: ObjetoItem


class ResolvedorAliquotas(Protocol):
    def __call__(self, dados: DadosAliquotas, collector: ColetorItem) -> AliquotasItem: ...


@dataclass(frozen=True)
class ItemAProcessar:
    entrada: EntradaItem
    resolvedor: ResolvedorAliquotas


class ValidacaoNomenclatura(Protocol):
    def validar_estrutural(
        self, ncm: str | None, nbs: str | None, data: date, collector: ColetorItem
    ) -> bool: ...

    def validar_por_classificacao(
        self,
        ncm: str | None,
        nbs: str | None,
        data: date,
        sigla_dfe: str | None,
        classificacao: ClassificacaoTributaria | None,
        estrutura_valida: bool,
        collector: ColetorItem,
    ) -> None: ...


class ValidacaoNomenclaturaBasica:
    """Validação estrutural mínima (NCM+NBS simultâneos e formato)."""

    def __init__(
        self,
        existe_ncm: Callable[[str, date], bool] | None = None,
        existe_nbs: Callable[[str, date], bool] | None = None,
        validar_classificacao: Callable[..., None] | None = None,
    ) -> None:
        self._existe_ncm = existe_ncm
        self._existe_nbs = existe_nbs
        self._validar_classificacao = validar_classificacao

    def validar_estrutural(
        self, ncm: str | None, nbs: str | None, data: date, collector: ColetorItem
    ) -> bool:
        try:
            if ncm and nbs:
                collector.add_erro_validacao(
                    "VSN-041",
                    "ncm",
                    "Não é permitido informar NCM e NBS simultaneamente para um item",
                )
                return False
            if ncm and not re.fullmatch(r"[0-9]{8}", ncm):
                collector.add_erro_validacao("VSN-051", "ncm", _msg_formato("ncm", 8))
                return False
            if nbs and not re.fullmatch(r"[0-9]{9}", nbs):
                collector.add_erro_validacao("VSN-051", "nbs", _msg_formato("nbs", 9))
                return False
            if ncm and self._existe_ncm and not self._existe_ncm(ncm, data):
                collector.add_erro_validacao(
                    "VSN-049", "ncm", f"NCM de código {ncm} não encontrada para a data {data}"
                )
                return False
            if nbs and self._existe_nbs and not self._existe_nbs(nbs, data):
                collector.add_erro_validacao(
                    "VSN-050", "nbs", f"NBS de código {nbs} não encontrada para a data {data}"
                )
                return False
        except BaseException as ex:
            collector.add_falha_tecnica(ex)
            return False
        return True

    def validar_por_classificacao(
        self,
        ncm: str | None,
        nbs: str | None,
        data: date,
        sigla_dfe: str | None,
        classificacao: ClassificacaoTributaria | None,
        estrutura_valida: bool,
        collector: ColetorItem,
    ) -> None:
        if not estrutura_valida or collector.has_erros() or classificacao is None:
            return
        if self._validar_classificacao is None:
            return
        try:
            if sigla_dfe is None:
                raise RuntimeError("Sigla TIPO_DFE ausente para o documento habilitado na data")
            self._validar_classificacao(sigla_dfe, classificacao, ncm, nbs, data)
        except BaseException as ex:
            _registrar_nomenclatura(ex, ncm, nbs, collector)


class ProcessadorItemSimples:
    def __init__(
        self,
        parametro: ParametroCalculo | None = None,
        nomenclatura: ValidacaoNomenclatura | None = None,
    ) -> None:
        self._parametro = parametro or ParametroCalculo()
        self._nomenclatura = nomenclatura or ValidacaoNomenclaturaBasica()

    def processar_itens(self, itens: list[ItemAProcessar], contexto: ContextoItem) -> list[ItemProcessado]:
        return [
            self.processar_item(item.entrada, index, contexto, item.resolvedor)
            for index, item in enumerate(itens)
        ]

    def processar_item(
        self,
        item: EntradaItem,
        index: int,
        contexto: ContextoItem,
        resolvedor: ResolvedorAliquotas,
    ) -> ItemProcessado:
        collector = ColetorItem(index)
        numero = item.numero
        if numero is None:
            collector.add_erro_validacao("VSN-010", "numero", "O número do item é obrigatório.")

        if _cclass_nao_implementado(item.class_trib, contexto, collector):
            return _resultado(collector, numero, index, None, None)

        ncm = item.ncm
        if contexto.permite_ncm_zero and ncm in ("00", "00000000"):
            ncm = None

        base = _validar_decimal(
            item.base_calculo, collector, "baseCalculo", "VSN-001", "VSN-002"
        )
        estrutura_ok = self._nomenclatura.validar_estrutural(ncm, item.nbs, contexto.data, collector)
        valor_is = (
            _validar_decimal(
                item.valor_imposto_seletivo,
                collector,
                "valorImpostoSeletivo",
                "VSN-003",
                "VSN-003",
            )
            if contexto.admite_imposto_seletivo
            else _validar_is_nao_admitido(item.valor_imposto_seletivo, collector)
        )

        resolucao = _resolver_tipo_receita(item.class_trib, contexto, collector, self._parametro)
        tipo_receita = resolucao.tipo_receita if resolucao else None
        self._nomenclatura.validar_por_classificacao(
            ncm,
            item.nbs,
            contexto.data,
            contexto.sigla_dfe,
            resolucao.classificacao if resolucao else None,
            estrutura_ok,
            collector,
        )

        calcula = contexto.regime.calcula_tributos
        atividade = AtividadeItem(None, None, None, False)
        aliquotas = AliquotasItem(None, None)
        if calcula:
            atividade = _validar_cativ_sn(item.cativ_sn, tipo_receita, contexto, collector)
            exigidas = atividade.valida() and tipo_receita is not None and tipo_receita.exige_aliquota
            ibs_exigida = exigidas and bool(contexto.regime.gera_ibs)
            aliquotas = resolvedor(
                DadosAliquotas(index, atividade, tipo_receita, exigidas, ibs_exigida), collector
            )

        if collector.has_erros():
            return _resultado(collector, numero, index, None, None)

        motivo = _motivo_nao_calculo(atividade, aliquotas, contexto) if calcula else None
        try:
            if tipo_receita is None:
                return _resultado(collector, numero, index, None, None)
            regime_calc = _regime_de_contexto(contexto.regime)
            insumo = Insumo(
                regime_calc,
                tipo_receita_para_calculo(tipo_receita),
                motivo,
                base,
                valor_is,
                aliquotas.aliquota_ibs,
                aliquotas.aliquota_cbs,
                contexto.tp_ente_gov,
                contexto.fator_transicao_compra_gov,
                contexto.casas_aliquota_calculo,
            )
            resultado = calcular_item(insumo)
            return _resultado_calculado(collector, numero, index, resultado)
        except BaseException as ex:
            collector.add_falha_tecnica(ex)
            return _resultado(collector, numero, index, None, None)

    @staticmethod
    def normalizar_cativ_sn(cativ_sn: str | None, completar_zero: bool) -> str | None:
        if cativ_sn is None or not cativ_sn.strip():
            return None
        codigo = cativ_sn.strip()
        return f"0{codigo}" if completar_zero and _UM_DIGITO.fullmatch(codigo) else codigo

    @staticmethod
    def validar_aliquota(
        valor: str | None, exigida: bool, collector: ColetorItem, campo: str, ausente: str, invalido: str
    ) -> Decimal | None:
        if valor is None or not valor.strip():
            if exigida:
                collector.add_erro_validacao(
                    ausente, campo, "A alíquota é exigida para o cálculo do item e não foi informada."
                )
            return None
        return _converter_no_formato(valor, _FORMATO_ALIQUOTA, _DESCRICAO_FORMATO_ALIQUOTA, collector, campo, invalido)


def _ponteiro(index: int, campo: str | None) -> str:
    return f"#/itens/{index}" if campo is None else f"#/itens/{index}/{campo}"


def _msg_formato(campo: str, digitos: int) -> str:
    return (
        f"O {campo.upper()} deve conter exclusivamente {digitos} dígitos ASCII, sem espaços ou símbolos."
    )


def _registrar_nomenclatura(ex: BaseException, ncm: str | None, nbs: str | None, collector: ColetorItem) -> None:
    mensagem = str(ex)
    if "simultaneamente" in mensagem.lower():
        collector.add_erro_validacao("VSN-041", "ncm", mensagem)
    elif "obrigat" in mensagem.lower():
        collector.add_erro_validacao("VSN-044", "cClassTrib", mensagem)
    elif "incompat" in mensagem.lower() or "não permitida para a classificação" in mensagem.lower():
        campo = "ncm" if ncm else "nbs" if nbs else "cClassTrib"
        collector.add_erro_validacao("VSN-045", campo, mensagem)
    else:
        collector.add_falha_tecnica(ex)


def _cclass_nao_implementado(class_trib: str | None, contexto: ContextoItem, collector: ColetorItem) -> bool:
    if class_trib is None or not class_trib.strip():
        return False
    codigo = class_trib.strip()
    if contar_tratamentos_nao_implementados(codigo, contexto.data) == 0:
        return False
    collector.add_nao_implementado(
        "VSN-027",
        _CAMPO_CCLASSTRIB,
        f"A classificação tributária '{codigo}' ainda não possui tratamento implementado no "
        f"cálculo do Simples Nacional na data '{contexto.data}'. Essa funcionalidade está prevista no "
        "roadmap e será disponibilizada em versão futura.",
    )
    return True


def _resolver_tipo_receita(
    class_trib: str | None,
    contexto: ContextoItem,
    collector: ColetorItem,
    parametro: ParametroCalculo,
) -> ResolucaoClassificacao | None:
    if class_trib is None or not class_trib.strip():
        collector.add_erro_validacao(
            "VSN-020",
            _CAMPO_CCLASSTRIB,
            "O código de classificação tributária (cClassTrib) é obrigatório e não foi informado.",
        )
        return None
    codigo = class_trib.strip()
    vigentes = buscar_classificacoes_vigentes(codigo, contexto.data)
    if not vigentes:
        collector.add_erro_validacao(
            "VSN-021",
            _CAMPO_CCLASSTRIB,
            f"O cClassTrib '{codigo}' não existe ou não está vigente na data '{contexto.data}': "
            "o tpRBSN não pôde ser determinado.",
        )
        return None
    classificacao = vigentes[0]
    if contar_vinculo_classificacao_tpdoc(codigo, contexto.tp_doc, contexto.data) == 0:
        collector.add_erro_validacao(
            "VSN-022",
            _CAMPO_CCLASSTRIB,
            f"O cClassTrib '{codigo}' não é admissível para o tipo de documento fiscal {contexto.tp_doc}.",
        )
        return None
    tp_rbsn = classificacao.tp_rbsn
    tipo = (
        parametro.buscar_tipo_receita_bruta(tp_rbsn, contexto.data)
        if contexto.vocabulario_tipo_receita is None
        else parametro.buscar_tipo_receita_bruta(tp_rbsn, contexto.data, contexto.vocabulario_tipo_receita)
    )
    if tipo is None:
        collector.add_erro_validacao(
            "VSN-026",
            _CAMPO_CCLASSTRIB,
            f"Não há parametrização de efeito vigente para o tipo de receita bruta "
            f"tpRBSN={tp_rbsn} na data '{contexto.data}'.",
        )
    return ResolucaoClassificacao(classificacao, tipo) if tipo else None


def _validar_cativ_sn(
    cativ_sn: str | None,
    tipo_receita: TipoReceitaBruta | None,
    contexto: ContextoItem,
    collector: ColetorItem,
) -> AtividadeItem:
    codigo = ProcessadorItemSimples.normalizar_cativ_sn(cativ_sn, contexto.normalizar_cativ_sn)
    if codigo is None:
        return AtividadeItem(None, None, None, False)
    atividades = buscar_atividades_por_cativsn(codigo, contexto.data)
    if not atividades:
        return AtividadeItem(codigo, None, None, False)
    atividade = atividades[0]
    if contar_vinculo_atividade_tpdoc(atividade.id, contexto.tp_doc, contexto.data) == 0:
        return AtividadeItem(codigo, atividade.id, atividade.nao_tributavel, False)
    if atividade.nao_tributavel and tipo_receita is not None and tipo_receita.vedado_nao_tributavel:
        collector.add_erro_validacao(
            "VSN-023",
            "cAtivSN",
            f"O código de atividade '{codigo}' (Operações não Tributáveis) é incompatível com "
            f"cClassTrib de tpRBSN={tipo_receita.codigo}.",
        )
    return AtividadeItem(codigo, atividade.id, atividade.nao_tributavel, True)


def _motivo_nao_calculo(
    atividade: AtividadeItem, aliquotas: AliquotasItem, contexto: ContextoItem
) -> Motivo | None:
    if atividade.codigo is None:
        return Motivo(
            "CATIVSN_AUSENTE",
            "O código de atividade do Simples Nacional (cAtivSN) não foi informado; sem ele o IBS e a CBS "
            "do item não são calculados (NT 2026.005, §5.3.3).",
        )
    if atividade.atividade_id is None:
        return Motivo(
            "CATIVSN_DESCONHECIDO",
            f"O código de atividade '{atividade.codigo}' não existe ou não está vigente na data do fato gerador; "
            "o IBS e a CBS do item não são calculados.",
        )
    if not atividade.admissivel:
        documento = contexto.sigla_dfe or "informado"
        return Motivo(
            "CATIVSN_INADMISSIVEL_NO_DOCUMENTO",
            f"A atividade '{atividade.codigo}' não é admitida no tipo de documento {documento} "
            f"(tpDoc {contexto.tp_doc}); o IBS e a CBS do item não são calculados.",
        )
    if aliquotas.nao_calcular:
        return Motivo(
            "ANEXO_SEM_ALIQUOTA_CBS",
            "A Tabela de Alíquotas Efetivas do Simples Nacional não traz a alíquota de CBS do Anexo "
            "aplicado para o contribuinte no período; o IBS e a CBS do item não são calculados.",
        )
    return None


def _validar_decimal(
    valor: str | None, collector: ColetorItem, campo: str, ausente: str, invalido: str
) -> Decimal | None:
    if valor is None or not valor.strip():
        collector.add_erro_validacao(ausente, campo, "O campo é obrigatório e não foi informado.")
        return None
    return _converter_no_formato(valor, _FORMATO_VALOR, _DESCRICAO_FORMATO_VALOR, collector, campo, invalido)


def _validar_is_nao_admitido(valor: str | None, collector: ColetorItem) -> Decimal | None:
    if valor is None or not valor.strip():
        return None
    convertido = _converter_no_formato(
        valor, _FORMATO_VALOR, _DESCRICAO_FORMATO_VALOR, collector, "valorImpostoSeletivo", "VSN-003"
    )
    if convertido is not None and convertido != 0:
        collector.add_erro_validacao(
            "VSN-035",
            "valorImpostoSeletivo",
            f"O documento não tem Imposto Seletivo: o valor deve ser zero ou não ser informado, recebido: '{valor}'.",
        )
    return None


def _converter_no_formato(
    valor: str,
    formato: re.Pattern[str],
    descricao: str,
    collector: ColetorItem,
    campo: str,
    invalido: str,
) -> Decimal | None:
    texto = valor.strip()
    if formato.fullmatch(texto):
        return Decimal(texto)
    if texto.startswith("-") and formato.fullmatch(texto[1:]):
        collector.add_erro_validacao(invalido, campo, f"O valor não pode ser negativo, recebido: '{valor}'.")
    else:
        collector.add_erro_validacao(
            invalido,
            campo,
            f"O valor não é um número decimal válido, recebido: '{valor}'. Informe {descricao}.",
        )
    return None


def _regime_de_contexto(regime: RegimeContexto):
    from calculadora_rtc_simples_nacional.simples import Destino, Regime

    destinos = {
        "SN_PLENO": (Destino.DEVIDO, Destino.PENDENTE_SUSPENSO),
        "SN_SUBLIMITE": (Destino.DEVIDO, Destino.PENDENTE_SUSPENSO),
        "PENDENTE": (Destino.PENDENTE_SUSPENSO, Destino.ZERO),
        "PENDENTE_SUBLIMITE": (Destino.PENDENTE_SUSPENSO, Destino.ZERO),
        "SOMENTE_RECEITA": (Destino.DEVIDO, Destino.PENDENTE_SUSPENSO),
    }
    devido, pendente = destinos.get(regime.codigo, (Destino.DEVIDO, Destino.PENDENTE_SUSPENSO))
    gera_ibs = regime.gera_ibs if regime.gera_ibs is not None else regime.codigo != "SN_SUBLIMITE"
    return Regime(regime.codigo, regime.calcula_tributos, regime.descricao, gera_ibs, devido, pendente)


def _resultado(
    collector: ColetorItem,
    numero: int | None,
    index: int,
    tributos: Tributos | None,
    motivo: Motivo | None,
) -> ItemProcessado:
    n = numero if numero is not None else index + 1
    erros = tuple(collector.erros) if collector.erros else None
    return ItemProcessado(
        ObjetoItem(n, collector.estado, motivo, tributos, erros)
    )


def _resultado_calculado(collector: ColetorItem, numero: int | None, index: int, resultado: Resultado) -> ItemProcessado:
    estado = (
        EstadoItemProcessado.CALCULADO
        if resultado.estado is EstadoItem.CALCULADO
        else EstadoItemProcessado.NAO_CALCULADO
    )
    n = numero if numero is not None else index + 1
    return ItemProcessado(
        ObjetoItem(n, estado, resultado.motivo, resultado.tributos, None)
    )