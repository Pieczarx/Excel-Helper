from pathlib import Path

from app.faktura_reader import wczytaj_fakture_energia_oddana

FAKTURY_ROOT = Path(__file__).resolve().parents[2] / "examples" / "Faktury MPECWIK 2026"
FAKTURA_BABIN = next(p for p in FAKTURY_ROOT.rglob("D 01 31.pdf") if p.parent.name.startswith("Babin"))
FAKTURA_CHWALKOWO_LIPIEC = next(p for p in FAKTURY_ROOT.rglob("D 07 31.pdf") if p.parent.name.startswith("Chwałkowo"))
FAKTURA_20_PAZDZIERNIKA = next(p for p in FAKTURY_ROOT.rglob("D 01.pdf") if "Pa" in p.parent.name)


def test_parsuje_energie_oddana_2_strefowa():
    # Babin (taryfa C12A, 2-strefowa) - styczeń: szczytowa=0, pozaszczytowa=1 (potwierdzone
    # bezpośrednio z surowego tekstu faktury), zgodne z arkuszem 'fotowoltaika energia oddana'.
    wynik = wczytaj_fakture_energia_oddana(FAKTURA_BABIN)

    assert not wynik.pominiete
    assert len(wynik.pozycje) == 1
    pozycja = wynik.pozycje[0]
    assert pozycja.ppe == "590310600000411976"
    assert pozycja.trzy_strefy is False
    assert pozycja.p_s1 == 0.0
    assert pozycja.p_s2 == 1.0
    assert pozycja.p_s3 == 0.0


def test_parsuje_energie_oddana_3_strefowa_wliczajac_straty():
    # Chwałkowo (taryfa B23, 3-strefowa) - lipiec: 0/0/5 na liczniku "energii czynnej oddanej",
    # plus liczniki strat "oddanej" I2h/U2h (oba 0 na tej fakturze - nie zmieniają sumy, ale
    # potwierdzają że kod je czyta bez wywalenia się).
    wynik = wczytaj_fakture_energia_oddana(FAKTURA_CHWALKOWO_LIPIEC)

    assert not wynik.pominiete
    assert len(wynik.pozycje) == 1
    pozycja = wynik.pozycje[0]
    assert pozycja.ppe == "590310600000414373"
    assert pozycja.trzy_strefy is True
    assert pozycja.p_s1 == 0.0
    assert pozycja.p_s2 == 0.0
    assert pozycja.p_s3 == 5.0


def test_obiekt_bez_pv_jest_po_cichu_pomijany():
    # Faktura Małych odbiorów (bez tabeli ODCZYTY, więc na pewno bez sekcji "energii czynnej
    # oddanej") - żadna z jej sekcji nie powinna trafić do pozycje ani do pominiete.
    wynik = wczytaj_fakture_energia_oddana(FAKTURA_20_PAZDZIERNIKA)

    assert wynik.pozycje == []
    assert wynik.pominiete == []
