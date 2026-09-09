"""Spina magazyn historii wpisanych faktur i przetwarzanie folderów 'Do wpisania'/'Do aktualizacji'
pod jednym obiektem - analogicznie do Kontroler (kontroler.py, zakładka Weryfikacja), ale dla
zakładki Uzupełnij Excel. QObject z tych samych powodów co Kontroler: przetwarzanie idzie w
osobnym wątku (może potrwać, dużo PDF-ów), a Qt bezpiecznie kolejkuje sygnały do wątku GUI."""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from app.config import DEFAULT_FAKTURY_CONFIG_PATH, wczytaj_sciezke_faktur, zapisz_sciezke_faktur
from app.foldery_faktur import (
    NAZWA_DO_AKTUALIZACJI,
    NAZWA_DO_WPISANIA,
    WynikPrzetworzeniaPliku,
    dodaj_do_kolejki,
    przetworz_foldery_faktur,
    upewnij_sie_ze_foldery_istnieja,
    znajdz_faktury,
)
from app.historia_faktur import WpisHistorii
from app.historia_faktur_base import MagazynHistorii


class KontrolerFaktur(QObject):
    historia_zmieniona = Signal(list)  # list[WpisHistorii]
    zakonczono_przetwarzanie = Signal(list)  # list[WynikPrzetworzeniaPliku] - do sekcji "Uzupełnione dane"
    kolejka_zmieniona = Signal(list)  # list[Path]
    w_trakcie = Signal(bool)
    blad = Signal(str)

    def __init__(
        self,
        historia: MagazynHistorii,
        config_path: str | Path = DEFAULT_FAKTURY_CONFIG_PATH,
    ):
        super().__init__()
        self._historia = historia
        self._config_path = config_path
        self._folder: Path | None = None

        zapamietany = wczytaj_sciezke_faktur(config_path)
        if zapamietany is not None:
            self._ustaw_folder_bez_zapisu(zapamietany)

    @property
    def folder(self) -> Path | None:
        return self._folder

    def ustaw_folder(self, folder: str | Path) -> None:
        self._ustaw_folder_bez_zapisu(folder)
        zapisz_sciezke_faktur(self._folder, self._config_path)

    def _ustaw_folder_bez_zapisu(self, folder: str | Path) -> None:
        self._folder = Path(folder).resolve()
        upewnij_sie_ze_foldery_istnieja(self._folder)
        self.kolejka_zmieniona.emit(self.kolejka())

    def kolejka(self) -> list[Path]:
        """Faktury czekające w 'Do wpisania'/'Do aktualizacji' na to, żeby ktoś kliknął
        'Uzupełnij Excel' - to jest cała "kolejka", nie osobny stan w pamięci."""
        if self._folder is None:
            return []
        return znajdz_faktury(self._folder / NAZWA_DO_WPISANIA) + znajdz_faktury(
            self._folder / NAZWA_DO_AKTUALIZACJI
        )

    def dodaj_pliki_do_kolejki(self, sciezki: list[str | Path]) -> None:
        """Kopiuje wskazane PDF-y (upuszczone albo wybrane w oknie dialogowym) do 'Do wpisania' -
        wpisanie do arkusza wymaga osobnego, świadomego kliknięcia 'Uzupełnij Excel'."""
        if self._folder is None:
            raise RuntimeError("Najpierw wybierz folder faktur.")
        folder_docelowy = self._folder / NAZWA_DO_WPISANIA
        for sciezka in sciezki:
            dodaj_do_kolejki(sciezka, folder_docelowy)
        self.kolejka_zmieniona.emit(self.kolejka())

    def usun_z_kolejki(self, sciezka: str | Path) -> None:
        Path(sciezka).unlink(missing_ok=True)
        self.kolejka_zmieniona.emit(self.kolejka())

    def historia_ostatnich(self, limit: int = 20) -> list[WpisHistorii]:
        return self._historia.ostatnie(limit)

    def ustaw_magazyn(self, historia: MagazynHistorii) -> None:
        """Podmienia magazyn historii (np. po zalogowaniu/wylogowaniu - patrz
        GlowneOkno._synchronizuj_historie_faktur w window.py) i od razu odświeża UI nową
        (pustą albo per-konto) zawartością."""
        self._historia = historia
        self.historia_zmieniona.emit(self._historia.ostatnie())

    def usun_z_historii(self, wpis_id: int) -> None:
        self._historia.usun(wpis_id)
        self.historia_zmieniona.emit(self._historia.ostatnie())

    def przetworz_w_tle(self, sciezka_excel: str | Path) -> None:
        threading.Thread(target=self._przetworz, args=(sciezka_excel,), daemon=True).start()

    def _przetworz(self, sciezka_excel: str | Path) -> None:
        self.w_trakcie.emit(True)
        try:
            if self._folder is None:
                raise RuntimeError("Najpierw wybierz folder faktur.")
            wyniki_per_folder = przetworz_foldery_faktur(sciezka_excel, self._folder)
            wszystkie: list[WynikPrzetworzeniaPliku] = [
                wynik for lista in wyniki_per_folder.values() for wynik in lista
            ]
            for wynik in wszystkie:
                self._historia.zapisz(wynik.sciezka.name, wynik.wyniki, powod_odrzucenia=wynik.blad)

            self.zakonczono_przetwarzanie.emit(wszystkie)
            self.historia_zmieniona.emit(self._historia.ostatnie())
            self.kolejka_zmieniona.emit(self.kolejka())
        except Exception as exc:
            self.blad.emit(str(exc))
        finally:
            self.w_trakcie.emit(False)

    def close(self) -> None:
        self._historia.close()
