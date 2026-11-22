"""Espelho dos testes unitários de nomenclatura (pin a926d5a7), sem Spring."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from calculadora_rtc_simples_nacional.nomenclatura import (
    ModoValidacaoNomenclatura,
    NbsAplicavelService,
    NbsCompletoNaoInformadoException,
    NbsNaoVinculadaException,
    NcmAplicavelService,
    NcmCompletoNaoInformadoException,
    NcmNaoVinculadaException,
    NomenclaturaIncompativelTipoDfeException,
    NomenclaturaNaoPermitidaTipoDfeException,
    NomenclaturaObrigatoriaNaoInformadaException,
    SiglaDFe,
    ValidacaoNomenclaturaService,
)

_CLASSNAME_VAL = "br.gov.serpro.rtc.testesunitarios.nomenclatura.Teste_ValidacaoNomenclaturaService"
_CLASSNAME_TAB = "br.gov.serpro.rtc.testesunitarios.nomenclatura.Teste_NcmNbsAplicavelService_TabelaVerdade"

DATA = date(2026, 1, 1)
ID = 7
CODIGO = "200044"
TRIBUTOS = "CBS e IBS"

_CASOS_AES = [
    (False, False, False),
    (False, True, False),
    (True, False, False),
    (True, False, True),
    (True, True, False),
    (True, True, True),
]


def _junit(record_xml_attribute, classname: str, name: str) -> None:
    record_xml_attribute("classname", classname)
    record_xml_attribute("name", name)


class TesteValidacaoNomenclaturaServiceJava:
    def setup_method(self) -> None:
        self.nomenclatura = MagicMock()
        self.ncm = MagicMock()
        self.nbs = MagicMock()
        self.service = ValidacaoNomenclaturaService(self.nomenclatura, self.ncm, self.nbs)

    def _resultado(self, valor: str) -> None:
        self.nomenclatura.determinar_nomenclatura = MagicMock(return_value=valor)

    def _validar(
        self,
        dfe: SiglaDFe,
        codigo: str,
        valor_ncm: str | None,
        valor_nbs: str | None,
        modo: ModoValidacaoNomenclatura,
        id_: int = ID,
    ) -> None:
        self.service.validar(dfe, id_, codigo, valor_ncm, valor_nbs, DATA, TRIBUTOS, modo)

    def test_ncmObrigatorioEValidaContraAnexo(self, record_xml_attribute) -> None:
        _junit(record_xml_attribute, _CLASSNAME_VAL, "ncmObrigatorioEValidaContraAnexo")
        self._resultado("NCM")
        self._validar(
            SiglaDFe.NFCOM, CODIGO, "87100000", None, ModoValidacaoNomenclatura.PERMISSIVO
        )
        self.ncm.criticar_ncm_contra_anexo.assert_called_once_with(
            "87100000", ID, CODIGO, DATA, TRIBUTOS
        )
        self.nbs.assert_not_called()

    def test_nomenclaturaNcmRejeitaAusenciaOuNbsIncompativel(self, record_xml_attribute) -> None:
        _junit(record_xml_attribute, _CLASSNAME_VAL, "nomenclaturaNcmRejeitaAusenciaOuNbsIncompativel")
        self._resultado("NCM")
        with pytest.raises(NcmCompletoNaoInformadoException):
            self._validar(SiglaDFe.NFCOM, CODIGO, None, None, ModoValidacaoNomenclatura.PERMISSIVO)
        with pytest.raises(NomenclaturaIncompativelTipoDfeException):
            self._validar(
                SiglaDFe.NFCOM, CODIGO, "87100000", "115012000", ModoValidacaoNomenclatura.PERMISSIVO
            )

    def test_nbsObrigatorioERejeitaNcmOuCodigoIncompleto(self, record_xml_attribute) -> None:
        _junit(record_xml_attribute, _CLASSNAME_VAL, "nbsObrigatorioERejeitaNcmOuCodigoIncompleto")
        self._resultado("NBS")
        with pytest.raises(NbsCompletoNaoInformadoException):
            self._validar(SiglaDFe.NFCOM, CODIGO, None, None, ModoValidacaoNomenclatura.PERMISSIVO)
        with pytest.raises(NomenclaturaIncompativelTipoDfeException):
            self._validar(
                SiglaDFe.NFCOM, CODIGO, "87100000", "115012000", ModoValidacaoNomenclatura.PERMISSIVO
            )
        with pytest.raises(NbsCompletoNaoInformadoException):
            self._validar(SiglaDFe.NFCOM, CODIGO, None, "123", ModoValidacaoNomenclatura.PERMISSIVO)

    def test_mistoAceitaUmaDasNomenclaturasEExigeUmaQuandoAmbasVazias(
        self, record_xml_attribute
    ) -> None:
        _junit(
            record_xml_attribute,
            _CLASSNAME_VAL,
            "mistoAceitaUmaDasNomenclaturasEExigeUmaQuandoAmbasVazias",
        )
        self._resultado("MISTO")
        self._validar(
            SiglaDFe.NFCOM, CODIGO, "87100000", None, ModoValidacaoNomenclatura.PERMISSIVO
        )
        self._validar(
            SiglaDFe.NFCOM, CODIGO, None, "115012000", ModoValidacaoNomenclatura.PERMISSIVO
        )
        with pytest.raises(NomenclaturaObrigatoriaNaoInformadaException):
            self._validar(SiglaDFe.NFCOM, CODIGO, "", " ", ModoValidacaoNomenclatura.PERMISSIVO)
        self.ncm.criticar_ncm_contra_anexo.assert_called_with(
            "87100000", ID, CODIGO, DATA, TRIBUTOS
        )
        self.nbs.criticar_nbs_contra_anexo.assert_called_with(
            "115012000", ID, CODIGO, DATA, TRIBUTOS
        )

    def test_semNoTrioAceitaAusenciaENomenclaturaNaturalMasRejeitaContraria(
        self, record_xml_attribute
    ) -> None:
        _junit(
            record_xml_attribute,
            _CLASSNAME_VAL,
            "semNoTrioAceitaAusenciaENomenclaturaNaturalMasRejeitaContraria",
        )
        self._resultado("SEM")
        self._validar(SiglaDFe.NFE, CODIGO, None, None, ModoValidacaoNomenclatura.RIGIDO)
        self._validar(SiglaDFe.NFE, CODIGO, "87100000", None, ModoValidacaoNomenclatura.RIGIDO)
        with pytest.raises(NomenclaturaIncompativelTipoDfeException):
            self._validar(SiglaDFe.NFE, CODIGO, None, "115012000", ModoValidacaoNomenclatura.PERMISSIVO)
        self._validar(SiglaDFe.NFSE, CODIGO, None, "115012000", ModoValidacaoNomenclatura.RIGIDO)
        with pytest.raises(NomenclaturaIncompativelTipoDfeException):
            self._validar(SiglaDFe.NFSE, CODIGO, "87100000", None, ModoValidacaoNomenclatura.PERMISSIVO)

    def test_semForaDoTrioDistingueModoRigidoEPermissivo(self, record_xml_attribute) -> None:
        _junit(record_xml_attribute, _CLASSNAME_VAL, "semForaDoTrioDistingueModoRigidoEPermissivo")
        self._resultado("SEM")
        with pytest.raises(NomenclaturaNaoPermitidaTipoDfeException):
            self._validar(
                SiglaDFe.NFCOM, CODIGO, "87100000", None, ModoValidacaoNomenclatura.RIGIDO
            )
        self._validar(
            SiglaDFe.NFCOM, CODIGO, "87100000", None, ModoValidacaoNomenclatura.PERMISSIVO
        )
        self.ncm.validar_ncm_aplicavel.assert_called_once_with(
            "87100000", ID, CODIGO, DATA, TRIBUTOS
        )


class TesteNcmNbsAplicavelServiceTabelaVerdadeJava:
    @staticmethod
    def _rejeita(a: bool, e: bool, s: bool) -> bool:
        return not a or (e and not s)

    def test_tabelaVerdadeNcm(self, record_xml_attribute) -> None:
        _junit(record_xml_attribute, _CLASSNAME_TAB, "tabelaVerdadeNcm")
        id_tab = 9
        for a, e, s in _CASOS_AES:
            repo = MagicMock()
            repo.tem.return_value = True
            repo.tem_ncm_aplicavel.return_value = a
            repo.tem_excecao_ncm_aplicavel.return_value = e
            repo.tem_ncm_aplicavel_sem_excecao.return_value = s
            service = NcmAplicavelService(repo)
            if self._rejeita(a, e, s):
                with pytest.raises(NcmNaoVinculadaException):
                    service.criticar_ncm_contra_anexo("12345678", id_tab, CODIGO, DATA, TRIBUTOS)
            else:
                service.criticar_ncm_contra_anexo("12345678", id_tab, CODIGO, DATA, TRIBUTOS)

    def test_tabelaVerdadeNbs(self, record_xml_attribute) -> None:
        _junit(record_xml_attribute, _CLASSNAME_TAB, "tabelaVerdadeNbs")
        id_tab = 9
        for a, e, s in _CASOS_AES:
            repo = MagicMock()
            repo.tem.return_value = True
            repo.tem_nbs_aplicavel.return_value = a
            repo.tem_excecao_nbs_aplicavel.return_value = e
            repo.tem_nbs_aplicavel_sem_excecao.return_value = s
            service = NbsAplicavelService(repo)
            if self._rejeita(a, e, s):
                with pytest.raises(NbsNaoVinculadaException):
                    service.criticar_nbs_contra_anexo("123456789", id_tab, CODIGO, DATA, TRIBUTOS)
            else:
                service.criticar_nbs_contra_anexo("123456789", id_tab, CODIGO, DATA, TRIBUTOS)

    def test_codigoIncompletoComAnexoFalhaSemConsultarVinculoEspecifico(
        self, record_xml_attribute
    ) -> None:
        _junit(record_xml_attribute, _CLASSNAME_TAB, "codigoIncompletoComAnexoFalhaSemConsultarVinculoEspecifico")
        id_tab = 9
        ncm_repo = MagicMock()
        ncm_repo.tem.return_value = True
        with pytest.raises(NcmCompletoNaoInformadoException):
            NcmAplicavelService(ncm_repo).validar_ncm_aplicavel(
                "123", id_tab, CODIGO, DATA, TRIBUTOS
            )
        ncm_repo.tem_ncm_aplicavel.assert_not_called()

        nbs_repo = MagicMock()
        nbs_repo.tem.return_value = True
        with pytest.raises(NbsCompletoNaoInformadoException):
            NbsAplicavelService(nbs_repo).validar_nbs_aplicavel(
                "123", id_tab, CODIGO, DATA, TRIBUTOS
            )
        nbs_repo.tem_nbs_aplicavel.assert_not_called()

    def test_semAnexoAceitaCodigoCompletoSemCriticaEIncompleto(self, record_xml_attribute) -> None:
        _junit(record_xml_attribute, _CLASSNAME_TAB, "semAnexoAceitaCodigoCompletoSemCriticaEIncompleto")
        id_tab = 9
        ncm_repo = MagicMock()
        ncm_repo.tem.return_value = False
        ncm = NcmAplicavelService(ncm_repo)
        assert ncm.validar_ncm_aplicavel("12345678", id_tab, CODIGO, DATA, TRIBUTOS) is True
        assert ncm.validar_ncm_aplicavel("123", id_tab, CODIGO, DATA, TRIBUTOS) is True
        ncm_repo.tem_ncm_aplicavel.assert_not_called()
        ncm_repo.tem_excecao_ncm_aplicavel.assert_not_called()

        nbs_repo = MagicMock()
        nbs_repo.tem.return_value = False
        nbs = NbsAplicavelService(nbs_repo)
        assert nbs.validar_nbs_aplicavel("123456789", id_tab, CODIGO, DATA, TRIBUTOS) is True
        assert nbs.validar_nbs_aplicavel("123", id_tab, CODIGO, DATA, TRIBUTOS) is True
        nbs_repo.tem_nbs_aplicavel.assert_not_called()
        nbs_repo.tem_excecao_nbs_aplicavel.assert_not_called()