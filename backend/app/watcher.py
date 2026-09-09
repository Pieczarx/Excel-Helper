"""Obserwator pliku Excel — wykrywa zamknięcie pliku przez użytkownika.

Excel trzyma plik blokady '~$nazwa.xlsx' w tym samym folderze przez cały czas, gdy skoroszyt
jest otwarty (niezależnie ile razy w międzyczasie zapisano) i usuwa go dopiero przy zamknięciu.
Reagujemy więc na zniknięcie tego pliku, a nie na zdarzenia zapisu — patrz [[project_excelhelper_overview]].
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


def _plik_blokady(sciezka: Path) -> Path:
    return sciezka.with_name(f"~${sciezka.name}")


class _ZamkniecieHandler(FileSystemEventHandler):
    def __init__(self, sciezka: Path, callback: Callable[[], None]):
        self._nazwa_blokady = _plik_blokady(sciezka).name.lower()
        self._callback = callback

    def on_deleted(self, event) -> None:
        if event.is_directory:
            return
        if Path(event.src_path).name.lower() == self._nazwa_blokady:
            self._callback()


class ObserwatorPliku:
    """Wywołuje `callback` za każdym razem, gdy obserwowany plik Excel zostanie zamknięty."""

    def __init__(self, sciezka_pliku: str | Path, callback: Callable[[], None]):
        self._sciezka = Path(sciezka_pliku).resolve()
        self._callback = callback
        self._observer = Observer()

    def start(self) -> None:
        handler = _ZamkniecieHandler(self._sciezka, self._callback)
        self._observer.schedule(handler, str(self._sciezka.parent), recursive=False)
        self._observer.start()

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join()

    def czy_plik_jest_teraz_otwarty(self) -> bool:
        return _plik_blokady(self._sciezka).exists()
