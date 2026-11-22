"""Consulta de atividades do Simples Nacional (domínio; pin a926d5a)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from enum import Enum

from calculadora_rtc_simples_nacional import banco
from calculadora_rtc_simples_nacional.parametro import (
    ParametroCalculo,
    buscar_classificacoes_vigentes,
    buscar_vinculos_tpdoc_vigentes,
)


class ErroConsultaAtividade(ValueError):
    """Erro de parâmetro equivalente ao HTTP 400 do endpoint Java."""


class ModoFatorR(Enum):
    NAO_APLICAVEL = "NAO_APLICAVEL"
    OPCIONAL = "OPCIONAL"
    INDISPONIVEL = "INDISPONIVEL"
    OBRIGATORIO = "OBRIGATORIO"


ANEXOS_VALIDOS: tuple[str, ...] = ("I", "II", "III", "IV", "V")


def _validar_anexos_configurados(anexos_configurados: set[str] | None) -> set[str] | None:
    if anexos_configurados is None:
        return None
    for anexo in anexos_configurados:
        if anexo not in ANEXOS_VALIDOS:
            raise ErroConsultaAtividade(
                f"Anexo inválido: '{anexo}'. Valores aceitos: {', '.join(ANEXOS_VALIDOS)}."
            )
    return anexos_configurados


@dataclass(frozen=True)
class Derivacao:
    disponivel: bool
    anexos_faltantes: tuple[str, ...]
    modo_fator_r: ModoFatorR


@dataclass(frozen=True)
class AtividadeSimplesDomain:
    codigo: str
    ordem: int
    descricao: str
    anexo_sem_fator_r: str | None
    anexo_com_fator_r: str | None
    sujeita_fator_r: bool
    rotulo_anexo: str
    rotulo_curto_anexo: str
    disponivel: bool
    anexos_faltantes: tuple[str, ...]
    modo_fator_r: ModoFatorR
    tp_docs_admissiveis: tuple[str, ...]
    admissivel_no_documento: bool | None = None
    compativel_com_class_trib: bool | None = None


@dataclass(frozen=True)
class _AtividadeVigente:
    id: int
    ordem: int
    descricao: str
    codigo: str
    anexo_sem_fator_r: str | None
    anexo_com_fator_r: str | None
    rotulo: str
    rotulo_curto: str
    nao_tributavel: bool


def derivar_anexos(
    anexo_sem_fator_r: str | None,
    anexo_com_fator_r: str | None,
    anexos_configurados: set[str] | None,
) -> Derivacao:
    if anexo_com_fator_r is not None and anexo_sem_fator_r is None:
        raise ValueError(
            f'Atividade inconsistente: anexoComFatorR ({anexo_com_fator_r}) preenchido sem '
            'anexoSemFatorR. Não existe atividade "só com Fator R"; corrija o banco.'
        )
    configurados = set(ANEXOS_VALIDOS) if anexos_configurados is None else set(anexos_configurados)
    anexos_possiveis = [
        anexo for anexo in ANEXOS_VALIDOS if anexo in (anexo_sem_fator_r, anexo_com_fator_r)
    ]
    anexos_faltantes = tuple(a for a in anexos_possiveis if a not in configurados)
    disponivel = not anexos_possiveis or any(a in configurados for a in anexos_possiveis)
    if anexo_com_fator_r is None:
        modo = ModoFatorR.NAO_APLICAVEL
    elif anexo_com_fator_r in configurados:
        modo = (
            ModoFatorR.OPCIONAL
            if anexo_sem_fator_r in configurados
            else ModoFatorR.OBRIGATORIO
        )
    else:
        modo = ModoFatorR.INDISPONIVEL
    return Derivacao(disponivel, anexos_faltantes, modo)


def _bool_sql(valor: object) -> bool:
    return bool(int(valor)) if valor is not None else False


def _buscar_vigentes(data: date) -> list[_AtividadeVigente]:
    sql = """
        SELECT ATSN_ID, ATSN_ORDEM, ATSN_DESCRICAO, ATSN_CATIVSN,
               ATSN_ANEXO_SEM_FATOR_R, ATSN_ANEXO_COM_FATOR_R,
               ATSN_ROTULO, ATSN_ROTULO_CURTO, ATSN_IN_NAO_TRIBUTAVEL
        FROM ATIVIDADE_SIMPLES_NACIONAL a
        WHERE ? BETWEEN a.ATSN_INICIO_VIGENCIA AND COALESCE(a.ATSN_FIM_VIGENCIA, ?)
        ORDER BY a.ATSN_ORDEM ASC
    """
    iso = data.isoformat()
    with banco.conectar() as conexao:
        conexao.row_factory = sqlite3.Row
        return [
            _AtividadeVigente(
                int(row["ATSN_ID"]),
                int(row["ATSN_ORDEM"]),
                row["ATSN_DESCRICAO"],
                row["ATSN_CATIVSN"],
                row["ATSN_ANEXO_SEM_FATOR_R"],
                row["ATSN_ANEXO_COM_FATOR_R"],
                row["ATSN_ROTULO"],
                row["ATSN_ROTULO_CURTO"],
                _bool_sql(row["ATSN_IN_NAO_TRIBUTAVEL"]),
            )
            for row in conexao.execute(sql, (iso, iso)).fetchall()
        ]


def _contar_tipos_dfe_por_tipo(tp_doc: int) -> int:
    sql = "SELECT COUNT(1) AS n FROM TIPO_DFE td WHERE td.TPDF_TIPO = ?"
    with banco.conectar() as conexao:
        conexao.row_factory = sqlite3.Row
        return int(conexao.execute(sql, (tp_doc,)).fetchone()["n"])


class AtividadeSimplesService:
    """Espelho de br.gov.serpro.rtc.api.atividadesimples.service.AtividadeSimplesService."""

    def __init__(self, parametro: ParametroCalculo | None = None) -> None:
        self._parametro = parametro or ParametroCalculo()

    def listar(
        self,
        data: date,
        anexos_configurados: set[str] | None = None,
        tp_doc: str | None = None,
        c_class_trib: str | None = None,
    ) -> list[AtividadeSimplesDomain]:
        anexos = _validar_anexos_configurados(anexos_configurados)
        tp_doc_validado = self._validar_tp_doc(tp_doc)
        vedado_nao_tributavel = self._resolver_vedado_nao_tributavel(c_class_trib, data)
        tp_docs_por_atividade = self._buscar_tp_docs_admissiveis(data)
        return [
            self._to_domain(
                atividade,
                anexos,
                list(tp_docs_por_atividade.get(atividade.id, ())),
                tp_doc_validado,
                vedado_nao_tributavel,
            )
            for atividade in _buscar_vigentes(data)
        ]

    def buscar_por_codigo(
        self,
        codigo: str | None,
        data: date,
        tp_doc: str | None = None,
        c_class_trib: str | None = None,
    ) -> AtividadeSimplesDomain | None:
        if codigo is None:
            return None
        for atividade in self.listar(data, None, tp_doc, c_class_trib):
            if atividade.codigo == codigo:
                return atividade
        return None

    def _validar_tp_doc(self, tp_doc: str | None) -> str | None:
        if tp_doc is None or not tp_doc.strip():
            return None
        informado = tp_doc.strip()
        try:
            tipo = int(informado)
        except ValueError as exc:
            raise ErroConsultaAtividade(
                f"Tipo de documento fiscal inválido: '{informado}'. "
                "Informe o valor numérico da coluna TPDF_TIPO da TIPO_DFE (ex.: 55, 65, 91)."
            ) from exc
        if tipo < 0 or _contar_tipos_dfe_por_tipo(tipo) == 0:
            raise ErroConsultaAtividade(
                f"Tipo de documento fiscal desconhecido: '{informado}'. "
                "Não há linha na TIPO_DFE com TPDF_TIPO correspondente."
            )
        return str(tipo)

    def _resolver_vedado_nao_tributavel(
        self, c_class_trib: str | None, data: date
    ) -> bool | None:
        if c_class_trib is None or not c_class_trib.strip():
            return None
        codigo = c_class_trib.strip()
        vigentes = buscar_classificacoes_vigentes(codigo, data)
        if not vigentes:
            raise ErroConsultaAtividade(
                f"Código de classificação tributária desconhecido ou fora de vigência: '{codigo}'. "
                "Informe um cClassTrib do grupo da CBS vigente na data de referência."
            )
        tp_rbsn = vigentes[0].tp_rbsn
        tipo_receita = self._parametro.buscar_tipo_receita_bruta(tp_rbsn, data)
        if tipo_receita is None:
            raise ErroConsultaAtividade(
                f"Não há parametrização de efeito vigente para o tipo de receita bruta tpRBSN={tp_rbsn} "
                f"do cClassTrib '{codigo}' na data de referência."
            )
        return tipo_receita.vedado_nao_tributavel

    @staticmethod
    def _buscar_tp_docs_admissiveis(data: date) -> dict[int, tuple[str, ...]]:
        agrupado: dict[int, list[int]] = {}
        for vinculo in buscar_vinculos_tpdoc_vigentes(data):
            agrupado.setdefault(vinculo.atividade_id, []).append(vinculo.tp_doc)
        return {
            atividade_id: tuple(str(t) for t in sorted(docs))
            for atividade_id, docs in agrupado.items()
        }

    @staticmethod
    def _to_domain(
        atividade: _AtividadeVigente,
        anexos_configurados: set[str] | None,
        tp_docs_admissiveis: list[str],
        tp_doc: str | None,
        vedado_nao_tributavel: bool | None,
    ) -> AtividadeSimplesDomain:
        derivacao = derivar_anexos(
            atividade.anexo_sem_fator_r,
            atividade.anexo_com_fator_r,
            anexos_configurados,
        )
        admissivel_no_documento = None if tp_doc is None else tp_doc in tp_docs_admissiveis
        compativel_com_class_trib = None
        if vedado_nao_tributavel is not None:
            compativel_com_class_trib = not (
                vedado_nao_tributavel and atividade.nao_tributavel
            )
        disponivel = (
            derivacao.disponivel
            and admissivel_no_documento is not False
            and compativel_com_class_trib is not False
        )
        return AtividadeSimplesDomain(
            atividade.codigo,
            atividade.ordem,
            atividade.descricao,
            atividade.anexo_sem_fator_r,
            atividade.anexo_com_fator_r,
            atividade.anexo_com_fator_r is not None,
            atividade.rotulo,
            atividade.rotulo_curto,
            disponivel,
            derivacao.anexos_faltantes,
            derivacao.modo_fator_r,
            tuple(tp_docs_admissiveis),
            admissivel_no_documento,
            compativel_com_class_trib,
        )


def listar(
    data: date,
    anexos_configurados: set[str] | None = None,
    tp_doc: str | None = None,
    c_class_trib: str | None = None,
) -> list[AtividadeSimplesDomain]:
    return AtividadeSimplesService().listar(data, anexos_configurados, tp_doc, c_class_trib)


def buscar_por_codigo(
    codigo: str | None,
    data: date,
    tp_doc: str | None = None,
    c_class_trib: str | None = None,
) -> AtividadeSimplesDomain | None:
    return AtividadeSimplesService().buscar_por_codigo(codigo, data, tp_doc, c_class_trib)