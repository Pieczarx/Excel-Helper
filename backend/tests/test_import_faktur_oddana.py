import shutil
from datetime import date
from pathlib import Path

import openpyxl

from app.faktura_reader import KAT_JUZ_WYPELNIONE, KAT_SUKCES, PozycjaEnergiaOddana
from app.import_faktur_oddana import (
    polacz_pozycje_wielookresowe_oddana,
    wpisz_fakture_oddana_do_arkusza,
    wpisz_polaczone_pozycje_oddana,
)

TESTY_FILE = Path(__file__).resolve().parents[2] / "examples" / "MPECWIK 2026_testy.xlsx"
FAKTURY_ROOT = Path(__file__).resolve().parents[2] / "examples" / "Faktury MPECWIK 2026"
FAKTURA_BABIN_STYCZEN = next(p for p in FAKTURY_ROOT.rglob("D 01 31.pdf") if p.parent.name.startswith("Babin"))
FAKTURA_CHWALKOWO_LIPIEC = next(p for p in FAKTURY_ROOT.rglob("D 07 31.pdf") if p.parent.name.startswith("Chwałkowo"))

WIERSZ_BABIN = 2
WIERSZ_CHWALKOWO = 9


def _kopia_testy(tmp_path) -> Path:
    cel = tmp_path / "testy.xlsx"
    shutil.copy(TESTY_FILE, cel)
    return cel


def test_wpisuje_energie_oddana_2_strefowa(tmp_path):
    excel = _kopia_testy(tmp_path)

    wyniki = wpisz_fakture_oddana_do_arkusza(excel, FAKTURA_BABIN_STYCZEN, nadpisuj=True)

    assert len(wyniki) == 1
    assert wyniki[0].kategoria == KAT_SUKCES
    assert wyniki[0].wiersz == WIERSZ_BABIN
    assert wyniki[0].nazwa_obiektu == "Babin"

    wb = openpyxl.load_workbook(excel, data_only=False)
    ws = wb["fotowoltaika energia oddana"]
    assert ws["J2"].value == 0  # P-S1 styczeń
    assert ws["K2"].value == 1  # P-S2 styczeń
    assert ws["L2"].value is None  # P-S3 - taryfa 2-strefowa, nie literalne zero
    assert ws["M2"].value is None  # Energia wyprodukowana - pole ręczne, nie dotykane


def test_nie_nadpisuje_wypelnionych_komorek_bez_zgody(tmp_path):
    excel = _kopia_testy(tmp_path)
    # wypełniamy najpierw sami (nadpisuj=True), żeby drugie wpisanie (nadpisuj=False) miało na
    # czym sprawdzić "już wypełnione" - nie polegamy na tym, czy fixture akurat ma tu dane.
    wpisz_fakture_oddana_do_arkusza(excel, FAKTURA_BABIN_STYCZEN, nadpisuj=True)
    wyniki = wpisz_fakture_oddana_do_arkusza(excel, FAKTURA_BABIN_STYCZEN, nadpisuj=False)

    assert len(wyniki) == 1
    assert wyniki[0].kategoria == KAT_JUZ_WYPELNIONE
    assert not wyniki[0].zapisano


def test_wpisuje_energie_oddana_3_strefowa_wliczajac_straty(tmp_path):
    excel = _kopia_testy(tmp_path)

    wyniki = wpisz_fakture_oddana_do_arkusza(excel, FAKTURA_CHWALKOWO_LIPIEC, nadpisuj=True)

    assert len(wyniki) == 1
    assert wyniki[0].kategoria == KAT_SUKCES
    assert wyniki[0].wiersz == WIERSZ_CHWALKOWO

    wb = openpyxl.load_workbook(excel, data_only=False)
    ws = wb["fotowoltaika energia oddana"]
    assert ws["AH9"].value == 0  # P-S1 lipiec
    assert ws["AI9"].value == 0  # P-S2 lipiec
    assert ws["AJ9"].value == 5  # P-S3 lipiec (0.35 -> zaokrąglone w tekście faktury do 5 kWh)


def _pozycja(ppe="PPE", miesiac=2, p_s1=100.0) -> PozycjaEnergiaOddana:
    return PozycjaEnergiaOddana(
        ppe=ppe, okres_od=date(2026, miesiac, 1), okres_do=date(2026, miesiac, 19),
        p_s1=p_s1, p_s2=0.0, p_s3=0.0, trzy_strefy=False,
    )


def test_polacz_pozycje_wielookresowe_oddana_sumuje_energie():
    plik1, plik2 = Path("a.pdf"), Path("b.pdf")
    p1 = _pozycja(p_s1=10.0)
    p2 = _pozycja(p_s1=5.0)

    grupy = polacz_pozycje_wielookresowe_oddana([(plik1, p1), (plik2, p2)])

    assert len(grupy) == 1
    pliki, polaczona = grupy[0]
    assert set(pliki) == {plik1, plik2}
    assert polaczona.p_s1 == 15.0
    assert polaczona.okres_od == date(2026, 2, 1)
    assert polaczona.okres_do == date(2026, 2, 19)


def test_polacz_pozycje_wielookresowe_oddana_rozne_ppe_zostaja_osobno():
    plik1, plik2 = Path("a.pdf"), Path("b.pdf")
    grupy = polacz_pozycje_wielookresowe_oddana([(plik1, _pozycja(ppe="X")), (plik2, _pozycja(ppe="Y"))])

    assert len(grupy) == 2


def test_wpisz_polaczone_pozycje_oddana_pomija_pliki_bez_pv(tmp_path):
    # Faktura Małych odbiorów (bez PV) obok faktury Babin - nie powinna wywalić całego przebiegu
    # ani dodać żadnego wpisu dla siebie.
    excel = _kopia_testy(tmp_path)
    faktura_bez_pv = next(p for p in FAKTURY_ROOT.rglob("D 01.pdf") if "Pa" in p.parent.name)

    wynik_per_plik = wpisz_polaczone_pozycje_oddana(excel, [FAKTURA_BABIN_STYCZEN, faktura_bez_pv], nadpisuj=True)

    assert wynik_per_plik[FAKTURA_BABIN_STYCZEN][0].kategoria == KAT_SUKCES
    assert wynik_per_plik.get(faktura_bez_pv, []) == []
