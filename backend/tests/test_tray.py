from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, Signal

from app.kontroler import Kontroler
from app.store import AlertStore
from app.tray import TrayApp

EXAMPLE_FILE = Path(__file__).resolve().parents[2] / "examples" / "MPECWIK 2026.xlsx"


class _FakeOkno(QObject):
    """Zastępuje GlowneOkno w testach - TrayApp potrzebuje tylko sygnału pokaz_zadanie."""

    pokaz_zadanie = Signal()


def _app():
    app = QCoreApplication.instance()
    return app or QCoreApplication([])


def test_tytul_zostaje_staly_niezaleznie_od_alertow(tmp_path):
    # Tooltip z liczbą obiektów z problemem - z decyzji użytkownika usunięty, tytuł jest stały.
    _app()
    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "supabase.json")
        tray = TrayApp(kontroler, _FakeOkno())

        kontroler.ustaw_plik(EXAMPLE_FILE)

        assert tray._icon.title == "Excel Helper"
        kontroler.zamknij()


def test_tytul_gdy_brak_alertow(tmp_path):
    _app()
    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "supabase.json")
        tray = TrayApp(kontroler, _FakeOkno())
        tray._na_zmiane([])
        assert tray._icon.title == "Excel Helper"
