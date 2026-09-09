"""Parser faktur dystrybucyjnych PDF (ENEA Operator) - wyciąga pozycje per Kod PPE.

Faktura ENEA to natywny PDF z warstwą tekstu (nie skan) - PyMuPDF wyciąga tekst liniowo,
jeden token tabeli na linię. Jedna faktura opisuje wiele miejsc poboru (PPE) na kolejnych
stronach/sekcjach, więc parsujemy cały tekst dokumentu i dzielimy go na sekcje po znaczniku
"Za okres od ... do ... Kod PPE: ...", który występuje raz na sekcję.

Kategorie w `KATEGORIE` to wspólny słownik dla całego modułu importu faktur (import_faktur.py,
foldery_faktur.py, UI) - dzięki temu warstwa prezentacji rozróżnia typy problemów po stałej,
a nie przez dopasowywanie polskiego tekstu opisu.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pymupdf

KAT_SUKCES = "sukces"
KAT_PPE_NIEZNALEZIONE = "ppe_nieznalezione"
KAT_BRAK_PPE_NA_FAKTURZE = "brak_ppe_na_fakturze"
KAT_DANE_NIEROZPOZNANE = "dane_nierozpoznane"
KAT_NIEZGODNOSC_SUMY = "niezgodnosc_sumy"
KAT_JUZ_WYPELNIONE = "juz_wypelnione"
KAT_FAKTURA_NIEROZPOZNANA = "faktura_nierozpoznana"

_SEKCJA_START = re.compile(
    r"Za okres od\s*(\d{2})/(\d{2})/(\d{4})\s*do\s*(\d{2})/(\d{2})/(\d{4})\s*Kod PPE:\s*(\d+)"
)
# Czyta z bloku "Opłata zmienna sieciowa" (Ilość - jednostki kWh naliczone w rozliczeniu), NIE
# z tabeli ODCZYTY (stan licznika) - dla punktów z instalacją fotowoltaiczną/net-meteringiem
# (np. hydrofornie z PV) ODCZYTY pokazuje surowy pobór z sieci, a rzeczywiście rozliczana ilość
# (ta, która sumuje się do "Zużycie: X kWh" na końcu sekcji) jest w "Opłata zmienna sieciowa"  -
# potwierdzone na PPE 590310600000433732, D 05.pdf/Koszuty PV: ODCZYTY dał 152/994 (pobór),
# "Opłata zmienna sieciowa" dał poprawne 127/929 (rozliczone, sumujące się do 1056 - zgodnego
# z "Zużycie:").
#
# "Opłata zmienna sieciowa" rozbija się na WIELE par szczytowa/pozaszczytowa (każda z częściową
# ilością), kiedy w trakcie okresu rozliczeniowego zmieniła się taryfa, albo okres obejmuje więcej
# niż jeden miesiąc kalendarzowy (odczyt na koniec każdego) - trzeba sumować WSZYSTKIE wystąpienia,
# nie tylko pierwsze (potwierdzone na PPE 590310600000423740, D 02.pdf/20 Października).
#
# (?:^|\n) przed nazwą strefy jest konieczne - "szczytowa" bez tej kotwicy dopasowuje się też
# jako sufiks słowa "pozaszczytowa" (podciąg!), co fałszywie podwajało zużycie szczytowej strefy
# przy sumowaniu wielu wystąpień.
_BLOK_OPLATY_ZMIENNEJ = re.compile(r"Opłata zmienna sieciowa\n(.*?)(?=\nOpłata |\Z)", re.DOTALL)
_ILOSC_STREFY = r"(?:^|\n){strefa}\s*\nkWh\s*\n\d{{2}}/\d{{2}}/\d{{4}}\s*\n([\d.,]+)"
_SZCZYTOWA = re.compile(_ILOSC_STREFY.format(strefa="szczytowa"))
_POZASZCZYTOWA = re.compile(_ILOSC_STREFY.format(strefa="pozaszczytowa"))
# Licznik jednostrefowy/całodobowy (taryfa C11 i podobne) nie ma podziału szczytowa/pozaszczytowa
# w ogóle - cała ilość jest pod nazwą strefy "całodobowa". Arkusz nie ma osobnej kolumny na to,
# więc z decyzji użytkownika taka wartość zawsze ląduje w P-S1 (szczytowa), P-S2 zostaje puste -
# patrz `jednostrefowa` na PozycjaFaktury i obsługa w import_faktur.py.
_CALODOBOWA = re.compile(_ILOSC_STREFY.format(strefa="całodobowa"))


def _suma_strefy(blok_oplaty_zmiennej: str, wzorzec: re.Pattern) -> float | None:
    wartosci = [_parsuj_liczbe(m.group(1)) for m in wzorzec.finditer(blok_oplaty_zmiennej)]
    return sum(wartosci) if wartosci else None


_ZUZYCIE_NETTO = re.compile(
    r"Zużycie:\s*([\d.,]+)\s*kWh\s*Ogółem wartość netto:\s*([\d.,]+)\s*zł"
)
# Strona 1 faktury wymienia wszystkie miejsca poboru w tym jednym bloku, ponumerowane "N. opis" -
# licząc te pozycje i porównując z liczbą znalezionych sekcji "Kod PPE:" wykrywamy przypadek, gdy
# jakiś punkt poboru w ogóle nie ma sekcji szczegółowej z numerem PPE (np. z winy samej faktury).
# Sprawdzone na 479 realnych fakturach D z przykładowego zbioru - liczby zawsze się zgadzały.
_BLOK_ROZLICZENIA = re.compile(
    r"Rozliczenie dla miejsc poboru energii(.*?)Razem za usługi dystrybucji", re.DOTALL
)
_POZYCJA_NUMEROWANA = re.compile(r"^(\d+)\.\s", re.MULTILINE)


class NieRozpoznanoFaktury(ValueError):
    pass


@dataclass
class PozycjaFaktury:
    ppe: str
    okres_od: date
    okres_do: date
    zuzycie_szczytowa: float
    zuzycie_pozaszczytowa: float
    zuzycie_razem: float
    oplata_dystrybucja: float
    jednostrefowa: bool = False  # licznik całodobowy - P-S2 nie ma być wpisywane, patrz import_faktur.py


@dataclass
class PominietaSekcja:
    kategoria: str
    opis: str
    ppe: str | None = None
    okres_od: date | None = None
    okres_do: date | None = None


@dataclass
class WynikOdczytuFaktury:
    pozycje: list[PozycjaFaktury]
    pominiete: list[PominietaSekcja]


def _parsuj_liczbe(tekst: str) -> float:
    """Format polski: kropka = separator tysięcy, przecinek = separator dziesiętny."""
    return float(tekst.replace(".", "").replace(",", "."))


def _wczytaj_tekst(sciezka: str | Path) -> str:
    dokument = pymupdf.open(sciezka)
    try:
        return "\n".join(strona.get_text() for strona in dokument)
    finally:
        dokument.close()


def _pozycja_z_sekcji(tekst_sekcji: str, ppe: str, okres_od: date, okres_do: date) -> PozycjaFaktury:
    dopasowanie_bloku = _BLOK_OPLATY_ZMIENNEJ.search(tekst_sekcji)
    if dopasowanie_bloku is None:
        raise NieRozpoznanoFaktury("nie znaleziono sekcji 'Opłata zmienna sieciowa'")
    blok_oplaty_zmiennej = dopasowanie_bloku.group(1)

    zuzycie_szczytowa = _suma_strefy(blok_oplaty_zmiennej, _SZCZYTOWA)
    zuzycie_pozaszczytowa = _suma_strefy(blok_oplaty_zmiennej, _POZASZCZYTOWA)
    jednostrefowa = False
    if zuzycie_szczytowa is None and zuzycie_pozaszczytowa is None:
        zuzycie_calodobowa = _suma_strefy(blok_oplaty_zmiennej, _CALODOBOWA)
        if zuzycie_calodobowa is None:
            raise NieRozpoznanoFaktury(
                "nie znaleziono wartości zużycia szczytowa/pozaszczytowa/całodobowa"
            )
        zuzycie_szczytowa = zuzycie_calodobowa
        zuzycie_pozaszczytowa = 0.0
        jednostrefowa = True
    elif zuzycie_szczytowa is None or zuzycie_pozaszczytowa is None:
        raise NieRozpoznanoFaktury(
            "znaleziono tylko jedną ze stref szczytowa/pozaszczytowa - niekompletne dane"
        )

    dopasowanie_podsumowania = _ZUZYCIE_NETTO.search(tekst_sekcji)
    if dopasowanie_podsumowania is None:
        raise NieRozpoznanoFaktury("nie znaleziono podsumowania 'Zużycie: ... Ogółem wartość netto: ...'")

    return PozycjaFaktury(
        ppe=ppe,
        okres_od=okres_od,
        okres_do=okres_do,
        zuzycie_szczytowa=zuzycie_szczytowa,
        zuzycie_pozaszczytowa=zuzycie_pozaszczytowa,
        zuzycie_razem=_parsuj_liczbe(dopasowanie_podsumowania.group(1)),
        oplata_dystrybucja=_parsuj_liczbe(dopasowanie_podsumowania.group(2)),
        jednostrefowa=jednostrefowa,
    )


def _sprawdz_liczbe_pozycji(tekst: str, liczba_znalezionych_sekcji: int) -> PominietaSekcja | None:
    """Porównuje liczbę pozycji wymienionych na stronie 1 z liczbą znalezionych sekcji PPE.
    Brak dopasowania bloku (np. inny układ faktury) nie jest błędem - po prostu nie sprawdzamy."""
    dopasowanie_bloku = _BLOK_ROZLICZENIA.search(tekst)
    if dopasowanie_bloku is None:
        return None
    liczba_na_stronie = len(_POZYCJA_NUMEROWANA.findall(dopasowanie_bloku.group(1)))
    if liczba_na_stronie <= liczba_znalezionych_sekcji:
        return None
    brakuje = liczba_na_stronie - liczba_znalezionych_sekcji
    return PominietaSekcja(
        kategoria=KAT_BRAK_PPE_NA_FAKTURZE,
        opis=(
            f"strona 1 faktury wymienia {liczba_na_stronie} miejsc poboru, ale rozpoznano tylko "
            f"{liczba_znalezionych_sekcji} sekcji szczegółowych z numerem PPE - {brakuje} "
            f"{'pozycja' if brakuje == 1 else 'pozycje/pozycji'} mogła nie mieć numeru PPE albo sekcji "
            "szczegółowej na fakturze"
        ),
    )


def wczytaj_fakture_dystrybucyjna(sciezka: str | Path) -> WynikOdczytuFaktury:
    """Zwraca pozycje (jedna na Kod PPE) z faktury dystrybucyjnej PDF (ENEA Operator).

    Sekcje, których nie da się jednoznacznie sparsować (np. licznik jednostrefowy/całodobowy -
    poza obecnym zakresem, tylko P-S1/P-S2) trafiają do `pominiete` z powodem zamiast przerywać
    parsowanie całego pliku - inne, poprawne sekcje tej samej faktury i tak powinny się wczytać.
    Rzuca NieRozpoznanoFaktury tylko wtedy, gdy w pliku nie ma ani jednej sekcji faktury
    dystrybucyjnej (np. to w ogóle nie ten typ dokumentu).
    """
    tekst = _wczytaj_tekst(sciezka)
    starty_sekcji = list(_SEKCJA_START.finditer(tekst))
    if not starty_sekcji:
        raise NieRozpoznanoFaktury(f"{sciezka}: nie rozpoznano żadnej sekcji 'Za okres od ... Kod PPE: ...'")

    pozycje: list[PozycjaFaktury] = []
    pominiete: list[PominietaSekcja] = []
    for i, dopasowanie in enumerate(starty_sekcji):
        koniec_sekcji = starty_sekcji[i + 1].start() if i + 1 < len(starty_sekcji) else len(tekst)
        tekst_sekcji = tekst[dopasowanie.start():koniec_sekcji]

        od_dzien, od_miesiac, od_rok, do_dzien, do_miesiac, do_rok, ppe = dopasowanie.groups()
        okres_od = date(int(od_rok), int(od_miesiac), int(od_dzien))
        okres_do = date(int(do_rok), int(do_miesiac), int(do_dzien))

        try:
            pozycje.append(_pozycja_z_sekcji(tekst_sekcji, ppe, okres_od, okres_do))
        except NieRozpoznanoFaktury as exc:
            pominiete.append(
                PominietaSekcja(
                    kategoria=KAT_DANE_NIEROZPOZNANE, opis=str(exc), ppe=ppe, okres_od=okres_od, okres_do=okres_do
                )
            )

    problem_liczby_pozycji = _sprawdz_liczbe_pozycji(tekst, len(starty_sekcji))
    if problem_liczby_pozycji is not None:
        pominiete.append(problem_liczby_pozycji)

    return WynikOdczytuFaktury(pozycje=pozycje, pominiete=pominiete)


# --- Duże odbiory ------------------------------------------------------------------------------
#
# Ta sama rodzina faktur (ENEA Operator, "Za okres od ... Kod PPE: ...") - duże odbiory mają
# dodatkowo tabelę ODCZYTY (surowe odczyty licznika: moc pobrana, energia czynna, energia bierna
# indukcyjna/pojemnościowa) i rozszerzoną sekcję ROZLICZENIE (opłaty za ponadumowny pobór energii
# biernej). Z decyzji użytkownika P-S1/P-S2/P-S3 czytamy z ODCZYTY (nie z "Opłata zmienna sieciowa"
# jak w wczytaj_fakture_dystrybucyjna) - nawet jeśli to się nie zgadza z sumą zużycia na fakturze
# (patrz zuzycie_razem_faktura/KAT_ZUZYCIE_NIEZGODNE_Z_FAKTURA - to sprawdza import_faktur_duze.py
# już po wczytaniu, nie ten moduł).
#
# Dwie taryfy potwierdzone na realnych fakturach:
# - 2-strefowa (np. C22W): strefy "szczytowa"/"pozaszczytowa", jednostki kWh/kvarh.
# - 3-strefowa (np. B23, potwierdzone na Chwałkowo D 01.31.pdf): strefy "szczyt przedpołudniowy"/
#   "szczyt popołudniowy"/"pozostałe godziny doby" (w tej kolejności = P-S1/P-S2/P-S3 - zgodne
#   z kolejnością już wypełnionych danych testowych), jednostki MWh/Mvarh zamiast kWh/kvarh (więksi
#   odbiorcy) - stąd jednostka jest wariantowa (kWh|MWh, kvarh|Mvarh) wszędzie, gdzie występuje.
# - 3-strefowe faktury mają dodatkowo liczniki strat na przekładnikach pomiarowych ("Licznik
#   rozliczeniowy strat energii czynnej I2h"/"...U2h") - potwierdzone (Chwałkowo), że trzeba je
#   doliczyć do P-S1/P-S2/P-S3 (kolejno: 1. licznik strat -> P-S1, 2. -> P-S2, 3. -> P-S3), żeby
#   suma zgadzała się z "Zużycie: X" na fakturze co do kWh (139478 surowych + 4 + 3 strat = 139485,
#   dokładnie jak zadeklarowane) - z decyzji użytkownika.
KAT_ZUZYCIE_NIEZGODNE_Z_FAKTURA = "zuzycie_niezgodne_z_faktura"

# Sposób odczytu - zwykle "Zdalny", ale spotykany też "Fizyczny" (odczyt ręczny, potwierdzone na
# Kórnicka 82 D 02 19.pdf - krótki, 19-dniowy podokres rozliczeniowy, licznik nie zdążył się
# odezwać zdalnie).
_SPOSOB_ODCZYTU = r"(?:Zdalny|Fizyczny)"

_MOC_POBRANA = re.compile(
    rf"Moc pobrana\n\d{{2}}/\d{{2}}/\d{{4}} \d{{2}}:\d{{2}}\n[\d.,]+\n[\d.,]+\n\d+\n[\d.,]+\n{_SPOSOB_ODCZYTU}\n\d+\n([\d.,]+)"
)


def _wiersz_licznika(strefa: str) -> re.Pattern:
    # (?:^|\n) przed strefa jest konieczne - patrz komentarz przy _SZCZYTOWA/_POZASZCZYTOWA wyżej,
    # ten sam problem podciągu "szczytowa" w "pozaszczytowa" dotyczy też tabeli ODCZYTY.
    return re.compile(
        rf"(?:^|\n){strefa}\n\d{{2}}/\d{{2}}/\d{{4}}\n[\d.,]+\n[\d.,]+\n\d+\n[\d.,]+\n{_SPOSOB_ODCZYTU}\n\d+\n([\d.,]+)"
    )


_LICZNIK_SZCZYTOWA = _wiersz_licznika("szczytowa")
_LICZNIK_POZASZCZYTOWA = _wiersz_licznika("pozaszczytowa")
_LICZNIK_PRZEDPOLUDNIOWY = _wiersz_licznika("szczyt przedpołudniowy")
_LICZNIK_POPOLUDNIOWY = _wiersz_licznika("szczyt popołudniowy")
_LICZNIK_POZOSTALE = _wiersz_licznika("pozostałe godziny doby")
# Taryfa B12 (potwierdzone na Kórnicka 82) - dzienna/nocna zamiast szczytowa/pozaszczytowa.
_LICZNIK_DZIENNA = _wiersz_licznika("dzienna")
_LICZNIK_NOCNA = _wiersz_licznika("nocna")

_WIERSZ_POZAUMOWNA_INDUKCYJNA = re.compile(
    r"[\d,]+\s+[\d,]+\n[kM]Wh\n\d{2}/\d{2}/\d{4}\n[\d.,]+\n[\d.,]+\n[\d.,]+\n([\d.,]+)\n\d+"
)
_BLOK_POZAUMOWNA_INDUKCYJNA = re.compile(
    r"Opłata za ponadumowny pobór energii biernej indukcyjnej\n(.*?)(?=\nOpłata |\Z)", re.DOTALL
)
_WIERSZ_POZAUMOWNA_POJEMNOSCIOWA = re.compile(
    r"(?:szczytowa|pozaszczytowa|szczyt przedpołudniowy|szczyt popołudniowy|pozostałe godziny doby"
    r"|dzienna|nocna)"
    r"\n[kM]varh\n\d{2}/\d{2}/\d{4}\n[\d.,]+\n[\d.,]+\n([\d.,]+)\n\d+"
)
_BLOK_POZAUMOWNA_POJEMNOSCIOWA = re.compile(
    r"Opłata za ponadumowny pobór energii biernej pojemnościowej\n(.*?)(?=\nOpłata |\Z)", re.DOTALL
)

_ZUZYCIE_NETTO_DUZE = re.compile(
    r"Zużycie:\s*([\d.,]+)\s*(kWh|MWh)\s*Ogółem wartość netto:\s*([\d.,]+)\s*zł"
)

# Liczniki strat na przekładnikach (I2h/U2h - nie "...oddanej I2h/U2h", stąd wymóg ' nr ' zaraz po
# nazwie, ten sam trik co w _blok_licznika). Kolejność występowania w tekście = kolejność 1./2./3.
# straty z decyzji użytkownika (patrz komentarz modułu wyżej).
_BLOK_STRATY_CZYNNEJ = re.compile(
    r"Licznik rozliczeniowy strat energii czynnej (?!oddanej)\S+ nr [^\n]+\n(.*?)(?=\nLicznik rozliczeniowy|\nROZLICZENIE|\Z)",
    re.DOTALL,
)
_WIERSZ_STRATY_CZYNNEJ = re.compile(
    rf"całodobowa\n\d{{2}}/\d{{2}}/\d{{4}}\n[\d.,]+\n[\d.,]+\n[\d.]+\n[\d.,]+\n{_SPOSOB_ODCZYTU}\n\d+\n([\d.,]+)"
)


@dataclass
class PozycjaFakturyDuze:
    ppe: str
    okres_od: date
    okres_do: date
    moc_pobrana: float
    p_s1: float
    p_s2: float
    p_s3: float
    q_plus_s1: float
    q_plus_s2: float
    q_plus_s3: float
    q_minus_s1: float
    q_minus_s2: float
    q_minus_s3: float
    q_plus_zl: float
    q_minus_zl: float
    oplata_dystrybucja: float
    zuzycie_razem_faktura: float  # do walidacji (KAT_ZUZYCIE_NIEZGODNE_Z_FAKTURA) - nie zapisywane wprost
    trzy_strefy: bool = False  # gdy False, *_s3 wyżej to 0.0 (fikcyjne) - import_faktur_duze.py
    # nie ma wtedy pisać literalnego zera do P-S3/Q+S3/Q-S3, te kolumny mają zostać puste.


@dataclass
class WynikOdczytuFakturyDuze:
    pozycje: list[PozycjaFakturyDuze]
    pominiete: list[PominietaSekcja]


def _blok_licznika(tekst_sekcji: str, nazwa: str) -> str | None:
    """Tekst między 'Licznik rozliczeniowy {nazwa} nr ...' a następnym nagłówkiem 'Licznik
    rozliczeniowy ...' (albo 'ROZLICZENIE'). Wymóg ' nr ' zaraz po nazwie odróżnia np. 'energii
    czynnej' od 'energii czynnej oddanej' - inaczej [^\\n]* złapałby też ten dłuższy nagłówek.
    Po numerze licznika akceptujemy dowolny dalszy tekst do końca linii - potwierdzone (Kórnicka
    82), że bywa tam doklejone np. '+ 3%' (inny procent przy różnych licznikach tego samego
    obiektu), nie tylko goły numer."""
    dopasowanie = re.search(
        rf"Licznik rozliczeniowy {nazwa} nr [^\n]+\n(.*?)(?=\nLicznik rozliczeniowy|\nROZLICZENIE|\Z)",
        tekst_sekcji,
        re.DOTALL,
    )
    return dopasowanie.group(1) if dopasowanie else None


def _wartosc_strefy_odczytow(blok: str | None, wzorzec: re.Pattern) -> float | None:
    if blok is None:
        return None
    dopasowanie = wzorzec.search(blok)
    return _parsuj_liczbe(dopasowanie.group(1)) if dopasowanie else None


def _wartosci_stref(blok: str | None) -> tuple[float, float, float, bool] | None:
    """Próbuje najpierw taryfę 3-strefową (szczyt przedpołudniowy/popołudniowy/pozostałe godziny
    doby -> S1/S2/S3), potem warianty 2-strefowe: szczytowa/pozaszczytowa -> S1/S2, oraz
    dzienna/nocna -> S1/S2 (taryfa B12, potwierdzone liczbowo na Kórnicka 82: "dzienna" i P-S1
    zgadzają się co do kWh) - S3=0.0/fikcyjne w obu wariantach 2-strefowych, stąd zwracana flaga
    "czy naprawdę 3-strefowa". None, jeśli żaden z wariantów nie znajdzie się w całości."""
    if blok is None:
        return None
    s1 = _wartosc_strefy_odczytow(blok, _LICZNIK_PRZEDPOLUDNIOWY)
    s2 = _wartosc_strefy_odczytow(blok, _LICZNIK_POPOLUDNIOWY)
    s3 = _wartosc_strefy_odczytow(blok, _LICZNIK_POZOSTALE)
    if s1 is not None and s2 is not None and s3 is not None:
        return s1, s2, s3, True
    s1 = _wartosc_strefy_odczytow(blok, _LICZNIK_SZCZYTOWA)
    s2 = _wartosc_strefy_odczytow(blok, _LICZNIK_POZASZCZYTOWA)
    if s1 is not None and s2 is not None:
        return s1, s2, 0.0, False
    s1 = _wartosc_strefy_odczytow(blok, _LICZNIK_DZIENNA)
    s2 = _wartosc_strefy_odczytow(blok, _LICZNIK_NOCNA)
    if s1 is not None and s2 is not None:
        return s1, s2, 0.0, False
    return None


def _suma_pozaumownej(tekst_sekcji: str, blok_wzorzec: re.Pattern, wiersz_wzorzec: re.Pattern) -> float:
    dopasowanie_bloku = blok_wzorzec.search(tekst_sekcji)
    if dopasowanie_bloku is None:
        return 0.0
    return sum(_parsuj_liczbe(m.group(1)) for m in wiersz_wzorzec.finditer(dopasowanie_bloku.group(1)))


def _straty_energii_czynnej(tekst_sekcji: str) -> list[float]:
    straty: list[float] = []
    for dopasowanie_bloku in _BLOK_STRATY_CZYNNEJ.finditer(tekst_sekcji):
        dopasowanie_wiersza = _WIERSZ_STRATY_CZYNNEJ.search(dopasowanie_bloku.group(1))
        if dopasowanie_wiersza is not None:
            straty.append(_parsuj_liczbe(dopasowanie_wiersza.group(1)))
    return straty


def _pozycja_duza_z_sekcji(tekst_sekcji: str, ppe: str, okres_od: date, okres_do: date) -> PozycjaFakturyDuze:
    odczyty_mocy = [_parsuj_liczbe(m.group(1)) for m in _MOC_POBRANA.finditer(tekst_sekcji)]
    if not odczyty_mocy:
        raise NieRozpoznanoFaktury("nie znaleziono odczytów 'Moc pobrana' w tabeli ODCZYTY")
    moc_pobrana = max(odczyty_mocy)

    blok_czynnej = _blok_licznika(tekst_sekcji, "energii czynnej")
    wartosci_czynnej = _wartosci_stref(blok_czynnej)
    if wartosci_czynnej is None:
        raise NieRozpoznanoFaktury(
            "nie znaleziono stref w 'Licznik rozliczeniowy energii czynnej' (ani 2-, ani 3-strefowych)"
        )
    p_s1, p_s2, p_s3, trzy_strefy = wartosci_czynnej
    strefy_czynnej = [p_s1, p_s2, p_s3]
    for indeks, strata in enumerate(_straty_energii_czynnej(tekst_sekcji)[:3]):
        strefy_czynnej[indeks] += strata
    p_s1, p_s2, p_s3 = strefy_czynnej

    blok_indukcyjnej = _blok_licznika(tekst_sekcji, "energii biernej indukcyjnej")
    q_plus_s1, q_plus_s2, q_plus_s3, _ = _wartosci_stref(blok_indukcyjnej) or (0.0, 0.0, 0.0, False)

    blok_pojemnosciowej = _blok_licznika(tekst_sekcji, "energii biernej pojemnościowej")
    q_minus_s1, q_minus_s2, q_minus_s3, _ = _wartosci_stref(blok_pojemnosciowej) or (0.0, 0.0, 0.0, False)

    q_plus_zl = _suma_pozaumownej(tekst_sekcji, _BLOK_POZAUMOWNA_INDUKCYJNA, _WIERSZ_POZAUMOWNA_INDUKCYJNA)
    q_minus_zl = _suma_pozaumownej(tekst_sekcji, _BLOK_POZAUMOWNA_POJEMNOSCIOWA, _WIERSZ_POZAUMOWNA_POJEMNOSCIOWA)

    dopasowanie_podsumowania = _ZUZYCIE_NETTO_DUZE.search(tekst_sekcji)
    if dopasowanie_podsumowania is None:
        raise NieRozpoznanoFaktury("nie znaleziono podsumowania 'Zużycie: ... Ogółem wartość netto: ...'")
    zuzycie_tekst, jednostka, netto_tekst = dopasowanie_podsumowania.groups()
    zuzycie_razem_faktura = _parsuj_liczbe(zuzycie_tekst)
    if jednostka == "MWh":
        zuzycie_razem_faktura *= 1000

    return PozycjaFakturyDuze(
        ppe=ppe,
        okres_od=okres_od,
        okres_do=okres_do,
        moc_pobrana=moc_pobrana,
        p_s1=p_s1,
        p_s2=p_s2,
        p_s3=p_s3,
        q_plus_s1=q_plus_s1,
        q_plus_s2=q_plus_s2,
        q_plus_s3=q_plus_s3,
        q_minus_s1=q_minus_s1,
        q_minus_s2=q_minus_s2,
        q_minus_s3=q_minus_s3,
        q_plus_zl=q_plus_zl,
        q_minus_zl=q_minus_zl,
        oplata_dystrybucja=_parsuj_liczbe(netto_tekst),
        zuzycie_razem_faktura=zuzycie_razem_faktura,
        trzy_strefy=trzy_strefy,
    )


def wczytaj_fakture_duzy_odbior(sciezka: str | Path) -> WynikOdczytuFakturyDuze:
    """Zwraca pozycje (jedna na Kod PPE) z faktury dystrybucyjnej PDF dla obiektów typu "duży
    odbiór" (z tabelą ODCZYTY: moc pobrana, energia czynna/bierna per strefa).

    Ten sam plik PDF może zawierać sekcje zarówno małych, jak i dużych odbiorów na raz - sekcje
    bez tabeli ODCZYTY (małe odbiory) trafiają do `pominiete` z KAT_DANE_NIEROZPOZNANE, tak samo
    jak każda inna niekompletna sekcja. To nie jest błąd tego modułu - routing do właściwego
    arkusza robi import_faktur_duze.py/foldery_faktur.py, łącząc wynik tej funkcji z wynikiem
    wczytaj_fakture_dystrybucyjna."""
    tekst = _wczytaj_tekst(sciezka)
    starty_sekcji = list(_SEKCJA_START.finditer(tekst))
    if not starty_sekcji:
        raise NieRozpoznanoFaktury(f"{sciezka}: nie rozpoznano żadnej sekcji 'Za okres od ... Kod PPE: ...'")

    pozycje: list[PozycjaFakturyDuze] = []
    pominiete: list[PominietaSekcja] = []
    for i, dopasowanie in enumerate(starty_sekcji):
        koniec_sekcji = starty_sekcji[i + 1].start() if i + 1 < len(starty_sekcji) else len(tekst)
        tekst_sekcji = tekst[dopasowanie.start():koniec_sekcji]

        od_dzien, od_miesiac, od_rok, do_dzien, do_miesiac, do_rok, ppe = dopasowanie.groups()
        okres_od = date(int(od_rok), int(od_miesiac), int(od_dzien))
        okres_do = date(int(do_rok), int(do_miesiac), int(do_dzien))

        try:
            pozycje.append(_pozycja_duza_z_sekcji(tekst_sekcji, ppe, okres_od, okres_do))
        except NieRozpoznanoFaktury as exc:
            pominiete.append(
                PominietaSekcja(
                    kategoria=KAT_DANE_NIEROZPOZNANE, opis=str(exc), ppe=ppe, okres_od=okres_od, okres_do=okres_do
                )
            )

    problem_liczby_pozycji = _sprawdz_liczbe_pozycji(tekst, len(starty_sekcji))
    if problem_liczby_pozycji is not None:
        pominiete.append(problem_liczby_pozycji)

    return WynikOdczytuFakturyDuze(pozycje=pozycje, pominiete=pominiete)


# --- Fotowoltaika (energia oddana) -------------------------------------------------------------
#
# Ten sam plik D (ENEA Operator) co dla zwykłego zużycia (wczytaj_fakture_duzy_odbior) - obiekty
# z instalacją PV/net-meteringiem mają w tabeli ODCZYTY DODATKOWO sekcję "Licznik rozliczeniowy
# energii czynnej oddanej" (energia oddana do sieci), o dokładnie tej samej strukturze co "Licznik
# rozliczeniowy energii czynnej" (2-strefowa: szczytowa/pozaszczytowa; 3-strefowa: szczyt
# przedpołudniowy/popołudniowy/pozostałe godziny doby) - stąd ponowne użycie _blok_licznika/
# _wartosci_stref. Potwierdzone liczbowo na dwóch fakturach:
# - Babin (2-strefowa, D 01 31.pdf): szczytowa=0, pozaszczytowa=1 - zgodne z arkuszem
#   'fotowoltaika energia oddana', styczeń, P-S1/P-S2.
# - Chwałkowo (3-strefowa, D 07 31.pdf): 0/0/5 - zgodne z arkuszem, lipiec, P-S1/P-S2/P-S3.
#
# Obiekty 3-strefowe mają też własne liczniki strat "oddanej" (I2h/U2h) - osobna sekcja "Licznik
# rozliczeniowy strat energii czynnej oddanej {I2h,U2h}", dokładnie równoległa do strat zwykłego
# zużycia (patrz _BLOK_STRATY_CZYNNEJ wyżej) - z tej samej decyzji użytkownika doliczamy je do
# P-S1/P-S2/P-S3 w kolejności występowania (1. -> P-S1, 2. -> P-S2, 3. -> P-S3).
#
# Kolumna "Energia wyprodukowana" w arkuszu NIE ma odpowiednika na żadnej sprawdzonej fakturze
# (D ani E) - z decyzji użytkownika to pole ręczne, ten moduł go nie czyta/nie zapisuje.
#
# Sekcje BEZ bloku "energii czynnej oddanej" (obiekt bez PV - większość Dużych odbiorów) są po
# cichu pomijane, nie trafiają do `pominiete` - to nie błąd, to normalny brak PV na tym obiekcie.

_BLOK_STRATY_CZYNNEJ_ODDANEJ = re.compile(
    r"Licznik rozliczeniowy strat energii czynnej oddanej \S+ nr [^\n]+\n(.*?)(?=\nLicznik rozliczeniowy|\nROZLICZENIE|\Z)",
    re.DOTALL,
)


@dataclass
class PozycjaEnergiaOddana:
    ppe: str
    okres_od: date
    okres_do: date
    p_s1: float
    p_s2: float
    p_s3: float
    trzy_strefy: bool = False  # gdy False, p_s3 to 0.0 fikcyjne - import_faktur_oddana.py nie ma
    # wtedy pisać literalnego zera do P-S3, ta kolumna ma zostać puste (jak w Duże odbiory).


@dataclass
class WynikOdczytuEnergiiOddanej:
    pozycje: list[PozycjaEnergiaOddana]
    pominiete: list[PominietaSekcja]


def _straty_energii_oddanej(tekst_sekcji: str) -> list[float]:
    straty: list[float] = []
    for dopasowanie_bloku in _BLOK_STRATY_CZYNNEJ_ODDANEJ.finditer(tekst_sekcji):
        dopasowanie_wiersza = _WIERSZ_STRATY_CZYNNEJ.search(dopasowanie_bloku.group(1))
        if dopasowanie_wiersza is not None:
            straty.append(_parsuj_liczbe(dopasowanie_wiersza.group(1)))
    return straty


def _pozycja_oddana_z_sekcji(tekst_sekcji: str, ppe: str, okres_od: date, okres_do: date) -> PozycjaEnergiaOddana | None:
    blok_oddanej = _blok_licznika(tekst_sekcji, "energii czynnej oddanej")
    wartosci = _wartosci_stref(blok_oddanej)
    if wartosci is None:
        return None  # obiekt bez PV - brak sekcji "energii czynnej oddanej" na tej fakturze
    p_s1, p_s2, p_s3, trzy_strefy = wartosci
    strefy = [p_s1, p_s2, p_s3]
    for indeks, strata in enumerate(_straty_energii_oddanej(tekst_sekcji)[:3]):
        strefy[indeks] += strata
    p_s1, p_s2, p_s3 = strefy
    return PozycjaEnergiaOddana(
        ppe=ppe, okres_od=okres_od, okres_do=okres_do, p_s1=p_s1, p_s2=p_s2, p_s3=p_s3, trzy_strefy=trzy_strefy
    )


def wczytaj_fakture_energia_oddana(sciezka: str | Path) -> WynikOdczytuEnergiiOddanej:
    """Zwraca pozycje (energia oddana do sieci per strefa) z faktury dystrybucyjnej PDF, dla
    obiektów z instalacją fotowoltaiczną/net-meteringiem. Sekcje bez sekcji "energii czynnej
    oddanej" (obiekt bez PV) są pominięte bez żadnego wpisu w `pominiete` - patrz komentarz
    modułu wyżej. Rzuca NieRozpoznanoFaktury tylko, gdy w pliku nie ma ani jednej sekcji faktury
    dystrybucyjnej w ogóle (to samo kryterium co w innych wczytaj_fakture_*)."""
    tekst = _wczytaj_tekst(sciezka)
    starty_sekcji = list(_SEKCJA_START.finditer(tekst))
    if not starty_sekcji:
        raise NieRozpoznanoFaktury(f"{sciezka}: nie rozpoznano żadnej sekcji 'Za okres od ... Kod PPE: ...'")

    pozycje: list[PozycjaEnergiaOddana] = []
    for i, dopasowanie in enumerate(starty_sekcji):
        koniec_sekcji = starty_sekcji[i + 1].start() if i + 1 < len(starty_sekcji) else len(tekst)
        tekst_sekcji = tekst[dopasowanie.start():koniec_sekcji]

        od_dzien, od_miesiac, od_rok, do_dzien, do_miesiac, do_rok, ppe = dopasowanie.groups()
        okres_od = date(int(od_rok), int(od_miesiac), int(od_dzien))
        okres_do = date(int(do_rok), int(do_miesiac), int(do_dzien))

        pozycja = _pozycja_oddana_z_sekcji(tekst_sekcji, ppe, okres_od, okres_do)
        if pozycja is not None:
            pozycje.append(pozycja)

    return WynikOdczytuEnergiiOddanej(pozycje=pozycje, pominiete=[])
