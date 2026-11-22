"""NCM/NBS aplicável, determinação e validação de nomenclatura.

Pin ``a926d5a76095ac0295a6612a9a54db7ffead2396`` — espelha
``ValidacaoNomenclaturaService``, ``NomenclaturaService``, ``NcmAplicavelService``,
``NbsAplicavelService``, ``NcmService``, ``NbsService`` e SQL dos repositórios Java.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Protocol

from calculadora_rtc_simples_nacional import banco
from calculadora_rtc_simples_nacional.parametro import ClassificacaoTributaria
from calculadora_rtc_simples_nacional.processador import ColetorItem, ValidacaoNomenclatura

conectar = banco.conectar

_DATA_ISO = "%Y-%m-%d"

_CLASSIFICACOES_EXCECAO = frozenset({"200038", "515001"})
_TRIO_RIGIDO = frozenset({"NFE", "NFCE", "NFSE"})
_NCM_APLICAVEL_DFE = frozenset({"NFSE", "NFE", "NFCE"})
_NBS_APLICAVEL_DFE = frozenset({"NFSE"})


class ValidacaoException(Exception):
    """Equivalente a ``ValidacaoException`` do domínio Java."""


class NcmNbsSimultaneasException(ValidacaoException):
    def __init__(self) -> None:
        super().__init__("Não é permitido informar NCM e NBS simultaneamente para um item")


class NcmNaoEncontradaException(ValidacaoException):
    def __init__(self, ncm: str, data: date) -> None:
        super().__init__(f"NCM de código {ncm} não encontrada para a data {data}")


class NbsNaoEncontradaException(ValidacaoException):
    def __init__(self, nbs: str, data: date) -> None:
        super().__init__(f"NBS de código {nbs} não encontrada para a data {data}")


class FormatoNomenclaturaInvalidoException(ValidacaoException):
    def __init__(self, campo: str) -> None:
        digitos = 8 if campo == "ncm" else 9
        super().__init__(
            f"O {campo.upper()} deve conter exclusivamente {digitos} dígitos ASCII, "
            "sem espaços ou símbolos."
        )
        self.campo = campo


class NcmCompletoNaoInformadoException(ValidacaoException):
    def __init__(self) -> None:
        super().__init__("NCM completo não informado")


class NbsCompletoNaoInformadoException(ValidacaoException):
    def __init__(self) -> None:
        super().__init__("NBS completo não informado")


class NcmNaoVinculadaException(ValidacaoException):
    def __init__(self, ncm: str, c_class_trib: str, tributo: str) -> None:
        super().__init__(
            f"NCM de código {ncm} não vinculada à Classificação Tributária de código {c_class_trib} ({tributo})"
        )


class NbsNaoVinculadaException(ValidacaoException):
    def __init__(self, nbs: str, c_class_trib: str, tributo: str) -> None:
        super().__init__(
            f"NBS de código {nbs} não vinculada à Classificação Tributária de código {c_class_trib} ({tributo})"
        )


class NomenclaturaIncompativelTipoDfeException(ValidacaoException):
    def __init__(self, nomenclatura: str, c_class_trib: str, sigla_dfe: str) -> None:
        super().__init__(
            f"{nomenclatura} não permitida para a Classificação Tributária de código {c_class_trib} "
            f"no tipo de documento {sigla_dfe}"
        )


class NomenclaturaNaoPermitidaTipoDfeException(ValidacaoException):
    def __init__(self, c_class_trib: str, sigla_dfe: str) -> None:
        super().__init__(
            f"NCM/NBS não permitido para a Classificação Tributária de código {c_class_trib} "
            f"no tipo de documento {sigla_dfe}"
        )


class NomenclaturaObrigatoriaNaoInformadaException(ValidacaoException):
    def __init__(self, c_class_trib: str, sigla_dfe: str) -> None:
        super().__init__(
            f"A Classificação Tributária de código {c_class_trib} exige NCM ou NBS completo "
            f"para o tipo de documento {sigla_dfe}"
        )


class SiglaDFeNaoEncontradaException(ValidacaoException):
    def __init__(self, sigla: str) -> None:
        super().__init__(f"Sigla DFe inválida: {sigla}")


class ClassificacaoTributariaNaoEncontradaException(ValidacaoException):
    def __init__(self, codigo: str, tributo: str, data: date) -> None:
        super().__init__(
            f"Classificação tributária não encontrada para código {codigo} e data {data} ({tributo})"
        )


class ModoValidacaoNomenclatura(Enum):
    PERMISSIVO = "PERMISSIVO"
    RIGIDO = "RIGIDO"


class NomenclaturaResultado(Enum):
    SEM = "SEM"
    NCM = "NCM"
    NBS = "NBS"
    MISTO = "MISTO"
    EXCECAO_NCM = "EXCECAO_NCM"
    EXCECAO_NBS = "EXCECAO_NBS"


class SiglaDFe(Enum):
    NFEABI = "NFe ABI"
    NFE = "NFe"
    NFCE = "NFCe"
    CTE = "CTe"
    CTEOS = "CTe OS"
    CTESIMPLIFICADO = "CT-e Simplificado"
    BPE = "BPe"
    BPETA = "BPe TA"
    BPETM = "BPe TM"
    NF3E = "NF3e"
    NFSE = "NFSe"
    NFSEVIA = "NFSe Via"
    NFCOM = "NFCom"
    DERE = "DERE"
    DIR = "DIR"
    DUIMP = "Duimp"
    NFAG = "NFAg"
    NFGAS = "NFGas"

    @property
    def chave_normalizada(self) -> str:
        return self.name

    @property
    def sigla(self) -> str:
        return self.value

    def corresponde(self, sigla: str) -> bool:
        return self.name == normalizar_sigla(sigla)


def normalizar_sigla(sigla: str | None) -> str:
    if sigla is None:
        return ""
    return re.sub(r"[\s\-_]", "", sigla).upper()


def sigla_dfe_por_normalizada(sigla: str) -> SiglaDFe:
    chave = normalizar_sigla(sigla)
    for item in SiglaDFe:
        if item.name == chave:
            return item
    raise SiglaDFeNaoEncontradaException(sigla)


def ncm_aplicavel_dfe(sigla_dfe: str) -> bool:
    return normalizar_sigla(sigla_dfe) in _NCM_APLICAVEL_DFE


def nbs_aplicavel_dfe(sigla_dfe: str) -> bool:
    return normalizar_sigla(sigla_dfe) in _NBS_APLICAVEL_DFE


def _em_branco(valor: str | None) -> bool:
    return valor is None or valor.strip() == ""


def _informado_literal(valor: str | None) -> bool:
    """Espelha ``ValidacaoNomenclaturaAdapter#isNullOrEmpty`` (sem trim)."""
    return valor is not None and valor != ""


def _comprimento(valor: str | None) -> int:
    return 0 if valor is None else len(valor)


def _data_iso(data: date) -> str:
    return data.strftime(_DATA_ISO)


@dataclass(frozen=True)
class NcmVigencia:
    codigo: str
    descricao: str


@dataclass(frozen=True)
class ClassificacaoTributariaResumo:
    id: int
    codigo: str


@dataclass(frozen=True)
class TipoDfeResumo:
    sigla: str


@dataclass(frozen=True)
class TipoDfeClassificacaoResumo:
    tipo_dfe: TipoDfeResumo


class NcmAplicavelRepositorio(Protocol):
    def tem(self, id_classificacao_tributaria: int, data: date) -> bool: ...

    def tem_ncm_aplicavel(self, ncm: str, id_classificacao_tributaria: int, data: date) -> bool: ...

    def tem_excecao_ncm_aplicavel(self, ncm: str, id_classificacao_tributaria: int, data: date) -> bool: ...

    def tem_ncm_aplicavel_sem_excecao(self, ncm: str, id_classificacao_tributaria: int, data: date) -> bool: ...


class NbsAplicavelRepositorio(Protocol):
    def tem(self, id_classificacao_tributaria: int, data: date) -> bool: ...

    def tem_nbs_aplicavel(self, nbs: str, id_classificacao_tributaria: int, data: date) -> bool: ...

    def tem_excecao_nbs_aplicavel(self, nbs: str, id_classificacao_tributaria: int, data: date) -> bool: ...

    def tem_nbs_aplicavel_sem_excecao(self, nbs: str, id_classificacao_tributaria: int, data: date) -> bool: ...


class NcmRepositorio(Protocol):
    def existe_ncm(self, codigo: str, data: date) -> bool: ...

    def buscar_todos_ncms_vigentes(self, data: date) -> list[NcmVigencia]: ...


class NbsRepositorio(Protocol):
    def existe_nbs(self, codigo: str, data: date) -> bool: ...


class ClassificacaoTributariaRepositorio(Protocol):
    def buscar_classificacao_tributaria(
        self, codigo: str, id_tributo: int, data: date
    ) -> ClassificacaoTributariaResumo | None: ...


class TipoDfeClassificacaoRepositorio(Protocol):
    def buscar(self, id_classificacao_tributaria: int, data: date) -> list[TipoDfeClassificacaoResumo]: ...


def _existe(conexao: sqlite3.Connection, sql: str, params: tuple[object, ...]) -> bool:
    linha = conexao.execute(sql, params).fetchone()
    return bool(linha and linha[0])


class NcmAplicavelRepositorioSqlite:
    def __init__(self, conexao: sqlite3.Connection | None = None) -> None:
        self._conexao = conexao

    def _abrir(self) -> sqlite3.Connection:
        return self._conexao or conectar()

    def tem(self, id_classificacao_tributaria: int, data: date) -> bool:
        d = _data_iso(data)
        sql = """
            SELECT EXISTS (
                SELECT 1 FROM NCM_APLICAVEL n
                WHERE n.NCMA_CLTR_ID = ?
                AND ? BETWEEN n.NCMA_INICIO_VIGENCIA AND COALESCE(n.NCMA_FIM_VIGENCIA, ?)
            )
        """
        with self._abrir() as conexao:
            return _existe(conexao, sql, (id_classificacao_tributaria, d, d))

    def tem_ncm_aplicavel(self, ncm: str, id_classificacao_tributaria: int, data: date) -> bool:
        d = _data_iso(data)
        sql = """
            SELECT EXISTS (
                SELECT 1 FROM NCM_APLICAVEL n
                WHERE n.NCMA_NCM_CD = substr(?, 1, length(n.NCMA_NCM_CD))
                AND n.NCMA_CLTR_ID = ?
                AND ? BETWEEN n.NCMA_INICIO_VIGENCIA AND COALESCE(n.NCMA_FIM_VIGENCIA, ?)
            )
        """
        with self._abrir() as conexao:
            return _existe(conexao, sql, (ncm, id_classificacao_tributaria, d, d))

    def tem_excecao_ncm_aplicavel(self, ncm: str, id_classificacao_tributaria: int, data: date) -> bool:
        d = _data_iso(data)
        sql = """
            SELECT EXISTS (
                SELECT 1 FROM EXCECAO_NCM_APLICAVEL e
                JOIN NCM_APLICAVEL n ON e.ENCM_NCMA_ID = n.NCMA_ID
                WHERE n.NCMA_NCM_CD = substr(?, 1, length(n.NCMA_NCM_CD))
                AND e.ENCM_NCM_CD = substr(?, 1, length(e.ENCM_NCM_CD))
                AND n.NCMA_CLTR_ID = ?
                AND ? BETWEEN e.ENCM_INICIO_VIGENCIA AND COALESCE(e.ENCM_FIM_VIGENCIA, ?)
            )
        """
        with self._abrir() as conexao:
            return _existe(conexao, sql, (ncm, ncm, id_classificacao_tributaria, d, d))

    def tem_ncm_aplicavel_sem_excecao(self, ncm: str, id_classificacao_tributaria: int, data: date) -> bool:
        d = _data_iso(data)
        sql = """
            SELECT EXISTS (
                SELECT 1 FROM NCM_APLICAVEL n
                LEFT JOIN EXCECAO_NCM_APLICAVEL e ON e.ENCM_NCMA_ID = n.NCMA_ID
                WHERE n.NCMA_NCM_CD = substr(?, 1, length(n.NCMA_NCM_CD))
                AND n.NCMA_CLTR_ID = ?
                AND ? BETWEEN n.NCMA_INICIO_VIGENCIA AND COALESCE(n.NCMA_FIM_VIGENCIA, ?)
                AND (
                    e.ENCM_ID IS NULL
                    OR ? NOT BETWEEN e.ENCM_INICIO_VIGENCIA AND COALESCE(e.ENCM_FIM_VIGENCIA, ?)
                )
            )
        """
        with self._abrir() as conexao:
            return _existe(conexao, sql, (ncm, id_classificacao_tributaria, d, d, d, d))


class NbsAplicavelRepositorioSqlite:
    def __init__(self, conexao: sqlite3.Connection | None = None) -> None:
        self._conexao = conexao

    def _abrir(self) -> sqlite3.Connection:
        return self._conexao or conectar()

    def tem(self, id_classificacao_tributaria: int, data: date) -> bool:
        d = _data_iso(data)
        sql = """
            SELECT EXISTS (
                SELECT 1 FROM NBS_APLICAVEL n
                WHERE n.NBSA_CLTR_ID = ?
                AND ? BETWEEN n.NBSA_INICIO_VIGENCIA AND COALESCE(n.NBSA_FIM_VIGENCIA, ?)
            )
        """
        with self._abrir() as conexao:
            return _existe(conexao, sql, (id_classificacao_tributaria, d, d))

    def tem_nbs_aplicavel(self, nbs: str, id_classificacao_tributaria: int, data: date) -> bool:
        d = _data_iso(data)
        sql = """
            SELECT EXISTS (
                SELECT 1 FROM NBS_APLICAVEL n
                WHERE n.NBSA_NBS_CD = substr(?, 1, length(n.NBSA_NBS_CD))
                AND n.NBSA_CLTR_ID = ?
                AND ? BETWEEN n.NBSA_INICIO_VIGENCIA AND COALESCE(n.NBSA_FIM_VIGENCIA, ?)
            )
        """
        with self._abrir() as conexao:
            return _existe(conexao, sql, (nbs, id_classificacao_tributaria, d, d))

    def tem_excecao_nbs_aplicavel(self, nbs: str, id_classificacao_tributaria: int, data: date) -> bool:
        d = _data_iso(data)
        sql = """
            SELECT EXISTS (
                SELECT 1 FROM EXCECAO_NBS_APLICAVEL e
                JOIN NBS_APLICAVEL n ON e.ENBS_NBSA_ID = n.NBSA_ID
                WHERE n.NBSA_NBS_CD = substr(?, 1, length(n.NBSA_NBS_CD))
                AND e.ENBS_NBS_CD = substr(?, 1, length(e.ENBS_NBS_CD))
                AND n.NBSA_CLTR_ID = ?
                AND ? BETWEEN e.ENBS_INICIO_VIGENCIA AND COALESCE(e.ENBS_FIM_VIGENCIA, ?)
            )
        """
        with self._abrir() as conexao:
            return _existe(conexao, sql, (nbs, nbs, id_classificacao_tributaria, d, d))

    def tem_nbs_aplicavel_sem_excecao(self, nbs: str, id_classificacao_tributaria: int, data: date) -> bool:
        d = _data_iso(data)
        sql = """
            SELECT EXISTS (
                SELECT 1 FROM NBS_APLICAVEL n
                LEFT JOIN EXCECAO_NBS_APLICAVEL e ON e.ENBS_NBSA_ID = n.NBSA_ID
                WHERE n.NBSA_NBS_CD = substr(?, 1, length(n.NBSA_NBS_CD))
                AND n.NBSA_CLTR_ID = ?
                AND ? BETWEEN n.NBSA_INICIO_VIGENCIA AND COALESCE(n.NBSA_FIM_VIGENCIA, ?)
                AND (
                    e.ENBS_ID IS NULL
                    OR ? NOT BETWEEN e.ENBS_INICIO_VIGENCIA AND COALESCE(e.ENBS_FIM_VIGENCIA, ?)
                )
            )
        """
        with self._abrir() as conexao:
            return _existe(conexao, sql, (nbs, id_classificacao_tributaria, d, d, d, d))


class NcmRepositorioSqlite:
    def __init__(self, conexao: sqlite3.Connection | None = None) -> None:
        self._conexao = conexao

    def _abrir(self) -> sqlite3.Connection:
        return self._conexao or conectar()

    def existe_ncm(self, codigo: str, data: date) -> bool:
        d = _data_iso(data)
        sql = """
            SELECT EXISTS (
                SELECT 1 FROM NCM n
                WHERE n.NCM_CD = ?
                AND ? BETWEEN n.NCM_INICIO_VIGENCIA AND COALESCE(n.NCM_FIM_VIGENCIA, ?)
            )
        """
        with self._abrir() as conexao:
            return _existe(conexao, sql, (codigo, d, d))

    def buscar_todos_ncms_vigentes(self, data: date) -> list[NcmVigencia]:
        d = _data_iso(data)
        sql = """
            SELECT DISTINCT n.NCM_CD, n.NCM_DESCRICAO
            FROM NCM n
            WHERE ? BETWEEN n.NCM_INICIO_VIGENCIA AND COALESCE(n.NCM_FIM_VIGENCIA, ?)
            AND length(n.NCM_CD) = 8
            ORDER BY n.NCM_CD
        """
        with self._abrir() as conexao:
            linhas = conexao.execute(sql, (d, d)).fetchall()
        return [NcmVigencia(codigo=linha[0], descricao=linha[1]) for linha in linhas]


class NbsRepositorioSqlite:
    def __init__(self, conexao: sqlite3.Connection | None = None) -> None:
        self._conexao = conexao

    def _abrir(self) -> sqlite3.Connection:
        return self._conexao or conectar()

    def existe_nbs(self, codigo: str, data: date) -> bool:
        d = _data_iso(data)
        sql = """
            SELECT EXISTS (
                SELECT 1 FROM NBS n
                WHERE n.NBS_CD = ?
                AND ? BETWEEN n.NBS_INICIO_VIGENCIA AND COALESCE(n.NBS_FIM_VIGENCIA, ?)
            )
        """
        with self._abrir() as conexao:
            return _existe(conexao, sql, (codigo, d, d))


class ClassificacaoTributariaRepositorioSqlite:
    def __init__(self, conexao: sqlite3.Connection | None = None) -> None:
        self._conexao = conexao

    def _abrir(self) -> sqlite3.Connection:
        return self._conexao or conectar()

    def buscar_classificacao_tributaria(
        self, codigo: str, id_tributo: int, data: date
    ) -> ClassificacaoTributariaResumo | None:
        d = _data_iso(data)
        sql = """
            SELECT ct.CLTR_ID, ct.CLTR_CD
            FROM CLASSIFICACAO_TRIBUTARIA ct
            JOIN SITUACAO_TRIBUTARIA st ON ct.CLTR_SITR_ID = st.SITR_ID
            JOIN TRIBUTO_SITUACAO_TRIBUTARIA tst ON tst.TRST_SITR_ID = st.SITR_ID
            JOIN TRIBUTO tb ON tst.TRST_TBTO_ID = tb.TBTO_ID
            WHERE ct.CLTR_CD = ?
            AND tb.TBTO_ID = ?
            AND ? BETWEEN ct.CLTR_INICIO_VIGENCIA AND COALESCE(ct.CLTR_FIM_VIGENCIA, ?)
            AND ? BETWEEN st.SITR_INICIO_VIGENCIA AND COALESCE(st.SITR_FIM_VIGENCIA, ?)
            AND ? BETWEEN tst.TRST_INICIO_VIGENCIA AND COALESCE(tst.TRST_FIM_VIGENCIA, ?)
            AND ? BETWEEN tb.TBTO_INICIO_VIGENCIA AND COALESCE(tb.TBTO_FIM_VIGENCIA, ?)
            LIMIT 1
        """
        params = (codigo, id_tributo, d, d, d, d, d, d, d, d)
        with self._abrir() as conexao:
            linha = conexao.execute(sql, params).fetchone()
        if linha is None:
            return None
        return ClassificacaoTributariaResumo(id=linha[0], codigo=linha[1])


class TipoDfeClassificacaoRepositorioSqlite:
    def __init__(self, conexao: sqlite3.Connection | None = None) -> None:
        self._conexao = conexao

    def _abrir(self) -> sqlite3.Connection:
        return self._conexao or conectar()

    def buscar(self, id_classificacao_tributaria: int, data: date) -> list[TipoDfeClassificacaoResumo]:
        d = _data_iso(data)
        sql = """
            SELECT td.TPDF_SIGLA
            FROM TIPO_DFE_CLASSIFICACAO tdcl
            JOIN TIPO_DFE td ON tdcl.TDCL_TPDF_ID = td.TPDF_ID
            WHERE tdcl.TDCL_CLTR_ID = ?
            AND tdcl.TDCL_INICIO_VIGENCIA <= ?
            AND (tdcl.TDCL_FIM_VIGENCIA IS NULL OR tdcl.TDCL_FIM_VIGENCIA >= ?)
        """
        with self._abrir() as conexao:
            linhas = conexao.execute(sql, (id_classificacao_tributaria, d, d)).fetchall()
        return [TipoDfeClassificacaoResumo(tipo_dfe=TipoDfeResumo(sigla=linha[0])) for linha in linhas]


class NcmAplicavelService:
    def __init__(self, repositorio: NcmAplicavelRepositorio) -> None:
        self._repositorio = repositorio

    def validar_ncm_aplicavel(
        self,
        ncm: str | None,
        id_classificacao_tributaria: int,
        codigo_classificacao_tributaria: str,
        data: date,
        tributos: str,
    ) -> bool:
        possui_ncm_completo = _comprimento(ncm) == 8
        tem_classificacao = self._repositorio.tem(id_classificacao_tributaria, data)
        if tem_classificacao and not possui_ncm_completo:
            raise NcmCompletoNaoInformadoException()
        if possui_ncm_completo:
            self._criticar(
                ncm or "",
                id_classificacao_tributaria,
                codigo_classificacao_tributaria,
                data,
                tributos,
                tem_classificacao,
            )
        return True

    def criticar_ncm_contra_anexo(
        self,
        ncm: str,
        id_classificacao_tributaria: int,
        codigo_classificacao_tributaria: str,
        data: date,
        tributos: str,
    ) -> None:
        tem_classificacao = self._repositorio.tem(id_classificacao_tributaria, data)
        self._criticar(
            ncm, id_classificacao_tributaria, codigo_classificacao_tributaria, data, tributos, tem_classificacao
        )

    def _criticar(
        self,
        ncm: str,
        id_classificacao_tributaria: int,
        codigo_classificacao_tributaria: str,
        data: date,
        tributos: str,
        tem_classificacao_tributaria: bool,
    ) -> None:
        if not tem_classificacao_tributaria:
            return
        if not self._repositorio.tem_ncm_aplicavel(ncm, id_classificacao_tributaria, data):
            raise NcmNaoVinculadaException(ncm, codigo_classificacao_tributaria, tributos)
        if self._repositorio.tem_excecao_ncm_aplicavel(
            ncm, id_classificacao_tributaria, data
        ) and not self._repositorio.tem_ncm_aplicavel_sem_excecao(ncm, id_classificacao_tributaria, data):
            raise NcmNaoVinculadaException(ncm, codigo_classificacao_tributaria, tributos)


class NbsAplicavelService:
    def __init__(self, repositorio: NbsAplicavelRepositorio) -> None:
        self._repositorio = repositorio

    def validar_nbs_aplicavel(
        self,
        nbs: str | None,
        id_classificacao_tributaria: int,
        codigo_classificacao_tributaria: str,
        data: date,
        tributos: str,
    ) -> bool:
        possui_nbs_completo = _comprimento(nbs) == 9
        tem_classificacao = self._repositorio.tem(id_classificacao_tributaria, data)
        if tem_classificacao and not possui_nbs_completo:
            raise NbsCompletoNaoInformadoException()
        if possui_nbs_completo:
            self._criticar(
                nbs or "",
                id_classificacao_tributaria,
                codigo_classificacao_tributaria,
                data,
                tributos,
                tem_classificacao,
            )
        return True

    def criticar_nbs_contra_anexo(
        self,
        nbs: str,
        id_classificacao_tributaria: int,
        codigo_classificacao_tributaria: str,
        data: date,
        tributos: str,
    ) -> None:
        tem_classificacao = self._repositorio.tem(id_classificacao_tributaria, data)
        self._criticar(
            nbs, id_classificacao_tributaria, codigo_classificacao_tributaria, data, tributos, tem_classificacao
        )

    def _criticar(
        self,
        nbs: str,
        id_classificacao_tributaria: int,
        codigo_classificacao_tributaria: str,
        data: date,
        tributos: str,
        tem_classificacao_tributaria: bool,
    ) -> None:
        if not tem_classificacao_tributaria:
            return
        if not self._repositorio.tem_nbs_aplicavel(nbs, id_classificacao_tributaria, data):
            raise NbsNaoVinculadaException(nbs, codigo_classificacao_tributaria, tributos)
        if self._repositorio.tem_excecao_nbs_aplicavel(
            nbs, id_classificacao_tributaria, data
        ) and not self._repositorio.tem_nbs_aplicavel_sem_excecao(nbs, id_classificacao_tributaria, data):
            raise NbsNaoVinculadaException(nbs, codigo_classificacao_tributaria, tributos)


class NcmService:
    def __init__(self, repositorio: NcmRepositorio) -> None:
        self._repositorio = repositorio

    def existe_ncm(self, ncm: str, data: date) -> bool:
        return self._repositorio.existe_ncm(ncm, data)

    def consultar_ncms_vigentes(self, data: date) -> list[NcmVigencia]:
        return self._repositorio.buscar_todos_ncms_vigentes(data)


class NbsService:
    def __init__(self, repositorio: NbsRepositorio) -> None:
        self._repositorio = repositorio

    def existe_nbs(self, nbs: str, data: date) -> bool:
        return self._repositorio.existe_nbs(nbs, data)


class ClassificacaoTributariaService:
    def __init__(self, repositorio: ClassificacaoTributariaRepositorio) -> None:
        self._repositorio = repositorio

    def buscar_classificacao_tributaria_cbs_ibs(self, codigo: str, data: date) -> ClassificacaoTributariaResumo:
        resumo = self._repositorio.buscar_classificacao_tributaria(codigo, 2, data)
        if resumo is None:
            raise ClassificacaoTributariaNaoEncontradaException(codigo, "CBS e IBS", data)
        return resumo


class TipoDfeClassificacaoService:
    def __init__(self, repositorio: TipoDfeClassificacaoRepositorio) -> None:
        self._repositorio = repositorio

    def buscar(self, id_classificacao_tributaria: int, data: date) -> list[TipoDfeClassificacaoResumo]:
        return self._repositorio.buscar(id_classificacao_tributaria, data)


class NomenclaturaService:
    def __init__(
        self,
        classificacao_tributaria_service: ClassificacaoTributariaService,
        tipo_dfe_classificacao_service: TipoDfeClassificacaoService,
        ncm_aplicavel_repositorio: NcmAplicavelRepositorio,
        nbs_aplicavel_repositorio: NbsAplicavelRepositorio,
    ) -> None:
        self._classificacao_tributaria_service = classificacao_tributaria_service
        self._tipo_dfe_classificacao_service = tipo_dfe_classificacao_service
        self._ncm_aplicavel_repositorio = ncm_aplicavel_repositorio
        self._nbs_aplicavel_repositorio = nbs_aplicavel_repositorio

    def determinar_nomenclatura(self, sigla_dfe: str, c_class_trib: str, data: date) -> str:
        classificacao = self._classificacao_tributaria_service.buscar_classificacao_tributaria_cbs_ibs(
            c_class_trib, data
        )
        id_classificacao = classificacao.id
        if not self._sigla_dfe_compativel(sigla_dfe, id_classificacao, data):
            return NomenclaturaResultado.SEM.value
        ncm_aplicavel = self._ncm_aplicavel_repositorio.tem(id_classificacao, data)
        nbs_aplicavel = self._nbs_aplicavel_repositorio.tem(id_classificacao, data)
        return self._determinar_resultado(sigla_dfe, c_class_trib, ncm_aplicavel, nbs_aplicavel).value

    def _sigla_dfe_compativel(self, sigla_dfe: str, id_classificacao: int, data: date) -> bool:
        tipos = self._tipo_dfe_classificacao_service.buscar(id_classificacao, data)
        sigla_normalizada = sigla_dfe_por_normalizada(sigla_dfe)
        return any(sigla_normalizada.corresponde(item.tipo_dfe.sigla) for item in tipos)

    @staticmethod
    def _tratar_caso_excecao(sigla_dfe: str) -> NomenclaturaResultado:
        sigla_normalizada = sigla_dfe_por_normalizada(sigla_dfe)
        if sigla_normalizada in (SiglaDFe.NFE, SiglaDFe.NFCE):
            return NomenclaturaResultado.EXCECAO_NCM
        if sigla_normalizada == SiglaDFe.NFSE:
            return NomenclaturaResultado.EXCECAO_NBS
        return NomenclaturaResultado.SEM

    @staticmethod
    def _determinar_resultado(
        sigla_dfe: str, c_class_trib: str, ncm_aplicavel: bool, nbs_aplicavel: bool
    ) -> NomenclaturaResultado:
        if c_class_trib in _CLASSIFICACOES_EXCECAO:
            return NomenclaturaService._tratar_caso_excecao(sigla_dfe)
        if ncm_aplicavel_dfe(sigla_dfe) and not nbs_aplicavel_dfe(sigla_dfe):
            return NomenclaturaResultado.NCM if ncm_aplicavel else NomenclaturaResultado.SEM
        if nbs_aplicavel_dfe(sigla_dfe):
            if ncm_aplicavel and nbs_aplicavel:
                return NomenclaturaResultado.MISTO
            if ncm_aplicavel:
                return NomenclaturaResultado.NCM
            if nbs_aplicavel:
                return NomenclaturaResultado.NBS
            return NomenclaturaResultado.SEM
        return NomenclaturaResultado.SEM


class ValidacaoNomenclaturaService:
    def __init__(
        self,
        nomenclatura_service: NomenclaturaService,
        ncm_aplicavel_service: NcmAplicavelService,
        nbs_aplicavel_service: NbsAplicavelService,
    ) -> None:
        self._nomenclatura_service = nomenclatura_service
        self._ncm_aplicavel_service = ncm_aplicavel_service
        self._nbs_aplicavel_service = nbs_aplicavel_service

    def validar(
        self,
        sigla_dfe: SiglaDFe,
        id_classificacao_tributaria: int,
        codigo_classificacao_tributaria: str,
        ncm: str | None,
        nbs: str | None,
        data: date,
        tributos: str,
        modo: ModoValidacaoNomenclatura,
    ) -> None:
        resultado_str = self._nomenclatura_service.determinar_nomenclatura(
            sigla_dfe.chave_normalizada, codigo_classificacao_tributaria, data
        )
        resultado = NomenclaturaResultado(resultado_str)
        if resultado in (NomenclaturaResultado.NCM, NomenclaturaResultado.EXCECAO_NCM):
            self._exigir_ncm(
                sigla_dfe, id_classificacao_tributaria, codigo_classificacao_tributaria, ncm, nbs, data, tributos
            )
        elif resultado in (NomenclaturaResultado.NBS, NomenclaturaResultado.EXCECAO_NBS):
            self._exigir_nbs(
                sigla_dfe, id_classificacao_tributaria, codigo_classificacao_tributaria, ncm, nbs, data, tributos
            )
        elif resultado == NomenclaturaResultado.MISTO:
            self._exigir_ncm_ou_nbs(
                sigla_dfe, id_classificacao_tributaria, codigo_classificacao_tributaria, ncm, nbs, data, tributos
            )
        else:
            self._validar_sem_exigencia(
                sigla_dfe,
                id_classificacao_tributaria,
                codigo_classificacao_tributaria,
                ncm,
                nbs,
                data,
                tributos,
                modo,
            )

    def _exigir_ncm(
        self,
        sigla_dfe: SiglaDFe,
        id_classificacao_tributaria: int,
        codigo: str,
        ncm: str | None,
        nbs: str | None,
        data: date,
        tributos: str,
    ) -> None:
        if not _em_branco(nbs):
            raise NomenclaturaIncompativelTipoDfeException("NBS", codigo, sigla_dfe.sigla)
        if _comprimento(ncm) != 8:
            raise NcmCompletoNaoInformadoException()
        self._ncm_aplicavel_service.criticar_ncm_contra_anexo(
            ncm or "", id_classificacao_tributaria, codigo, data, tributos
        )

    def _exigir_nbs(
        self,
        sigla_dfe: SiglaDFe,
        id_classificacao_tributaria: int,
        codigo: str,
        ncm: str | None,
        nbs: str | None,
        data: date,
        tributos: str,
    ) -> None:
        if not _em_branco(ncm):
            raise NomenclaturaIncompativelTipoDfeException("NCM", codigo, sigla_dfe.sigla)
        if _comprimento(nbs) != 9:
            raise NbsCompletoNaoInformadoException()
        self._nbs_aplicavel_service.criticar_nbs_contra_anexo(
            nbs or "", id_classificacao_tributaria, codigo, data, tributos
        )

    def _exigir_ncm_ou_nbs(
        self,
        sigla_dfe: SiglaDFe,
        id_classificacao_tributaria: int,
        codigo: str,
        ncm: str | None,
        nbs: str | None,
        data: date,
        tributos: str,
    ) -> None:
        if not _em_branco(ncm):
            if _comprimento(ncm) != 8:
                raise NcmCompletoNaoInformadoException()
            self._ncm_aplicavel_service.criticar_ncm_contra_anexo(
                ncm or "", id_classificacao_tributaria, codigo, data, tributos
            )
        elif not _em_branco(nbs):
            if _comprimento(nbs) != 9:
                raise NbsCompletoNaoInformadoException()
            self._nbs_aplicavel_service.criticar_nbs_contra_anexo(
                nbs or "", id_classificacao_tributaria, codigo, data, tributos
            )
        else:
            raise NomenclaturaObrigatoriaNaoInformadaException(codigo, sigla_dfe.sigla)

    def _validar_sem_exigencia(
        self,
        sigla_dfe: SiglaDFe,
        id_classificacao_tributaria: int,
        codigo: str,
        ncm: str | None,
        nbs: str | None,
        data: date,
        tributos: str,
        modo: ModoValidacaoNomenclatura,
    ) -> None:
        ncm_informado = not _em_branco(ncm)
        nbs_informado = not _em_branco(nbs)
        if not ncm_informado and not nbs_informado:
            return
        if sigla_dfe.name in _TRIO_RIGIDO:
            if sigla_dfe == SiglaDFe.NFSE:
                if ncm_informado:
                    raise NomenclaturaIncompativelTipoDfeException("NCM", codigo, sigla_dfe.sigla)
            elif nbs_informado:
                raise NomenclaturaIncompativelTipoDfeException("NBS", codigo, sigla_dfe.sigla)
            return
        if modo == ModoValidacaoNomenclatura.RIGIDO:
            raise NomenclaturaNaoPermitidaTipoDfeException(codigo, sigla_dfe.sigla)
        if ncm_informado:
            self._ncm_aplicavel_service.validar_ncm_aplicavel(
                ncm, id_classificacao_tributaria, codigo, data, tributos
            )
        else:
            self._nbs_aplicavel_service.validar_nbs_aplicavel(
                nbs, id_classificacao_tributaria, codigo, data, tributos
            )


def montar_nomenclatura_sqlite(
    conexao: sqlite3.Connection | None = None,
) -> ValidacaoNomenclaturaService:
    """Empilha serviços sobre os repositórios SQLite oficiais (somente leitura)."""
    ncm_repo = NcmAplicavelRepositorioSqlite(conexao)
    nbs_repo = NbsAplicavelRepositorioSqlite(conexao)
    classif_repo = ClassificacaoTributariaRepositorioSqlite(conexao)
    tipo_repo = TipoDfeClassificacaoRepositorioSqlite(conexao)
    nomenclatura = NomenclaturaService(
        ClassificacaoTributariaService(classif_repo),
        TipoDfeClassificacaoService(tipo_repo),
        ncm_repo,
        nbs_repo,
    )
    return ValidacaoNomenclaturaService(
        nomenclatura,
        NcmAplicavelService(ncm_repo),
        NbsAplicavelService(nbs_repo),
    )


def montar_validacao_nomenclatura() -> ValidacaoNomenclaturaAdapter:
    return ValidacaoNomenclaturaAdapter(
        NcmService(NcmRepositorioSqlite()),
        NbsService(NbsRepositorioSqlite()),
        montar_nomenclatura_sqlite(),
    )


class ValidacaoNomenclaturaAdapter(ValidacaoNomenclatura):
    """Adapta validações de nomenclatura ao coletor do Simples Nacional."""

    def __init__(
        self,
        ncm_service: NcmService,
        nbs_service: NbsService,
        validacao_nomenclatura_service: ValidacaoNomenclaturaService,
    ) -> None:
        self._ncm = ncm_service
        self._nbs = nbs_service
        self._validacao = validacao_nomenclatura_service

    def validar_estrutural(
        self, ncm: str | None, nbs: str | None, data: date, collector: ColetorItem
    ) -> bool:
        try:
            self._validar_ncm_nbs(ncm, nbs, data)
            return True
        except BaseException as ex:
            self._registrar(ex, ncm, nbs, collector)
            return False

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
        try:
            if sigla_dfe is None:
                raise RuntimeError("Sigla TIPO_DFE ausente para o documento habilitado na data")
            sigla = sigla_dfe_por_normalizada(sigla_dfe)
            self._validacao.validar(
                sigla,
                classificacao.id,
                classificacao.codigo,
                ncm,
                nbs,
                data,
                "CBS e IBS",
                ModoValidacaoNomenclatura.PERMISSIVO,
            )
        except BaseException as ex:
            self._registrar(ex, ncm, nbs, collector)

    def _registrar(
        self, ex: BaseException, ncm: str | None, nbs: str | None, collector: ColetorItem
    ) -> None:
        if not self._traduzir_erro_conhecido(ex, ncm, nbs, collector):
            collector.add_falha_tecnica(ex)

    @staticmethod
    def _traduzir_erro_conhecido(
        ex: BaseException, ncm: str | None, nbs: str | None, collector: ColetorItem
    ) -> bool:
        campo: str | None = None
        if isinstance(ex, NcmNbsSimultaneasException):
            codigo = "VSN-041"
            campo = "ncm"
        elif isinstance(ex, NcmNaoEncontradaException):
            codigo = "VSN-049"
            campo = "ncm"
        elif isinstance(ex, NbsNaoEncontradaException):
            codigo = "VSN-050"
            campo = "nbs"
        elif isinstance(ex, NcmCompletoNaoInformadoException):
            codigo = "VSN-042"
            campo = "ncm"
        elif isinstance(ex, NbsCompletoNaoInformadoException):
            codigo = "VSN-043"
            campo = "nbs"
        elif isinstance(ex, NomenclaturaObrigatoriaNaoInformadaException):
            codigo = "VSN-044"
        elif isinstance(ex, NomenclaturaIncompativelTipoDfeException):
            codigo = "VSN-045"
            campo = "ncm" if ncm else "nbs" if nbs else None
        elif isinstance(ex, NomenclaturaNaoPermitidaTipoDfeException):
            codigo = "VSN-046"
        elif isinstance(ex, NcmNaoVinculadaException):
            codigo = "VSN-047"
            campo = "ncm"
        elif isinstance(ex, NbsNaoVinculadaException):
            codigo = "VSN-048"
            campo = "nbs"
        elif isinstance(ex, FormatoNomenclaturaInvalidoException):
            codigo = "VSN-051"
            campo = ex.campo
        else:
            return False
        collector.add_erro_validacao(codigo, campo, str(ex))
        return True

    def _validar_ncm_nbs(self, ncm: str | None, nbs: str | None, data: date) -> None:
        if _informado_literal(ncm) and _informado_literal(nbs):
            raise NcmNbsSimultaneasException()
        if _informado_literal(ncm) and not re.fullmatch(r"[0-9]{8}", ncm or ""):
            raise FormatoNomenclaturaInvalidoException("ncm")
        if _informado_literal(nbs) and not re.fullmatch(r"[0-9]{9}", nbs or ""):
            raise FormatoNomenclaturaInvalidoException("nbs")
        if _informado_literal(ncm) and not self._ncm.existe_ncm(ncm or "", data):
            raise NcmNaoEncontradaException(ncm or "", data)
        if _informado_literal(nbs) and not self._nbs.existe_nbs(nbs or "", data):
            raise NbsNaoEncontradaException(nbs or "", data)