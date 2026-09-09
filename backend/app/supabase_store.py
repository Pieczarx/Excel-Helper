"""Magazyn alertów oparty o Supabase (Postgres + Auth) - współdzielony między komputerami.

Ma ten sam interfejs co lokalny AlertStore (store.py, patrz store_base.MagazynAlertow), więc
Kontroler przełącza się między nimi bez żadnych zmian we własnym kodzie.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, TypeVar

from postgrest.exceptions import APIError
from supabase import Client, create_client

from app.alerts import Alert
from app.config import (
    DEFAULT_SUPABASE_SESSION_PATH,
    usun_sesje_supabase,
    wczytaj_sesje_supabase,
    zapisz_sesje_supabase,
)

TABELA = "oznaczone_prawidlowe"
KOD_WYGASLEGO_TOKENU = "PGRST303"

T = TypeVar("T")


class BledneDaneLogowania(Exception):
    pass


class SupabaseAlertStore:
    def __init__(
        self,
        klient: Client,
        session_path: str | Path = DEFAULT_SUPABASE_SESSION_PATH,
        email: str | None = None,
    ):
        self._klient = klient
        self._session_path = session_path
        self.email = email

    @property
    def klient(self) -> Client:
        """Klient Supabase już zalogowany - do współdzielenia z innymi magazynami tego samego
        usera (np. historią faktur, per-konto), żeby nie logować się drugi raz tymi samymi danymi."""
        return self._klient

    def wyloguj(self) -> None:
        try:
            self._klient.auth.sign_out()
        except Exception:
            pass  # nawet jesli serwer nie odpowie, i tak kasujemy lokalna sesje ponizej
        usun_sesje_supabase(self._session_path)

    def _z_odswiezeniem_tokenu(self, wywolanie: Callable[[], T]) -> T:
        """Jeśli token dostępu wygasł, odświeża go z refresh_token i próbuje raz jeszcze -
        user nie powinien być wylogowywany tylko dlatego, że appka posiedziała chwilę w tle."""
        try:
            return wywolanie()
        except APIError as exc:
            if exc.code != KOD_WYGASLEGO_TOKENU:
                raise
            odpowiedz = self._klient.auth.refresh_session()
            if odpowiedz.session is not None:
                zapisz_sesje_supabase(
                    odpowiedz.session.access_token, odpowiedz.session.refresh_token, self._session_path
                )
            return wywolanie()

    def oznacz_jako_prawidlowy(self, alert: Alert) -> None:
        self._z_odswiezeniem_tokenu(
            lambda: self._klient.table(TABELA)
            .upsert(
                {
                    "klucz": alert.klucz,
                    "rodzaj": alert.rodzaj,
                    "obiekt_wiersz": alert.obiekt_wiersz,
                    "obiekt_nazwa": alert.obiekt_nazwa,
                    "opis": alert.opis,
                }
            )
            .execute()
        )

    def cofnij_oznaczenie(self, klucz: str) -> None:
        self._z_odswiezeniem_tokenu(lambda: self._klient.table(TABELA).delete().eq("klucz", klucz).execute())

    def wszystkie_oznaczone_klucze(self) -> set[str]:
        wynik = self._z_odswiezeniem_tokenu(lambda: self._klient.table(TABELA).select("klucz").execute())
        return {wiersz["klucz"] for wiersz in wynik.data}

    def odfiltruj_aktywne(self, alerty: list[Alert]) -> list[Alert]:
        oznaczone = self.wszystkie_oznaczone_klucze()
        return [a for a in alerty if a.klucz not in oznaczone]

    def close(self) -> None:
        pass

    def __enter__(self) -> "SupabaseAlertStore":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


def zaloguj(
    url: str,
    anon_key: str,
    email: str,
    haslo: str,
    session_path: str | Path = DEFAULT_SUPABASE_SESSION_PATH,
) -> SupabaseAlertStore:
    """Loguje się e-mailem/hasłem i zapamiętuje sesję (żeby nie pytać o hasło przy każdym starcie)."""
    klient = create_client(url, anon_key)
    try:
        odpowiedz = klient.auth.sign_in_with_password({"email": email, "password": haslo})
    except Exception as exc:  # supabase/gotrue rzuca różne wyjątki zależnie od wersji - łapiemy szeroko
        raise BledneDaneLogowania(str(exc)) from exc

    sesja = odpowiedz.session
    if sesja is not None:
        zapisz_sesje_supabase(sesja.access_token, sesja.refresh_token, session_path)
    email_uzytkownika = odpowiedz.user.email if odpowiedz.user is not None else None
    return SupabaseAlertStore(klient, session_path, email=email_uzytkownika)


def przywroc_sesje(
    url: str, anon_key: str, session_path: str | Path = DEFAULT_SUPABASE_SESSION_PATH
) -> SupabaseAlertStore | None:
    """Próbuje odtworzyć poprzednie logowanie z zapamiętanej sesji. Zwraca None, jeśli nie da się.

    set_session() sam odświeża wygasły access_token przy pomocy refresh_tokenu - ale Supabase
    ROTUJE refresh_token przy każdym użyciu (stary staje się nieważny), więc świeżą parę trzeba
    od razu zapisać z powrotem na dysk. Bez tego pierwszy restart po wygaśnięciu access_tokenu
    jeszcze działa (odświeżenie zaszło tylko w pamięci), ale każdy KOLEJNY restart próbuje użyć
    już zużytego refresh_tokenu zapisanego na dysku i się wywala - użytkownik musi się logować
    ręcznie od nowa, mimo że w międzyczasie nigdy się nie wylogował."""
    dane = wczytaj_sesje_supabase(session_path)
    if dane is None:
        return None
    klient = create_client(url, anon_key)
    try:
        odpowiedz = klient.auth.set_session(dane["access_token"], dane["refresh_token"])
        if odpowiedz.session is None:
            return None
        zapisz_sesje_supabase(odpowiedz.session.access_token, odpowiedz.session.refresh_token, session_path)
    except Exception:
        return None
    email_uzytkownika = odpowiedz.user.email if odpowiedz.user is not None else None
    return SupabaseAlertStore(klient, session_path, email=email_uzytkownika)
