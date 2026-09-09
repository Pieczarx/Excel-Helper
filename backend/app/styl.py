"""Wspólna paleta kolorów UI (window.py, widok_uzupelnij_excel.py, widok_weryfikacji.py) - ciepła,
zaokrąglona, przyjazna wersja zatwierdzona przez użytkownika na podstawie makiety:
https://claude.ai/code/artifact/a3e7afab-2360-4ba1-8492-1315af72224c (trzeci wariant, po dwóch
rundach poprawek - jaśniejsze tło strony i biała, nie zielona, strefa upuszczania faktur)."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QLabel

PAPIER = "#FAFAF6"
POWIERZCHNIA = "#FFFFFF"
POWIERZCHNIA_MIEKKA = "#F2F1EA"
ATRAMENT = "#2E2820"
STONOWANY = "#807B6E"
BLADY = "#B4B0A2"
LINIA = "#E9E7DD"
LINIA_MOCNA = "#D8D4C4"

ZIELEN = "#2FA968"
ZIELEN_GLEBOKA = "#1C7A48"
ZIELEN_TLO = "#E3F6EA"

KORAL = "#FF6F51"
KORAL_GLEBOKI = "#D6502F"
KORAL_TLO = "#FFE9DF"

SLONCE = "#EE9F2E"
SLONCE_GLEBOKIE = "#B9740F"
SLONCE_TLO = "#FFF1D6"

CZERWIEN = "#E5564A"
CZERWIEN_GLEBOKA = "#B93A30"
CZERWIEN_TLO = "#FDE8E5"

# Po dwóch rundach ozdobniejszych krojów (Quicksand, potem Comfortaa) użytkownik zdecydował:
# zwykły, powszechnie znany Arial - zero ryzyka dziwnych kształtów liter, zawsze zainstalowany
# na Windows (appka już nic nie musi pakować/rejestrować - patrz usunięte assets/fonts/).
CZCIONKA_NAGLOWEK = "'Arial', sans-serif"
CZCIONKA_TEKST = "'Arial', sans-serif"
CZCIONKA_MONO = "'Consolas', 'Cascadia Mono', monospace"

STYL_SUWAKA = """
    QScrollArea { border: none; background: transparent; }
    QScrollBar:vertical { background: transparent; width: 11px; margin: 2px; }
    QScrollBar::handle:vertical { background: #D8D4C4; border-radius: 4px; min-height: 28px; }
    QScrollBar::handle:vertical:hover { background: #BFBAA6; }
    QScrollBar::handle:vertical:pressed { background: #2FA968; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; border: none; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
    QScrollBar:horizontal { background: transparent; height: 11px; margin: 2px; }
    QScrollBar::handle:horizontal { background: #D8D4C4; border-radius: 4px; min-width: 28px; }
    QScrollBar::handle:horizontal:hover { background: #BFBAA6; }
    QScrollBar::handle:horizontal:pressed { background: #2FA968; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; border: none; }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
"""


def przycisk_pill(tlo: str, tekst: str, tlo_hover: str, obwodka: str | None = None, rozmiar: str = "13px") -> str:
    """QSS dla w pełni zaokrąglonego (pigułkowego) przycisku - główny język przycisków w nowym UI."""
    ramka = f"1.5px solid {obwodka}" if obwodka else "none"
    return (
        f"QPushButton {{ background: {tlo}; color: {tekst}; border: {ramka}; border-radius: 16px; "
        f"padding: 9px 20px; font-size: {rozmiar}; font-weight: 600; font-family: {CZCIONKA_NAGLOWEK}; }}"
        f"QPushButton:hover {{ background: {tlo_hover}; }}"
        "QPushButton:disabled { background: #E4E2D8; color: #B4B0A2; border-color: transparent; }"
    )


class EtykietaSciezki(QLabel):
    """QLabel do wyświetlania ścieżek plików/folderów.

    Zwykły QLabel z długą ścieżką (np. pełna ścieżka do folderu faktur) żąda od layoutu pełnej
    szerokości tekstu w jednej linii - to usztywniało minimalny rozmiar całego okna (potwierdzone:
    okno nie dawało się zmniejszyć poniżej ~634px, wymuszone właśnie przez taki label), a przy
    zawijaniu słów ścieżki Windows i tak się nie zawijają (brak spacji, same "\\") - `setWordWrap`
    nie pomaga.

    `text()`/`setText()` NADAL zwracają/przyjmują pełną ścieżkę (kontrakt reszty appki i testów -
    np. `assert sciezka in etykieta.text()`) - tylko WIDOCZNY render jest przycinany wielokropkiem
    od lewej (`Qt.ElideLeft`, najważniejsza końcówka ścieżki zostaje widoczna) do aktualnej
    szerokości widgetu, na bieżąco przy zmianie rozmiaru okna. Pełna ścieżka trafia też do tooltipa."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pelny_tekst = ""

    def setText(self, tekst: str) -> None:  # noqa: N802 (nazwa metody Qt, nie do zmiany)
        self._pelny_tekst = tekst
        self.setToolTip(tekst)
        self._odswiez_wyswietlany_tekst()

    def text(self) -> str:  # noqa: N802
        return self._pelny_tekst

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._odswiez_wyswietlany_tekst()

    def minimumSizeHint(self) -> QSize:
        metryki = QFontMetrics(self.font())
        return QSize(50, metryki.height())

    def sizeHint(self) -> QSize:
        metryki = QFontMetrics(self.font())
        szerokosc = min(metryki.horizontalAdvance(self._pelny_tekst or " "), 320)
        return QSize(szerokosc, metryki.height())

    def _odswiez_wyswietlany_tekst(self) -> None:
        metryki = QFontMetrics(self.font())
        skrocony = metryki.elidedText(self._pelny_tekst, Qt.ElideLeft, max(self.width(), 1))
        super().setText(skrocony)
