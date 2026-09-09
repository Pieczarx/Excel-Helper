import time
from pathlib import Path

from PySide6.QtWidgets import QApplication, QPushButton

from app.kontroler import Kontroler
from app.store import AlertStore
from app.widok_weryfikacji import WidokWeryfikacji

EXAMPLE_FILE = Path(__file__).resolve().parents[2] / "examples" / "MPECWIK 2026.xlsx"


def _app():
    app = QApplication.instance()
    return app or QApplication([])


def _liczba_kart(widok: WidokWeryfikacji) -> int:
    # Karty niepasujace do filtra/wyszukiwania nie sa juz niszczone, tylko ukrywane -
    # liczymy widoczne (isHidden() dziala niezaleznie od tego, czy caly widok jest pokazany).
    return sum(1 for karta in widok._karty if not karta.isHidden())


def _poczekaj_az(warunek, timeout: float = 5.0) -> bool:
    """Pompuje petle zdarzen Qt czekajac az warunek bedzie prawdziwy - potrzebne bo
    oznacz_jako_prawidlowy_w_tle/odswiez_w_tle dzialaja teraz w osobnym watku."""
    koniec = time.time() + timeout
    while time.time() < koniec:
        QApplication.processEvents()
        if warunek():
            return True
        time.sleep(0.02)
    return False


def test_widok_pokazuje_karte_na_kazdy_alert(tmp_path):
    _app()
    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "supabase.json")
        widok = WidokWeryfikacji(kontroler)
        widok.show()  # isVisible() na dziecku odzwierciedla widocznosc dopiero gdy widok tez jest pokazany
        kontroler.ustaw_plik(EXAMPLE_FILE)

        liczba_alertow = sum(len(g.alerty) for g in kontroler.ostatnie_grupy)
        assert _liczba_kart(widok) == liczba_alertow
        assert widok._badge.isVisible()
        kontroler.zamknij()


def test_filtr_ciaglosc_pokazuje_tylko_jedna_karte(tmp_path):
    _app()
    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "supabase.json")
        widok = WidokWeryfikacji(kontroler)
        kontroler.ustaw_plik(EXAMPLE_FILE)

        widok._ustaw_filtr("LUKA_CIAGLOSCI")

        liczba_luk = sum(1 for g in kontroler.ostatnie_grupy for a in g.alerty if a.rodzaj == "LUKA_CIAGLOSCI")
        assert _liczba_kart(widok) == liczba_luk == 1


def test_zmiana_filtra_nie_tworzy_nowych_widgetow(tmp_path):
    _app()
    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "supabase.json")
        widok = WidokWeryfikacji(kontroler)
        kontroler.ustaw_plik(EXAMPLE_FILE)

        karty_przed = list(widok._karty)
        widok._ustaw_filtr("ODCHYLENIE")
        widok._ustaw_filtr("LUKA_CIAGLOSCI")
        widok._ustaw_filtr("WSZYSTKIE")

        assert widok._karty == karty_przed  # te same obiekty (identycznosc), nic nie zostalo przebudowane


def test_oznacz_jako_prawidlowe_usuwa_karte(tmp_path):
    _app()
    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "supabase.json")
        widok = WidokWeryfikacji(kontroler)
        kontroler.ustaw_plik(EXAMPLE_FILE)

        liczba_przed = _liczba_kart(widok)
        pierwsza_karta = widok._karty[0]
        przycisk = pierwsza_karta.findChild(QPushButton)  # jedyny przycisk na karcie: "Oznacz jako prawidlowe"
        przycisk.click()

        assert _poczekaj_az(lambda: _liczba_kart(widok) == liczba_przed - 1)


def test_w_trakcie_wylacza_przycisk_sprawdz(tmp_path):
    _app()
    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "supabase.json")
        widok = WidokWeryfikacji(kontroler)
        kontroler.ustaw_plik(EXAMPLE_FILE)

        stany: list[bool] = []
        kontroler.w_trakcie.connect(stany.append)

        widok._przycisk_sprawdz.click()

        assert _poczekaj_az(lambda: stany == [True, False])
        assert widok._przycisk_sprawdz.isEnabled()
        assert widok._przycisk_sprawdz.text() == "Sprawdź teraz"


def test_wyszukiwanie_jest_debounced(tmp_path):
    _app()
    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "supabase.json")
        widok = WidokWeryfikacji(kontroler)
        kontroler.ustaw_plik(EXAMPLE_FILE)
        liczba_przed = _liczba_kart(widok)

        widok._pole_szukaj.setText("xyz-nieistniejacy-obiekt")
        # zaraz po wpisaniu lista NIE powinna sie jeszcze przebudowac (debounce)
        assert _liczba_kart(widok) == liczba_przed

        assert _poczekaj_az(lambda: _liczba_kart(widok) == 0)
