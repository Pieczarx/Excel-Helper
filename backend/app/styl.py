"""Wspólna paleta kolorów UI (window.py, widok_uzupelnij_excel.py, widok_weryfikacji.py) - ciepła,
zaokrąglona, przyjazna wersja zatwierdzona przez użytkownika na podstawie makiety:
https://claude.ai/code/artifact/a3e7afab-2360-4ba1-8492-1315af72224c (trzeci wariant, po dwóch
rundach poprawek - jaśniejsze tło strony i biała, nie zielona, strefa upuszczania faktur)."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics, QPixmap
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

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


class Checkbox(QWidget):
    """Checkbox z w pełni własnym kwadracikiem (QLabel z ptaszkiem "✓"), nie systemowym
    wskaźnikiem - dwa niezależne powody, żeby go tu nie używać:

    1. Natywny wskaźnik potrafi się różnie przerysować, kiedy widget jest tylko częściowo
       widoczny w przewijanym obszarze (górna/dolna krawędź robi się cieńsza/jaśniejsza).
    2. QSS może w pełni przejąć rysowanie `QCheckBox::indicator` (np. samo tło/ramkę), ale wtedy
       Qt przestaje też dorysowywać natywny ptaszek - próba "biały kwadracik + zielone tło po
       zaznaczeniu" wychodziła jako martwe, wypełnione pole bez żadnego ptaszka.

    Zamiast tego zaznaczenie po prostu podmienia tekst/kolor małej etykiety na zielony "✓" -
    dokładnie ten sam język (kolorowy unicode w QLabel), jakiego appka już używa gdzie indziej
    (np. znaczniki sukcesu/błędu w widok_uzupelnij_excel.py)."""

    toggled = Signal(bool)

    def __init__(self, tekst: str, tekst_kolor: str = ATRAMENT, rozmiar: str = "13px", parent=None):
        super().__init__(parent)
        self._zaznaczony = False
        self.setCursor(Qt.PointingHandCursor)

        uklad = QHBoxLayout(self)
        uklad.setContentsMargins(0, 0, 0, 0)
        uklad.setSpacing(8)

        self._kwadracik = QLabel()
        self._kwadracik.setFixedSize(16, 16)
        self._kwadracik.setAlignment(Qt.AlignCenter)
        uklad.addWidget(self._kwadracik)

        self._etykieta = QLabel(tekst)
        self._etykieta.setStyleSheet(
            f"background: transparent; color: {tekst_kolor}; font-size: {rozmiar}; "
            f"font-weight: 600; font-family: {CZCIONKA_NAGLOWEK}; border: none;"
        )
        uklad.addWidget(self._etykieta)
        uklad.addStretch()

        self._odswiez_kwadracik()

    def isChecked(self) -> bool:  # noqa: N802 (nazwa metody zgodna z QCheckBox, nie do zmiany)
        return self._zaznaczony

    def setChecked(self, zaznaczony: bool) -> None:  # noqa: N802
        if zaznaczony == self._zaznaczony:
            return
        self._zaznaczony = zaznaczony
        self._odswiez_kwadracik()
        self.toggled.emit(self._zaznaczony)

    def mousePressEvent(self, event) -> None:
        self.setChecked(not self._zaznaczony)
        super().mousePressEvent(event)

    def _odswiez_kwadracik(self) -> None:
        if self._zaznaczony:
            self._kwadracik.setText("✓")
            self._kwadracik.setStyleSheet(
                f"background: {POWIERZCHNIA}; color: {ZIELEN}; border: 1.5px solid {ZIELEN}; "
                "border-radius: 4px; font-size: 11px; font-weight: 700;"
            )
        else:
            self._kwadracik.setText("")
            self._kwadracik.setStyleSheet(
                f"background: {POWIERZCHNIA}; border: 1.5px solid {LINIA_MOCNA}; border-radius: 4px;"
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


class EkranStartowy(QWidget):
    """Mały ekran powitalny z paskiem postępu, pokazywany od razu po starcie appki - zanim
    zdąży się zbudować właściwe okno (rejestracja autostartu, odtworzenie sesji Supabase i
    zbudowanie GłównegoOkna razem mogą zająć kilka sekund, w trakcie których appka bez tego
    ekranu nie pokazywała NICZEGO, co przy ręcznym uruchomieniu appki wyglądało jak "nic się nie
    dzieje" - patrz main.py po kolejność wywołań ustaw_postep()).

    Bez ramki okna i paska tytułu (Qt.SplashScreen) - to komunikat "trwa ładowanie", nie
    pełnoprawne okno appki, więc nie powinien mieć własnej ikony na pasku zadań/w Alt+Tab."""

    def __init__(self, ikona: QPixmap | None = None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setFixedSize(320, 200)
        self.setStyleSheet(f"EkranStartowy {{ background: {PAPIER}; border-radius: 16px; border: 1px solid {LINIA}; }}")

        uklad = QVBoxLayout(self)
        uklad.setContentsMargins(28, 28, 28, 28)
        uklad.setSpacing(14)
        uklad.addStretch()

        if ikona is not None and not ikona.isNull():
            znak = QLabel()
            znak.setPixmap(ikona.scaled(44, 44, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            znak.setAlignment(Qt.AlignCenter)
            znak.setStyleSheet("background: transparent; border: none;")
            uklad.addWidget(znak)

        tytul = QLabel("Excel Helper")
        tytul.setAlignment(Qt.AlignCenter)
        tytul.setStyleSheet(
            f"background: transparent; border: none; color: {ATRAMENT}; font-size: 16px; "
            f"font-weight: 700; font-family: {CZCIONKA_NAGLOWEK};"
        )
        uklad.addWidget(tytul)

        self._pasek = QProgressBar()
        self._pasek.setRange(0, 100)
        self._pasek.setTextVisible(False)
        self._pasek.setFixedHeight(6)
        self._pasek.setStyleSheet(
            f"QProgressBar {{ background: {POWIERZCHNIA_MIEKKA}; border: none; border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background: {ZIELEN}; border-radius: 3px; }}"
        )
        uklad.addWidget(self._pasek)

        self._etykieta = QLabel()
        self._etykieta.setAlignment(Qt.AlignCenter)
        self._etykieta.setStyleSheet(
            f"background: transparent; border: none; color: {STONOWANY}; font-size: 11.5px; "
            f"font-family: {CZCIONKA_TEKST};"
        )
        uklad.addWidget(self._etykieta)
        uklad.addStretch()

        self.ustaw_postep(0, "Uruchamianie…")
        self._wysrodkuj()

    def ustaw_postep(self, procent: int, tekst: str) -> None:
        self._pasek.setValue(procent)
        self._etykieta.setText(tekst)
        # Bez processEvents appka nie odmalowuje sie ponownie w trakcie dlugich, blokujacych
        # krokow startu (rejestracja autostartu, siec do Supabase) - pasek zostalby zamrozony na
        # poprzedniej wartosci az appka skonczy sie budowac.
        QApplication.processEvents()

    def _wysrodkuj(self) -> None:
        ekran = QApplication.primaryScreen()
        if ekran is None:
            return
        srodek = ekran.availableGeometry().center()
        self.move(srodek.x() - self.width() // 2, srodek.y() - self.height() // 2)
