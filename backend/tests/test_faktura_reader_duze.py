from pathlib import Path

from app.faktura_reader import wczytaj_fakture_duzy_odbior

FAKTURY_ROOT = Path(__file__).resolve().parents[2] / "examples" / "Faktury MPECWIK 2026"
FAKTURA_BRODOWO = next(p for p in FAKTURY_ROOT.rglob("D 03 31.pdf") if p.parent.name.startswith("Brodowo"))
FAKTURA_CHWALKOWO = next(p for p in FAKTURY_ROOT.rglob("D 01.31.pdf") if p.parent.name.startswith("Chwałkowo"))


def test_parsuje_pozycje_duzego_odbioru():
    wynik = wczytaj_fakture_duzy_odbior(FAKTURA_BRODOWO)

    assert not wynik.pominiete
    assert len(wynik.pozycje) == 1
    pozycja = wynik.pozycje[0]
    assert pozycja.ppe == "590310600000411983"


def test_pozycja_zgadza_sie_z_trescia_faktury():
    wynik = wczytaj_fakture_duzy_odbior(FAKTURA_BRODOWO)
    pozycja = wynik.pozycje[0]

    assert pozycja.moc_pobrana == 39.0
    assert pozycja.p_s1 == 6807.0
    assert pozycja.p_s2 == 9011.0
    assert pozycja.q_plus_s1 == 3470.0
    assert pozycja.q_plus_s2 == 3216.0
    assert pozycja.q_minus_s1 == 50.0
    assert pozycja.q_minus_s2 == 211.0
    assert pozycja.q_plus_zl == 447.62
    assert pozycja.q_minus_zl == 406.23
    assert pozycja.oplata_dystrybucja == 5857.71
    # to jest błąd po stronie ENEA - 6807+9011=15818, nie 15793 (patrz KAT_ZUZYCIE_NIEZGODNE_Z_FAKTURA
    # w import_faktur_duze.py) - potwierdzone bezpośrednio z surowego tekstu faktury.
    assert pozycja.zuzycie_razem_faktura == 15793.0
    assert pozycja.trzy_strefy is False
    assert pozycja.p_s3 == 0.0


def test_parsuje_taryfe_3_strefowa_z_jednostkami_mwh():
    # Chwałkowo (taryfa B23): strefy "szczyt przedpołudniowy/popołudniowy/pozostałe godziny doby"
    # zamiast "szczytowa/pozaszczytowa", jednostki MWh/Mvarh zamiast kWh/kvarh.
    wynik = wczytaj_fakture_duzy_odbior(FAKTURA_CHWALKOWO)

    assert not wynik.pominiete
    assert len(wynik.pozycje) == 1
    pozycja = wynik.pozycje[0]
    assert pozycja.ppe == "590310600000414373"
    assert pozycja.trzy_strefy is True


def test_pozycja_3_strefowa_zgadza_sie_z_trescia_faktury_wliczajac_straty():
    wynik = wczytaj_fakture_duzy_odbior(FAKTURA_CHWALKOWO)
    pozycja = wynik.pozycje[0]

    assert pozycja.moc_pobrana == 414.0
    # 24383 (odczyt) + 4 (1. licznik strat, I2h) = 24387 - z decyzji użytkownika.
    assert pozycja.p_s1 == 24387.0
    # 10850 (odczyt) + 3 (2. licznik strat, U2h) = 10853.
    assert pozycja.p_s2 == 10853.0
    # brak 3. licznika strat na tej fakturze - bez korekty.
    assert pozycja.p_s3 == 104245.0
    assert pozycja.q_plus_s1 == 8233.0
    assert pozycja.q_plus_s2 == 3164.0
    assert pozycja.q_plus_s3 == 38280.0
    assert pozycja.q_minus_s1 == 8.0
    assert pozycja.q_minus_s2 == 71.0
    assert pozycja.q_minus_s3 == 111.0
    assert pozycja.q_plus_zl == 0.0
    assert round(pozycja.q_minus_zl, 2) == 98.58
    assert pozycja.oplata_dystrybucja == 29539.22
    # "Ogółem zużycie: 139,485 MWh" -> 139485 kWh po konwersji jednostki.
    assert pozycja.zuzycie_razem_faktura == 139485.0
    # Z policzonymi stratami suma zgadza się dokładnie - żadnego ostrzeżenia o niezgodności.
    assert pozycja.p_s1 + pozycja.p_s2 + pozycja.p_s3 == pozycja.zuzycie_razem_faktura
