"""Zakładka 'Weryfikacja': lista alertów, wybór pliku Excel, szczegóły obiektu.

Wydzielone z window.py, kiedy 'Uzupełnij Excel' stało się główną zakładką (patrz
widok_uzupelnij_excel.py) - to jest dokładnie ta sama funkcjonalność co wcześniej, teraz jako
osobny widget zamiast całego głównego okna.

Wygląd odświeżony wg tej samej makiety co widok_uzupelnij_excel.py (3. wariant):
https://claude.ai/code/artifact/a3e7afab-2360-4ba1-8492-1315af72224c"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.alerts import Alert, GrupaAlertow
from app.kontroler import Kontroler
from app.rok import NieRozpoznanoRoku
from app.styl import (
    ATRAMENT,
    BLADY,
    CZCIONKA_MONO,
    CZCIONKA_NAGLOWEK,
    CZCIONKA_TEKST,
    CZERWIEN,
    CZERWIEN_GLEBOKA,
    CZERWIEN_TLO,
    LINIA,
    PAPIER,
    POWIERZCHNIA,
    POWIERZCHNIA_MIEKKA,
    SLONCE,
    SLONCE_GLEBOKIE,
    SLONCE_TLO,
    STONOWANY,
    STYL_SUWAKA,
    ZIELEN,
    ZIELEN_GLEBOKA,
    ZIELEN_TLO,
    przycisk_pill,
)

KOLORY_WAGI = {
    "PODWYZSZONA": (SLONCE_TLO, SLONCE_GLEBOKIE, SLONCE),
    "KRYTYCZNA": (CZERWIEN_TLO, CZERWIEN_GLEBOKA, CZERWIEN),
    "CIAGLOSC": (CZERWIEN_TLO, CZERWIEN_GLEBOKA, CZERWIEN),
}


def _kolory_alertu(alert: Alert) -> tuple[str, str, str]:
    klucz = alert.waga if alert.rodzaj == "ODCHYLENIE" else "CIAGLOSC"
    return KOLORY_WAGI.get(klucz, KOLORY_WAGI["CIAGLOSC"])


def _etykieta_rodzaju(alert: Alert) -> str:
    return "Odchylenie" if alert.rodzaj == "ODCHYLENIE" else "Ciągłość"


class OknoSzczegolowObiektu(QDialog):
    def __init__(self, nazwa: str, identyfikacja: dict[str, str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(nazwa)
        self.setMinimumWidth(340)

        uklad = QVBoxLayout(self)
        tytul = QLabel(nazwa)
        tytul.setStyleSheet(f"font-size: 15px; font-weight: 700; font-family: {CZCIONKA_NAGLOWEK};")
        uklad.addWidget(tytul)

        tabela = QTableWidget(len(identyfikacja), 2)
        tabela.horizontalHeader().setVisible(False)
        tabela.verticalHeader().setVisible(False)
        tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        tabela.setSelectionMode(QTableWidget.NoSelection)
        tabela.setShowGrid(False)
        for wiersz, (klucz, wartosc) in enumerate(identyfikacja.items()):
            tabela.setItem(wiersz, 0, QTableWidgetItem(klucz))
            tabela.setItem(wiersz, 1, QTableWidgetItem(wartosc))
        tabela.resizeColumnsToContents()
        tabela.horizontalHeader().setStretchLastSection(True)
        uklad.addWidget(tabela)

        zamknij = QPushButton("Zamknij")
        zamknij.setCursor(Qt.PointingHandCursor)
        zamknij.setStyleSheet(przycisk_pill(ZIELEN, "white", ZIELEN_GLEBOKA))
        zamknij.clicked.connect(self.accept)
        uklad.addWidget(zamknij)


class KartaAlertu(QFrame):
    def __init__(self, alert: Alert, obiekt_nazwa: str, kontroler: Kontroler, on_klik_obiekt, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"KartaAlertu {{ background: {POWIERZCHNIA}; border: 1px solid {LINIA}; border-radius: 18px; }}"
        )
        self.alert = alert
        self.obiekt_nazwa = obiekt_nazwa
        bg, text, dot = _kolory_alertu(alert)

        uklad_glowny = QHBoxLayout(self)
        uklad_glowny.setContentsMargins(16, 15, 15, 15)
        uklad_glowny.setSpacing(14)

        znacznik = QLabel("⬤" if alert.rodzaj != "ODCHYLENIE" else "!")
        znacznik.setFixedSize(36, 36)
        znacznik.setAlignment(Qt.AlignCenter)
        znacznik.setStyleSheet(
            f"background: {bg}; color: {text}; border-radius: 18px; font-weight: 700; font-size: 14px; border: none;"
        )
        uklad_glowny.addWidget(znacznik, alignment=Qt.AlignTop)

        lewa = QVBoxLayout()
        lewa.setSpacing(4)
        gorny_wiersz = QHBoxLayout()
        gorny_wiersz.setSpacing(9)

        link_obiekt = QLabel(f'<a href="#" style="color:{ATRAMENT}; text-decoration:none;">{obiekt_nazwa}</a>')
        link_obiekt.setStyleSheet(
            f"background: transparent; border: none; font-size: 15px; font-weight: 700; font-family: {CZCIONKA_NAGLOWEK};"
        )
        link_obiekt.setTextInteractionFlags(Qt.TextBrowserInteraction)
        link_obiekt.linkActivated.connect(lambda _: on_klik_obiekt(alert.obiekt_wiersz, obiekt_nazwa))
        gorny_wiersz.addWidget(link_obiekt)

        tag = QLabel(_etykieta_rodzaju(alert))
        tag.setStyleSheet(
            f"background: {bg}; color: {text}; font-size: 11px; font-weight: 700; font-family: {CZCIONKA_NAGLOWEK}; "
            "padding: 2px 10px; border-radius: 9px; border: none;"
        )
        gorny_wiersz.addWidget(tag)
        gorny_wiersz.addStretch()
        lewa.addLayout(gorny_wiersz)

        if alert.okres_od and alert.okres_do:
            info = f"{alert.okres_od:%d.%m.%Y} - {alert.okres_do:%d.%m.%Y} · komórka {alert.komorka_biezaca}"
            info_label = QLabel(info)
            info_label.setWordWrap(True)
            info_label.setStyleSheet(
                f"background: transparent; border: none; font-size: 11.5px; color: {BLADY}; font-family: {CZCIONKA_MONO};"
            )
            lewa.addWidget(info_label)

        linie_opisu = alert.opis.split("\n")
        if alert.rodzaj == "ODCHYLENIE" and len(linie_opisu) > 1:
            *glowne_linie, linia_stosunku = linie_opisu
        else:
            glowne_linie, linia_stosunku = linie_opisu, None

        opis_label = QLabel("<br>".join(glowne_linie))
        opis_label.setTextFormat(Qt.RichText)
        opis_label.setStyleSheet(f"background: transparent; border: none; font-size: 13px; color: {ATRAMENT}; font-family: {CZCIONKA_TEKST};")
        opis_label.setWordWrap(True)
        lewa.addWidget(opis_label)

        if linia_stosunku:
            stosunek_label = QLabel(linia_stosunku)
            stosunek_label.setStyleSheet(
                f"background: {bg}; color: {text}; font-size: 11.5px; font-weight: 700; font-family: {CZCIONKA_MONO}; "
                "padding: 3px 11px; border-radius: 9px; border: none;"
            )
            lewa.addWidget(stosunek_label, alignment=Qt.AlignLeft)

        uklad_glowny.addLayout(lewa, stretch=1)

        oznacz = QPushButton("Oznacz jako prawidłowe")
        oznacz.setCursor(Qt.PointingHandCursor)
        oznacz.setStyleSheet(przycisk_pill(POWIERZCHNIA, ZIELEN_GLEBOKA, ZIELEN_TLO, LINIA, "12px"))
        oznacz.clicked.connect(lambda: kontroler.oznacz_jako_prawidlowy_w_tle(alert))
        uklad_glowny.addWidget(oznacz, alignment=Qt.AlignTop)


class WidokWeryfikacji(QWidget):
    def __init__(self, kontroler: Kontroler, parent=None):
        super().__init__(parent)
        self.kontroler = kontroler
        self._filtr_rodzaju = "WSZYSTKIE"
        self._szukaj_tekst = ""
        self._przyciski_filtrow: dict[str, QPushButton] = {}
        self._karty: list[KartaAlertu] = []

        self.setStyleSheet(f"QWidget {{ background: {PAPIER}; }}")

        self._timer_szukania = QTimer(self)
        self._timer_szukania.setSingleShot(True)
        self._timer_szukania.setInterval(250)
        self._timer_szukania.timeout.connect(self._wykonaj_szukanie)

        uklad = QVBoxLayout(self)
        uklad.setContentsMargins(0, 0, 0, 0)
        uklad.setSpacing(0)

        uklad.addWidget(self._zbuduj_naglowek_strony())
        uklad.addWidget(self._zbuduj_pasek_narzedzi())
        uklad.addWidget(self._zbuduj_pasek_filtrow())

        self._obszar_przewijania = QScrollArea()
        self._obszar_przewijania.setWidgetResizable(True)
        self._obszar_przewijania.setStyleSheet(STYL_SUWAKA)
        self._kontener_listy = QWidget()
        self._kontener_listy.setStyleSheet(f"background: {PAPIER};")
        self._uklad_listy = QVBoxLayout(self._kontener_listy)
        self._uklad_listy.setContentsMargins(24, 14, 24, 20)
        self._uklad_listy.setSpacing(10)
        self._uklad_listy.addStretch()
        self._obszar_przewijania.setWidget(self._kontener_listy)
        uklad.addWidget(self._obszar_przewijania, stretch=1)

        self.kontroler.zmiana.connect(self._odswiez_liste)
        self.kontroler.w_trakcie.connect(self._na_w_trakcie)
        self.kontroler.blad.connect(self._na_blad)

        self._odswiez_etykiete_pliku()
        if self.kontroler.sciezka is not None:
            self._odswiez_liste(self.kontroler.ostatnie_grupy)

    def _zbuduj_naglowek_strony(self) -> QWidget:
        blok = QFrame()
        blok.setStyleSheet(f"background: {PAPIER};")
        uklad = QVBoxLayout(blok)
        uklad.setContentsMargins(24, 22, 24, 4)
        uklad.setSpacing(3)

        tytul = QLabel("Sprawdźmy, co odstaje")
        tytul.setStyleSheet(f"color: {ATRAMENT}; font-size: 21px; font-weight: 700; font-family: {CZCIONKA_NAGLOWEK};")
        uklad.addWidget(tytul)

        opis = QLabel("Automatycznie porównujemy zużycie i ciągłość okresów — Ty decydujesz, co jest w porządku.")
        opis.setWordWrap(True)
        opis.setStyleSheet(f"color: {STONOWANY}; font-size: 13px; font-family: {CZCIONKA_TEKST};")
        uklad.addWidget(opis)
        return blok

    def _zbuduj_pasek_narzedzi(self) -> QWidget:
        pasek = QFrame()
        pasek.setStyleSheet(f"background: {PAPIER};")
        uklad = QHBoxLayout(pasek)
        uklad.setContentsMargins(24, 16, 24, 0)
        uklad.setSpacing(10)

        self._etykieta_pliku = QLabel("Brak wybranego pliku")
        self._etykieta_pliku.setStyleSheet(f"color: {ATRAMENT}; font-size: 13px; font-family: {CZCIONKA_MONO};")
        uklad.addWidget(self._etykieta_pliku)

        zmien = QPushButton("Zmień plik")
        zmien.setCursor(Qt.PointingHandCursor)
        zmien.setStyleSheet(przycisk_pill(POWIERZCHNIA, ATRAMENT, POWIERZCHNIA_MIEKKA, LINIA, "11.5px"))
        zmien.clicked.connect(self._wybierz_plik)
        uklad.addWidget(zmien)

        uklad.addStretch()

        self._badge = QLabel("")
        self._badge.setStyleSheet(
            f"background: {CZERWIEN_TLO}; color: {CZERWIEN_GLEBOKA}; font-size: 11.5px; font-weight: 700; "
            f"font-family: {CZCIONKA_NAGLOWEK}; padding: 4px 12px; border-radius: 11px;"
        )
        self._badge.hide()
        uklad.addWidget(self._badge)

        self._przycisk_sprawdz = QPushButton("Sprawdź teraz")
        self._przycisk_sprawdz.setCursor(Qt.PointingHandCursor)
        self._przycisk_sprawdz.setStyleSheet(przycisk_pill(ZIELEN, "white", ZIELEN_GLEBOKA, rozmiar="12.5px"))
        self._przycisk_sprawdz.clicked.connect(self.kontroler.odswiez_w_tle)
        uklad.addWidget(self._przycisk_sprawdz)

        return pasek

    def _zbuduj_pasek_filtrow(self) -> QWidget:
        pasek = QFrame()
        pasek.setStyleSheet(f"background: {PAPIER};")
        uklad = QHBoxLayout(pasek)
        uklad.setContentsMargins(24, 12, 24, 10)
        uklad.setSpacing(10)

        self._pole_szukaj = QLineEdit()
        self._pole_szukaj.setPlaceholderText("Szukaj obiektu…")
        self._pole_szukaj.setMaximumWidth(230)
        self._pole_szukaj.setStyleSheet(
            f"QLineEdit {{ background: {POWIERZCHNIA}; border: 1px solid {LINIA}; border-radius: 16px; "
            f"padding: 8px 15px; font-size: 13px; font-family: {CZCIONKA_TEKST}; }}"
            f"QLineEdit:focus {{ border-color: {ZIELEN}; }}"
        )
        self._pole_szukaj.textChanged.connect(self._na_zmiane_szukania)
        uklad.addWidget(self._pole_szukaj)

        kapsula = QFrame()
        kapsula.setStyleSheet(f"background: {POWIERZCHNIA_MIEKKA}; border: 1px solid {LINIA}; border-radius: 15px;")
        uklad_kapsuly = QHBoxLayout(kapsula)
        uklad_kapsuly.setContentsMargins(3, 3, 3, 3)
        uklad_kapsuly.setSpacing(2)
        for wartosc, etykieta in [
            ("WSZYSTKIE", "Wszystkie"),
            ("ODCHYLENIE", "Odchylenie"),
            ("LUKA_CIAGLOSCI", "Ciągłość"),
        ]:
            przycisk = QPushButton(etykieta)
            przycisk.setCursor(Qt.PointingHandCursor)
            przycisk.setCheckable(True)
            przycisk.setChecked(wartosc == "WSZYSTKIE")
            przycisk.clicked.connect(lambda _checked=False, w=wartosc: self._ustaw_filtr(w))
            self._przyciski_filtrow[wartosc] = przycisk
            uklad_kapsuly.addWidget(przycisk)
        uklad.addWidget(kapsula)
        self._odswiez_style_filtrow()

        uklad.addStretch()
        return pasek

    def _odswiez_style_filtrow(self) -> None:
        for wartosc, przycisk in self._przyciski_filtrow.items():
            aktywny = wartosc == self._filtr_rodzaju
            tlo = ZIELEN if aktywny else "transparent"
            kolor = "white" if aktywny else STONOWANY
            przycisk.setStyleSheet(
                f"QPushButton {{ background: {tlo}; color: {kolor}; border: none; font-weight: 700; "
                f"font-family: {CZCIONKA_NAGLOWEK}; border-radius: 12px; padding: 6px 14px; font-size: 12px; }}"
            )

    def _ustaw_filtr(self, wartosc: str) -> None:
        self._filtr_rodzaju = wartosc
        self._odswiez_style_filtrow()
        self._zastosuj_filtry()

    def _na_zmiane_szukania(self, tekst: str) -> None:
        self._szukaj_tekst = tekst
        self._timer_szukania.start()

    def _wykonaj_szukanie(self) -> None:
        self._zastosuj_filtry()

    def _zastosuj_filtry(self) -> None:
        # Tylko przelaczanie widocznosci JUZ ISTNIEJACYCH kart - zadnego niszczenia/tworzenia
        # widgetow. Poprzednia wersja (pelna przebudowa listy na kazda zmiane filtra/wyszukiwania)
        # migotala nawet z wylaczonym malowaniem w trakcie - to obejscie problemu u zrodla,
        # zamiast dalszego zgadywania co dokladnie w Qt to powodowalo.
        for karta in self._karty:
            pasuje_szukanie = (
                not self._szukaj_tekst or self._szukaj_tekst.lower() in karta.obiekt_nazwa.lower()
            )
            pasuje_filtr = self._filtr_rodzaju == "WSZYSTKIE" or karta.alert.rodzaj == self._filtr_rodzaju
            karta.setVisible(pasuje_szukanie and pasuje_filtr)

    def _odswiez_etykiete_pliku(self) -> None:
        if self.kontroler.sciezka is not None:
            self._etykieta_pliku.setText(self.kontroler.sciezka.name)
        else:
            self._etykieta_pliku.setText("Brak wybranego pliku")

    def _na_w_trakcie(self, w_trakcie: bool) -> None:
        self._przycisk_sprawdz.setEnabled(not w_trakcie)
        self._przycisk_sprawdz.setText("Sprawdzanie..." if w_trakcie else "Sprawdź teraz")
        self._obszar_przewijania.setEnabled(not w_trakcie)

    def _na_blad(self, tresc: str) -> None:
        QMessageBox.warning(self, "Coś poszło nie tak", tresc)

    def _wybierz_plik(self) -> None:
        sciezka, _ = QFileDialog.getOpenFileName(self, "Wybierz plik Excel", "", "Excel (*.xlsx)")
        if not sciezka:
            return
        try:
            self.kontroler.ustaw_plik(sciezka)
        except NieRozpoznanoRoku as exc:
            QMessageBox.warning(self, "Nie rozpoznano roku", str(exc))
            return
        self._odswiez_etykiete_pliku()

    def _pokaz_szczegoly_obiektu(self, wiersz: int, nazwa: str) -> None:
        identyfikacja = self.kontroler.identyfikacja_obiektu(wiersz)
        dialog = OknoSzczegolowObiektu(nazwa, identyfikacja, parent=self)
        dialog.exec()

    def _odswiez_liste(self, grupy: list[GrupaAlertow]) -> None:
        # Pelna przebudowa - wywolywana TYLKO gdy dane faktycznie sie zmienily (nowy plik,
        # odswiezenie, oznaczenie alertu). Zmiana filtra/wyszukiwania NIE przechodzi juz tedy -
        # patrz _zastosuj_filtry(), ktora tylko przelacza widocznosc, bez tworzenia/niszczenia
        # widgetow (to wlasnie te tworzenie/niszczenie powodowalo migotanie).
        for karta in self._karty:
            self._uklad_listy.removeWidget(karta)
            karta.hide()
            karta.deleteLater()
        self._karty = []

        for grupa in grupy:
            for alert in grupa.alerty:
                karta = KartaAlertu(alert, grupa.obiekt_nazwa, self.kontroler, self._pokaz_szczegoly_obiektu)
                self._uklad_listy.insertWidget(self._uklad_listy.count() - 1, karta)
                self._karty.append(karta)

        self._zastosuj_filtry()

        liczba = len({g.obiekt_wiersz for g in grupy})
        if liczba:
            self._badge.setText(f"{liczba} z problemem")
            self._badge.show()
        else:
            self._badge.hide()
        self._odswiez_etykiete_pliku()
