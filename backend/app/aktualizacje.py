"""Sprawdza GitHub Releases pod kątem nowszej wersji aplikacji niż WERSJA w wersja.py.

Repo jeszcze nie istnieje (excelHelper nie ma dziś zdalnego repo na GitHubie) - REPO_GITHUB
zostaje puste, dopóki użytkownik go nie założy i nie wpisze tu nazwy (np. "bpietrzyk/excelHelper").
Dopóki jest puste, sprawdzanie jest cichym no-opem - appka działa normalnie, bez baneru.

Patrz aktualizator.py dla faktycznego pobierania/instalowania znalezionego wydania.
"""
from __future__ import annotations

import json
import threading
import urllib.request
from dataclasses import dataclass
from urllib.error import URLError

from PySide6.QtCore import QObject, Signal

REPO_GITHUB: str | None = None

_TIMEOUT_SEKUND = 4


@dataclass
class Wydanie:
    tag: str  # dokladny tag z GitHuba (np. "v1.0.2" albo "1.0.2") - potrzebny do pobrania archiwum
    wersja: str  # znormalizowany numer (bez "v") - do porownan i wyswietlania
    url_zip: str  # archiwum zrodla dla tego taga (GitHub generuje je automatycznie dla kazdego taga)


def _wersja_do_krotki(wersja: str) -> tuple[int, ...]:
    oczyszczona = wersja.strip().lstrip("vV")
    return tuple(int(czesc) for czesc in oczyszczona.split("."))


def czy_nowsza(wersja_zdalna: str, wersja_lokalna: str) -> bool:
    try:
        return _wersja_do_krotki(wersja_zdalna) > _wersja_do_krotki(wersja_lokalna)
    except ValueError:
        return False


def pobierz_najnowsze_wydanie(repo: str | None = None) -> Wydanie | None:
    """Zwraca informacje o najnowszym wydaniu z GitHub Releases, albo None jeśli repo nie jest
    skonfigurowane, albo sprawdzenie się nie powiodło (offline, brak releases, limit zapytań
    GitHub API...) - nigdy nie rzuca wyjątku, to ma być cichy check w tle."""
    repo = repo if repo is not None else REPO_GITHUB
    if not repo:
        return None
    try:
        with urllib.request.urlopen(
            f"https://api.github.com/repos/{repo}/releases/latest", timeout=_TIMEOUT_SEKUND
        ) as odpowiedz:
            dane = json.loads(odpowiedz.read().decode("utf-8"))
        tag = dane["tag_name"]
        return Wydanie(
            tag=tag,
            wersja=tag.lstrip("vV"),
            url_zip=f"https://github.com/{repo}/archive/refs/tags/{tag}.zip",
        )
    except (URLError, KeyError, ValueError, TimeoutError, OSError):
        return None


class SprawdzarkaAktualizacji(QObject):
    """Sprawdza w osobnym wątku (zapytanie sieciowe), żeby nie mrozić startu okna - emituje
    sygnał tylko gdy realnie znaleziono wersję nowszą niż ta uruchomiona."""

    znaleziono_nowsza = Signal(object)  # Wydanie

    def sprawdz_w_tle(self, wersja_lokalna: str, repo: str | None = None) -> None:
        threading.Thread(target=self._sprawdz, args=(wersja_lokalna, repo), daemon=True).start()

    def _sprawdz(self, wersja_lokalna: str, repo: str | None) -> None:
        wydanie = pobierz_najnowsze_wydanie(repo)
        if wydanie is not None and czy_nowsza(wydanie.wersja, wersja_lokalna):
            self.znaleziono_nowsza.emit(wydanie)
