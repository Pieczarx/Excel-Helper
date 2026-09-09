"""Zapamiętywanie hasła do Supabase w Windows Credential Manager (przez keyring) - żeby nie
trzymać go w zwykłym pliku tekstowym na dysku, tak jak resztę konfiguracji."""
from __future__ import annotations

import keyring
import keyring.errors

SERWIS = "excelHelper-supabase"


def zapisz_haslo(email: str, haslo: str, serwis: str = SERWIS) -> None:
    keyring.set_password(serwis, email, haslo)


def wczytaj_haslo(email: str, serwis: str = SERWIS) -> str | None:
    return keyring.get_password(serwis, email)


def usun_haslo(email: str, serwis: str = SERWIS) -> None:
    try:
        keyring.delete_password(serwis, email)
    except keyring.errors.PasswordDeleteError:
        pass
