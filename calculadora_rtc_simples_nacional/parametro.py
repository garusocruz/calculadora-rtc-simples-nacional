"""Parâmetros e catálogo do Simples Nacional via SQLite (pin a926d5a)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from calculadora_rtc_simples_nacional import banco
from calculadora_rtc_simples_nacional.escolha import RegraAliquota, SituacaoIssParAliquota, TipoAliquota, VocabularioRegime
from calculadora_rtc_simples_nacional.simples import Destino, Regime, TipoReceita


class RegimeCalculo(Enum):
    CRT_1 = "CRT_1"
    CRT_2 = "CRT_2"
    CRT_3_TPREGIME_2 = "CRT_3_TPREGIME_2"


class CodigoRegimeApuracao(Enum):
    SN_PLENO = "SN_PLENO"
    SN_SUBLIMITE = "SN_SUBLIMITE"
    PENDENTE = "PENDENTE"
    PENDENTE_SUBLIMITE = "PENDENTE_SUBLIMITE"
    SOMENTE_RECEITA = "SOMENTE_RECEITA"


class DestinoValor(Enum):
    DEVIDO = "DEVIDO"
    PENDENTE_SUSPENSO = "PENDENTE_SUSPENSO"
    ZERO = "ZERO"


@dataclass(frozen=True)
class TipoReceitaBruta:
    codigo: int
    descricao: str
    compoe_receita: bool
    imposto_seletivo_compoe_receita: bool
    fator_receita: Decimal
    pendente_suspenso: bool
    exige_aliquota: bool
    vedado_nao_tributavel: bool
    vocabulario_regime: VocabularioRegime | None = None


@dataclass(frozen=True)
class RegimeApuracao:
    id: int
    codigo: CodigoRegimeApuracao
    descricao: str
    calcula_tributos: bool
    gera_ibs: bool | None
    destino_devido: DestinoValor | None
    destino_pendente: DestinoValor | None


@dataclass(frozen=True)
class TipoDfeCalculo:
    tipo_dfe_id: int
    vocabulario_regime: VocabularioRegime
    casas_aliquota_calculo: int | None
    maximo_itens: int | None
    admite_imposto_seletivo: bool


@dataclass
class AtividadeNacional:
    id: int
    ordem: int
    descricao: str
    codigo: str
    anexo_sem_fator_r: str | None
    anexo_com_fator_r: str | None
    nao_tributavel: bool
    iss_no_simples: bool
    admite_beneficio_municipal: bool


@dataclass(frozen=True)
class VinculoTpDocAtividade:
    atividade_id: int
    tp_doc: int


@dataclass(frozen=True)
class ClassificacaoTributaria:
    id: int
    codigo: str
    tp_rbsn: int


@dataclass(frozen=True)
class TransicaoAliquotaCompraGov:
    id: int
    fator: Decimal
    inicio_vigencia: date
    fim_vigencia: date | None


def banco_disponivel() -> bool:
    return banco.caminho().is_file()


def _conectar() -> sqlite3.Connection:
    conexao = banco.conectar()
    conexao.row_factory = sqlite3.Row
    return conexao


def _bool_sql(valor: object) -> bool:
    return bool(int(valor)) if valor is not None else False


def _decimal(valor: object) -> Decimal:
    return Decimal(str(valor))


def _destino(valor: str | None) -> DestinoValor | None:
    return DestinoValor(valor) if valor else None


def _vocabulario(valor: str | None) -> VocabularioRegime | None:
    return VocabularioRegime(valor) if valor else None


def _regime_row(row: sqlite3.Row) -> RegimeApuracao:
    return RegimeApuracao(
        int(row["RASN_ID"]),
        CodigoRegimeApuracao(row["RASN_CD"]),
        row["RASN_DESCRICAO"],
        _bool_sql(row["RASN_IN_CALCULA_TRIBUTOS"]),
        None if row["RASN_IN_GERA_IBS"] is None else _bool_sql(row["RASN_IN_GERA_IBS"]),
        _destino(row["RASN_DESTINO_DEVIDO"]),
        _destino(row["RASN_DESTINO_PENDENTE_SUSPENSO"]),
    )


def _tipo_receita_row(row: sqlite3.Row) -> TipoReceitaBruta:
    return TipoReceitaBruta(
        int(row["TRBS_CD"]),
        row["TRBS_DESCRICAO"],
        _bool_sql(row["TRBS_IN_COMPOE_RECEITA"]),
        _bool_sql(row["TRBS_IN_IS_COMPOE_RECEITA"]),
        _decimal(row["TRBS_FATOR_RECEITA"]),
        _bool_sql(row["TRBS_IN_PENDENTE_SUSPENSO"]),
        _bool_sql(row["TRBS_IN_EXIGE_ALIQUOTA"]),
        _bool_sql(row["TRBS_IN_VEDADO_NAO_TRIBUTAVEL"]),
        _vocabulario(row["TRBS_VOCABULARIO_REGIME"]),
    )


def _atividade_row(row: sqlite3.Row) -> AtividadeNacional:
    return AtividadeNacional(
        int(row["ATSN_ID"]),
        int(row["ATSN_ORDEM"]),
        row["ATSN_DESCRICAO"],
        row["ATSN_CATIVSN"],
        row["ATSN_ANEXO_SEM_FATOR_R"],
        row["ATSN_ANEXO_COM_FATOR_R"],
        _bool_sql(row["ATSN_IN_NAO_TRIBUTAVEL"]),
        _bool_sql(row["ATSN_IN_ISS_NO_SIMPLES"]),
        _bool_sql(row["ATSN_IN_ADMITE_BENEFICIO_MUNICIPAL"]),
    )


class ParametroCalculo:
    """Fachada dos parâmetros do cálculo (espelho de ParametroCalculoSimplesService)."""

    def tp_doc_suportado(self, tp_doc: int, data: date) -> bool:
        return _contar_vinculos_tpdoc_calculo(tp_doc, data) > 0

    def tp_doc_sem_tratamento_calculadora(self, tp_doc: int, data: date) -> bool:
        sql = """
            SELECT COUNT(1) AS n
            FROM TIPO_DFE td
            WHERE td.TPDF_TIPO = ?
              AND td.TPDF_B_POSSUI_TRATAMENTO_CALCULADORA = 0
              AND ? BETWEEN td.TPDF_INICIO_VIGENCIA AND COALESCE(td.TPDF_FIM_VIGENCIA, ?)
        """
        with _conectar() as conexao:
            return int(conexao.execute(sql, (tp_doc, data.isoformat(), data.isoformat())).fetchone()["n"]) > 0

    def buscar_tipo_dfe_calculo(self, tp_doc: int, data: date) -> TipoDfeCalculo | None:
        sql = """
            SELECT t.TDCS_TPDF_ID, t.TDCS_VOCABULARIO_REGIME, t.TDCS_CASAS_ALIQUOTA_CALCULO,
                   t.TDCS_MAXIMO_ITENS, t.TDCS_IN_ADMITE_IS
            FROM TIPO_DFE_CALCULO_SIMPLES_NACIONAL t
            JOIN TIPO_DFE td ON td.TPDF_ID = t.TDCS_TPDF_ID
            WHERE td.TPDF_TIPO = ?
              AND ? BETWEEN t.TDCS_INICIO_VIGENCIA AND COALESCE(t.TDCS_FIM_VIGENCIA, ?)
              AND ? BETWEEN td.TPDF_INICIO_VIGENCIA AND COALESCE(td.TPDF_FIM_VIGENCIA, ?)
            ORDER BY t.TDCS_INICIO_VIGENCIA DESC
            LIMIT 1
        """
        params = (tp_doc, data.isoformat(), data.isoformat(), data.isoformat(), data.isoformat())
        with _conectar() as conexao:
            row = conexao.execute(sql, params).fetchone()
        if row is None:
            return None
        return TipoDfeCalculo(
            int(row["TDCS_TPDF_ID"]),
            VocabularioRegime(row["TDCS_VOCABULARIO_REGIME"]),
            row["TDCS_CASAS_ALIQUOTA_CALCULO"],
            row["TDCS_MAXIMO_ITENS"],
            _bool_sql(row["TDCS_IN_ADMITE_IS"]),
        )

    def buscar_tipo_receita_bruta(
        self, tp_rbsn: int, data: date, vocabulario: VocabularioRegime | None = None
    ) -> TipoReceitaBruta | None:
        if vocabulario is None:
            sql = """
                SELECT *
                FROM TIPO_RECEITA_BRUTA_SIMPLES_NACIONAL t
                WHERE t.TRBS_CD = ?
                  AND t.TRBS_VOCABULARIO_REGIME IS NULL
                  AND ? BETWEEN t.TRBS_INICIO_VIGENCIA AND COALESCE(t.TRBS_FIM_VIGENCIA, ?)
                ORDER BY t.TRBS_INICIO_VIGENCIA DESC
                LIMIT 1
            """
            params: tuple = (tp_rbsn, data.isoformat(), data.isoformat())
        else:
            sql = """
                SELECT *
                FROM TIPO_RECEITA_BRUTA_SIMPLES_NACIONAL t
                WHERE t.TRBS_CD = ?
                  AND (t.TRBS_VOCABULARIO_REGIME = ? OR t.TRBS_VOCABULARIO_REGIME IS NULL)
                  AND ? BETWEEN t.TRBS_INICIO_VIGENCIA AND COALESCE(t.TRBS_FIM_VIGENCIA, ?)
                ORDER BY CASE WHEN t.TRBS_VOCABULARIO_REGIME IS NULL THEN 1 ELSE 0 END,
                         t.TRBS_INICIO_VIGENCIA DESC
                LIMIT 1
            """
            params = (tp_rbsn, vocabulario.value, data.isoformat(), data.isoformat())
        with _conectar() as conexao:
            conexao.row_factory = sqlite3.Row
            row = conexao.execute(sql, params).fetchone()
        return _tipo_receita_row(row) if row else None

    def buscar_regime_apuracao(self, regime: RegimeCalculo, data: date) -> RegimeApuracao | None:
        if regime is RegimeCalculo.CRT_1:
            return self.buscar_regime_por_campos(VocabularioRegime.CRT, 1, None, None, None, data)
        if regime is RegimeCalculo.CRT_2:
            return self.buscar_regime_por_campos(VocabularioRegime.CRT, 2, None, None, None, data)
        return self.buscar_regime_por_campos(VocabularioRegime.CRT, 3, 2, None, None, data)

    def buscar_regime_por_campos(
        self,
        vocabulario: VocabularioRegime,
        crt: int | None,
        tp_regime_ibscbs: int | None,
        op_simp_nac: int | None,
        reg_ap_ibscbssn: int | None,
        data: date,
    ) -> RegimeApuracao | None:
        sql = """
            SELECT r.*
            FROM ENQUADRAMENTO_REGIME_SIMPLES_NACIONAL e
            JOIN REGIME_APURACAO_SIMPLES_NACIONAL r ON r.RASN_ID = e.ERSN_RASN_ID
            WHERE e.ERSN_VOCABULARIO_REGIME = ?
              AND ((? IS NULL AND e.ERSN_CRT IS NULL) OR e.ERSN_CRT = ?)
              AND ((? IS NULL AND e.ERSN_TPREGIMEIBSCBS IS NULL) OR e.ERSN_TPREGIMEIBSCBS = ?)
              AND ((? IS NULL AND e.ERSN_OPSIMPNAC IS NULL) OR e.ERSN_OPSIMPNAC = ?)
              AND ((? IS NULL AND e.ERSN_REGAPIBSCBSSN IS NULL) OR e.ERSN_REGAPIBSCBSSN = ?)
              AND ? BETWEEN e.ERSN_INICIO_VIGENCIA AND COALESCE(e.ERSN_FIM_VIGENCIA, ?)
              AND ? BETWEEN r.RASN_INICIO_VIGENCIA AND COALESCE(r.RASN_FIM_VIGENCIA, ?)
            ORDER BY e.ERSN_INICIO_VIGENCIA DESC, r.RASN_INICIO_VIGENCIA DESC
            LIMIT 1
        """
        iso = data.isoformat()
        params = (
            vocabulario.value,
            crt,
            crt,
            tp_regime_ibscbs,
            tp_regime_ibscbs,
            op_simp_nac,
            op_simp_nac,
            reg_ap_ibscbssn,
            reg_ap_ibscbssn,
            iso,
            iso,
            iso,
            iso,
        )
        with _conectar() as conexao:
            conexao.row_factory = sqlite3.Row
            row = conexao.execute(sql, params).fetchone()
        return _regime_row(row) if row else None

    def buscar_fator_transicao_compra_gov(self, data: date) -> Decimal | None:
        sql = """
            SELECT TACG_FATOR
            FROM TRANSICAO_ALIQUOTA_COMPRA_GOV_SIMPLES_NACIONAL t
            WHERE ? BETWEEN t.TACG_INICIO_VIGENCIA AND COALESCE(t.TACG_FIM_VIGENCIA, ?)
            ORDER BY t.TACG_INICIO_VIGENCIA DESC
            LIMIT 1
        """
        iso = data.isoformat()
        with _conectar() as conexao:
            row = conexao.execute(sql, (iso, iso)).fetchone()
        return _decimal(row[0]) if row else None

    def buscar_situacoes_iss_par_aliquota(self, data: date) -> list[SituacaoIssParAliquota]:
        sql = """
            SELECT SIPA_ID, SIPA_CAMPO, SIPA_VALOR, SIPA_REGRA, SIPA_TIPO_ALIQUOTA, SIPA_ORDEM
            FROM SITUACAO_ISS_PAR_ALIQUOTA_SIMPLES_NACIONAL s
            WHERE ? BETWEEN s.SIPA_INICIO_VIGENCIA AND COALESCE(s.SIPA_FIM_VIGENCIA, ?)
            ORDER BY s.SIPA_ORDEM ASC, s.SIPA_ID ASC
        """
        iso = data.isoformat()
        with _conectar() as conexao:
            conexao.row_factory = sqlite3.Row
            linhas = conexao.execute(sql, (iso, iso)).fetchall()
        return [
            SituacaoIssParAliquota(
                int(row["SIPA_ID"]),
                row["SIPA_CAMPO"],
                int(row["SIPA_VALOR"]),
                RegraAliquota(row["SIPA_REGRA"]),
                TipoAliquota(row["SIPA_TIPO_ALIQUOTA"]),
                int(row["SIPA_ORDEM"]),
            )
            for row in linhas
        ]


def listar_atividades_vigentes(data: date) -> list[AtividadeNacional]:
    sql = """
        SELECT *
        FROM ATIVIDADE_SIMPLES_NACIONAL a
        WHERE ? BETWEEN a.ATSN_INICIO_VIGENCIA AND COALESCE(a.ATSN_FIM_VIGENCIA, ?)
        ORDER BY a.ATSN_ORDEM ASC
    """
    iso = data.isoformat()
    with _conectar() as conexao:
        conexao.row_factory = sqlite3.Row
        return [_atividade_row(row) for row in conexao.execute(sql, (iso, iso)).fetchall()]


def buscar_atividades_por_cativsn(codigo: str, data: date) -> list[AtividadeNacional]:
    sql = """
        SELECT *
        FROM ATIVIDADE_SIMPLES_NACIONAL a
        WHERE a.ATSN_CATIVSN = ?
          AND ? BETWEEN a.ATSN_INICIO_VIGENCIA AND COALESCE(a.ATSN_FIM_VIGENCIA, ?)
        ORDER BY a.ATSN_INICIO_VIGENCIA DESC
    """
    iso = data.isoformat()
    with _conectar() as conexao:
        conexao.row_factory = sqlite3.Row
        return [_atividade_row(row) for row in conexao.execute(sql, (codigo, iso, iso)).fetchall()]


def contar_vinculo_atividade_tpdoc(atividade_id: int, tp_doc: int, data: date) -> int:
    sql = """
        SELECT COUNT(1) AS n
        FROM TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL t
        JOIN TIPO_DFE td ON td.TPDF_ID = t.TDAS_TPDF_ID
        WHERE t.TDAS_ATSN_ID = ?
          AND td.TPDF_TIPO = ?
          AND ? BETWEEN t.TDAS_INICIO_VIGENCIA AND COALESCE(t.TDAS_FIM_VIGENCIA, ?)
          AND ? BETWEEN td.TPDF_INICIO_VIGENCIA AND COALESCE(td.TPDF_FIM_VIGENCIA, ?)
    """
    iso = data.isoformat()
    with _conectar() as conexao:
        return int(conexao.execute(sql, (atividade_id, tp_doc, iso, iso, iso, iso)).fetchone()["n"])


def buscar_vinculos_tpdoc_vigentes(data: date) -> list[VinculoTpDocAtividade]:
    sql = """
        SELECT t.TDAS_ATSN_ID AS atividade_id, td.TPDF_TIPO AS tp_doc
        FROM TIPO_DFE_ATIVIDADE_SIMPLES_NACIONAL t
        JOIN TIPO_DFE td ON td.TPDF_ID = t.TDAS_TPDF_ID
            AND ? BETWEEN td.TPDF_INICIO_VIGENCIA AND COALESCE(td.TPDF_FIM_VIGENCIA, ?)
        WHERE ? BETWEEN t.TDAS_INICIO_VIGENCIA AND COALESCE(t.TDAS_FIM_VIGENCIA, ?)
    """
    iso = data.isoformat()
    with _conectar() as conexao:
        conexao.row_factory = sqlite3.Row
        return [
            VinculoTpDocAtividade(int(row["atividade_id"]), int(row["tp_doc"]))
            for row in conexao.execute(sql, (iso, iso, iso, iso)).fetchall()
        ]


def buscar_classificacoes_vigentes(codigo: str, data: date) -> list[ClassificacaoTributaria]:
    sql = """
        SELECT ct.CLTR_ID, ct.CLTR_CD, ct.CLTR_TPRBSN
        FROM CLASSIFICACAO_TRIBUTARIA ct
        WHERE ct.CLTR_CD = ?
          AND ? BETWEEN ct.CLTR_INICIO_VIGENCIA AND COALESCE(ct.CLTR_FIM_VIGENCIA, ?)
          AND ct.CLTR_SITR_ID IN (
              SELECT tst.TRST_SITR_ID
              FROM TRIBUTO_SITUACAO_TRIBUTARIA tst
              WHERE tst.TRST_TBTO_ID = 2
          )
        ORDER BY ct.CLTR_INICIO_VIGENCIA DESC
    """
    iso = data.isoformat()
    with _conectar() as conexao:
        conexao.row_factory = sqlite3.Row
        return [
            ClassificacaoTributaria(int(row["CLTR_ID"]), row["CLTR_CD"], int(row["CLTR_TPRBSN"]))
            for row in conexao.execute(sql, (codigo, iso, iso)).fetchall()
        ]


def contar_vinculo_classificacao_tpdoc(codigo: str, tp_doc: int, data: date) -> int:
    sql = """
        SELECT COUNT(1) AS n
        FROM TIPO_DFE_CLASSIFICACAO tdcl
        JOIN TIPO_DFE td ON td.TPDF_ID = tdcl.TDCL_TPDF_ID
        JOIN CLASSIFICACAO_TRIBUTARIA ct ON ct.CLTR_ID = tdcl.TDCL_CLTR_ID
        WHERE ct.CLTR_CD = ?
          AND td.TPDF_TIPO = ?
          AND ct.CLTR_SITR_ID IN (
              SELECT tst.TRST_SITR_ID
              FROM TRIBUTO_SITUACAO_TRIBUTARIA tst
              WHERE tst.TRST_TBTO_ID = 2
          )
          AND ? BETWEEN tdcl.TDCL_INICIO_VIGENCIA AND COALESCE(tdcl.TDCL_FIM_VIGENCIA, ?)
          AND ? BETWEEN td.TPDF_INICIO_VIGENCIA AND COALESCE(td.TPDF_FIM_VIGENCIA, ?)
    """
    iso = data.isoformat()
    with _conectar() as conexao:
        return int(conexao.execute(sql, (codigo, tp_doc, iso, iso, iso, iso)).fetchone()["n"])


def _parse_data(valor: str) -> date:
    return date.fromisoformat(valor)


def listar_transicao_compra_gov() -> list[TransicaoAliquotaCompraGov]:
    sql = """
        SELECT TACG_ID, TACG_FATOR, TACG_INICIO_VIGENCIA, TACG_FIM_VIGENCIA
        FROM TRANSICAO_ALIQUOTA_COMPRA_GOV_SIMPLES_NACIONAL
        ORDER BY TACG_INICIO_VIGENCIA ASC
    """
    with _conectar() as conexao:
        conexao.row_factory = sqlite3.Row
        return [
            TransicaoAliquotaCompraGov(
                int(row["TACG_ID"]),
                _decimal(row["TACG_FATOR"]),
                _parse_data(row["TACG_INICIO_VIGENCIA"]),
                _parse_data(row["TACG_FIM_VIGENCIA"]) if row["TACG_FIM_VIGENCIA"] else None,
            )
            for row in conexao.execute(sql).fetchall()
        ]


def contar_tratamentos_nao_implementados(codigo: str, data: date) -> int:
    sql = """
        SELECT COUNT(1) AS n
        FROM TRATAMENTO_CLASSIFICACAO tc
        JOIN TRATAMENTO_TRIBUTARIO tt ON tt.TRTR_ID = tc.TRCL_TRTR_ID
        JOIN CLASSIFICACAO_TRIBUTARIA ct ON ct.CLTR_ID = tc.TRCL_CLTR_ID
        WHERE ct.CLTR_CD = ?
          AND tt.TRTR_IN_POSSUI_AJUSTE = 1
          AND ct.CLTR_SITR_ID IN (
              SELECT tst.TRST_SITR_ID
              FROM TRIBUTO_SITUACAO_TRIBUTARIA tst
              WHERE tst.TRST_TBTO_ID = 2
          )
          AND ? BETWEEN ct.CLTR_INICIO_VIGENCIA AND COALESCE(ct.CLTR_FIM_VIGENCIA, ?)
          AND ? BETWEEN tc.TRCL_INICIO_VIGENCIA AND COALESCE(tc.TRCL_FIM_VIGENCIA, ?)
          AND ? BETWEEN tt.TRTR_INICIO_VIGENCIA AND COALESCE(tt.TRTR_FIM_VIGENCIA, ?)
    """
    iso = data.isoformat()
    with _conectar() as conexao:
        return int(conexao.execute(sql, (codigo, iso, iso, iso, iso, iso, iso)).fetchone()["n"])


def _contar_vinculos_tpdoc_calculo(tp_doc: int, data: date) -> int:
    sql = """
        SELECT COUNT(1) AS n
        FROM TIPO_DFE_CALCULO_SIMPLES_NACIONAL t
        JOIN TIPO_DFE td ON td.TPDF_ID = t.TDCS_TPDF_ID
        WHERE td.TPDF_TIPO = ?
          AND ? BETWEEN t.TDCS_INICIO_VIGENCIA AND COALESCE(t.TDCS_FIM_VIGENCIA, ?)
          AND ? BETWEEN td.TPDF_INICIO_VIGENCIA AND COALESCE(td.TPDF_FIM_VIGENCIA, ?)
    """
    iso = data.isoformat()
    with _conectar() as conexao:
        return int(conexao.execute(sql, (tp_doc, iso, iso, iso, iso)).fetchone()["n"])


def regime_para_calculo(regime: RegimeApuracao) -> Regime:
    destino_map = {
        DestinoValor.DEVIDO: Destino.DEVIDO,
        DestinoValor.PENDENTE_SUSPENSO: Destino.PENDENTE_SUSPENSO,
        DestinoValor.ZERO: Destino.ZERO,
    }
    return Regime(
        regime.codigo.value,
        regime.calcula_tributos,
        regime.descricao,
        bool(regime.gera_ibs),
        destino_map[regime.destino_devido] if regime.destino_devido else Destino.DEVIDO,
        destino_map[regime.destino_pendente] if regime.destino_pendente else Destino.PENDENTE_SUSPENSO,
    )


def tipo_receita_para_calculo(tipo: TipoReceitaBruta) -> TipoReceita:
    return TipoReceita(
        tipo.codigo,
        tipo.descricao,
        tipo.compoe_receita,
        tipo.fator_receita,
        tipo.pendente_suspenso,
        tipo.imposto_seletivo_compoe_receita,
        tipo.exige_aliquota,
        tipo.vedado_nao_tributavel,
    )