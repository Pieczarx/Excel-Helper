"""Spina magazyn alertów, cykl weryfikacji i obserwator pliku pod jednym obiektem.

To jest QObject, żeby `zmiana`/`w_trakcie`/`blad` mogły być bezpiecznie nasłuchiwane przez okno Qt
mimo że watcher i odświeżanie w tle wywołują je z innych wątków - Qt automatycznie kolejkuje
wywołanie slotu do wątku GUI, kiedy odbiorca (np. GlowneOkno) mieszka w innym wątku niż nadawca.
"""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from supabase import Client

from app.alerts import GrupaAlertow, grupuj
from app.config import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_OSTATNI_LOGIN_PATH,
    DEFAULT_SUPABASE_CONFIG_PATH,
    DEFAULT_SUPABASE_SESSION_PATH,
    wczytaj_konfiguracje_supabase,
    wczytaj_ostatni_email,
    wczytaj_sciezke_pliku,
    zapisz_ostatni_email,
    zapisz_sciezke_pliku,
)
from app.excel_reader import Obiekt, parse_workbook
from app.haslo_store import SERWIS as HASLO_SERWIS
from app.haslo_store import usun_haslo, wczytaj_haslo, zapisz_haslo
from app.rok import wykryj_rok
from app.rules import uruchom_wszystkie_reguly
from app.store import DEFAULT_DB_PATH, AlertStore
from app.store_base import MagazynAlertow
from app.supabase_store import SupabaseAlertStore
from app.supabase_store import zaloguj as supabase_zaloguj
from app.watcher import ObserwatorPliku


class Kontroler(QObject):
    zmiana = Signal(list)  # list[GrupaAlertow]
    w_trakcie = Signal(bool)
    blad = Signal(str)

    def __init__(
        self,
        store: MagazynAlertow,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        supabase_config_path: str | Path = DEFAULT_SUPABASE_CONFIG_PATH,
        local_db_path: str | Path = DEFAULT_DB_PATH,
        ostatni_login_path: str | Path = DEFAULT_OSTATNI_LOGIN_PATH,
        haslo_serwis: str = HASLO_SERWIS,
        supabase_session_path: str | Path = DEFAULT_SUPABASE_SESSION_PATH,
    ):
        super().__init__()
        self._store = store
        self._config_path = config_path
        self._supabase_config_path = supabase_config_path
        self._local_db_path = local_db_path
        self._ostatni_login_path = ostatni_login_path
        self._haslo_serwis = haslo_serwis
        self._supabase_session_path = supabase_session_path
        self._sciezka: Path | None = None
        self._rok: int | None = None
        self._obserwator: ObserwatorPliku | None = None
        self.ostatnie_grupy: list[GrupaAlertow] = []
        self._obiekty_po_wierszu: dict[int, Obiekt] = {}

        zapamietana = wczytaj_sciezke_pliku(self._config_path)
        if zapamietana is not None and zapamietana.exists():
            self.ustaw_plik(zapamietana)

    @property
    def store(self) -> MagazynAlertow:
        """Aktualny magazyn alertów (lokalny SQLite albo Supabase) - do współdzielenia z INNYMI
        instancjami Kontroler (np. jedna appka/wiele firm, patrz app/firmy.py, window.py) tak, żeby
        logowanie w jednej firmie odpowiednio przełączyło też magazyn pozostałych, bez drugiego,
        zbędnego logowania sieciowego - wystarczy `inny_kontroler.ustaw_magazyn(ten.store)`."""
        return self._store

    @property
    def sciezka(self) -> Path | None:
        return self._sciezka

    @property
    def rok(self) -> int | None:
        return self._rok

    def czy_plik_otwarty(self) -> bool:
        """True, jeśli plik Excela jest teraz otwarty w Excelu (blokada '~$nazwa.xlsx' istnieje) -
        inne procesy (np. wpisywanie faktur) nie powinny wtedy pisać do tego pliku, bo późniejszy
        zapis z Excela nadpisałby te zmiany zapisaną wcześniej, nieaktualną zawartością z pamięci."""
        return self._obserwator is not None and self._obserwator.czy_plik_jest_teraz_otwarty()

    def stan_synchronizacji(self) -> str:
        """"NIESKONFIGUROWANY" (Supabase w ogóle nieustawiony), "NIEZALOGOWANY" albo "ZALOGOWANY"."""
        konfiguracja = wczytaj_konfiguracje_supabase(self._supabase_config_path)
        if konfiguracja is None:
            return "NIESKONFIGUROWANY"
        return "ZALOGOWANY" if isinstance(self._store, SupabaseAlertStore) else "NIEZALOGOWANY"

    def czy_potrzebuje_logowania(self) -> bool:
        """True, jeśli Supabase jest skonfigurowany, ale ten magazyn jeszcze nie jest nim zalogowany."""
        return self.stan_synchronizacji() == "NIEZALOGOWANY"

    def email_zalogowanego(self) -> str | None:
        return self._store.email if isinstance(self._store, SupabaseAlertStore) else None

    def klient_supabase(self) -> Client | None:
        """Klient Supabase aktywnej zalogowanej sesji, do współdzielenia z magazynami innych
        zakładek (np. historii faktur, per-konto) - None, jeśli nikt nie jest zalogowany."""
        return self._store.klient if isinstance(self._store, SupabaseAlertStore) else None

    def dane_do_logowania(self) -> tuple[str, str]:
        """(ostatni użyty e-mail, zapamiętane hasło) do wstępnego wypełnienia okna logowania."""
        email = wczytaj_ostatni_email(self._ostatni_login_path) or ""
        haslo = wczytaj_haslo(email, self._haslo_serwis) if email else None
        return email, haslo or ""

    def zaloguj_supabase(self, email: str, haslo: str, zapamietaj_haslo: bool = False) -> None:
        """Może rzucić BledneDaneLogowania albo RuntimeError (brak konfiguracji) - obsługuje UI."""
        konfiguracja = wczytaj_konfiguracje_supabase(self._supabase_config_path)
        if konfiguracja is None:
            raise RuntimeError("Synchronizacja Supabase nie jest skonfigurowana.")
        url, anon_key = konfiguracja
        nowy_store = supabase_zaloguj(url, anon_key, email, haslo, session_path=self._supabase_session_path)

        zapisz_ostatni_email(email, self._ostatni_login_path)
        if zapamietaj_haslo:
            zapisz_haslo(email, haslo, self._haslo_serwis)
        else:
            usun_haslo(email, self._haslo_serwis)

        self.ustaw_magazyn(nowy_store)

    def wyloguj(self) -> None:
        if isinstance(self._store, SupabaseAlertStore):
            self._store.wyloguj()
        self.ustaw_magazyn(AlertStore(self._local_db_path))

    def ustaw_magazyn(self, store: MagazynAlertow) -> None:
        self._store = store
        self.odswiez_w_tle()

    def ustaw_plik(self, sciezka: str | Path) -> None:
        """Może rzucić NieRozpoznanoRoku (app/rok.py) - to obsługuje wywołujący (UI pokazuje błąd)."""
        sciezka = Path(sciezka).resolve()
        rok = wykryj_rok(sciezka)

        if self._obserwator is not None:
            self._obserwator.stop()

        self._sciezka = sciezka
        self._rok = rok
        zapisz_sciezke_pliku(sciezka, self._config_path)

        self._obserwator = ObserwatorPliku(sciezka, callback=self._odswiez_bezpiecznie)
        self._obserwator.start()
        self.odswiez()

    def odswiez(self) -> None:
        if self._sciezka is None or self._rok is None:
            return
        obiekty = parse_workbook(self._sciezka, rok=self._rok)
        self._obiekty_po_wierszu = {o.wiersz: o for o in obiekty}

        alerty = uruchom_wszystkie_reguly(obiekty)
        aktywne = self._store.odfiltruj_aktywne(alerty)
        grupy = grupuj(aktywne)

        self.ostatnie_grupy = grupy
        self.zmiana.emit(grupy)

    def _odswiez_bezpiecznie(self) -> None:
        self.w_trakcie.emit(True)
        try:
            self.odswiez()
        except Exception as exc:
            self.blad.emit(str(exc))
        finally:
            self.w_trakcie.emit(False)

    def odswiez_w_tle(self) -> None:
        """Jak odswiez(), ale w osobnym wątku, żeby nie zamrażać UI na czas parsowania/sieci."""
        threading.Thread(target=self._odswiez_bezpiecznie, daemon=True).start()

    def oznacz_jako_prawidlowy(self, alert) -> None:
        self._store.oznacz_jako_prawidlowy(alert)
        self.odswiez()

    def _oznacz_bezpiecznie(self, alert) -> None:
        self.w_trakcie.emit(True)
        try:
            self._store.oznacz_jako_prawidlowy(alert)
            self.odswiez()
        except Exception as exc:
            self.blad.emit(str(exc))
        finally:
            self.w_trakcie.emit(False)

    def oznacz_jako_prawidlowy_w_tle(self, alert) -> None:
        threading.Thread(target=self._oznacz_bezpiecznie, args=(alert,), daemon=True).start()

    def identyfikacja_obiektu(self, wiersz: int) -> dict[str, str]:
        obiekt = self._obiekty_po_wierszu.get(wiersz)
        return obiekt.identyfikacja if obiekt else {}

    def zamknij(self) -> None:
        if self._obserwator is not None:
            self._obserwator.stop()
