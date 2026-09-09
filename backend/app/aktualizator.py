"""Pobiera i instaluje nowszą wersję aplikacji z GitHub Releases - patrz aktualizacje.py po samo
sprawdzanie wersji. "Instalacja" oznacza tu podmianę plików źródłowych aplikacji na dysku i
restart procesu, żeby nowy kod się wczytał - Python nie trzyma blokady na zaimportowanych .py
(w przeciwieństwie do np. podmiany działającego .exe), więc to bezpieczne. To nie jest jeszcze
prawdziwy instalator z paczki - dopasowane do obecnego sposobu dystrybucji (uruchamiane z źródła
przez `python -m app.main`); da się to później podmienić na coś bardziej "instalatorowego" bez
zmiany UX (dalej jeden przycisk "Zainstaluj").

Katalog aplikacji (ten, którego zawartość jest podmieniana) to `backend/` - dane użytkownika
(`data/`, `examples/`) leżą PIĘTRO WYŻEJ, jako rodzeństwo `backend/`, więc nie są w ogóle w
zasięgu tej podmiany - nie trzeba ich osobno wykluczać, są bezpieczne z konstrukcji.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path

from PySide6.QtCore import QObject, Signal

KATALOG_APLIKACJI = Path(__file__).resolve().parents[1]  # .../excelHelper/backend


class BladInstalacji(Exception):
    pass


def _pobierz_zip(url: str, cel: Path) -> None:
    try:
        urllib.request.urlretrieve(url, cel)
    except OSError as exc:
        raise BladInstalacji(f"Nie udało się pobrać aktualizacji: {exc}") from None


def _znajdz_katalog_backend(rozpakowane: Path) -> Path:
    """Archiwum GitHuba ma jeden folder najwyższego poziomu (np. 'excelHelper-1.0.2/') - szukamy
    w nim podfolderu 'backend', który faktycznie zawiera kod aplikacji."""
    kandydaci = list(rozpakowane.iterdir())
    korzen = kandydaci[0] if len(kandydaci) == 1 and kandydaci[0].is_dir() else rozpakowane
    backend = korzen / "backend"
    if not backend.is_dir():
        raise BladInstalacji("Nie znaleziono folderu 'backend' w pobranym archiwum")
    return backend


def _podmien_pliki(nowy_backend: Path, docelowy_backend: Path) -> None:
    for element in nowy_backend.iterdir():
        cel = docelowy_backend / element.name
        if cel.exists():
            shutil.rmtree(cel) if cel.is_dir() else cel.unlink()
        if element.is_dir():
            shutil.copytree(element, cel)
        else:
            shutil.copy2(element, cel)


def zainstaluj(url_zip: str, katalog_aplikacji: Path = KATALOG_APLIKACJI) -> None:
    """Pobiera archiwum źródła, podmienia pliki aplikacji. Robi kopię zapasową przed podmianą i
    przywraca ją, jeśli coś pójdzie nie tak w trakcie - podmiana samej siebie w trakcie działania
    nie może zostawić apki w połowie skopiowanego, niedziałającego stanu."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        archiwum = tmp_path / "wydanie.zip"
        _pobierz_zip(url_zip, archiwum)

        rozpakowane = tmp_path / "rozpakowane"
        try:
            with zipfile.ZipFile(archiwum) as zf:
                zf.extractall(rozpakowane)
        except zipfile.BadZipFile as exc:
            raise BladInstalacji(f"Pobrany plik nie jest poprawnym archiwum: {exc}") from None

        nowy_backend = _znajdz_katalog_backend(rozpakowane)

        kopia_zapasowa = tmp_path / "kopia_zapasowa"
        shutil.copytree(katalog_aplikacji, kopia_zapasowa)
        try:
            _podmien_pliki(nowy_backend, katalog_aplikacji)
        except Exception as exc:
            shutil.rmtree(katalog_aplikacji)
            shutil.copytree(kopia_zapasowa, katalog_aplikacji)
            raise BladInstalacji(
                f"Nie udało się zainstalować aktualizacji, przywrócono poprzednią wersję: {exc}"
            ) from exc


def uruchom_ponownie(katalog_aplikacji: Path = KATALOG_APLIKACJI) -> None:
    """Odpala nowy proces appki - ma być wywołane PO zainstaluj() i tuż przed zamknięciem
    bieżącego procesu, żeby nowy (podmieniony) kod faktycznie się załadował."""
    subprocess.Popen([sys.executable, "-m", "app.main"], cwd=str(katalog_aplikacji))


class Instalator(QObject):
    """Pobiera+instaluje w osobnym wątku (sieć + kopiowanie plików), żeby nie mrozić UI."""

    zakonczono = Signal()
    blad = Signal(str)

    def instaluj_w_tle(self, url_zip: str) -> None:
        threading.Thread(target=self._instaluj, args=(url_zip,), daemon=True).start()

    def _instaluj(self, url_zip: str) -> None:
        try:
            zainstaluj(url_zip)
        except BladInstalacji as exc:
            self.blad.emit(str(exc))
            return
        self.zakonczono.emit()
