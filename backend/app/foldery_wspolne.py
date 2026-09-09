"""Stałe i pomocnicze funkcje dot. drzewa folderów faktur, współdzielone między foldery_faktur.py
(kolejka 'Do wpisania'/'Do aktualizacji') i foldery_obiektow.py (routing po PPE do folderów
obiektów) - wydzielone osobno, żeby te dwa moduły nie importowały się nawzajem."""
from __future__ import annotations

from pathlib import Path

NAZWA_DO_WPISANIA = "Do wpisania"
NAZWA_DO_AKTUALIZACJI = "Do aktualizacji"
NAZWA_PRZETWORZONE = "Przetworzone"


def wolna_sciezka_docelowa(folder_docelowy: Path, nazwa_pliku: str) -> Path:
    """Jeśli plik o tej nazwie już jest w folderze docelowym, dokłada licznik zamiast nadpisać
    istniejący plik (np. poprzednio przetworzoną fakturę albo kopię z innego miesiąca o tej samej
    nazwie)."""
    kandydat = folder_docelowy / nazwa_pliku
    if not kandydat.exists():
        return kandydat
    trzon, kropka, rozszerzenie = nazwa_pliku.rpartition(".")
    licznik = 2
    while True:
        proba = folder_docelowy / f"{trzon} ({licznik}){kropka}{rozszerzenie}"
        if not proba.exists():
            return proba
        licznik += 1
