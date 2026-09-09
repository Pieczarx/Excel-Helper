"""Zakładka 'Uzupełnij Excel' (główna): upuszczanie/wybór faktur PDF, kolejka, przycisk
'Uzupełnij Excel', świeże wyniki ('Uzupełnione dane') i stała historia ('Ostatnio wpisane').

Wygląd odświeżony wg makiety zatwierdzonej przez użytkownika (3. wariant, ciepła/przyjazna wersja
po dwóch rundach poprawek): https://claude.ai/code/artifact/a3e7afab-2360-4ba1-8492-1315af72224c
Poprzednia, formularzowa makieta: https://claude.ai/code/artifact/ea4d78db-8c3e-4638-8d8f-218bc572a8b9
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.excel_reader_oddana import SHEET_NAME_ODDANA
from app.faktura_reader import (
    KAT_BRAK_PPE_NA_FAKTURZE,
    KAT_DANE_NIEROZPOZNANE,
    KAT_JUZ_WYPELNIONE,
    KAT_NIEZGODNOSC_SUMY,
    KAT_PPE_NIEZNALEZIONE,
    KAT_SUKCES,
    KAT_ZUZYCIE_NIEZGODNE_Z_FAKTURA,
)
from app.foldery_faktur import WynikPrzetworzeniaPliku
from app.foldery_obiektow import KAT_BRAK_FOLDERU_OBIEKTU
from app.historia_faktur import WpisHistorii
from app.import_faktur import WynikWpisu
from app.kontroler import Kontroler
from app.kontroler_faktur import KontrolerFaktur
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
    EtykietaSciezki,
    KORAL,
    KORAL_GLEBOKI,
    KORAL_TLO,
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

ETYKIETY_KATEGORII = {
    KAT_PPE_NIEZNALEZIONE: "PPE nieznalezione w arkuszu",
    KAT_BRAK_PPE_NA_FAKTURZE: "Obiekt na fakturze bez PPE",
    KAT_DANE_NIEROZPOZNANE: "Dane niemożliwe do odczytania",
    KAT_NIEZGODNOSC_SUMY: "Zapisano, ale niezgodność sumy zużycia",
    KAT_ZUZYCIE_NIEZGODNE_Z_FAKTURA: "Zapisano, ale zużycie niezgodne z fakturą",
    KAT_BRAK_FOLDERU_OBIEKTU: "Zapisano, ale brak folderu obiektu - dopisz PPE do folderu ręcznie",
}

MIESIACE_SKROT = {
    1: "sty", 2: "lut", 3: "mar", 4: "kwi", 5: "maj", 6: "cze",
    7: "lip", 8: "sie", 9: "wrz", 10: "paź", 11: "lis", 12: "gru",
}


def _selectable(label: QLabel) -> QLabel:
    """Tekst z realną treścią (nie same ikony/etykiety UI) ma dać się zaznaczyć i skopiować."""
    label.setTextInteractionFlags(Qt.TextSelectableByMouse)
    label.setCursor(Qt.IBeamCursor)
    return label


def _formatuj_okres(okres_od: date | None, okres_do: date | None) -> str:
    if okres_od is None or okres_do is None:
        return "-"
    if okres_od.month == okres_do.month and okres_od.year == okres_do.year:
        return f"{okres_od.day}–{okres_do.day} {MIESIACE_SKROT[okres_do.month]} {okres_do.year}"
    if okres_od.year == okres_do.year:
        return f"{okres_od.day} {MIESIACE_SKROT[okres_od.month]} – {okres_do.day} {MIESIACE_SKROT[okres_do.month]} {okres_do.year}"
    return (
        f"{okres_od.day} {MIESIACE_SKROT[okres_od.month]} {okres_od.year} – "
        f"{okres_do.day} {MIESIACE_SKROT[okres_do.month]} {okres_do.year}"
    )


def _formatuj_wartosc_chip(etykieta: str, wartosc: float) -> str:
    tekst = f"{wartosc:,.2f}" if etykieta == "Dystrybucja" else f"{wartosc:,.0f}"
    tekst = tekst.replace(",", " ").replace(".", ",")
    if etykieta == "Dystrybucja":
        return f"{tekst} zł"
    return f"{tekst} kWh"


def _chip_c1(etykieta: str, wartosc: float) -> QFrame:
    ramka = QFrame()
    ramka.setStyleSheet(f"QFrame {{ background: {POWIERZCHNIA_MIEKKA}; border-radius: 6px; border: none; }}")
    uklad = QHBoxLayout(ramka)
    uklad.setContentsMargins(6, 2, 6, 2)
    uklad.setSpacing(3)
    l_etykieta = QLabel(f"{etykieta}:")
    l_etykieta.setStyleSheet(
        f"background: transparent; color: {BLADY}; font-size: 9px; font-weight: 700; "
        f"border: none; font-family: {CZCIONKA_NAGLOWEK};"
    )
    uklad.addWidget(l_etykieta)
    l_wartosc = _selectable(QLabel(_formatuj_wartosc_chip(etykieta, wartosc)))
    l_wartosc.setStyleSheet(
        f"background: transparent; color: {ATRAMENT}; font-size: 10px; font-weight: 600; "
        f"border: none; font-family: {CZCIONKA_MONO};"
    )
    uklad.addWidget(l_wartosc)
    return ramka


def _wiersz_chipow(pozycje: list[tuple[str, float]]) -> QHBoxLayout:
    wiersz = QHBoxLayout()
    wiersz.setContentsMargins(42, 0, 0, 0)
    wiersz.setSpacing(5)
    for etykieta, wartosc in pozycje:
        wiersz.addWidget(_chip_c1(etykieta, wartosc))
    wiersz.addStretch()
    return wiersz


def _formatuj_meta(wyniki: list[WynikWpisu]) -> str:
    for wynik in wyniki:
        if wynik.okres_do is not None:
            return f"{MIESIACE_SKROT[wynik.okres_do.month]} {wynik.okres_do.year}"
    return "-"


def _formatuj_czas(czas: datetime | None) -> str:
    if czas is None:
        return "teraz"
    dzis = datetime.now().date()
    if czas.date() == dzis:
        return f"dziś, {czas:%H:%M}"
    if (dzis - czas.date()).days == 1:
        return "wczoraj"
    return f"{czas.day} {MIESIACE_SKROT[czas.month]}"


def _inicjaly(nazwa: str) -> str:
    """Pierwsze litery pierwszych dwóch słów nazwy obiektu - do znaczka-awatara w wierszu wyniku."""
    slowa = [s for s in nazwa.split() if s]
    if not slowa:
        return "?"
    if len(slowa) == 1:
        return slowa[0][:2].upper()
    return (slowa[0][0] + slowa[1][0]).upper()


class StrefaUpuszczania(QFrame):
    pliki_upuszczone = Signal(list)  # list[str]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._ustaw_styl(najechano=False)

        uklad = QVBoxLayout(self)
        uklad.setContentsMargins(20, 30, 20, 30)
        uklad.setSpacing(3)
        uklad.setAlignment(Qt.AlignCenter)

        znak = QLabel("📥")
        znak.setFixedSize(58, 58)
        znak.setAlignment(Qt.AlignCenter)
        znak.setStyleSheet(f"background: {POWIERZCHNIA}; border: 1px solid {LINIA}; border-radius: 18px; font-size: 24px;")
        uklad.addWidget(znak, alignment=Qt.AlignCenter)
        uklad.addSpacing(10)

        tytul = QLabel("Upuść faktury tutaj")
        tytul.setAlignment(Qt.AlignCenter)
        tytul.setStyleSheet(
            f"background: transparent; font-weight: 700; color: {ATRAMENT}; font-size: 16px; border: none; "
            f"font-family: {CZCIONKA_NAGLOWEK};"
        )
        uklad.addWidget(tytul)

        opis = QLabel("PDF trafi prosto do folderu roboczego")
        opis.setAlignment(Qt.AlignCenter)
        opis.setStyleSheet(
            f"background: transparent; color: {STONOWANY}; font-size: 12.5px; border: none; "
            f"font-family: {CZCIONKA_TEKST}; margin-top: 2px;"
        )
        uklad.addWidget(opis)
        uklad.addSpacing(12)

        self.przycisk_wybierz = QPushButton("Wybierz pliki")
        self.przycisk_wybierz.setCursor(Qt.PointingHandCursor)
        self.przycisk_wybierz.setStyleSheet(przycisk_pill(POWIERZCHNIA, ATRAMENT, POWIERZCHNIA_MIEKKA, LINIA))
        uklad.addWidget(self.przycisk_wybierz, alignment=Qt.AlignCenter)

    def _ustaw_styl(self, najechano: bool) -> None:
        tlo = ZIELEN_TLO if najechano else POWIERZCHNIA
        obramowanie = ZIELEN if najechano else LINIA
        self.setStyleSheet(
            f"StrefaUpuszczania {{ background: {tlo}; border: 2px dashed {obramowanie}; border-radius: 22px; }}"
        )

    @staticmethod
    def _sciezki_pdf(mime_data) -> list[str]:
        if not mime_data.hasUrls():
            return []
        return [
            url.toLocalFile()
            for url in mime_data.urls()
            if url.isLocalFile() and url.toLocalFile().lower().endswith(".pdf")
        ]

    def dragEnterEvent(self, event) -> None:
        if self._sciezki_pdf(event.mimeData()):
            self._ustaw_styl(najechano=True)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._ustaw_styl(najechano=False)

    def dropEvent(self, event) -> None:
        self._ustaw_styl(najechano=False)
        sciezki = self._sciezki_pdf(event.mimeData())
        if sciezki:
            self.pliki_upuszczone.emit(sciezki)
            event.acceptProposedAction()


def _przycisk_usuwania(tooltip: str) -> QPushButton:
    przycisk = QPushButton("🗑")
    przycisk.setToolTip(tooltip)
    przycisk.setFlat(True)
    przycisk.setCursor(Qt.PointingHandCursor)
    przycisk.setFixedSize(28, 28)
    przycisk.setStyleSheet(
        f"QPushButton {{ background: none; border: none; border-radius: 14px; color: {BLADY}; "
        "font-size: 13px; padding: 0; }}"
        f"QPushButton:hover {{ background: {CZERWIEN_TLO}; color: {CZERWIEN_GLEBOKA}; }}"
        "QPushButton:pressed { background: #f5cfc9; }"
    )
    return przycisk


class WierszKolejki(QFrame):
    usun_kliknieto = Signal(Path)

    def __init__(self, sciezka: Path, parent=None):
        super().__init__(parent)
        self.sciezka = sciezka
        self.setStyleSheet(
            f"WierszKolejki {{ background: {POWIERZCHNIA}; border: 1px solid {LINIA}; border-radius: 14px; }}"
        )
        uklad = QHBoxLayout(self)
        uklad.setContentsMargins(10, 8, 8, 8)
        uklad.setSpacing(10)

        ikona = QLabel("PDF")
        ikona.setFixedSize(32, 30)
        ikona.setAlignment(Qt.AlignCenter)
        ikona.setStyleSheet(
            f"background: {CZERWIEN_TLO}; color: {CZERWIEN_GLEBOKA}; border-radius: 9px; "
            f"font-size: 9.5px; font-weight: 700; border: none; font-family: {CZCIONKA_MONO};"
        )
        uklad.addWidget(ikona)

        nazwa = _selectable(QLabel(sciezka.name))
        nazwa.setStyleSheet(f"background: transparent; font-size: 13px; border: none; font-family: {CZCIONKA_TEKST};")
        uklad.addWidget(nazwa, stretch=1)

        gotowe = QLabel("gotowe")
        gotowe.setStyleSheet(
            f"background: {ZIELEN_TLO}; color: {ZIELEN_GLEBOKA}; font-size: 11px; font-weight: 700; "
            "padding: 3px 10px; border-radius: 9px; border: none;"
        )
        uklad.addWidget(gotowe)

        usun = _przycisk_usuwania("Usuń z kolejki")
        usun.clicked.connect(lambda: self.usun_kliknieto.emit(self.sciezka))
        uklad.addWidget(usun)


class WierszObiektu(QFrame):
    def __init__(self, wynik: WynikWpisu, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"WierszObiektu {{ border-top: 1px solid {LINIA}; }}")

        if wynik.kategoria == KAT_SUKCES:
            uklad_zewn = QVBoxLayout(self)
            uklad_zewn.setContentsMargins(16, 11, 16, 11)
            uklad_zewn.setSpacing(6)

            uklad = QHBoxLayout()
            uklad.setSpacing(12)
            uklad_zewn.addLayout(uklad)

            awatar = QLabel(_inicjaly(wynik.nazwa_obiektu or "?"))
            awatar.setFixedSize(30, 30)
            awatar.setAlignment(Qt.AlignCenter)
            awatar.setStyleSheet(
                f"background: {KORAL_TLO}; color: {KORAL_GLEBOKI}; border-radius: 15px; "
                f"font-size: 11.5px; font-weight: 700; border: none; font-family: {CZCIONKA_NAGLOWEK};"
            )
            uklad.addWidget(awatar)

            info = QVBoxLayout()
            info.setSpacing(1)
            wiersz_nazwy = QHBoxLayout()
            wiersz_nazwy.setSpacing(7)
            nazwa = _selectable(QLabel(wynik.nazwa_obiektu or "-"))
            nazwa.setStyleSheet(
                f"background: transparent; color: {ATRAMENT}; font-weight: 700; font-size: 13.5px; border: none; "
                f"font-family: {CZCIONKA_NAGLOWEK};"
            )
            wiersz_nazwy.addWidget(nazwa)
            if wynik.arkusz == SHEET_NAME_ODDANA:
                ikona_pv = QLabel("☀")
                ikona_pv.setStyleSheet(f"background: transparent; color: {SLONCE_GLEBOKIE}; font-size: 11px; border: none;")
                plakietka_uklad = QHBoxLayout()
                plakietka_uklad.setContentsMargins(7, 2, 9, 2)
                plakietka_uklad.setSpacing(4)
                plakietka = QFrame()
                plakietka.setStyleSheet(f"background: {SLONCE_TLO}; border-radius: 9px; border: none;")
                plakietka.setLayout(plakietka_uklad)
                plakietka_uklad.addWidget(ikona_pv)
                tekst_pv = QLabel("fotowoltaika")
                tekst_pv.setStyleSheet(
                    f"background: transparent; color: {SLONCE_GLEBOKIE}; font-size: 10.5px; font-weight: 700; "
                    f"border: none; font-family: {CZCIONKA_NAGLOWEK};"
                )
                plakietka_uklad.addWidget(tekst_pv)
                wiersz_nazwy.addWidget(plakietka)
            wiersz_nazwy.addStretch()
            info.addLayout(wiersz_nazwy)

            ppe = _selectable(QLabel(f"PPE {wynik.ppe}" if wynik.ppe else "-"))
            ppe.setStyleSheet(f"background: transparent; color: {BLADY}; font-size: 11.5px; border: none; font-family: {CZCIONKA_MONO};")
            info.addWidget(ppe)
            uklad.addLayout(info, stretch=1)

            okres = _selectable(QLabel(_formatuj_okres(wynik.okres_od, wynik.okres_do)))
            okres.setAlignment(Qt.AlignRight)
            okres.setStyleSheet(f"background: transparent; color: {STONOWANY}; font-size: 12px; font-weight: 600; border: none;")
            uklad.addWidget(okres)

            if wynik.wartosci:
                pozycje = list(wynik.wartosci.items())
                # Przy 3-strefowej pozycji (P-S3 obecne, np. Chwałkowo na Dużych odbiorach) wiersz z
                # kompletem chipów (z "kWh" przy każdej strefie) nie mieści się w minimalnej
                # szerokości okna appki (zweryfikowane pomiarem) - rozbijamy wtedy na strefy
                # (P-S1/P-S2/P-S3) i sumy (Razem/Dystrybucja).
                if "P-S3" in wynik.wartosci:
                    uklad_zewn.addLayout(_wiersz_chipow(pozycje[:3]))
                    if pozycje[3:]:
                        uklad_zewn.addLayout(_wiersz_chipow(pozycje[3:]))
                else:
                    uklad_zewn.addLayout(_wiersz_chipow(pozycje))
            return

        czy_ostrzezenie = wynik.kategoria != KAT_JUZ_WYPELNIONE
        tlo_ikony = SLONCE_TLO if czy_ostrzezenie else POWIERZCHNIA_MIEKKA
        kolor_ikony = SLONCE_GLEBOKIE if czy_ostrzezenie else STONOWANY
        znak = "!" if czy_ostrzezenie else "✓"

        self.setStyleSheet(
            f"WierszObiektu {{ background: {SLONCE_TLO if czy_ostrzezenie else POWIERZCHNIA_MIEKKA}; "
            f"border-top: 1px solid {LINIA}; }}"
        )
        uklad = QHBoxLayout(self)
        uklad.setContentsMargins(16, 11, 16, 11)
        uklad.setSpacing(11)

        ikona = QLabel(znak)
        ikona.setFixedSize(24, 24)
        ikona.setAlignment(Qt.AlignCenter)
        ikona.setStyleSheet(
            f"background: {tlo_ikony}; color: {kolor_ikony}; border-radius: 12px; font-weight: 700; "
            "font-size: 12px; border: none;"
        )
        uklad.addWidget(ikona, alignment=Qt.AlignTop)

        etykieta = ETYKIETY_KATEGORII.get(wynik.kategoria, "Już wypełnione")
        ppe_czesc = f" (PPE {wynik.ppe})" if wynik.ppe else ""
        tekst = _selectable(QLabel(f"<b>{etykieta}{ppe_czesc}:</b> {wynik.opis or ''}"))
        tekst.setTextFormat(Qt.RichText)
        tekst.setWordWrap(True)
        tekst.setStyleSheet(
            f"background: transparent; color: {ATRAMENT}; font-size: 12.5px; border: none; font-family: {CZCIONKA_TEKST};"
        )
        uklad.addWidget(tekst, stretch=1)


class KartaFaktury(QFrame):
    def __init__(
        self,
        nazwa_pliku: str,
        czas: datetime | None,
        blad: str | None,
        wyniki: list[WynikWpisu],
        domyslnie_zwinieta: bool,
        wpis_id: int | None = None,
        on_usun: Callable[[int], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._zwinieta = domyslnie_zwinieta
        uklad = QVBoxLayout(self)
        uklad.setContentsMargins(0, 0, 0, 0)
        uklad.setSpacing(0)

        przycisk_usun = None
        if wpis_id is not None and on_usun is not None:
            przycisk_usun = _przycisk_usuwania("Usuń z historii")
            przycisk_usun.clicked.connect(lambda: on_usun(wpis_id))

        if blad is not None:
            self.setStyleSheet(f"KartaFaktury {{ background: {POWIERZCHNIA}; border: 1px solid {CZERWIEN}; border-radius: 18px; }}")
            naglowek = self._zbuduj_naglowek(
                nazwa_pliku, czas, "✕", CZERWIEN, "faktura nierozpoznana",
                przycisk_usun=przycisk_usun,
            )
            naglowek.setCursor(Qt.ArrowCursor)
            uklad.addWidget(naglowek)

            powod = _selectable(QLabel(
                f"{blad}"
                f"<br><span style='color:{STONOWANY};'>Plik został w folderze źródłowym.</span>"
            ))
            powod.setTextFormat(Qt.RichText)
            powod.setWordWrap(True)
            powod.setStyleSheet(
                f"background: transparent; color: {CZERWIEN_GLEBOKA}; font-size: 12.5px; font-family: {CZCIONKA_TEKST}; "
                "padding: 4px 18px 14px 62px; border: none;"
            )
            uklad.addWidget(powod)
            return

        self.setStyleSheet(f"KartaFaktury {{ background: {POWIERZCHNIA}; border: 1px solid {LINIA}; border-radius: 18px; }}")
        sukcesy = sum(1 for w in wyniki if w.kategoria == KAT_SUKCES)
        problemy = len(wyniki) - sukcesy
        podsumowanie = (
            f"{sukcesy}/{len(wyniki)} obiektów, {problemy} do sprawdzenia" if problemy else f"{len(wyniki)} obiektów"
        )
        naglowek = self._zbuduj_naglowek(
            nazwa_pliku, czas,
            "!" if problemy else "✓", SLONCE_GLEBOKIE if problemy else ZIELEN_GLEBOKA,
            _formatuj_meta(wyniki), podsumowanie, tlo_znacznika=SLONCE_TLO if problemy else ZIELEN_TLO,
            przycisk_usun=przycisk_usun,
        )
        naglowek.mousePressEvent = lambda _e: self._przelacz_zwiniecie()
        naglowek.setCursor(Qt.PointingHandCursor)
        uklad.addWidget(naglowek)

        self._kontener_wierszy = QWidget()
        uklad_wierszy = QVBoxLayout(self._kontener_wierszy)
        uklad_wierszy.setContentsMargins(0, 0, 0, 0)
        uklad_wierszy.setSpacing(0)
        for wynik in wyniki:
            uklad_wierszy.addWidget(WierszObiektu(wynik))
        uklad.addWidget(self._kontener_wierszy)

        self._odswiez_zwiniecie()

    def _zbuduj_naglowek(
        self, nazwa_pliku, czas, znak, kolor_znaku, meta, podsumowanie=None, tlo_znacznika=None, przycisk_usun=None
    ) -> QFrame:
        naglowek = QFrame()
        naglowek.setStyleSheet("background: transparent; border: none;")
        uklad = QHBoxLayout(naglowek)
        uklad.setContentsMargins(16, 13, 14, 13)
        uklad.setSpacing(12)

        znacznik = QLabel(znak)
        znacznik.setFixedSize(30, 30)
        znacznik.setAlignment(Qt.AlignCenter)
        tlo = tlo_znacznika or (CZERWIEN_TLO if kolor_znaku == CZERWIEN else ZIELEN_TLO)
        znacznik.setStyleSheet(
            f"background: {tlo}; color: {kolor_znaku}; border-radius: 15px; font-size: 13px; font-weight: 700; border: none;"
        )
        uklad.addWidget(znacznik)

        nazwa = _selectable(QLabel(nazwa_pliku))
        nazwa.setStyleSheet(
            f"background: transparent; font-weight: 700; font-size: 13.5px; border: none; color: {ATRAMENT}; "
            f"font-family: {CZCIONKA_NAGLOWEK};"
        )
        uklad.addWidget(nazwa)

        info_meta = QLabel(f"{_formatuj_czas(czas)} · {meta}" if podsumowanie else meta)
        info_meta.setStyleSheet(f"background: transparent; color: {BLADY}; font-size: 12px; border: none; font-family: {CZCIONKA_TEKST};")
        uklad.addWidget(info_meta)
        uklad.addStretch()

        if podsumowanie:
            podsumowanie_label = QLabel(podsumowanie)
            podsumowanie_label.setStyleSheet(
                f"background: transparent; color: {STONOWANY}; font-size: 12px; font-weight: 600; border: none; "
                f"font-family: {CZCIONKA_TEKST};"
            )
            uklad.addWidget(podsumowanie_label)
            self._szewron = QLabel("▾")
            self._szewron.setStyleSheet(f"background: transparent; color: {BLADY}; font-size: 12px; border: none;")
            uklad.addWidget(self._szewron)
        if przycisk_usun is not None:
            uklad.addWidget(przycisk_usun)
        return naglowek

    def _przelacz_zwiniecie(self) -> None:
        self._zwinieta = not self._zwinieta
        self._odswiez_zwiniecie()

    def _odswiez_zwiniecie(self) -> None:
        self._kontener_wierszy.setVisible(not self._zwinieta)
        if hasattr(self, "_szewron"):
            self._szewron.setText("▸" if self._zwinieta else "▾")


def _karta_z_wyniku_pliku(wynik: WynikPrzetworzeniaPliku, domyslnie_zwinieta: bool) -> KartaFaktury:
    return KartaFaktury(wynik.sciezka.name, datetime.now(), wynik.blad, wynik.wyniki, domyslnie_zwinieta)


def _karta_z_wpisu_historii(
    wpis: WpisHistorii, domyslnie_zwinieta: bool, on_usun: Callable[[int], None]
) -> KartaFaktury:
    return KartaFaktury(
        wpis.nazwa_pliku, wpis.czas, wpis.powod_odrzucenia if wpis.nierozpoznana else None, wpis.pozycje,
        domyslnie_zwinieta, wpis_id=wpis.id, on_usun=on_usun,
    )


class ZrodloDanych(QFrame):
    """Jedna karta źródła (plik excel / folder faktur) - ikona + etykieta + wartość + przycisk zmiany."""

    def __init__(self, ikona_znak: str, ikona_tlo: str, ikona_kolor: str, etykieta: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"ZrodloDanych {{ background: {POWIERZCHNIA}; border: 1px solid {LINIA}; border-radius: 16px; }}")
        uklad = QHBoxLayout(self)
        uklad.setContentsMargins(13, 11, 11, 11)
        uklad.setSpacing(11)

        znak = QLabel(ikona_znak)
        znak.setFixedSize(36, 36)
        znak.setAlignment(Qt.AlignCenter)
        znak.setStyleSheet(f"background: {ikona_tlo}; color: {ikona_kolor}; border-radius: 11px; font-size: 15px; border: none;")
        uklad.addWidget(znak)

        info = QVBoxLayout()
        info.setSpacing(1)
        etykieta_label = QLabel(etykieta)
        etykieta_label.setStyleSheet(
            f"background: transparent; color: {BLADY}; font-size: 10.5px; font-weight: 700; "
            "text-transform: uppercase; border: none;"
        )
        info.addWidget(etykieta_label)
        self.wartosc = _selectable(EtykietaSciezki())
        self.wartosc.setStyleSheet(
            f"background: transparent; color: {ATRAMENT}; font-size: 13px; font-weight: 600; border: none; "
            f"font-family: {CZCIONKA_MONO};"
        )
        info.addWidget(self.wartosc)
        uklad.addLayout(info, stretch=1)

        self.przycisk_zmien = QPushButton("Zmień")
        self.przycisk_zmien.setCursor(Qt.PointingHandCursor)
        self.przycisk_zmien.setStyleSheet(przycisk_pill(POWIERZCHNIA, ZIELEN_GLEBOKA, ZIELEN_TLO, LINIA, "11.5px"))
        uklad.addWidget(self.przycisk_zmien)


class WidokUzupelnijExcel(QWidget):
    def __init__(
        self,
        kontroler_faktur: KontrolerFaktur,
        kontroler_excela: Kontroler,
        parent=None,
    ):
        super().__init__(parent)
        self._kontroler = kontroler_faktur
        self._kontroler_excela = kontroler_excela
        self.setStyleSheet(f"QWidget {{ background: {PAPIER}; }}")

        uklad_glowny = QVBoxLayout(self)
        uklad_glowny.setContentsMargins(0, 0, 0, 0)
        uklad_glowny.setSpacing(0)

        obszar = QScrollArea()
        obszar.setWidgetResizable(True)
        obszar.setStyleSheet(STYL_SUWAKA)
        tresc = QWidget()
        tresc.setStyleSheet(f"background: {PAPIER};")
        self._uklad_tresci = QVBoxLayout(tresc)
        self._uklad_tresci.setContentsMargins(24, 22, 24, 26)
        self._uklad_tresci.setSpacing(8)

        self._uklad_tresci.addWidget(self._zbuduj_naglowek_strony())
        self._uklad_tresci.addSpacing(14)
        self._uklad_tresci.addWidget(self._zbuduj_zrodla())
        self._uklad_tresci.addSpacing(14)

        self._strefa = StrefaUpuszczania()
        self._strefa.pliki_upuszczone.connect(self._na_pliki_wybrane)
        self._strefa.przycisk_wybierz.clicked.connect(self._na_klik_wybierz_pliki)
        self._uklad_tresci.addWidget(self._strefa)
        self._uklad_tresci.addSpacing(10)

        self._kontener_kolejki = QWidget()
        self._uklad_kolejki = QVBoxLayout(self._kontener_kolejki)
        self._uklad_kolejki.setContentsMargins(0, 0, 0, 0)
        self._uklad_kolejki.setSpacing(7)
        self._uklad_tresci.addWidget(self._kontener_kolejki)

        rzad_akcji = QHBoxLayout()
        rzad_akcji.setSpacing(10)
        self._przycisk_uzupelnij = QPushButton("Uzupełnij Excel")
        self._przycisk_uzupelnij.setToolTip("Wpisz faktury do pliku excel")
        self._przycisk_uzupelnij.setCursor(Qt.PointingHandCursor)
        self._przycisk_uzupelnij.setStyleSheet(przycisk_pill(ZIELEN, "white", ZIELEN_GLEBOKA, rozmiar="13.5px"))
        self._przycisk_uzupelnij.clicked.connect(self._na_klik_uzupelnij)
        rzad_akcji.addWidget(self._przycisk_uzupelnij)

        self._przycisk_sprawdz = QPushButton("Sprawdź")
        self._przycisk_sprawdz.setToolTip("Sprawdź czy w katalogu znajdują się faktury do wpisania")
        self._przycisk_sprawdz.setCursor(Qt.PointingHandCursor)
        self._przycisk_sprawdz.setStyleSheet(przycisk_pill(POWIERZCHNIA, ATRAMENT, POWIERZCHNIA_MIEKKA, LINIA, "13.5px"))
        self._przycisk_sprawdz.clicked.connect(self._na_klik_sprawdz)
        rzad_akcji.addWidget(self._przycisk_sprawdz)

        self._podpowiedz_akcji = QLabel("")
        self._podpowiedz_akcji.setStyleSheet(f"color: {STONOWANY}; font-size: 12.5px; font-family: {CZCIONKA_TEKST};")
        rzad_akcji.addWidget(self._podpowiedz_akcji)
        rzad_akcji.addStretch()
        self._uklad_tresci.addLayout(rzad_akcji)

        self._naglowek_swiezo = self._zbuduj_naglowek_sekcji("Uzupełnione dane", ze_znacznikiem=True)
        self._naglowek_swiezo.hide()
        self._uklad_tresci.addWidget(self._naglowek_swiezo)
        self._kontener_swiezo = QWidget()
        self._uklad_swiezo = QVBoxLayout(self._kontener_swiezo)
        self._uklad_swiezo.setContentsMargins(0, 0, 0, 0)
        self._uklad_swiezo.setSpacing(10)
        self._kontener_swiezo.hide()
        self._uklad_tresci.addWidget(self._kontener_swiezo)

        self._naglowek_historii = self._zbuduj_naglowek_sekcji("Ostatnio wpisane", ze_znacznikiem=False)
        self._naglowek_historii.hide()
        self._uklad_tresci.addWidget(self._naglowek_historii)
        self._kontener_historii = QWidget()
        self._uklad_historii = QVBoxLayout(self._kontener_historii)
        self._uklad_historii.setContentsMargins(0, 0, 0, 0)
        self._uklad_historii.setSpacing(10)
        self._kontener_historii.hide()
        self._uklad_tresci.addWidget(self._kontener_historii)

        self._uklad_tresci.addStretch()
        obszar.setWidget(tresc)
        uklad_glowny.addWidget(obszar, stretch=1)

        self._kontroler.kolejka_zmieniona.connect(self._odswiez_kolejke)
        self._kontroler.zakonczono_przetwarzanie.connect(self._na_zakonczone_przetwarzanie)
        self._kontroler.historia_zmieniona.connect(self._odswiez_historie)
        self._kontroler.w_trakcie.connect(self._na_w_trakcie)
        self._kontroler.blad.connect(self._na_blad)
        self._kontroler_excela.zmiana.connect(lambda _grupy: self._odswiez_pasek_excela())

        self._odswiez_pasek_excela()
        self._odswiez_pasek_folderu()
        self._odswiez_kolejke(self._kontroler.kolejka())
        self._odswiez_historie(self._kontroler.historia_ostatnich())

    def showEvent(self, event) -> None:
        # Uzytkownik moze recznie wrzucic plik do "Do wpisania"/"Do aktualizacji" przez Eksplorator
        # (np. celowo do "Do aktualizacji", zeby wymusic nadpisanie) - odswiezamy kolejke za kazdym
        # razem, gdy ta zakladka staje sie widoczna, zeby przycisk "Uzupelnij Excel" to zauwazyl.
        super().showEvent(event)
        self._odswiez_kolejke(self._kontroler.kolejka())

    def _zbuduj_naglowek_strony(self) -> QWidget:
        blok = QWidget()
        uklad = QVBoxLayout(blok)
        uklad.setContentsMargins(0, 0, 0, 0)
        uklad.setSpacing(3)

        tytul = QLabel("Wrzuć dzisiejsze faktury")
        tytul.setStyleSheet(
            f"color: {ATRAMENT}; font-size: 21px; font-weight: 700; font-family: {CZCIONKA_NAGLOWEK};"
        )
        uklad.addWidget(tytul)

        opis = QLabel("Rozpoznamy obiekty po numerze PPE i sami wpiszemy dane do arkusza — Ty tylko przejrzysz wynik.")
        opis.setWordWrap(True)
        opis.setStyleSheet(f"color: {STONOWANY}; font-size: 13px; font-family: {CZCIONKA_TEKST};")
        uklad.addWidget(opis)
        return blok

    def _zbuduj_zrodla(self) -> QWidget:
        blok = QWidget()
        uklad = QHBoxLayout(blok)
        uklad.setContentsMargins(0, 0, 0, 0)
        uklad.setSpacing(12)

        self._zrodlo_excela = ZrodloDanych("📄", ZIELEN_TLO, ZIELEN_GLEBOKA, "Plik excel")
        self._zrodlo_excela.przycisk_zmien.clicked.connect(self._na_klik_zmien_plik_excela)
        uklad.addWidget(self._zrodlo_excela, stretch=1)
        # zachowane dla zgodności - reszta appki/testów odwołuje się do etykiety wartości bezpośrednio
        self._etykieta_excela = self._zrodlo_excela.wartosc

        self._zrodlo_folderu = ZrodloDanych("📁", KORAL_TLO, KORAL_GLEBOKI, "Folder faktur")
        self._zrodlo_folderu.przycisk_zmien.clicked.connect(self._na_klik_zmien_folder)
        uklad.addWidget(self._zrodlo_folderu, stretch=1)
        self._etykieta_folderu = self._zrodlo_folderu.wartosc

        return blok

    def _odswiez_pasek_excela(self) -> None:
        if self._kontroler_excela.sciezka is not None:
            self._etykieta_excela.setText(self._kontroler_excela.sciezka.name)
        else:
            self._etykieta_excela.setText("nie wybrano")
        self._odswiez_stan_przycisku()

    def _na_klik_zmien_plik_excela(self) -> None:
        sciezka, _ = QFileDialog.getOpenFileName(self, "Wybierz plik Excel", "", "Excel (*.xlsx)")
        if not sciezka:
            return
        try:
            self._kontroler_excela.ustaw_plik(sciezka)
        except NieRozpoznanoRoku as exc:
            QMessageBox.warning(self, "Nie rozpoznano roku", str(exc))
            return
        self._odswiez_pasek_excela()

    def _zbuduj_naglowek_sekcji(self, tekst: str, ze_znacznikiem: bool) -> QWidget:
        pasek = QFrame()
        uklad = QHBoxLayout(pasek)
        uklad.setContentsMargins(2, 18, 0, 6)
        uklad.setSpacing(9)
        if ze_znacznikiem:
            kropka = QLabel()
            kropka.setFixedSize(8, 8)
            kropka.setStyleSheet(f"background: {ZIELEN}; border-radius: 4px;")
            uklad.addWidget(kropka)
        etykieta = QLabel(tekst)
        etykieta.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {ATRAMENT}; font-family: {CZCIONKA_NAGLOWEK};")
        uklad.addWidget(etykieta)
        if ze_znacznikiem:
            znacznik = QLabel("TERAZ")
            znacznik.setStyleSheet(
                f"color: {ZIELEN_GLEBOKA}; font-size: 11px; font-weight: 700; font-family: {CZCIONKA_NAGLOWEK};"
            )
            uklad.addWidget(znacznik)
        uklad.addStretch()
        return pasek

    def _odswiez_pasek_folderu(self) -> None:
        if self._kontroler.folder is not None:
            self._etykieta_folderu.setText(str(self._kontroler.folder))
        else:
            self._etykieta_folderu.setText("nie wybrano")

    def _na_klik_zmien_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Wybierz folder faktur")
        if not folder:
            return
        self._kontroler.ustaw_folder(folder)
        self._odswiez_pasek_folderu()

    def _na_klik_wybierz_pliki(self) -> None:
        sciezki, _ = QFileDialog.getOpenFileNames(self, "Wybierz faktury", "", "PDF (*.pdf)")
        if sciezki:
            self._na_pliki_wybrane(sciezki)

    def _na_pliki_wybrane(self, sciezki: list[str]) -> None:
        if self._kontroler.folder is None:
            QMessageBox.warning(self, "Nie wybrano folderu", "Najpierw wybierz folder faktur.")
            return
        self._kontroler.dodaj_pliki_do_kolejki(sciezki)

    def _odswiez_kolejke(self, kolejka: list[Path]) -> None:
        while self._uklad_kolejki.count():
            widget = self._uklad_kolejki.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        for sciezka in kolejka:
            wiersz = WierszKolejki(sciezka)
            wiersz.usun_kliknieto.connect(self._kontroler.usun_z_kolejki)
            self._uklad_kolejki.addWidget(wiersz)

        if kolejka:
            self._podpowiedz_akcji.setText(
                f"{len(kolejka)} {'faktura czeka' if len(kolejka) == 1 else 'faktury czekają'} na wpisanie"
            )
        else:
            self._podpowiedz_akcji.setText("")
        self._odswiez_stan_przycisku()

    def _odswiez_stan_przycisku(self, w_trakcie: bool = False) -> None:
        gotowe = bool(self._kontroler.kolejka()) and self._kontroler_excela.sciezka is not None
        self._przycisk_uzupelnij.setEnabled(not w_trakcie and gotowe)
        self._przycisk_uzupelnij.setText("Przetwarzanie..." if w_trakcie else "Uzupełnij Excel")

    def _na_klik_uzupelnij(self) -> None:
        sciezka_excel = self._kontroler_excela.sciezka
        if sciezka_excel is None:
            QMessageBox.warning(self, "Nie wybrano pliku Excel", "Najpierw wybierz plik Excel.")
            return
        if self._kontroler_excela.czy_plik_otwarty():
            QMessageBox.warning(
                self, "Plik Excel jest otwarty",
                "Zamknij plik Excel przed wpisaniem faktur - zapis w otwartym Excelu mógłby zostać "
                "później nadpisany, gdy Excel sam zapisze swoją (nieaktualną) wersję pliku.",
            )
            return
        self._kontroler.przetworz_w_tle(sciezka_excel)

    def _na_klik_sprawdz(self) -> None:
        self._odswiez_kolejke(self._kontroler.kolejka())

    def _na_w_trakcie(self, w_trakcie: bool) -> None:
        self._odswiez_stan_przycisku(w_trakcie)

    def _na_blad(self, tresc: str) -> None:
        QMessageBox.warning(self, "Coś poszło nie tak", tresc)

    def _na_zakonczone_przetwarzanie(self, wyniki: list[WynikPrzetworzeniaPliku]) -> None:
        while self._uklad_swiezo.count():
            widget = self._uklad_swiezo.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        for wynik in wyniki:
            self._uklad_swiezo.addWidget(_karta_z_wyniku_pliku(wynik, domyslnie_zwinieta=False))

        pokazuj = bool(wyniki)
        self._naglowek_swiezo.setVisible(pokazuj)
        self._kontener_swiezo.setVisible(pokazuj)

    def odswiez_widocznosc_historii(self, zalogowany: bool) -> None:
        """"Ostatnio wpisane" jest per konto - sekcja ma sens tylko dla zalogowanego usera (patrz
        GlowneOkno._synchronizuj_historie_faktur w window.py, wywoływane przy starcie okna i po
        każdym zalogowaniu/wylogowaniu)."""
        self._naglowek_historii.setVisible(zalogowany)
        self._kontener_historii.setVisible(zalogowany)

    def _odswiez_historie(self, wpisy: list[WpisHistorii]) -> None:
        while self._uklad_historii.count():
            widget = self._uklad_historii.takeAt(0).widget()
            if widget:
                widget.deleteLater()
        if not wpisy:
            pusty = QLabel("Brak historii - wpisane faktury pojawią się tutaj.")
            pusty.setStyleSheet(f"color: {BLADY}; font-size: 12.5px; font-family: {CZCIONKA_TEKST};")
            self._uklad_historii.addWidget(pusty)
            return
        for wpis in wpisy:
            self._uklad_historii.addWidget(
                _karta_z_wpisu_historii(wpis, domyslnie_zwinieta=True, on_usun=self._kontroler.usun_z_historii)
            )
