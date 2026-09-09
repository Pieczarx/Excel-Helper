import pytest

from datetime import date
from pathlib import Path

from app.faktura_reader import (
    KAT_BRAK_PPE_NA_FAKTURZE,
    KAT_DANE_NIEROZPOZNANE,
    NieRozpoznanoFaktury,
    _parsuj_liczbe,
    _sprawdz_liczbe_pozycji,
    wczytaj_fakture_dystrybucyjna,
)

FAKTURY_ROOT = Path(__file__).resolve().parents[2] / "examples" / "Faktury MPECWIK 2026"
FAKTURA_20_PAZDZIERNIKA = next(
    p for p in FAKTURY_ROOT.rglob("D 01.pdf") if "Pa" in p.parent.name
)
FAKTURA_JEDNOSTREFOWA = next(
    p for p in FAKTURY_ROOT.rglob("D 02.pdf") if p.parent.name.startswith("Azaliowa")
)
# Okres 21/01-27/02 - taryfa zmieniła się 31/01, "Opłata zmienna sieciowa" ma DWIE pary
# szczytowa/pozaszczytowa (częściowe ilości), trzeba je zsumować, nie wziąć tylko pierwszą.
FAKTURA_ZE_ZMIANA_TARYFY = next(
    p for p in FAKTURY_ROOT.rglob("D 02.pdf") if "Pa" in p.parent.name
)
# Punkt z instalacją PV/net-meteringiem - tabela ODCZYTY pokazuje surowy pobór z sieci, ale
# rozliczana (i jedyna poprawna) ilość jest w "Opłata zmienna sieciowa".
FAKTURA_Z_PV = next(
    p for p in FAKTURY_ROOT.rglob("D 05.pdf") if p.parent.name.startswith("Koszuty PV (Hydrofornia)")
)
# Plik nazwany "D 02.pdf", ale w rzeczywistości to faktura typu E (Energa, "Rozliczenie
# sprzedaży energii elektrycznej") - dobry przykład realnej niespójności nazwy pliku z
# faktyczną zawartością, którą parser dystrybucyjny musi po prostu odrzucić jako zero sekcji.
FAKTURA_NIEWLASCIWEGO_TYPU = next(
    p for p in FAKTURY_ROOT.rglob("D 02.pdf") if p.parent.name.startswith("Mączniki Sklep 4A")
)


def test_parsuje_wszystkie_pozycje_faktury():
    wynik = wczytaj_fakture_dystrybucyjna(FAKTURA_20_PAZDZIERNIKA)
    assert len(wynik.pozycje) == 5
    assert not wynik.pominiete


def test_pierwsza_pozycja_zgadza_sie_z_trescia_faktury():
    wynik = wczytaj_fakture_dystrybucyjna(FAKTURA_20_PAZDZIERNIKA)
    pozycja = next(p for p in wynik.pozycje if p.ppe == "590310600000423740")
    assert pozycja.okres_od == date(2026, 1, 1)
    assert pozycja.okres_do == date(2026, 1, 20)
    assert pozycja.zuzycie_szczytowa == 182.0
    assert pozycja.zuzycie_pozaszczytowa == 442.0
    assert pozycja.zuzycie_razem == 624.0
    assert pozycja.oplata_dystrybucja == 244.41


def test_sumuje_obie_polowy_okresu_gdy_taryfa_zmienila_sie_w_srodku():
    wynik = wczytaj_fakture_dystrybucyjna(FAKTURA_ZE_ZMIANA_TARYFY)
    pozycja = next(p for p in wynik.pozycje if p.ppe == "590310600000423740")
    assert pozycja.zuzycie_szczytowa == 349.0
    assert pozycja.zuzycie_pozaszczytowa == 837.0
    assert pozycja.zuzycie_razem == 1186.0


def test_punkt_z_pv_czyta_rozliczona_ilosc_nie_surowy_pobor_z_odczytow():
    wynik = wczytaj_fakture_dystrybucyjna(FAKTURA_Z_PV)
    pozycja = next(p for p in wynik.pozycje if p.ppe == "590310600000433732")
    # ODCZYTY (surowy pobór z sieci) dałby 152/994 - to jest wartość ROZLICZONA (netto po PV)
    assert pozycja.zuzycie_szczytowa == 127.0
    assert pozycja.zuzycie_pozaszczytowa == 929.0
    assert pozycja.zuzycie_razem == 1056.0


def test_licznik_jednostrefowy_calodobowy_trafia_do_pozycji_z_flaga():
    wynik = wczytaj_fakture_dystrybucyjna(FAKTURA_JEDNOSTREFOWA)
    assert not wynik.pominiete
    pozycja = next(p for p in wynik.pozycje if p.ppe == "590310600032021280")
    assert pozycja.jednostrefowa is True
    # cala ilosc ladauje w szczytowej (P-S1), pozaszczytowa (P-S2) zostaje zerem/puste
    assert pozycja.zuzycie_szczytowa == 9.0
    assert pozycja.zuzycie_pozaszczytowa == 0.0
    assert pozycja.zuzycie_razem == 9.0


def test_dwustrefowa_faktura_nie_ma_flagi_jednostrefowa():
    wynik = wczytaj_fakture_dystrybucyjna(FAKTURA_20_PAZDZIERNIKA)
    assert all(not p.jednostrefowa for p in wynik.pozycje)


def test_sprawdz_liczbe_pozycji_zwraca_none_gdy_sie_zgadza():
    tekst = "Rozliczenie dla miejsc poboru energii\n1. A\n2. B\nRazem za usługi dystrybucji"
    assert _sprawdz_liczbe_pozycji(tekst, liczba_znalezionych_sekcji=2) is None


def test_sprawdz_liczbe_pozycji_wykrywa_brakujaca_sekcje():
    tekst = "Rozliczenie dla miejsc poboru energii\n1. A\n2. B\n3. C\nRazem za usługi dystrybucji"
    wynik = _sprawdz_liczbe_pozycji(tekst, liczba_znalezionych_sekcji=2)
    assert wynik is not None
    assert wynik.kategoria == KAT_BRAK_PPE_NA_FAKTURZE
    assert "3" in wynik.opis and "2" in wynik.opis


def test_sprawdz_liczbe_pozycji_brak_bloku_nie_jest_bledem():
    assert _sprawdz_liczbe_pozycji("zupełnie inny dokument", liczba_znalezionych_sekcji=0) is None


def test_plik_bez_zadnej_sekcji_dystrybucyjnej_rzuca_blad():
    with pytest.raises(NieRozpoznanoFaktury):
        wczytaj_fakture_dystrybucyjna(FAKTURA_NIEWLASCIWEGO_TYPU)


def test_suma_p_s1_p_s2_zgadza_sie_z_zuzyciem_na_wszystkich_realnych_fakturach():
    """Regresja: sprawdza WSZYSTKIE 486 przykładowych faktur D naraz, nie tylko pojedyncze
    przypadki - właśnie tak wyszły na jaw błędy sumowania (zmiana taryfy w środku okresu, PV)."""
    niezgodnosci = []
    for plik in sorted(FAKTURY_ROOT.rglob("D *.pdf")):
        try:
            wynik = wczytaj_fakture_dystrybucyjna(plik)
        except NieRozpoznanoFaktury:
            continue
        for pozycja in wynik.pozycje:
            suma = pozycja.zuzycie_szczytowa + pozycja.zuzycie_pozaszczytowa
            if abs(suma - pozycja.zuzycie_razem) > 0.5:
                niezgodnosci.append((plik.name, pozycja.ppe, suma, pozycja.zuzycie_razem))
    assert not niezgodnosci


def test_parsuj_liczbe_format_polski():
    assert _parsuj_liczbe("182,000") == 182.0
    assert _parsuj_liczbe("244,41") == 244.41
    assert _parsuj_liczbe("1.066,80") == 1066.80
