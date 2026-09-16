"""Pobiera i instaluje nowszą wersję aplikacji z GitHub Releases - patrz aktualizacje.py po samo
sprawdzanie wersji. Dwa tryby instalacji, w zależności od tego, jak appka dziś działa (patrz
app/sciezki.py):

- Z kodu źródłowego (`python -m app.main`): "instalacja" to podmiana plików źródłowych na dysku -
  Python nie trzyma blokady na zaimportowanych .py, więc bezpieczne zrobić w locie.
- Spakowana do .exe (PyInstaller): nie ma plików źródłowych do podmiany - "instalacja" to pobranie
  nowego .exe (jako załącznik/asset danego GitHub Release, patrz Wydanie.url_exe w aktualizacje.py)
  i podmiana samego pliku wykonywalnego. Windows pozwala PRZENIEŚĆ (rename) działający .exe (loader
  trzyma go z FILE_SHARE_DELETE), więc stary plik jest odsuwany na bok, a nowy wchodzi na jego
  miejsce - restart odpala już nową wersję.

Katalog aplikacji (ten, którego zawartość jest podmieniana w trybie źródłowym / w którym leży .exe
w trybie zamrożonym) NIGDY nie zawiera `data/` - patrz app/sciezki.katalog_danych() - więc dane
użytkownika są bezpieczne z konstrukcji, bez osobnego wykluczania.
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
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from app.sciezki import czy_zamrozona
from app.sciezki import katalog_aplikacji as _katalog_aplikacji_biezacy

if TYPE_CHECKING:
    from app.aktualizacje import Wydanie

KATALOG_APLIKACJI = _katalog_aplikacji_biezacy()


class BladInstalacji(Exception):
    pass


def _pobierz_plik(url: str, cel: Path) -> None:
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
        _pobierz_plik(url_zip, archiwum)

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


def zainstaluj_zamrozona(url_exe: str, biezacy_exe: Path) -> None:
    """Podmienia sam plik .exe - odsuwa działający plik na bok (Windows na to pozwala, loader
    trzyma go z FILE_SHARE_DELETE), wstawia na jego miejsce nowo pobrany. Odsunięty plik zostaje
    obok (posprzątany przy następnym starcie - patrz posprzataj_poprzednia_wersje()), bo usunięcie
    pliku, który wciąż wykonuje działający proces, nie zawsze się na Windows udaje."""
    with tempfile.TemporaryDirectory() as tmp:
        nowy_exe = Path(tmp) / "nowy.exe"
        _pobierz_plik(url_exe, nowy_exe)

        poprzedni = biezacy_exe.with_name(biezacy_exe.name + ".poprzedni")
        poprzedni.unlink(missing_ok=True)
        try:
            biezacy_exe.rename(poprzedni)
        except OSError as exc:
            raise BladInstalacji(f"Nie udało się podmienić pliku aplikacji: {exc}") from None
        try:
            shutil.copy2(nowy_exe, biezacy_exe)
        except Exception as exc:
            poprzedni.rename(biezacy_exe)
            raise BladInstalacji(
                f"Nie udało się zainstalować aktualizacji, przywrócono poprzednią wersję: {exc}"
            ) from exc


def posprzataj_poprzednia_wersje(biezacy_exe: Path | None = None) -> None:
    """Usuwa odsunięty plik `.poprzedni` z ewentualnej wcześniejszej aktualizacji - wywoływane przy
    starcie appki (main.py), kiedy stary plik nie jest już przez nikogo wykonywany, więc usunięcie
    na pewno się uda. Cichy no-op, jeśli nic nie ma do posprzątania."""
    biezacy_exe = biezacy_exe or Path(sys.executable).resolve()
    biezacy_exe.with_name(biezacy_exe.name + ".poprzedni").unlink(missing_ok=True)


def zainstaluj_wydanie(wydanie: Wydanie, katalog_aplikacji: Path = KATALOG_APLIKACJI) -> None:
    """Dyspozytor: wybiera tryb instalacji zgodnie z tym, jak appka dziś faktycznie działa."""
    if czy_zamrozona():
        if not wydanie.url_exe:
            raise BladInstalacji("To wydanie nie zawiera zbudowanego pliku .exe")
        zainstaluj_zamrozona(wydanie.url_exe, Path(sys.executable).resolve())
        return
    zainstaluj(wydanie.url_zip, katalog_aplikacji)


def uruchom_ponownie(katalog_aplikacji: Path = KATALOG_APLIKACJI) -> None:
    """Odpala nowy proces appki - ma być wywołane PO zainstaluj_wydanie() i tuż przed zamknięciem
    bieżącego procesu, żeby nowy (podmieniony) kod/plik faktycznie się załadował."""
    if czy_zamrozona():
        subprocess.Popen([str(Path(sys.executable).resolve())])
        return
    subprocess.Popen([sys.executable, "-m", "app.main"], cwd=str(katalog_aplikacji))


class Instalator(QObject):
    """Pobiera+instaluje w osobnym wątku (sieć + kopiowanie plików), żeby nie mrozić UI."""

    zakonczono = Signal()
    blad = Signal(str)

    def instaluj_w_tle(self, wydanie: Wydanie) -> None:
        threading.Thread(target=self._instaluj, args=(wydanie,), daemon=True).start()

    def _instaluj(self, wydanie: Wydanie) -> None:
        try:
            zainstaluj_wydanie(wydanie)
        except BladInstalacji as exc:
            self.blad.emit(str(exc))
            return
        self.zakonczono.emit()
