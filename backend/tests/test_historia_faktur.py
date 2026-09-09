from datetime import date

from app.faktura_reader import KAT_PPE_NIEZNALEZIONE, KAT_SUKCES
from app.historia_faktur import HistoriaFakturStore
from app.import_faktur import WynikWpisu


def _sukces(nazwa="Obiekt X") -> WynikWpisu:
    return WynikWpisu(
        kategoria=KAT_SUKCES,
        ppe="590310600000423740",
        wiersz=3,
        nazwa_obiektu=nazwa,
        miesiac=1,
        okres_od=date(2026, 1, 1),
        okres_do=date(2026, 1, 20),
    )


def _problem() -> WynikWpisu:
    return WynikWpisu(
        kategoria=KAT_PPE_NIEZNALEZIONE,
        ppe="590310600000000000",
        wiersz=None,
        nazwa_obiektu=None,
        miesiac=1,
        okres_od=date(2026, 1, 1),
        okres_do=date(2026, 1, 20),
        opis="brak obiektu z tym numerem PPE w arkuszu",
    )


def test_zapisany_wpis_da_sie_odczytac(tmp_path):
    with HistoriaFakturStore(tmp_path / "historia.db") as store:
        store.zapisz("D 01.pdf", [_sukces(), _problem()])
        wpisy = store.ostatnie()

    assert len(wpisy) == 1
    wpis = wpisy[0]
    assert wpis.nazwa_pliku == "D 01.pdf"
    assert wpis.nierozpoznana is False
    assert wpis.powod_odrzucenia is None
    assert len(wpis.pozycje) == 2
    assert wpis.pozycje[0].kategoria == KAT_SUKCES
    assert wpis.pozycje[0].okres_od == date(2026, 1, 1)
    assert wpis.pozycje[1].kategoria == KAT_PPE_NIEZNALEZIONE


def test_odrzucona_faktura_ma_powod_i_nierozpoznana_true(tmp_path):
    with HistoriaFakturStore(tmp_path / "historia.db") as store:
        store.zapisz("D 09.pdf", [], powod_odrzucenia="Nie rozpoznano jako faktura dystrybucyjna")
        wpis = store.ostatnie()[0]

    assert wpis.nierozpoznana is True
    assert wpis.powod_odrzucenia == "Nie rozpoznano jako faktura dystrybucyjna"
    assert wpis.pozycje == []


def test_ostatnie_zwraca_od_najnowszego_i_respektuje_limit(tmp_path):
    with HistoriaFakturStore(tmp_path / "historia.db") as store:
        for i in range(5):
            store.zapisz(f"D {i}.pdf", [_sukces()])
        wpisy = store.ostatnie(limit=3)

    assert [w.nazwa_pliku for w in wpisy] == ["D 4.pdf", "D 3.pdf", "D 2.pdf"]


def test_usun_usuwa_konkretny_wpis(tmp_path):
    with HistoriaFakturStore(tmp_path / "historia.db") as store:
        store.zapisz("D 01.pdf", [_sukces()])
        store.zapisz("D 02.pdf", [_sukces()])
        id_do_usuniecia = store.ostatnie()[0].id

        store.usun(id_do_usuniecia)

        pozostale = store.ostatnie()
        assert len(pozostale) == 1
        assert pozostale[0].nazwa_pliku == "D 01.pdf"


def test_historia_przetrwa_ponowne_otwarcie_magazynu(tmp_path):
    sciezka = tmp_path / "historia.db"
    with HistoriaFakturStore(sciezka) as store:
        store.zapisz("D 01.pdf", [_sukces()])

    with HistoriaFakturStore(sciezka) as store:
        assert len(store.ostatnie()) == 1
