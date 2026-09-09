"""Magazyn historii wpisanych faktur oparty o Supabase - PER KONTO.

W przeciwieństwie do alertów (oznaczone_prawidlowe w supabase_store.py - współdzielone, każdy
zalogowany user widzi te same wiersze), tabela `historia_faktur` ma RLS ograniczające każdemu
userowi widoczność do własnych wierszy (auth.uid() = user_id, patrz supabase/historia_faktur.sql).
Klienta Supabase dostajemy gotowego (już zalogowanego) z Kontroler.klient_supabase() - login
odbywa się raz, po stronie alertów, żeby nie logować się dwa razy tymi samymi danymi."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable, TypeVar

from postgrest.exceptions import APIError
from supabase import Client

from app.config import DEFAULT_SUPABASE_SESSION_PATH, zapisz_sesje_supabase
from app.historia_faktur import WpisHistorii, pozycja_do_json, pozycja_z_json
from app.import_faktur import WynikWpisu

TABELA = "historia_faktur"
KOD_WYGASLEGO_TOKENU = "PGRST303"

T = TypeVar("T")


class SupabaseHistoriaFakturStore:
    def __init__(self, klient: Client, session_path: str | Path = DEFAULT_SUPABASE_SESSION_PATH):
        self._klient = klient
        self._session_path = session_path

    def _z_odswiezeniem_tokenu(self, wywolanie: Callable[[], T]) -> T:
        """Patrz SupabaseAlertStore._z_odswiezeniem_tokenu (supabase_store.py) - ten sam mechanizm,
        zduplikowany celowo, żeby ten moduł nie zależał od wewnętrznych szczegółów tamtego."""
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

    def zapisz(self, nazwa_pliku: str, wyniki: list[WynikWpisu], powod_odrzucenia: str | None = None) -> None:
        self._z_odswiezeniem_tokenu(
            lambda: self._klient.table(TABELA)
            .insert(
                {
                    "nazwa_pliku": nazwa_pliku,
                    "nierozpoznana": bool(powod_odrzucenia),
                    "powod_odrzucenia": powod_odrzucenia,
                    "pozycje": [pozycja_do_json(w) for w in wyniki],
                }
            )
            .execute()
        )

    def ostatnie(self, limit: int = 20) -> list[WpisHistorii]:
        wynik = self._z_odswiezeniem_tokenu(
            lambda: self._klient.table(TABELA)
            .select("id, nazwa_pliku, wpisano_dnia, nierozpoznana, powod_odrzucenia, pozycje")
            .order("id", desc=True)
            .limit(limit)
            .execute()
        )
        return [
            WpisHistorii(
                id=wiersz["id"],
                nazwa_pliku=wiersz["nazwa_pliku"],
                czas=datetime.fromisoformat(wiersz["wpisano_dnia"].replace("Z", "+00:00")),
                nierozpoznana=bool(wiersz["nierozpoznana"]),
                powod_odrzucenia=wiersz["powod_odrzucenia"],
                pozycje=[pozycja_z_json(d) for d in wiersz["pozycje"]],
            )
            for wiersz in wynik.data
        ]

    def usun(self, wpis_id: int) -> None:
        self._z_odswiezeniem_tokenu(lambda: self._klient.table(TABELA).delete().eq("id", wpis_id).execute())

    def close(self) -> None:
        pass

    def __enter__(self) -> "SupabaseHistoriaFakturStore":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
