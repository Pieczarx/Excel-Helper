"""Punkt wejścia: aplikacja z ikoną w zasobniku i głównym oknem."""
from __future__ import annotations

import subprocess
import sys
import threading

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication

from app import autostart
from app.aktualizator import posprzataj_poprzednia_wersje
from app.autostart import FLAGA_AUTOSTART
from app.config import wczytaj_konfiguracje_supabase
from app.firmy import FIRMY
from app.historia_faktur_base import PustyMagazynHistorii
from app.kontroler import Kontroler
from app.kontroler_faktur import KontrolerFaktur
from app.pojedyncza_instancja import czy_juz_dziala_i_aktywowano, uruchom_serwer
from app.sciezki import czy_zamrozona, katalog_zasobow
from app.store import AlertStore
from app.store_base import MagazynAlertow
from app.styl import EkranStartowy
from app.supabase_store import przywroc_sesje
from app.tray import TrayApp
from app.window import GlowneOkno

ICON_PATH = katalog_zasobow() / "icon.ico"


def _filtruj_komunikaty_qt(typ, kontekst, wiadomosc) -> None:
    """Tłumi konkretnie 'Could not parse stylesheet' - potwierdzone (rozległym testowaniem),
    że to nieszkodliwy szum silnika stylów Qt/PySide6 przy wielu dynamicznie stylowanych
    przyciskach, nie błąd w treści CSS ani coś wpływające na wygląd czy działanie appki.
    Wszystko inne przechodzi normalnie na stderr."""
    if "Could not parse stylesheet" in wiadomosc:
        return
    sys.stderr.write(wiadomosc + "\n")


def _zapewnij_autostart() -> None:
    """Rejestruje autostart automatycznie, bez pytania użytkownika - appka ma po prostu sama
    startować z systemem, nie wymagać od nikogo świadomej decyzji/checkboksa (patrz window.py -
    dawny checkbox w stopce świadomie usunięty). Cicho ignoruje błąd (np. brak uprawnień) - appka
    ma dalej normalnie działać, nawet jeśli akurat nie da się zarejestrować autostartu.

    Rejestruje ZAWSZE, nie tylko gdy zadania jeszcze nie ma (`schtasks /create /f` samo w sobie
    jest bezpieczne do powtórzenia - nadpisuje istniejące) - żeby stara instalacja (np. sprzed
    dodania FLAGA_AUTOSTART do polecenia) sama się naprawiła przy pierwszym uruchomieniu nowej
    wersji, zamiast zostać na zawsze z przestarzałym poleceniem startowym."""
    try:
        autostart.zainstaluj()
    except (subprocess.CalledProcessError, OSError):
        pass


def _czy_pokazac_okno_od_razu(uruchomiono_przez_autostart: bool, zaden_plik_nie_wybrany: bool) -> bool:
    """Autostart (FLAGA_AUTOSTART w sys.argv) ma zostać cichy, prosto do tray - każde INNE
    uruchomienie (ręcznie z Eksploratora/terminala) ma pokazać okno od razu, żeby user miał
    natychmiastowe potwierdzenie, że coś się stało, a nie musiał szukać nowej ikonki w (często
    ukrytym) zasobniku systemowym. Świeża instalacja (jeszcze bez wybranego pliku) pokazuje okno
    zawsze, nawet z autostartu - inaczej nie miałby jak zacząć jej konfigurować."""
    return zaden_plik_nie_wybrany or not uruchomiono_przez_autostart


def _poczatkowy_magazyn() -> MagazynAlertow:
    """Supabase, jeśli da się cicho odtworzyć zapamiętaną sesję - inaczej lokalny SQLite od razu,
    żeby appka nigdy nie blokowała startu na oknie logowania. Użytkownik loguje się później,
    kiedy sam zechce, przyciskiem "Zaloguj" w pasku narzędzi. Jeden magazyn dzielony między
    WSZYSTKIE firmy (app/firmy.py) - logowanie/synchronizacja nie jest per firma, patrz window.py."""
    url, anon_key = wczytaj_konfiguracje_supabase()
    magazyn = przywroc_sesje(url, anon_key)
    return magazyn if magazyn is not None else AlertStore()


def main() -> None:
    qInstallMessageHandler(_filtruj_komunikaty_qt)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # dalej dziala w tray po zamknieciu okna (X)
    app.setWindowIcon(QIcon(str(ICON_PATH)))  # fallback ikony dla okna glownego i wszystkich dialogow

    # Appka dalej dziala w tray po zamknieciu okna (linijka wyzej) - bez tej blokady kazda kolejna
    # proba uruchomienia (np. podwojny klik w .exe) odpalalaby NOWY, niezalezny proces zamiast
    # pokazac juz dzialajace okno. Druga+ instancja konczy sie od razu, bez budowania reszty appki.
    #
    # Sprawdzenie i zalozenie WLASNEGO serwera musza isc zaraz jedno po drugim, na samym poczatku
    # main() - kiedy stal to na koncu (po _zapewnij_autostart/_poczatkowy_magazyn/zbudowaniu
    # calego okna, czyli nawet kilka sekund), dwie proby uruchomienia blisko siebie w czasie
    # (np. sfrustrowany podwojny klik, gdy pierwsza jeszcze nie zdazyla ruszyc) obie zdazaly
    # sprawdzic "nikt nie nasluchuje" ZANIM ktorakolwiek zdazyla zaczac nasluchiwac - obie stawaly
    # sie pelnoprawnymi, niezaleznymi instancjami (stad zgloszone mnozace sie procesy).
    if czy_juz_dziala_i_aktywowano():
        return

    # Autostart odpala appke z ta flaga (patrz autostart.py) - ma zostac CICHO w tray, tak jak
    # dzialalo to dotychczas. Recznemu uruchomieniu (podwojny klik w .exe) tej flagi brakuje, wiec
    # dostaje ekran startowy i normalnie pokazane okno - dawniej odrozniane tylko tym, czy stdout
    # jest terminalem, co dawalo identyczny (falszywy) wynik dla obu przypadkow i przy juz
    # skonfigurowanym pliku appka odpalona recznie nie pokazywala sie wcale (zgloszony blad).
    uruchomiono_przez_autostart = FLAGA_AUTOSTART in sys.argv

    splash = None
    if not uruchomiono_przez_autostart:
        splash = EkranStartowy(QPixmap(str(ICON_PATH)))
        splash.show()
        splash.ustaw_postep(10, "Uruchamianie…")

    stan_okna: dict[str, object] = {"okno": None, "pokaz_oczekuje": False}

    def _pokaz_okno(okno: GlowneOkno) -> None:
        okno.show()
        okno.raise_()
        okno.activateWindow()

    def _na_sygnal_pokaz() -> None:
        okno = stan_okna["okno"]
        if okno is not None:
            _pokaz_okno(okno)
        else:
            # Sygnal przyszedl, zanim zdazylismy zbudowac wlasne okno (bardzo waski margines,
            # patrz komentarz wyzej) - zapamietujemy, zeby i tak je pokazac zaraz po zbudowaniu.
            stan_okna["pokaz_oczekuje"] = True

    # Referencja musi przezyc cala funkcje (patrz pojedyncza_instancja.py) - stad zmienna, nie
    # tylko wywolanie bez przypisania.
    serwer_instancji = uruchom_serwer(_na_sygnal_pokaz)

    if czy_zamrozona():
        posprzataj_poprzednia_wersje()  # sprzata plik .poprzedni po ewentualnej aktualizacji
    if splash:
        splash.ustaw_postep(30, "Przygotowywanie…")
    _zapewnij_autostart()

    if splash:
        splash.ustaw_postep(55, "Łączenie z kontem…")
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
        if splash:
            splash.ustaw_postep(80, "Budowanie okna…")
        okno = GlowneOkno(pary)
        stan_okna["okno"] = okno
        if stan_okna["pokaz_oczekuje"]:
            _pokaz_okno(okno)

        # Tray śledzi na razie tylko pierwszą (domyślną) firmę - rozszerzenie o wszystkie
        # to osobna decyzja, poza zakresem dzisiejszego przygotowania gruntu pod drugą firmę.
        tray = TrayApp(pary[0][1], okno)

        watek_tray = threading.Thread(target=tray.run, daemon=True)
        watek_tray.start()

        if splash:
            splash.ustaw_postep(100, "Gotowe")
            splash.close()

        zaden_plik_nie_wybrany = all(kontroler.sciezka is None for _, kontroler, _ in pary)
        if _czy_pokazac_okno_od_razu(uruchomiono_przez_autostart, zaden_plik_nie_wybrany):
            okno.show()

        kod_wyjscia = app.exec()
        for _, kontroler, kontroler_faktur in pary:
            kontroler.zamknij()
            kontroler_faktur.close()
    finally:
        store.close()
        if splash is not None:
            splash.close()  # bezpieczne nawet gdy juz zamkniety (np. wczesniej, po zbudowaniu okna)

    sys.exit(kod_wyjscia)


if __name__ == "__main__":
    main()
