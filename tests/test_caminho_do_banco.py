"""O sqlite empacotado só entra quando CALC_DB não foi informado."""

from pathlib import Path

from calculadora_rtc_simples_nacional import banco


def test_calc_db_vence_o_arquivo_empacotado(monkeypatch, tmp_path: Path) -> None:
    alvo = tmp_path / "informado.db"
    alvo.write_bytes(b"")
    monkeypatch.setenv("CALC_DB", str(alvo))
    monkeypatch.setattr(banco, "EMPACOTADO", tmp_path / "calculadora-pro.db")
    assert banco.caminho() == alvo


def test_pacote_vence_o_caminho_relativo(monkeypatch, tmp_path: Path) -> None:
    pacote = tmp_path / "calculadora-pro.db"
    pacote.write_bytes(b"")
    monkeypatch.delenv("CALC_DB", raising=False)
    monkeypatch.setattr(banco, "EMPACOTADO", pacote)
    assert banco.caminho() == pacote


def test_sem_banco_empacotado_usa_o_caminho_relativo(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CALC_DB", raising=False)
    monkeypatch.setattr(banco, "EMPACOTADO", tmp_path / "ausente.db")
    assert banco.caminho() == banco.ARQUIVO
