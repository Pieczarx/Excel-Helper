import pytest

from app.rok import NieRozpoznanoRoku, wykryj_rok


def test_wykrywa_rok_z_nazwy_pliku():
    assert wykryj_rok("MPECWIK 2026.xlsx") == 2026
    assert wykryj_rok(r"C:\dane\Faktury_2025.xlsx") == 2025


def test_brak_roku_w_nazwie_rzuca_czytelny_blad():
    with pytest.raises(NieRozpoznanoRoku):
        wykryj_rok("tabelka.xlsx")


def test_dwa_mozliwe_lata_rzuca_czytelny_blad():
    with pytest.raises(NieRozpoznanoRoku):
        wykryj_rok("Faktury_2025_kopia_2026.xlsx")
