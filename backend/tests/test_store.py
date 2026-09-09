import threading
from datetime import date

from app.alerts import Alert
from app.store import AlertStore


def _alert(wartosc_biezaca: float) -> Alert:
    return Alert(
        rodzaj="ODCHYLENIE",
        obiekt_wiersz=3,
        obiekt_nazwa="Testowy obiekt",
        opis="opis testowy",
        okres_od=date(2026, 3, 1),
        okres_do=date(2026, 3, 31),
        pole="zuzycie_razem",
        wartosc_poprzednia=100.0,
        wartosc_biezaca=wartosc_biezaca,
    )


def test_oznaczenie_jako_prawidlowe_wycisza_alert(tmp_path):
    with AlertStore(tmp_path / "alerts.db") as store:
        alert = _alert(250.0)

        assert store.odfiltruj_aktywne([alert]) == [alert]

        store.oznacz_jako_prawidlowy(alert)
        assert store.odfiltruj_aktywne([alert]) == []


def test_oznaczenie_przetrwa_ponowne_otwarcie_magazynu(tmp_path):
    db_path = tmp_path / "alerts.db"
    alert = _alert(250.0)

    with AlertStore(db_path) as store:
        store.oznacz_jako_prawidlowy(alert)

    with AlertStore(db_path) as store2:
        assert store2.odfiltruj_aktywne([alert]) == []


def test_zmiana_wartosci_zrodlowej_daje_nowy_klucz_i_alert_wraca(tmp_path):
    with AlertStore(tmp_path / "alerts.db") as store:
        stary_alert = _alert(250.0)
        store.oznacz_jako_prawidlowy(stary_alert)

        # Uzytkownik poprawil fakture zrodlowa - ta sama pozycja (obiekt/okres/pole), inna wartosc.
        nowy_alert = _alert(400.0)
        assert nowy_alert.klucz != stary_alert.klucz
        assert store.odfiltruj_aktywne([nowy_alert]) == [nowy_alert]


def test_uzycie_z_watku_w_tle_dziala(tmp_path):
    """Kontroler.oznacz_jako_prawidlowy_w_tle/odswiez_w_tle wolaja ten magazyn z watku w tle -
    sqlite3 domyslnie rzuca ProgrammingError przy uzyciu polaczenia spoza watku, ktory je stworzyl."""
    with AlertStore(tmp_path / "alerts.db") as store:
        alert = _alert(250.0)
        blad: list[Exception] = []

        def w_tle():
            try:
                store.oznacz_jako_prawidlowy(alert)
            except Exception as exc:  # noqa: BLE001 - chcemy zlapac wlasnie to, zeby test go pokazal
                blad.append(exc)

        watek = threading.Thread(target=w_tle)
        watek.start()
        watek.join(timeout=5)

        assert not blad, f"oznacz_jako_prawidlowy z innego watku rzucil: {blad}"
        assert store.odfiltruj_aktywne([alert]) == []
