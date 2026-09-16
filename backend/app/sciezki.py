"""Rozwiązuje ścieżki bazowe appki tak, żeby działały identycznie uruchomione z kodu źródłowego
(`python -m app.main` w `backend/`) i spakowane przez PyInstaller do jednego pliku .exe.

W trybie --onefile PyInstaller przy KAŻDYM starcie rozpakowuje spakowane zasoby do nowego,
zmiennego katalogu tymczasowego (sys._MEIPASS) i usuwa go po zamknięciu appki - więc jest dobry
na zasoby tylko do odczytu (ikony), ale NIGDY na dane użytkownika (config/historia/alerty), bo te
zniknęłyby przy każdym restarcie. Dane użytkownika muszą leżeć obok samego pliku .exe
(sys.executable), nie w katalogu tymczasowym.
"""
from __future__ import annotations

import sys
from pathlib import Path


def czy_zamrozona() -> bool:
    """True, gdy appka działa jako spakowany .exe (PyInstaller), nie z kodu źródłowego."""
    return getattr(sys, "frozen", False)


def katalog_aplikacji() -> Path:
    """Folder z uruchamialną wersją appki - .exe (tryb zamrożony) albo `backend/` (kod źródłowy).
    To jest katalog, który podmienia samoaktualizacja (patrz aktualizator.py)."""
    if czy_zamrozona():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def katalog_danych() -> Path:
    """Folder z lokalnym, trwałym stanem appki (config/historia/alerty) - ZAWSZE poza zasięgiem
    samoaktualizacji: piętro wyżej niż `backend/` w trybie źródłowym, obok pliku .exe w trybie
    zamrożonym (samoaktualizacja podmienia tam tylko sam plik .exe, nie cały folder)."""
    if czy_zamrozona():
        return katalog_aplikacji() / "data"
    return katalog_aplikacji().parent / "data"


def katalog_zasobow() -> Path:
    """Folder z pakowanymi zasobami tylko do odczytu (ikony) - katalog tymczasowy PyInstallera w
    trybie zamrożonym, `assets/` obok `app/` w trybie źródłowym."""
    if czy_zamrozona():
        return Path(sys._MEIPASS) / "assets"  # noqa: SLF001 - oficjalny atrybut PyInstallera
    return Path(__file__).resolve().parents[1] / "assets"
