"""Comparação de versão local e remota no modo offline."""

from __future__ import annotations

import http.client
import json
import logging
import re
import time
import urllib.parse
from dataclasses import dataclass
from datetime import timedelta

logger = logging.getLogger(__name__)

_TENTATIVAS = 3
_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")


class IllegalArgumentException(Exception):
    """Equivalente a ``java.lang.IllegalArgumentException``: a subida não repete."""


class RestClientException(Exception):
    """Equivalente a ``org.springframework.web.client.RestClientException``."""


@dataclass(frozen=True)
class VersaoDomain:
    versao_app: str | None = None
    versao_db: str | None = None
    descricao_versao_db: str | None = None
    data_versao_db: str | None = None
    arquivo_db: str | None = None
    ambiente: str | None = None

    @classmethod
    def from_json(cls, payload: object) -> VersaoDomain:
        if not isinstance(payload, dict):
            raise RestClientException(
                "Error while extracting response for type VersaoDomain"
            )
        return cls(
            versao_app=payload.get("versaoApp"),
            versao_db=payload.get("versaoDb"),
            descricao_versao_db=payload.get("descricaoVersaoDb"),
            data_versao_db=payload.get("dataVersaoDb"),
            arquivo_db=payload.get("arquivoDb"),
            ambiente=payload.get("ambiente"),
        )


def _extrair_semver(versao: str | None) -> str | None:
    if versao is None:
        return None
    match = _SEMVER.search(versao)
    return match.group() if match else None


def _versoes_aplicacao_iguais(local: str | None, remota: str | None) -> bool:
    if local is None or remota is None:
        return False
    semver_local = _extrair_semver(local)
    semver_remota = _extrair_semver(remota)
    if semver_local is not None and semver_remota is not None:
        return semver_local == semver_remota
    return local == remota


@dataclass(frozen=True)
class VersaoOfflineDomain:
    aplicacao_atualizada: bool
    db_atualizada: bool
    data_db_atualizada: bool
    versao_aplicacao_local: str | None
    versao_aplicacao_remota: str | None
    versao_db_local: str | None
    versao_db_remota: str | None
    data_db_local: str | None
    data_db_remota: str | None

    @classmethod
    def de(cls, local: VersaoDomain, remota: VersaoDomain | None) -> VersaoOfflineDomain:
        versao_aplicacao_local = local.versao_app
        versao_db_local = local.versao_db
        data_db_local = local.data_versao_db
        versao_aplicacao_remota = remota.versao_app if remota is not None else None
        versao_db_remota = remota.versao_db if remota is not None else None
        data_db_remota = remota.data_versao_db if remota is not None else None
        return cls(
            _versoes_aplicacao_iguais(versao_aplicacao_local, versao_aplicacao_remota),
            versao_db_local is not None and versao_db_local == versao_db_remota,
            data_db_local is not None and data_db_local == data_db_remota,
            versao_aplicacao_local,
            versao_aplicacao_remota,
            versao_db_local,
            versao_db_remota,
            data_db_local,
            data_db_remota,
        )


class ServicoVersaoOffline:
    def __init__(
        self,
        versao_service: object,
        url_versao_remota: str,
        connect_timeout: timedelta,
        read_timeout: timedelta,
        intervalo_entre_tentativas: timedelta = timedelta(seconds=2),
    ) -> None:
        self._versao_service = versao_service
        self._url_versao_remota = url_versao_remota
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._intervalo_entre_tentativas = intervalo_entre_tentativas

    def verificar_versao(self) -> VersaoOfflineDomain:
        try:
            remota: VersaoDomain | None = self._consultar_versao_remota()
        except RestClientException as exc:
            logger.warning(
                "Consulta da versão remota indisponível em [%s]: %s",
                self._url_versao_remota,
                exc,
            )
            remota = None
        return VersaoOfflineDomain.de(self._versao_service.getVersao(), remota)

    def verificar_versao_na_inicializacao(self) -> None:
        ultimo: BaseException | None = None
        for tentativa in range(1, _TENTATIVAS + 1):
            try:
                status = VersaoOfflineDomain.de(
                    self._versao_service.getVersao(),
                    self._consultar_versao_remota(),
                )
                self._exibir_status_versao(status)
                return
            except IllegalArgumentException as exc:
                logger.warning(
                    "Não foi possível verificar versão remota após %s tentativas: %s",
                    _TENTATIVAS,
                    exc,
                )
                return
            except RestClientException as exc:
                ultimo = exc
                if tentativa < _TENTATIVAS:
                    time.sleep(self._intervalo_entre_tentativas.total_seconds())
        logger.warning(
            "Não foi possível verificar versão remota após %s tentativas: %s",
            _TENTATIVAS,
            ultimo,
        )

    def _consultar_versao_remota(self) -> VersaoDomain:
        parsed = urllib.parse.urlparse(self._url_versao_remota)
        if parsed.scheme not in ("http", "https"):
            raise RestClientException(f"unsupported url scheme: {parsed.scheme}")
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        conn: http.client.HTTPConnection | http.client.HTTPSConnection
        if parsed.scheme == "https":
            conn = http.client.HTTPSConnection(
                host, port, timeout=self._connect_timeout.total_seconds()
            )
        else:
            conn = http.client.HTTPConnection(
                host, port, timeout=self._connect_timeout.total_seconds()
            )
        try:
            conn.request("GET", path)
            if conn.sock is not None:
                conn.sock.settimeout(self._read_timeout.total_seconds())
            resp = conn.getresponse()
            raw = resp.read()
            content_type = resp.getheader("Content-Type", "")
            if resp.status >= 400:
                body = raw.decode(errors="replace") if raw else ""
                detail = body if body else "[no body]"
                raise RestClientException(
                    f"{resp.status} {resp.reason} on GET request for "
                    f'"{self._url_versao_remota}": {detail}'
                )
            if content_type and "json" not in content_type.lower():
                raise RestClientException(
                    "Could not extract response: no suitable HttpMessageConverter "
                    "found for response type VersaoDomain "
                    f"and content type [{content_type.split(';')[0]}]"
                )
            try:
                payload = json.loads(raw.decode())
            except json.JSONDecodeError as err:
                raise RestClientException(
                    "Error while extracting response for type VersaoDomain "
                    "and content type [application/json]"
                ) from err
            return VersaoDomain.from_json(payload)
        except TimeoutError as err:
            raise RestClientException(
                f'I/O error on GET request for "{self._url_versao_remota}": Read timed out'
            ) from err
        except ConnectionRefusedError as err:
            raise RestClientException(
                f'I/O error on GET request for "{self._url_versao_remota}": '
                "Connection refused (connect failed)"
            ) from err
        except OSError as err:
            if isinstance(err, RestClientException):
                raise
            raise RestClientException(
                f'I/O error on GET request for "{self._url_versao_remota}": {err}'
            ) from err
        finally:
            conn.close()

    def _exibir_status_versao(self, status: VersaoOfflineDomain) -> None:
        atualizados: list[str] = []
        desatualizados: list[str] = []
        if status.aplicacao_atualizada:
            atualizados.append(f"Aplicação (LOCAL):  {status.versao_aplicacao_local}")
            atualizados.append(f"Aplicação (ONLINE): {status.versao_aplicacao_remota}")
        else:
            desatualizados.append(f"Aplicação (LOCAL):  {status.versao_aplicacao_local}")
            desatualizados.append(f"Aplicação (ONLINE): {status.versao_aplicacao_remota}")
        if status.db_atualizada:
            atualizados.append(f"Banco de Dados (LOCAL):  {status.versao_db_local}")
            atualizados.append(f"Banco de Dados (ONLINE): {status.versao_db_remota}")
        else:
            desatualizados.append(f"Banco de Dados (LOCAL):  {status.versao_db_local}")
            desatualizados.append(f"Banco de Dados (ONLINE): {status.versao_db_remota}")
        if status.data_db_atualizada:
            atualizados.append(f"Data do Banco (LOCAL):  {status.data_db_local}")
            atualizados.append(f"Data do Banco (ONLINE): {status.data_db_remota}")
        else:
            desatualizados.append(f"Data do Banco (LOCAL):  {status.data_db_local}")
            desatualizados.append(f"Data do Banco (ONLINE): {status.data_db_remota}")
        if atualizados:
            logger.info("= VERSÃO ATUALIZADA " + "=" * 30)
            for linha in atualizados:
                logger.info(linha)
        if desatualizados:
            logger.info("= VERSÃO DESATUALIZADA " + "=" * 27)
            for linha in desatualizados:
                logger.info(linha)
