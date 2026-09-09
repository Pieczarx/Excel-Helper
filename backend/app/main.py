"""Punkt wejścia: aplikacja z ikoną w zasobniku i głównym oknem."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.config import wczytaj_konfiguracje_supabase
from app.firmy import FIRMY
from app.historia_faktur_base import PustyMagazynHistorii
from app.kontroler import Kontroler
from app.kontroler_faktur import KontrolerFaktur
from app.store import AlertStore
from app.store_base import MagazynAlertow
from app.supabase_store import przywroc_sesje
from app.tray import TrayApp
from app.window import GlowneOkno

ICON_PATH = Path(__file__).resolve().parents[1] / "assets" / "icon.ico"


def _filtruj_komunikaty_qt(typ, kontekst, wiadomosc) -> None:
    """Tłumi konkretnie 'Could not parse stylesheet' - potwierdzone (rozległym testowaniem),
    że to nieszkodliwy szum silnika stylów Qt/PySide6 przy wielu dynamicznie stylowanych
    przyciskach, nie błąd w treści CSS ani coś wpływające na wygląd czy działanie appki.
    Wszystko inne przechodzi normalnie na stderr."""
    if "Could not parse stylesheet" in wiadomosc:
        return
    sys.stderr.write(wiadomosc + "\n")


def _poczatkowy_magazyn() -> MagazynAlertow:
    """Supabase, jeśli da się cicho odtworzyć zapamiętaną sesję - inaczej lokalny SQLite od razu,
    żeby appka nigdy nie blokowała startu na oknie logowania. Użytkownik loguje się później,
    kiedy sam zechce, przyciskiem "Zaloguj" w pasku narzędzi. Jeden magazyn dzielony między
    WSZYSTKIE firmy (app/firmy.py) - logowanie/synchronizacja nie jest per firma, patrz window.py."""
    konfiguracja = wczytaj_konfiguracje_supabase()
    if konfiguracja is None:
        return AlertStore()

    url, anon_key = konfiguracja
    magazyn = przywroc_sesje(url, anon_key)
    return magazyn if magazyn is not None else AlertStore()


def main() -> None:
    qInstallMessageHandler(_filtruj_komunikaty_qt)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # dalej dziala w tray po zamknieciu okna (X)
    app.setWindowIcon(QIcon(str(ICON_PATH)))  # fallback ikony dla okna glownego i wszystkich dialogow

    store = _poczatkowy_magazyn()
    try:
        # Jedna para (Kontroler, KontrolerFaktur) na firmę - własny plik Excela/folder faktur
        # (config_path), ale ten sam `store` (magazyn alertów) - patrz app/firmy.py po uzasadnienie.
        pary = [
            (
                firma,
                Kontroler(store, config_path=firma.config_path),
                # GlowneOkno._synchronizuj_historie_faktur podmieni to na Supabase per-konto, jeśli
                # _poczatkowy_magazyn() cicho przywrócił zalogowaną sesję.
                KontrolerFaktur(PustyMagazynHistorii(), config_path=firma.faktury_config_path),
            )
            for firma in FIRMY
        ]
        okno = GlowneOkno(pary)
        # Tray śledzi na razie tylko pierwszą (domyślną) firmę - rozszerzenie o wszystkie
        # to osobna decyzja, poza zakresem dzisiejszego przygotowania gruntu pod drugą firmę.
        tray = TrayApp(pary[0][1], okno)

        watek_tray = threading.Thread(target=tray.run, daemon=True)
        watek_tray.start()

        # Autostart leci przez pythonw.exe bez konsoli - ma byc cichy, prosto do tray.
        # Recznie odpalone z terminala (python -m app.main) ma pokazac okno od razu,
        # zeby user mial natychmiastowe potwierdzenie ze cos sie stalo, a nie musial
        # szukac nowej ikonki w (czesto ukrytym) zasobniku systemowym.
        uruchomiono_z_terminala = sys.stdout is not None and sys.stdout.isatty()
        zaden_plik_nie_wybrany = all(kontroler.sciezka is None for _, kontroler, _ in pary)
        if zaden_plik_nie_wybrany or uruchomiono_z_terminala:
            okno.show()

        kod_wyjscia = app.exec()
        for _, kontroler, kontroler_faktur in pary:
            kontroler.zamknij()
            kontroler_faktur.close()
    finally:
        store.close()

    sys.exit(kod_wyjscia)


if __name__ == "__main__":
    main()
