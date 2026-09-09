"""Główne okno aplikacji: dwie zakładki - 'Uzupełnienie faktur' (główna, domyślna) i 'Weryfikacja'
(dotychczasowa funkcjonalność, teraz drugorzędna). Patrz widok_uzupelnij_excel.py / widok_weryfikacji.py
dla zawartości każdej z nich - to okno tylko je hostuje razem z paskiem logowania/zakładek/stopką,
które są wspólne dla całej appki, nie konkretnej zakładki."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.aktualizacje import REPO_GITHUB, SprawdzarkaAktualizacji, Wydanie
from app.aktualizator import Instalator, uruchom_ponownie
from app.firmy import Firma
from app.historia_faktur_base import PustyMagazynHistorii
from app.kontroler import Kontroler
from app.kontroler_faktur import KontrolerFaktur
from app.login_dialog import OknoLogowania
from app.styl import (
    ATRAMENT,
    BLADY,
    CZCIONKA_NAGLOWEK,
    CZCIONKA_TEKST,
    LINIA,
    PAPIER,
    POWIERZCHNIA,
    POWIERZCHNIA_MIEKKA,
    SLONCE,
    SLONCE_GLEBOKIE,
    STONOWANY,
    ZIELEN,
    ZIELEN_GLEBOKA,
    ZIELEN_TLO,
    przycisk_pill,
)
from app.supabase_historia_store import SupabaseHistoriaFakturStore
from app.supabase_store import BledneDaneLogowania
from app.wersja import CHANGELOG, WERSJA
from app.widok_uzupelnij_excel import WidokUzupelnijExcel
from app.widok_weryfikacji import WidokWeryfikacji

ZAKLADKA_UZUPELNIJ = 0
ZAKLADKA_WERYFIKACJA = 1


class OknoChangelog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Excel Helper — wersja {WERSJA}")
        self.setMinimumWidth(360)

        uklad = QVBoxLayout(self)
        tytul = QLabel(f"Excel Helper {WERSJA}")
        tytul.setStyleSheet("font-size: 15px; font-weight: 700;")
        uklad.addWidget(tytul)

        for wpis in CHANGELOG:
            naglowek = QLabel(f"{wpis['wersja']} — {wpis['data']}")
            naglowek.setStyleSheet("font-size: 13px; font-weight: 600; margin-top: 8px;")
            uklad.addWidget(naglowek)
            for zmiana in wpis["zmiany"]:
                pozycja = QLabel(f"• {zmiana}")
                pozycja.setWordWrap(True)
                pozycja.setStyleSheet("font-size: 13px; color: #444441;")
                uklad.addWidget(pozycja)

        zamknij = QPushButton("Zamknij")
        zamknij.clicked.connect(self.accept)
        uklad.addWidget(zamknij)


class GlowneOkno(QMainWindow):
    pokaz_zadanie = Signal()

    def __init__(self, pary: list[tuple[Firma, Kontroler, KontrolerFaktur]]):
        """`pary` - jedna (Firma, Kontroler, KontrolerFaktur) na każdą obsługiwaną firmę (patrz
        app/firmy.py), w kolejności wyświetlania w przełączniku firm. Logowanie/synchronizacja są
        WSPÓLNE dla wszystkich firm (świadoma decyzja użytkownika - to jedna spójna appka, nie
        odizolowane profile) - stąd `_kontroler_glowny` (pierwsza firma) jako źródło prawdy o
        stanie logowania, propagowanym do pozostałych firm przy każdej zmianie (patrz
        _na_klik_zaloguj/_na_klik_wyloguj/_synchronizuj_historie_faktur)."""
        super().__init__()
        self._pary = pary
        self._kontroler_glowny = pary[0][1]

        self.setWindowTitle("Excel Helper")
        self.resize(800, 720)
        self.setStyleSheet(f"QMainWindow {{ background: {PAPIER}; }}")

        centralny = QWidget()
        self.setCentralWidget(centralny)
        uklad = QVBoxLayout(centralny)
        uklad.setContentsMargins(0, 0, 0, 0)
        uklad.setSpacing(0)

        uklad.addWidget(self._zbuduj_pasek_aktualizacji())
        uklad.addWidget(self._zbuduj_pasmo_tozsamosci())
        uklad.addWidget(self._zbuduj_pasek_firm())

        self._widoki: dict[str, dict] = {}
        self._stos_firm = QStackedWidget()
        for firma, kontroler, kontroler_faktur in pary:
            strona, dane = self._zbuduj_strone_firmy(firma, kontroler, kontroler_faktur)
            self._stos_firm.addWidget(strona)
            self._widoki[firma.id] = dane
        self._stos_firm.setCurrentIndex(0)
        uklad.addWidget(self._stos_firm, stretch=1)

        uklad.addWidget(self._zbuduj_stopke())

        self.pokaz_zadanie.connect(self._na_pokaz_zadanie)
        self._odswiez_przycisk_logowania()
        self._synchronizuj_historie_faktur()

        self._instalator = Instalator()
        self._instalator.zakonczono.connect(self._na_instalacja_zakonczona)
        self._instalator.blad.connect(self._na_blad_instalacji)

        self._sprawdzarka_aktualizacji = SprawdzarkaAktualizacji()
        self._sprawdzarka_aktualizacji.znaleziono_nowsza.connect(self._na_znaleziono_nowsza_wersje)
        self._sprawdzarka_aktualizacji.sprawdz_w_tle(WERSJA, REPO_GITHUB)

    def _zbuduj_pasek_aktualizacji(self) -> QWidget:
        # Ukryty dopoki SprawdzarkaAktualizacji faktycznie nie znajdzie nowszej wersji niz WERSJA -
        # patrz REPO_GITHUB w aktualizacje.py (wymaga publicznego repo + opublikowanego GitHub
        # Release z tagiem wyzszym niz WERSJA, inaczej pasek sie nie pokaze).
        self._pasek_aktualizacji = QFrame()
        self._pasek_aktualizacji.setStyleSheet(f"background: {SLONCE};")
        self._pasek_aktualizacji.hide()
        uklad = QHBoxLayout(self._pasek_aktualizacji)
        uklad.setContentsMargins(20, 9, 20, 9)

        self._etykieta_aktualizacji = QLabel("")
        self._etykieta_aktualizacji.setStyleSheet(
            f"background: transparent; color: white; font-size: 12.5px; font-family: {CZCIONKA_TEKST};"
        )
        uklad.addWidget(self._etykieta_aktualizacji)
        uklad.addStretch()

        self._przycisk_zainstaluj = QPushButton("Zainstaluj")
        self._przycisk_zainstaluj.setCursor(Qt.PointingHandCursor)
        self._przycisk_zainstaluj.setStyleSheet(
            "QPushButton { background: white; border: none; border-radius: 14px; padding: 6px 16px; "
            f"color: {SLONCE_GLEBOKIE}; font-size: 12px; font-weight: 700; font-family: {CZCIONKA_NAGLOWEK}; }}"
            "QPushButton:hover:enabled { background: #fff6e6; }"
            "QPushButton:disabled { background: #fbe3ba; color: #a37b3e; }"
        )
        self._przycisk_zainstaluj.clicked.connect(self._na_klik_zainstaluj)
        uklad.addWidget(self._przycisk_zainstaluj)
        return self._pasek_aktualizacji

    def _na_znaleziono_nowsza_wersje(self, wydanie: Wydanie) -> None:
        self._wydanie_do_instalacji = wydanie
        self._etykieta_aktualizacji.setText(f"Dostępna nowa wersja {wydanie.wersja}")
        self._pasek_aktualizacji.show()

    def _na_klik_zainstaluj(self) -> None:
        self._przycisk_zainstaluj.setEnabled(False)
        self._przycisk_zainstaluj.setText("Instalowanie...")
        self._instalator.instaluj_w_tle(self._wydanie_do_instalacji.url_zip)

    def _na_instalacja_zakonczona(self) -> None:
        # Restart natychmiast, bez pytania - nowy kod jest juz na dysku, ale ten proces dalej
        # dziala na starym (zaladowanym do pamieci), wiec musi ustapic miejsca nowemu.
        uruchom_ponownie()
        QApplication.instance().quit()

    def _na_blad_instalacji(self, tresc: str) -> None:
        self._przycisk_zainstaluj.setEnabled(True)
        self._przycisk_zainstaluj.setText("Zainstaluj")
        QMessageBox.warning(self, "Nie udało się zainstalować aktualizacji", tresc)

    def _zbuduj_pasmo_tozsamosci(self) -> QWidget:
        # Osobny, najwyzszy pasek - logowanie/synchronizacja dotyczy calej appki, nie konkretnej
        # zakladki, wiec zyje POZA obszarem zakladek. Niesie tez marke appki (dawniej widoczna
        # tylko w tytule okna).
        pasmo = QFrame()
        pasmo.setObjectName("pasmoTozsamosci")
        # Selektor QUALIFIKOWANY nazwą obiektu (#pasmoTozsamosci), nie goły "background: ...;" -
        # goły border-bottom bez selektora w Qt Style Sheets potrafi "przeciekać" na dzieci bez
        # własnej ramki (np. etykietę marki) i wyjść jako fałszywe podkreślenie pod tekstem.
        pasmo.setStyleSheet(f"QFrame#pasmoTozsamosci {{ background: {POWIERZCHNIA}; border-bottom: 1px solid {LINIA}; }}")
        uklad = QHBoxLayout(pasmo)
        uklad.setContentsMargins(22, 14, 22, 14)
        uklad.setSpacing(12)

        znak = QLabel("🧾")
        znak.setFixedSize(38, 38)
        znak.setAlignment(Qt.AlignCenter)
        znak.setStyleSheet(f"background: {ZIELEN}; border-radius: 12px; font-size: 17px;")
        uklad.addWidget(znak)

        marka = QLabel("Excel Helper")
        marka.setStyleSheet(
            f"background: transparent; color: {ATRAMENT}; font-size: 17px; font-weight: 700; "
            f"font-family: {CZCIONKA_NAGLOWEK}; border: none;"
        )
        uklad.addWidget(marka)

        uklad.addStretch()
        self._przycisk_zaloguj = QPushButton("Zaloguj (synchronizacja)")
        self._przycisk_zaloguj.setCursor(Qt.PointingHandCursor)
        self._przycisk_zaloguj.clicked.connect(self._na_klik_zaloguj)
        uklad.addWidget(self._przycisk_zaloguj)
        self._przycisk_konto = QPushButton("")
        self._przycisk_konto.setCursor(Qt.PointingHandCursor)
        self._przycisk_konto.clicked.connect(self._pokaz_menu_konta)
        self._przycisk_konto.hide()
        uklad.addWidget(self._przycisk_konto)
        return pasmo

    def _zbuduj_pasek_firm(self) -> QWidget:
        """Przełącznik firm (MPECWIK/UK, patrz app/firmy.py) - NAD zakładkami Uzupełnienie/Weryfikacja
        każdej firmy, bo to appka wspólna dla obu, tylko z różnymi obiektami/plikami pod spodem.

        Celowo płaski (kropka + podkreślenie w kolorze firmy, `Firma.akcent`), NIE pigułkowy jak
        zakładki pod spodem - żeby te dwa poziomy przełączników nie wyglądały jak jeden i ten sam
        rodzaj kontrolki (makieta/decyzja użytkownika: wariant B2, płaski, wyraźnie odmienny od
        wypełnionych pigułek zakładek)."""
        pasek = QFrame()
        pasek.setStyleSheet(f"background: {POWIERZCHNIA}; border-bottom: 1px solid {LINIA};")
        uklad_p = QHBoxLayout(pasek)
        uklad_p.setContentsMargins(22, 0, 22, 0)
        uklad_p.setSpacing(30)

        self._widgety_firm: dict[str, dict] = {}
        for indeks, (firma, _kontroler, _kf) in enumerate(self._pary):
            kolumna = QWidget()
            uklad_k = QVBoxLayout(kolumna)
            uklad_k.setContentsMargins(0, 13, 0, 0)
            uklad_k.setSpacing(9)

            wiersz = QHBoxLayout()
            wiersz.setSpacing(7)
            kropka = QLabel()
            kropka.setFixedSize(8, 8)
            wiersz.addWidget(kropka, alignment=Qt.AlignVCenter)

            przycisk = QPushButton(firma.nazwa)
            przycisk.setFlat(True)
            przycisk.setCursor(Qt.PointingHandCursor)
            przycisk.clicked.connect(lambda _checked=False, i=indeks: self._przelacz_firme(i))
            wiersz.addWidget(przycisk)
            uklad_k.addLayout(wiersz)

            kreska = QFrame()
            kreska.setFixedHeight(3)
            uklad_k.addWidget(kreska)

            uklad_p.addWidget(kolumna)
            self._widgety_firm[firma.id] = {"kropka": kropka, "przycisk": przycisk, "kreska": kreska}

        uklad_p.addStretch()

        self._odswiez_style_firm(self._pary[0][0].id)
        return pasek

    def _przelacz_firme(self, indeks: int) -> None:
        self._stos_firm.setCurrentIndex(indeks)
        self._odswiez_style_firm(self._pary[indeks][0].id)

    def _odswiez_style_firm(self, aktywna_id: str) -> None:
        for firma, _kontroler, _kf in self._pary:
            aktywna = firma.id == aktywna_id
            widgety = self._widgety_firm[firma.id]
            widgety["kropka"].setStyleSheet(
                f"background: {firma.akcent if aktywna else LINIA}; border-radius: 4px; border: none;"
            )
            widgety["przycisk"].setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; padding: 0; "
                f"color: {ATRAMENT if aktywna else BLADY}; font-size: 14.5px; "
                f"font-weight: {'700' if aktywna else '600'}; font-family: {CZCIONKA_NAGLOWEK}; }}"
            )
            widgety["kreska"].setStyleSheet(
                f"background: {firma.akcent if aktywna else 'transparent'}; border-radius: 2px; border: none;"
            )

    def _zbuduj_strone_firmy(
        self, firma: Firma, kontroler: Kontroler, kontroler_faktur: KontrolerFaktur
    ) -> tuple[QWidget, dict]:
        """Buduje jedną 'stronę' firmy: własny pasek zakładek Uzupełnienie/Weryfikacja + własny
        stos widoków - identyczna struktura co dawniej dla jedynej firmy, teraz powielona per
        firma. Zwraca (widget strony, słownik z referencjami do jej części - używany przez
        _synchronizuj_historie_faktur i testy)."""
        strona = QWidget()
        uklad = QVBoxLayout(strona)
        uklad.setContentsMargins(0, 0, 0, 0)
        uklad.setSpacing(0)

        pasek = QFrame()
        pasek.setStyleSheet(f"background: {PAPIER};")
        uklad_zewn = QHBoxLayout(pasek)
        uklad_zewn.setContentsMargins(22, 10, 22, 4)

        kapsula = QFrame()
        kapsula.setStyleSheet(f"background: {POWIERZCHNIA_MIEKKA}; border: 1px solid {LINIA}; border-radius: 18px;")
        uklad_kapsuly = QHBoxLayout(kapsula)
        uklad_kapsuly.setContentsMargins(4, 4, 4, 4)
        uklad_kapsuly.setSpacing(2)

        zakladki: dict[int, QPushButton] = {}

        def odswiez_style(aktywna: int) -> None:
            # Jasny odcień zieleni zamiast pełnego wypełnienia na aktywnej zakładce (celowo, żeby
            # nie konkurować wizualnie z przełącznikiem firm tuż nad tym paskiem - patrz
            # _zbuduj_pasek_firm) - kapsuła wokół zostaje, więc dalej czytelne jako jedna grupa.
            for indeks, przycisk in zakladki.items():
                if indeks == aktywna:
                    przycisk.setStyleSheet(
                        f"QPushButton {{ background: {ZIELEN_TLO}; color: {ZIELEN_GLEBOKA}; font-size: 12.5px; "
                        f"font-weight: 700; font-family: {CZCIONKA_NAGLOWEK}; padding: 7px 16px; border: none; "
                        "border-radius: 12px; }"
                    )
                else:
                    przycisk.setStyleSheet(
                        f"QPushButton {{ background: none; color: {STONOWANY}; font-size: 12.5px; font-weight: 600; "
                        f"font-family: {CZCIONKA_NAGLOWEK}; padding: 7px 16px; border: none; border-radius: 12px; }}"
                        f"QPushButton:hover {{ background: {POWIERZCHNIA}; color: {ATRAMENT}; }}"
                    )

        stos = QStackedWidget()

        def przelacz(indeks: int) -> None:
            stos.setCurrentIndex(indeks)
            odswiez_style(indeks)

        for indeks, etykieta in [(ZAKLADKA_UZUPELNIJ, "Uzupełnienie faktur"), (ZAKLADKA_WERYFIKACJA, "Weryfikacja")]:
            przycisk = QPushButton(etykieta)
            przycisk.setCursor(Qt.PointingHandCursor)
            przycisk.clicked.connect(lambda _checked=False, i=indeks: przelacz(i))
            uklad_kapsuly.addWidget(przycisk)
            zakladki[indeks] = przycisk

        uklad_zewn.addWidget(kapsula)
        uklad_zewn.addStretch()
        uklad.addWidget(pasek)

        widok_uzupelnij = WidokUzupelnijExcel(kontroler_faktur, kontroler)
        widok_weryfikacji = WidokWeryfikacji(kontroler)
        stos.addWidget(widok_uzupelnij)
        stos.addWidget(widok_weryfikacji)
        stos.setCurrentIndex(ZAKLADKA_UZUPELNIJ)
        uklad.addWidget(stos, stretch=1)

        odswiez_style(ZAKLADKA_UZUPELNIJ)

        return strona, {
            "firma": firma,
            "kontroler": kontroler,
            "kontroler_faktur": kontroler_faktur,
            "widok_uzupelnij": widok_uzupelnij,
            "widok_weryfikacji": widok_weryfikacji,
            "stos": stos,
            "zakladki": zakladki,
        }

    def _odswiez_przycisk_logowania(self) -> None:
        # Stan logowania jest wspólny dla wszystkich firm - _kontroler_glowny jest tu tylko
        # źródłem prawdy do odczytu, żadna z jego metod poniżej niczego nie zmienia.
        stan = self._kontroler_glowny.stan_synchronizacji()
        if stan == "NIESKONFIGUROWANY":
            self._przycisk_zaloguj.hide()
            self._przycisk_konto.hide()
            return

        if stan == "ZALOGOWANY":
            self._przycisk_zaloguj.hide()
            email = self._kontroler_glowny.email_zalogowanego()
            self._przycisk_konto.setText(f"{email}  ▾" if email else "Zalogowano  ▾")
            self._przycisk_konto.setStyleSheet(przycisk_pill(ZIELEN_TLO, ZIELEN_GLEBOKA, "#d7ecdd", ZIELEN, "12px"))
            self._przycisk_konto.show()
        else:
            self._przycisk_konto.hide()
            self._przycisk_zaloguj.setText("Zaloguj")
            self._przycisk_zaloguj.setStyleSheet(przycisk_pill(ZIELEN, "white", ZIELEN_GLEBOKA, rozmiar="12px"))
            self._przycisk_zaloguj.show()

    def _propaguj_magazyn_do_pozostalych_firm(self) -> None:
        """Po zalogowaniu/wylogowaniu przez _kontroler_glowny (pierwsza firma) - reszta firm
        dostaje TEN SAM magazyn (`Kontroler.store`), zamiast osobno logować się/wylogowywać
        sieciowo po raz drugi (trzeci...). To jest to, co robi logowanie/synchronizację
        "wspólną", nie "per firma" - decyzja użytkownika, patrz app/firmy.py."""
        magazyn = self._kontroler_glowny.store
        for _firma, kontroler, _kf in self._pary[1:]:
            kontroler.ustaw_magazyn(magazyn)

    def _na_klik_zaloguj(self) -> None:
        domyslny_email, domyslne_haslo = self._kontroler_glowny.dane_do_logowania()
        dialog = OknoLogowania(parent=self, domyslny_email=domyslny_email, domyslne_haslo=domyslne_haslo)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            self._kontroler_glowny.zaloguj_supabase(dialog.email, dialog.haslo, dialog.zapamietaj_haslo)
        except BledneDaneLogowania:
            QMessageBox.critical(self, "Błąd logowania", "Nieprawidłowy e-mail lub hasło. Spróbuj ponownie.")
            return
        self._propaguj_magazyn_do_pozostalych_firm()
        self._odswiez_przycisk_logowania()
        self._synchronizuj_historie_faktur()

    def _synchronizuj_historie_faktur(self) -> None:
        """Wpina magazyn historii faktur (WSPÓLNY dla wszystkich firm, jedna instancja) pod
        bieżący stan logowania: Supabase per-konto (współdzielący zalogowanego klienta z alertami,
        żeby nie logować się drugi raz) albo "wyłączony", jeśli nikt nie jest zalogowany - patrz
        historia_faktur_base.py po decyzję, czemu nic nie ląduje lokalnie. Wywoływane przy starcie
        okna oraz po każdym zalogowaniu/wylogowaniu."""
        klient = self._kontroler_glowny.klient_supabase()
        magazyn = SupabaseHistoriaFakturStore(klient) if klient is not None else PustyMagazynHistorii()
        for dane in self._widoki.values():
            dane["kontroler_faktur"].ustaw_magazyn(magazyn)
            dane["widok_uzupelnij"].odswiez_widocznosc_historii(klient is not None)

    def _pokaz_menu_konta(self) -> None:
        # Na razie tylko wylogowanie - miejsce na wiecej pozycji (np. przelaczanie konta) pozniej.
        menu = QMenu(self)
        akcja_wyloguj = menu.addAction("Wyloguj")
        akcja_wyloguj.triggered.connect(self._na_klik_wyloguj)
        menu.exec(self._przycisk_konto.mapToGlobal(self._przycisk_konto.rect().bottomLeft()))

    def _na_klik_wyloguj(self) -> None:
        self._kontroler_glowny.wyloguj()
        self._propaguj_magazyn_do_pozostalych_firm()
        self._odswiez_przycisk_logowania()
        self._synchronizuj_historie_faktur()

    def _zbuduj_stopke(self) -> QWidget:
        stopka = QFrame()
        stopka.setStyleSheet(f"background: {PAPIER};")
        uklad = QHBoxLayout(stopka)
        uklad.setContentsMargins(16, 4, 16, 10)

        self._przycisk_wersja = QPushButton(f"ver. {WERSJA}")
        self._przycisk_wersja.setFlat(True)
        self._przycisk_wersja.setCursor(Qt.PointingHandCursor)
        self._przycisk_wersja.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {BLADY}; font-size: 11px; "
            f"font-family: {CZCIONKA_TEKST}; text-align: left; padding: 2px 0; }}"
            f"QPushButton:hover {{ color: {STONOWANY}; }}"
        )
        self._przycisk_wersja.clicked.connect(self._pokaz_changelog)
        uklad.addStretch()
        uklad.addWidget(self._przycisk_wersja)
        uklad.addStretch()
        return stopka

    def _pokaz_changelog(self) -> None:
        dialog = OknoChangelog(parent=self)
        dialog.exec()

    def _na_pokaz_zadanie(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:
        # nie zamykamy aplikacji przy X - dziala dalej w tray, patrz app.setQuitOnLastWindowClosed(False) w main.py
        event.ignore()
        self.hide()
