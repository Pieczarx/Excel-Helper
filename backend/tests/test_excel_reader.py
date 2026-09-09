from datetime import date
from pathlib import Path

from app.excel_reader import _parse_data_range, parse_workbook

EXAMPLE_FILE = Path(__file__).resolve().parents[2] / "examples" / "MPECWIK 2026.xlsx"


def _by_wiersz(obiekty, wiersz):
    return next(o for o in obiekty if o.wiersz == wiersz)


def test_parsuje_wszystkie_obiekty():
    obiekty = parse_workbook(EXAMPLE_FILE, rok=2026)
    assert len(obiekty) == 106


def test_pierwszy_obiekt_pierwszy_okres():
    obiekty = parse_workbook(EXAMPLE_FILE, rok=2026)
    obiekt = _by_wiersz(obiekty, 3)
    assert obiekt.nazwa == "20 Października 40B"
    okres = obiekt.okresy[0]
    assert okres.data_od == date(2026, 1, 1)
    assert okres.data_do == date(2026, 1, 20)
    assert okres.zuzycie_szczytowa == 182.0
    assert okres.zuzycie_pozaszczytowa == 442.0
    assert okres.zuzycie_razem == 624.0
    assert okres.oplata_dystrybucja == 244.41
    assert okres.oplata_energia == 310.67
    assert okres.koszty_razem == 555.08


def test_pomija_ukryty_blok_i_ukryte_kolumny_tozsamosci():
    obiekty = parse_workbook(EXAMPLE_FILE, rok=2026)
    obiekt = _by_wiersz(obiekty, 3)
    # 12 realnych miesiecy, nie 13 (ukryty zdublowany blok "WRZESIEŃ" pominięty)
    assert len(obiekt.okresy) <= 12


def test_zglasza_niepoprawny_zakres_dat_jako_problem_a_nie_wyjatek():
    obiekty = parse_workbook(EXAMPLE_FILE, rok=2026)
    obiekt = _by_wiersz(obiekty, 76)
    assert obiekt.nazwa == "Słupia Wielka PI oczyszczal"
    assert len(obiekt.problemy) == 1
    assert obiekt.problemy[0].tresc == "02.01.11.03"


def test_okres_przechodzacy_przez_nowy_rok():
    data_od, data_do = _parse_data_range("28.12-15.01", rok=2026)
    assert data_od == date(2025, 12, 28)
    assert data_do == date(2026, 1, 15)


def test_identyfikacja_obiektu_zawiera_dane_z_kolumn_tozsamosci():
    obiekty = parse_workbook(EXAMPLE_FILE, rok=2026)
    obiekt = _by_wiersz(obiekty, 3)
    assert obiekt.identyfikacja["Nr licznika"] == "87268444"
    assert obiekt.identyfikacja["Taryfa"] == "C12A"
    assert obiekt.identyfikacja["Moc umowna"] == "9kW"
    assert "Ulica/ Nazwa własna" not in obiekt.identyfikacja  # to jest juz obiekt.nazwa, nie duplikujemy


def test_komorka_zwraca_adres_zgodny_z_arkuszem():
    obiekty = parse_workbook(EXAMPLE_FILE, rok=2026)
    obiekt = _by_wiersz(obiekty, 3)
    assert obiekt.okresy[0].komorka("zuzycie_razem") == "S3"
