"""Espelho de ``Teste_SimplesNacionalObservabilidadeService`` (pin a926d5a7)."""

from __future__ import annotations

import os
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from calculadora_rtc_simples_nacional import parametro
from calculadora_rtc_simples_nacional.consumo import SimplesNacionalObservabilidadeService
from calculadora_rtc_simples_nacional.observabilidade import (
    ItemSimplesClassico,
    OperacaoSimplesClassica,
    uri_erro,
)
from calculadora_rtc_simples_nacional.parametro import AtividadeNacional, ClassificacaoTributaria, banco_disponivel
from calculadora_rtc_simples_nacional.processador import EstadoItemProcessado
from calculadora_rtc_simples_nacional.unificado import ErrosCalculoException

os.environ.setdefault(
    "CALC_DB",
    "/home/garusotec/projects/lynko/libs/calculadora-rtc-simples-nacional/.cache/oficial/java/calculadora/db/calculadora-pro.db",
)

_CLASSNAME = (
    "br.gov.serpro.rtc.testesunitarios.simplesnacional.Teste_SimplesNacionalObservabilidadeService"
)
BASE_URL = "http://localhost/api"
DATA_PADRAO = "2027-03-15"

pytestmark = pytest.mark.skipif(not banco_disponivel(), reason="calculadora-pro.db ausente")


def _junit(record_xml_attribute, name: str) -> None:
    record_xml_attribute("classname", _CLASSNAME)
    record_xml_attribute("name", name)


def _item(
    numero: int | None = 1,
    cativ_sn: str | None = "01",
    class_trib: str | None = "000001",
    base: str = "1000.00",
    pis: str | None = "1.25",
    pcbs: str | None = "2.75",
) -> ItemSimplesClassico:
    return ItemSimplesClassico(numero, cativ_sn, class_trib, None, None, base, "0.00", pis, pcbs)


def _operacao(*, itens=None, **kwargs) -> OperacaoSimplesClassica:
    return OperacaoSimplesClassica(
        kwargs.get("id", "507f1f77bcf86cd799439011"),
        kwargs.get("versao", "2.0.0"),
        kwargs.get("data", DATA_PADRAO),
        kwargs.get("tp_doc", "55"),
        kwargs.get("crt", "1"),
        kwargs.get("tp_regime_ibscbs"),
        kwargs.get("tp_ente_gov"),
        list(itens or [_item()]),
    )


def _operacao_compra_gov(*, itens=None, **kwargs) -> OperacaoSimplesClassica:
    return _operacao(itens=itens, **kwargs)


def _codigos_item(obj) -> list[str]:
    return [e.code for e in (obj.erros or ())]


def _codigos_globais(svc: SimplesNacionalObservabilidadeService, operacao: OperacaoSimplesClassica) -> list[str]:
    with pytest.raises(ErrosCalculoException) as exc:
        svc.processarOperacao(operacao, BASE_URL)
    return [e.code for e in exc.value.erros]


class _RepositorioStubs:
    """Stubs de catálogo (espelho Mockito dos repositórios Java)."""

    def __init__(self) -> None:
        self._classificacoes: dict[str, ClassificacaoTributaria] = {}
        self._vinculo_class_tpdoc: dict[str, int] = {}
        self._atividades: dict[str, list[AtividadeNacional]] = {}
        self._vinculo_ativ: dict[int, int] = {}
        self._nao_implementados: dict[str, int] = {}
        self._patchers: list = []

    def start(self) -> None:
        self._patchers = [
            patch(
                "calculadora_rtc_simples_nacional.processador.buscar_classificacoes_vigentes",
                side_effect=self._buscar_classificacoes,
            ),
            patch(
                "calculadora_rtc_simples_nacional.processador.contar_vinculo_classificacao_tpdoc",
                side_effect=self._contar_class_tpdoc,
            ),
            patch(
                "calculadora_rtc_simples_nacional.processador.buscar_atividades_por_cativsn",
                side_effect=self._buscar_atividades,
            ),
            patch(
                "calculadora_rtc_simples_nacional.processador.contar_vinculo_atividade_tpdoc",
                side_effect=self._contar_ativ_tpdoc,
            ),
            patch(
                "calculadora_rtc_simples_nacional.processador.contar_tratamentos_nao_implementados",
                side_effect=self._contar_nao_impl,
            ),
        ]
        for p in self._patchers:
            p.start()

    def stop(self) -> None:
        for p in self._patchers:
            p.stop()
        self._patchers.clear()

    def stub_class_trib(self, codigo: str, tp_rbsn: int) -> None:
        self._classificacoes[codigo] = ClassificacaoTributaria(1, codigo, tp_rbsn)
        self._vinculo_class_tpdoc[codigo] = 1

    def stub_class_trib_incompativel(self, codigo: str, tp_rbsn: int) -> None:
        self._classificacoes[codigo] = ClassificacaoTributaria(1, codigo, tp_rbsn)
        self._vinculo_class_tpdoc[codigo] = 0

    def stub_class_trib_desconhecido(self, codigo: str) -> None:
        self._classificacoes.pop(codigo, None)

    def stub_atividade(
        self, cativ: str, ativ_id: int, vinculos: int, nao_tributavel: bool
    ) -> None:
        self._atividades[cativ] = [
            AtividadeNacional(ativ_id, ativ_id, f"Atividade {cativ}", cativ, "I", None, nao_tributavel, False, False)
        ]
        self._vinculo_ativ[ativ_id] = vinculos

    def stub_atividade_com_vinculo(self, cativ: str, ativ_id: int) -> None:
        self.stub_atividade(cativ, ativ_id, 1, False)

    def stub_atividade_inexistente(self, cativ: str) -> None:
        self._atividades[cativ] = []

    def stub_nao_implementado(self, codigo: str) -> None:
        self._nao_implementados[codigo] = 1

    def stub_implementado_explicito(self, codigo: str) -> None:
        self._nao_implementados[codigo] = 0

    def _buscar_classificacoes(self, codigo: str, _data):
        row = self._classificacoes.get(codigo)
        return [row] if row is not None else []

    def _contar_class_tpdoc(self, codigo: str, _tp_doc, _data):
        if codigo in self._vinculo_class_tpdoc:
            return self._vinculo_class_tpdoc[codigo]
        return 1 if codigo in self._classificacoes else 0

    def _buscar_atividades(self, codigo: str, _data):
        return list(self._atividades.get(codigo, []))

    def _contar_ativ_tpdoc(self, ativ_id: int, _tp_doc, _data):
        return self._vinculo_ativ.get(ativ_id, 0)

    def _contar_nao_impl(self, codigo: str, _data):
        if codigo in self._nao_implementados:
            return self._nao_implementados[codigo]
        return 0


@pytest.fixture
def repo() -> _RepositorioStubs:
    stubs = _RepositorioStubs()
    stubs.start()
    yield stubs
    stubs.stop()


@pytest.fixture
def svc() -> SimplesNacionalObservabilidadeService:
    return SimplesNacionalObservabilidadeService(parametro.ParametroCalculo())


def test_caso19_cAtivSNSemLinhaNoCatalogo_naoCalculado(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso19_cAtivSNSemLinhaNoCatalogo_naoCalculado")
    repo.stub_class_trib("000001", 1)
    repo.stub_atividade_inexistente("99")
    resultado = svc.processarOperacao(_operacao(itens=[_item(cativ_sn="99")]), BASE_URL)
    assert resultado.objetos[0].estado is EstadoItemProcessado.NAO_CALCULADO


def test_atividadeSemVinculoAlgum_naoCalculadaEmTpDocNenhum(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "atividadeSemVinculoAlgum_naoCalculadaEmTpDocNenhum")
    repo.stub_class_trib("000001", 1)
    repo.stub_atividade("05", 5, 0, False)
    for tp_doc in ("55", "65"):
        resultado = svc.processarOperacao(
            _operacao(tp_doc=tp_doc, itens=[_item(cativ_sn="05")]), BASE_URL
        )
        assert resultado.objetos[0].estado is EstadoItemProcessado.NAO_CALCULADO, tp_doc


def test_atividadeVinculadaApenasAOutroTpDoc_naoCalculado(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "atividadeVinculadaApenasAOutroTpDoc_naoCalculado")
    repo.stub_class_trib("000001", 1)
    repo.stub_atividade("12", 12, 0, False)
    resultado = svc.processarOperacao(_operacao(itens=[_item(cativ_sn="12")]), BASE_URL)
    assert resultado.objetos[0].estado is EstadoItemProcessado.NAO_CALCULADO


def test_atividadeVinculadaAoTpDocDaOperacao_calculado(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "atividadeVinculadaAoTpDocDaOperacao_calculado")
    repo.stub_class_trib("000001", 1)
    repo.stub_atividade("01", 1, 1, False)
    resultado = svc.processarOperacao(_operacao(itens=[_item(cativ_sn="01")]), BASE_URL)
    assert resultado.objetos[0].estado is EstadoItemProcessado.CALCULADO


def test_vinculoComVigenciaEncerrada_ehIgnorado_atividadeFicaInadmissivel(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "vinculoComVigenciaEncerrada_ehIgnorado_atividadeFicaInadmissivel")
    repo.stub_class_trib("000001", 1)
    repo.stub_atividade("01", 1, 0, False)
    resultado = svc.processarOperacao(_operacao(itens=[_item(cativ_sn="01")]), BASE_URL)
    assert resultado.objetos[0].estado is EstadoItemProcessado.NAO_CALCULADO


def test_caso21_atividadeNaoTributavelComReceitaTributavel_erroDeItem(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso21_atividadeNaoTributavelComReceitaTributavel_erroDeItem")
    repo.stub_class_trib("000001", 1)
    repo.stub_atividade("90", 15, 1, True)
    resultado = svc.processarOperacao(_operacao(itens=[_item(cativ_sn="90")]), BASE_URL)
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    assert "VSN-023" in _codigos_item(obj)
    assert obj.tributos is None
    assert resultado.total is None


def test_atividadeNaoTributavelComTpRBSN0_calculadoComTudoZero(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "atividadeNaoTributavelComTpRBSN0_calculadoComTudoZero")
    repo.stub_class_trib("410001", 0)
    repo.stub_atividade("90", 15, 1, True)
    resultado = svc.processarOperacao(_operacao(itens=[_item(cativ_sn="90", class_trib="410001")]), BASE_URL)
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.CALCULADO
    trib = obj.tributos
    assert trib is not None
    assert Decimal(0) == trib.receita_bruta
    assert trib.tipo_receita == 0
    assert Decimal(0) == trib.valor_ibs
    assert Decimal(0) == trib.valor_cbs


def test_cClassTribNaoImplementado_estadoNaoImplementadoSemCalculoNemTotal(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "cClassTribNaoImplementado_estadoNaoImplementadoSemCalculoNemTotal")
    repo.stub_nao_implementado("620001")
    resultado = svc.processarOperacao(_operacao(itens=[_item(class_trib="620001")]), BASE_URL)
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.NAO_IMPLEMENTADO
    assert _codigos_item(obj) == ["VSN-027"]
    assert obj.erros is not None
    assert obj.erros[0].pointer == "#/itens/0/cClassTrib"
    assert uri_erro(BASE_URL, "VSN-027").endswith("codigo=VSN-027")
    assert "620001" in obj.erros[0].detail
    assert obj.tributos is None
    assert resultado.total is None


def test_cClassTribNaoImplementado_ehAPrimeiraConsultaEEncerraOItem(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "cClassTribNaoImplementado_ehAPrimeiraConsultaEEncerraOItem")
    repo.stub_nao_implementado("800001")
    resultado = svc.processarOperacao(
        _operacao(
            itens=[
                ItemSimplesClassico(1, "01", "800001", None, None, "-10.00", "0.00", None, None)
            ]
        ),
        BASE_URL,
    )
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.NAO_IMPLEMENTADO
    assert _codigos_item(obj) == ["VSN-027"]


def test_cClassTribNaoImplementado_prevaleceSobreNumeroAusente(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "cClassTribNaoImplementado_prevaleceSobreNumeroAusente")
    repo.stub_nao_implementado("620001")
    resultado = svc.processarOperacao(
        _operacao(itens=[_item(numero=None, class_trib="620001")]), BASE_URL
    )
    obj = resultado.objetos[0]
    assert obj.numero == 1
    assert obj.estado is EstadoItemProcessado.NAO_IMPLEMENTADO
    assert _codigos_item(obj) == ["VSN-010", "VSN-027"]


def test_cClassTribNaoImplementado_naoContaminaOsDemaisItensNemOsTotais(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "cClassTribNaoImplementado_naoContaminaOsDemaisItensNemOsTotais")
    repo.stub_nao_implementado("620001")
    repo.stub_implementado_explicito("000001")
    repo.stub_class_trib("000001", 1)
    repo.stub_atividade_com_vinculo("01", 1)
    resultado = svc.processarOperacao(
        _operacao(
            itens=[
                _item(numero=1, class_trib="620001"),
                _item(numero=2, class_trib="000001"),
            ]
        ),
        BASE_URL,
    )
    assert len(resultado.objetos) == 2
    assert resultado.objetos[0].estado is EstadoItemProcessado.NAO_IMPLEMENTADO
    assert resultado.objetos[1].estado is EstadoItemProcessado.CALCULADO
    assert resultado.total is not None
    assert Decimal("1000.00") == resultado.total.receita_bruta_total
    assert Decimal("12.50") == resultado.total.ibs_total
    assert Decimal("27.50") == resultado.total.cbs_total


def test_cClassTribImplementado_segueOFluxoNormal(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "cClassTribImplementado_segueOFluxoNormal")
    repo.stub_class_trib("000001", 1)
    repo.stub_atividade_com_vinculo("01", 1)
    resultado = svc.processarOperacao(_operacao(), BASE_URL)
    assert resultado.objetos[0].estado is EstadoItemProcessado.CALCULADO


def test_cClassTribAusente_naoConsultaImplementacao(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "cClassTribAusente_naoConsultaImplementacao")
    with patch(
        "calculadora_rtc_simples_nacional.processador.contar_tratamentos_nao_implementados",
        side_effect=AssertionError("contar_tratamentos não deveria ser chamado"),
    ):
        resultado = svc.processarOperacao(
            _operacao(itens=[_item(class_trib=" ")]), BASE_URL
        )
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    assert "VSN-020" in _codigos_item(obj)


def test_caso22_cClassTribDesconhecido_erroDeItem(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso22_cClassTribDesconhecido_erroDeItem")
    repo.stub_class_trib_desconhecido("999999")
    resultado = svc.processarOperacao(_operacao(itens=[_item(class_trib="999999")]), BASE_URL)
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    assert "VSN-021" in _codigos_item(obj)


def test_cClassTribIncompativelComTpDoc_erroDeItem(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "cClassTribIncompativelComTpDoc_erroDeItem")
    repo.stub_class_trib_incompativel("222001", 5)
    resultado = svc.processarOperacao(_operacao(itens=[_item(class_trib="222001")]), BASE_URL)
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    assert "VSN-022" in _codigos_item(obj)


def test_cClassTribAusente_erroDeItem(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "cClassTribAusente_erroDeItem")
    resultado = svc.processarOperacao(_operacao(itens=[_item(class_trib=None)]), BASE_URL)
    assert "VSN-020" in _codigos_item(resultado.objetos[0])


def test_tipoReceitaBrutaSemLinhaVigente_erroDeItemVsn026(
    repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "tipoReceitaBrutaSemLinhaVigente_erroDeItemVsn026")
    param = parametro.ParametroCalculo()
    original = param.buscar_tipo_receita_bruta

    def sem_linha(tp: int, data, vocab=None):
        if tp == 1:
            return None
        if vocab is None:
            return original(tp, data)
        return original(tp, data, vocab)

    param.buscar_tipo_receita_bruta = sem_linha  # type: ignore[method-assign]
    svc = SimplesNacionalObservabilidadeService(param)
    repo.stub_class_trib("000001", 1)
    repo.stub_atividade_com_vinculo("01", 1)
    resultado = svc.processarOperacao(_operacao(), BASE_URL)
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    assert "VSN-026" in _codigos_item(obj)


def test_regimeSemLinhaVigente_erroGlobalVsn026(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "regimeSemLinhaVigente_erroGlobalVsn026")
    param = MagicMock(spec=parametro.ParametroCalculo)
    param.tp_doc_suportado.return_value = True
    param.tp_doc_sem_tratamento_calculadora.return_value = False
    param.buscar_regime_apuracao.return_value = None
    svc = SimplesNacionalObservabilidadeService(param)
    codigos = _codigos_globais(svc, _operacao())
    assert "VSN-026" in codigos


def test_caso23_tpRegimeIbsCbs1_regimeRegularForaDeEscopo(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "caso23_tpRegimeIbsCbs1_regimeRegularForaDeEscopo")
    svc = SimplesNacionalObservabilidadeService()
    assert "VSN-019" in _codigos_globais(svc, _operacao(tp_regime_ibscbs="1"))


def test_caso24_crt4_meiForaDeEscopo(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "caso24_crt4_meiForaDeEscopo")
    svc = SimplesNacionalObservabilidadeService()
    assert "VSN-019" in _codigos_globais(svc, _operacao(crt="4"))


def test_caso25_crt1ComTpRegime2_incompativel(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "caso25_crt1ComTpRegime2_incompativel")
    svc = SimplesNacionalObservabilidadeService()
    assert "VSN-018" in _codigos_globais(svc, _operacao(tp_regime_ibscbs="2"))


def test_caso26_crt3SemTpRegime_regimeNormalPuroForaDeEscopo(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "caso26_crt3SemTpRegime_regimeNormalPuroForaDeEscopo")
    svc = SimplesNacionalObservabilidadeService()
    assert "VSN-019" in _codigos_globais(svc, _operacao(crt="3"))


def _parametro_tpdoc_apenas_55_65() -> parametro.ParametroCalculo:
    """Espelha o stub lenient de ``tpDocSuportado`` do setup Java (55 e 65)."""
    param = parametro.ParametroCalculo()
    param.tp_doc_suportado = lambda doc, _data: doc in (55, 65)  # type: ignore[method-assign]
    return param


def test_caso27_tpDoc91_naoSuportado(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "caso27_tpDoc91_naoSuportado")
    svc = SimplesNacionalObservabilidadeService(_parametro_tpdoc_apenas_55_65())
    assert "VSN-015" in _codigos_globais(svc, _operacao(tp_doc="91"))


@pytest.mark.parametrize("tp_doc", ["77", "94", "95", "96"])
def test_tpDocSemTratamento_rejeitadoGlobalmente(tp_doc: str, record_xml_attribute) -> None:
    _junit(record_xml_attribute, "tpDocSemTratamento_rejeitadoGlobalmente")
    param = parametro.ParametroCalculo()

    def sem_tratamento(doc: int, _data):
        return doc in (77, 94, 95, 96)

    param.tp_doc_sem_tratamento_calculadora = sem_tratamento  # type: ignore[method-assign]
    svc = SimplesNacionalObservabilidadeService(param)
    assert "VSN-015" in _codigos_globais(svc, _operacao(tp_doc=tp_doc))


def test_caso28_tpDocAusente_erroGlobal(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "caso28_tpDocAusente_erroGlobal")
    svc = SimplesNacionalObservabilidadeService()
    assert "VSN-014" in _codigos_globais(svc, _operacao(tp_doc=None))


def test_crtAusente_erroGlobal(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "crtAusente_erroGlobal")
    svc = SimplesNacionalObservabilidadeService()
    assert "VSN-016" in _codigos_globais(svc, _operacao(crt=None))


def test_tpRegimeInvalido_erroGlobal(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "tpRegimeInvalido_erroGlobal")
    svc = SimplesNacionalObservabilidadeService()
    assert "VSN-017" in _codigos_globais(svc, _operacao(crt="3", tp_regime_ibscbs="9"))


def test_dataInvalida_reportaApenasErroDeData_semVerificarSuporteDoTpDoc(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "dataInvalida_reportaApenasErroDeData_semVerificarSuporteDoTpDoc")
    svc = SimplesNacionalObservabilidadeService()
    codigos = _codigos_globais(svc, _operacao(data="2027-13-99"))
    assert "VSN-012" in codigos
    assert len(codigos) == 1


def test_caso29_tpRBSN1SemPCbssn_erroDeAliquotaExigida(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso29_tpRBSN1SemPCbssn_erroDeAliquotaExigida")
    repo.stub_class_trib("000001", 1)
    repo.stub_atividade_com_vinculo("01", 1)
    resultado = svc.processarOperacao(
        _operacao(itens=[_item(pcbs=None)]), BASE_URL
    )
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.INCONSISTENCIA_ENTRADA
    assert "VSN-004" in _codigos_item(obj)


def test_caso30_tpRBSN2SemAliquotas_calculadoComTudoZero(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "caso30_tpRBSN2SemAliquotas_calculadoComTudoZero")
    repo.stub_class_trib("410008", 2)
    repo.stub_atividade_com_vinculo("01", 1)
    resultado = svc.processarOperacao(
        _operacao(itens=[_item(class_trib="410008", pis=None, pcbs=None)]), BASE_URL
    )
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.CALCULADO
    trib = obj.tributos
    assert trib is not None
    assert Decimal(0) == trib.valor_ibs
    assert Decimal(0) == trib.valor_cbs
    assert trib.aliquota_ibs is None
    assert trib.aliquota_cbs is None


def test_crt2_pIbssnNuncaExigida(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "crt2_pIbssnNuncaExigida")
    repo.stub_class_trib("000001", 1)
    repo.stub_atividade_com_vinculo("01", 1)
    resultado = svc.processarOperacao(
        _operacao(crt="2", itens=[_item(pis=None)]), BASE_URL
    )
    obj = resultado.objetos[0]
    assert obj.estado is EstadoItemProcessado.CALCULADO
    trib = obj.tributos
    assert trib is not None
    assert trib.aliquota_ibs is None
    assert trib.valor_ibs is None
    assert Decimal("27.50") == trib.valor_cbs
    assert resultado.total is not None
    assert resultado.total.ibs_total is None
    assert resultado.total.ibs_pendente_total is None


def test_caso31_compraGovComDataForaDasVigencias_erroGlobal(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "caso31_compraGovComDataForaDasVigencias_erroGlobal")
    from datetime import date as date_cls

    param = _parametro_tpdoc_apenas_55_65()
    regime_crt1 = param.buscar_regime_apuracao(parametro.RegimeCalculo.CRT_1, date_cls(2027, 3, 15))
    param.buscar_regime_apuracao = lambda _enum, _data: regime_crt1  # type: ignore[method-assign]

    def fator_transicao(data: date_cls) -> Decimal | None:
        if data < date_cls(2027, 1, 1):
            return None
        return Decimal("0.00")

    param.buscar_fator_transicao_compra_gov = fator_transicao  # type: ignore[method-assign]
    svc = SimplesNacionalObservabilidadeService(param)
    codigos = _codigos_globais(
        svc,
        _operacao_compra_gov(data="2025-06-01", tp_ente_gov="2"),
    )
    assert "VSN-025" in codigos


def test_tpEnteGovForaDoDominio_erroGlobal(record_xml_attribute) -> None:
    _junit(record_xml_attribute, "tpEnteGovForaDoDominio_erroGlobal")
    svc = SimplesNacionalObservabilidadeService()
    codigos = _codigos_globais(svc, _operacao_compra_gov(tp_ente_gov="5"))
    assert "VSN-024" in codigos


def test_tpEnteGovDaOperacao_aplicadoATodosOsItens(
    svc: SimplesNacionalObservabilidadeService, repo: _RepositorioStubs, record_xml_attribute
) -> None:
    _junit(record_xml_attribute, "tpEnteGovDaOperacao_aplicadoATodosOsItens")
    repo.stub_class_trib("000001", 1)
    repo.stub_atividade_com_vinculo("01", 1)
    resultado = svc.processarOperacao(
        _operacao_compra_gov(
            tp_ente_gov="1",
            itens=[_item(numero=1), _item(numero=2)],
        ),
        BASE_URL,
    )
    assert len(resultado.objetos) == 2
    for obj in resultado.objetos:
        assert obj.estado is EstadoItemProcessado.CALCULADO
        trib = obj.tributos
        assert trib is not None
        assert Decimal(0) == trib.aliquota_ibs
        assert Decimal(0) == trib.valor_ibs
        assert Decimal("4.00") == trib.aliquota_cbs
        assert Decimal("40.00") == trib.valor_cbs