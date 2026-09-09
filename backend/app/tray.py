"""Aplikacja w zasobniku systemowym: badge = liczba obiektów z aktywnym alertem, bez popupów."""
from __future__ import annotations

import pystray
from PySide6.QtCore import Qt, QMetaObject
from PySide6.QtWidgets import QApplication

from app.alerts import GrupaAlertow
from app.kontroler import Kontroler
from app.tray_icon import rysuj_ikone
from app.window import GlowneOkno


class TrayApp:
    def __init__(self, kontroler: Kontroler, okno: GlowneOkno):
        self._kontroler = kontroler
        self._okno = okno

        self._icon = pystray.Icon(
            "excelHelper",
            rysuj_ikone(0),
            "Excel Helper",
            menu=pystray.Menu(
                pystray.MenuItem("Otwórz", self._on_otworz, default=True),
                pystray.MenuItem("Sprawdź teraz", self._on_sprawdz_teraz),
                pystray.MenuItem("Zakończ", self._on_zakoncz),
            ),
        )
        kontroler.zmiana.connect(self._na_zmiane)

    def _na_zmiane(self, grupy: list[GrupaAlertow]) -> None:
        # Czerwony badge z liczbą na ikonie ORAZ tooltip z liczbą obiektów z problemem - z decyzji
        # użytkownika oba na razie wyłączone (kod liczący liczba_obiektow_z_alertami zostaje w
        # alerts.py na przyszłość). rysuj_ikone(0) nigdy nie rysuje badge'u, tylko samą ikonę.
        self._icon.icon = rysuj_ikone(0)
        self._icon.title = "Excel Helper"

    def _on_otworz(self, icon, item) -> None:
        self._okno.pokaz_zadanie.emit()

    def _on_sprawdz_teraz(self, icon, item) -> None:
        self._kontroler.odswiez_w_tle()

    def _on_zakoncz(self, icon, item) -> None:
        self._kontroler.zamknij()
        icon.stop()
        QMetaObject.invokeMethod(QApplication.instance(), "quit", Qt.QueuedConnection)

    def _on_setup(self, icon) -> None:
        icon.visible = True
        # renderuj natychmiast to co juz wiadomo (Kontroler.__init__ mogl juz zrobic pierwszy
        # odswiez() zanim ten obiekt zdazyl sie podlaczyc do sygnalu zmiana - inaczej badge
        # zostaje pusty az do nastepnego odswiezenia)
        self._na_zmiane(self._kontroler.ostatnie_grupy)

    def run(self) -> None:
        self._icon.run(setup=self._on_setup)
