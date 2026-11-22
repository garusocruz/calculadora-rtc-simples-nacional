"""Paridade de ``Teste_VersaoOfflineService``: retentativa na subida, sem API."""

from __future__ import annotations

from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from calculadora_rtc_simples_nacional.consumo import VersaoOfflineService
from calculadora_rtc_simples_nacional.versao import IllegalArgumentException, VersaoDomain

_CLASSNAME = "br.gov.serpro.rtc.testesunitarios.versao.Teste_VersaoOfflineService"
_CORPO = b'{"versaoApp":"1.0.0","versaoDb":"V0001","dataVersaoDb":"2026-01-01"}'


def _junit(record_xml_attribute, name: str) -> None:
    record_xml_attribute("classname", _CLASSNAME)
    record_xml_attribute("name", name)


class _Local:
    def __init__(self, erro: BaseException | None = None) -> None:
        self.chamadas = 0
        self._erro = erro

    def getVersao(self) -> VersaoDomain:
        self.chamadas += 1
        if self._erro is not None:
            raise self._erro
        return VersaoDomain(
            versao_app="1.0.0",
            versao_db="V0001",
            data_versao_db="2026-01-01",
        )


class _Fila(BaseHTTPRequestHandler):
    respostas: list[int] = []
    pedidos = 0

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:
        type(self).pedidos += 1
        status = self.respostas.pop(0) if self.respostas else 500
        if status >= 400:
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(_CORPO)))
        self.end_headers()
        self.wfile.write(_CORPO)


def _servidor(respostas: list[int]):
    _Fila.respostas = list(respostas)
    _Fila.pedidos = 0
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), _Fila)
    thread = Thread(target=servidor.serve_forever, daemon=True)
    thread.start()
    return servidor


def _servico(local: _Local, url: str) -> VersaoOfflineService:
    return VersaoOfflineService(
        local,
        url,
        connect_timeout=timedelta(seconds=5),
        read_timeout=timedelta(seconds=10),
        intervalo_entre_tentativas=timedelta(milliseconds=1),
    )


def test_ConsultaRespondeNaPrimeira_NaoRepete(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "teste_ConsultaRespondeNaPrimeira_NaoRepete")
    servidor = _servidor([200])
    try:
        url = f"http://127.0.0.1:{servidor.server_address[1]}/versao"
        _servico(_Local(), url).verificarVersaoNaInicializacao()
        assert _Fila.pedidos == 1
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_ConsultaFalhaUmaVez_RespondeNaSegundaTentativa(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "teste_ConsultaFalhaUmaVez_RespondeNaSegundaTentativa")
    servidor = _servidor([500, 200])
    try:
        url = f"http://127.0.0.1:{servidor.server_address[1]}/versao"
        _servico(_Local(), url).verificarVersaoNaInicializacao()
        assert _Fila.pedidos == 2
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_ConsultaFalhaSempre_TresTentativasESubidaSegue(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "teste_ConsultaFalhaSempre_TresTentativasESubidaSegue")
    servidor = _servidor([500, 500, 500])
    try:
        url = f"http://127.0.0.1:{servidor.server_address[1]}/versao"
        _servico(_Local(), url).verificarVersaoNaInicializacao()
        assert _Fila.pedidos == 3
    finally:
        servidor.shutdown()
        servidor.server_close()


def test_IllegalArgumentException_NaoERepetidaESubidaSegue(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "teste_IllegalArgumentException_NaoERepetidaESubidaSegue")
    local = _Local(IllegalArgumentException("versão local inválida"))
    servidor = _servidor([])
    try:
        url = f"http://127.0.0.1:{servidor.server_address[1]}/versao"
        _servico(local, url).verificarVersaoNaInicializacao()
        assert local.chamadas == 1
        assert _Fila.pedidos == 0
    finally:
        servidor.shutdown()
        servidor.server_close()
