"""Wpisuje pozycje z faktur dystrybucyjnych PDF do arkusza 'Duże odbiory', dopasowując obiekty
po Kodzie PPE - mirror import_faktur.py (Małe odbiory), patrz tam po ogólny opis mechanizmu
zapisu (xlsx_patch.py, formuły niedotykane, "nie nadpisuj bez zgody").

Różnica: tu niezgodność sumy zużycia (P-S1+P-S2 z ODCZYTY vs "Zużycie: X kWh" z faktury) NIE
blokuje zapisu - z decyzji użytkownika dane do arkusza nadal biorą się z ODCZYTY, a niezgodność
(np. błąd po stronie ENEA - potwierdzone na fakturze Brodowo D 03 31.pdf, różnica 25 kWh) tylko
oznacza wynik kategorią KAT_ZUZYCIE_NIEZGODNE_Z_FAKTURA, żeby user to zweryfikował ręcznie."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import openpyxl
from openpyxl.utils import get_column_letter

from app import xlsx_patch
from app.excel_reader import norm
from app.excel_reader_duze import (
    FIRST_DATA_ROW_DUZE,
    SHEET_NAME_DUZE,
    find_block_starts_duze,
    find_identity_headers_duze,
    find_name_column_duze,
    read_block_columns_duze,
)
from app.faktura_reader import (
    KAT_DANE_NIEROZPOZNANE,
    KAT_JUZ_WYPELNIONE,
    KAT_PPE_NIEZNALEZIONE,
    KAT_SUKCES,
    KAT_ZUZYCIE_NIEZGODNE_Z_FAKTURA,
    NieRozpoznanoFaktury,
    PominietaSekcja,
    PozycjaFakturyDuze,
    wczytaj_fakture_duzy_odbior,
)
from app.import_faktur import WynikWpisu

TOLERANCJA_SUMY_KWH = 0.5

# Pola pisane wprost - "Razem zużycie"/"Razem" to formuły (jak w Małe odbiory), "Opłata netto
# energia el." nie jest dziś wypełniana (osobna faktura sprzedażowa, poza zakresem).
POLA_DO_ZAPISU = (
    "moc_pobrana", "p_s1", "p_s2", "p_s3",
    "q_plus_s1", "q_plus_s2", "q_plus_s3", "q_minus_s1", "q_minus_s2", "q_minus_s3",
    "q_plus_zl", "q_minus_zl",
    "oplata_dystrybucja",
)


def _bloki_po_miesiacu_duze(ws, kolumny_startowe: list[int]) -> dict[int, dict[str, int]]:
    """Numer miesiąca (1-12) -> mapowanie pole->kolumna. Arkusz Duże odbiory nie ma wiersza z
    nazwami miesięcy - bloki są w kolejności występowania (1. = styczeń, ..., 12. = grudzień)."""
    return {indeks + 1: read_block_columns_duze(ws, start) for indeks, start in enumerate(kolumny_startowe)}


def _wiersze_po_ppe_duze(ws, name_col: int, ppe_col: int | None) -> dict[str, tuple[int, str]]:
    if ppe_col is None:
        return {}
    wynik: dict[str, tuple[int, str]] = {}
    for row in range(FIRST_DATA_ROW_DUZE, ws.max_row + 1):
        nazwa = ws.cell(row=row, column=name_col).value
        if nazwa is None or norm(nazwa) == "":
            continue
        ppe = norm(ws.cell(row=row, column=ppe_col).value)
        if ppe:
            wynik[ppe] = (row, norm(nazwa))
    return wynik


def _komorki_puste_duze(ws, wiersz: int, kolumny: dict[str, int]) -> bool:
    for pole in ("moc_pobrana", "p_s1", "p_s2", "oplata_dystrybucja"):
        col = kolumny.get(pole)
        if col is not None and norm(ws.cell(row=wiersz, column=col).value) != "":
            return False
    return True


def _referencja(wiersz: int, kolumna: int) -> str:
    return f"{get_column_letter(kolumna)}{wiersz}"


def _wpisz_pozycje_duze(
    ws,
    pozycje: list[PozycjaFakturyDuze],
    bloki_po_miesiacu: dict[int, dict[str, int]],
    wiersze_po_ppe: dict[str, tuple[int, str]],
    nadpisuj: bool,
) -> tuple[list[WynikWpisu], dict[str, str | float]]:
    wyniki: list[WynikWpisu] = []
    zapisy: dict[str, str | float] = {}
    for pozycja in pozycje:
        miesiac = pozycja.okres_do.month
        trafienie = wiersze_po_ppe.get(pozycja.ppe)
        if trafienie is None:
            wyniki.append(
                WynikWpisu(
                    kategoria=KAT_PPE_NIEZNALEZIONE,
                    ppe=pozycja.ppe,
                    wiersz=None,
                    nazwa_obiektu=None,
                    miesiac=miesiac,
                    okres_od=pozycja.okres_od,
                    okres_do=pozycja.okres_do,
                    opis="brak obiektu z tym numerem PPE w arkuszu",
                    arkusz=SHEET_NAME_DUZE,
                )
            )
            continue
        wiersz, nazwa_obiektu = trafienie

        kolumny = bloki_po_miesiacu.get(miesiac)
        if kolumny is None:
            wyniki.append(
                WynikWpisu(
                    kategoria=KAT_DANE_NIEROZPOZNANE,
                    ppe=pozycja.ppe,
                    wiersz=wiersz,
                    nazwa_obiektu=nazwa_obiektu,
                    miesiac=miesiac,
                    okres_od=pozycja.okres_od,
                    okres_do=pozycja.okres_do,
                    opis="nie znaleziono bloku dla tego miesiąca w arkuszu",
                    arkusz=SHEET_NAME_DUZE,
                )
            )
            continue

        if not nadpisuj and not _komorki_puste_duze(ws, wiersz, kolumny):
            wyniki.append(
                WynikWpisu(
                    kategoria=KAT_JUZ_WYPELNIONE,
                    ppe=pozycja.ppe,
                    wiersz=wiersz,
                    nazwa_obiektu=nazwa_obiektu,
                    miesiac=miesiac,
                    okres_od=pozycja.okres_od,
                    okres_do=pozycja.okres_do,
                    opis="komórki już wypełnione (tryb bez nadpisywania)",
                    arkusz=SHEET_NAME_DUZE,
                )
            )
            continue

        wartosci = {
            "moc_pobrana": pozycja.moc_pobrana,
            "p_s1": pozycja.p_s1,
            "p_s2": pozycja.p_s2,
            "p_s3": pozycja.p_s3,
            "q_plus_s1": pozycja.q_plus_s1,
            "q_plus_s2": pozycja.q_plus_s2,
            "q_plus_s3": pozycja.q_plus_s3,
            "q_minus_s1": pozycja.q_minus_s1,
            "q_minus_s2": pozycja.q_minus_s2,
            "q_minus_s3": pozycja.q_minus_s3,
            "q_plus_zl": pozycja.q_plus_zl,
            "q_minus_zl": pozycja.q_minus_zl,
            "oplata_dystrybucja": pozycja.oplata_dystrybucja,
        }
        # Taryfa 2-strefowa: *_s3 to fikcyjne 0.0 (patrz PozycjaFakturyDuze.trzy_strefy) - kolumny
        # P-S3/Q+S3/Q-S3 mają zostać puste, nie dostać literalne zero.
        pola = POLA_DO_ZAPISU if pozycja.trzy_strefy else tuple(p for p in POLA_DO_ZAPISU if not p.endswith("_s3"))
        for pole in pola:
            col = kolumny.get(pole)
            if col is not None:
                zapisy[_referencja(wiersz, col)] = wartosci[pole]

        wartosci_wyswietlane: dict[str, float] = {"P-S1": pozycja.p_s1, "P-S2": pozycja.p_s2}
        if pozycja.trzy_strefy:
            wartosci_wyswietlane["P-S3"] = pozycja.p_s3
        wartosci_wyswietlane["Razem"] = pozycja.p_s1 + pozycja.p_s2 + pozycja.p_s3
        wartosci_wyswietlane["Dystrybucja"] = pozycja.oplata_dystrybucja

        # Niezgodność NIE blokuje zapisu (ten sam mechanizm co KAT_NIEZGODNOSC_SUMY w Małe
        # odbiory) - z decyzji użytkownika dane i tak biorą się z ODCZYTY, to tylko ostrzeżenie
        # do sprawdzenia. Dla taryf 3-strefowych P-S1/P-S2/P-S3 mają już doliczone liczniki strat
        # (patrz faktura_reader.py), więc suma powinna się zgadzać z fakturą co do kWh.
        suma = pozycja.p_s1 + pozycja.p_s2 + pozycja.p_s3
        if abs(suma - pozycja.zuzycie_razem_faktura) > TOLERANCJA_SUMY_KWH:
            wyniki.append(
                WynikWpisu(
                    kategoria=KAT_ZUZYCIE_NIEZGODNE_Z_FAKTURA,
                    ppe=pozycja.ppe,
                    wiersz=wiersz,
                    nazwa_obiektu=nazwa_obiektu,
                    miesiac=miesiac,
                    okres_od=pozycja.okres_od,
                    okres_do=pozycja.okres_do,
                    opis=(
                        f"P-S1+P-S2+P-S3 ({suma:g}) nie zgadza się z zużyciem na fakturze "
                        f"({pozycja.zuzycie_razem_faktura:g})"
                    ),
                    arkusz=SHEET_NAME_DUZE,
                )
            )
            continue

        wyniki.append(
            WynikWpisu(
                kategoria=KAT_SUKCES,
                ppe=pozycja.ppe,
                wiersz=wiersz,
                nazwa_obiektu=nazwa_obiektu,
                miesiac=miesiac,
                okres_od=pozycja.okres_od,
                okres_do=pozycja.okres_do,
                arkusz=SHEET_NAME_DUZE,
                wartosci=wartosci_wyswietlane,
            )
        )
    return wyniki, zapisy


def wpisz_fakture_duzy_odbior_do_arkusza(
    sciezka_excel: str | Path, sciezka_faktury: str | Path, nadpisuj: bool
) -> list[WynikWpisu]:
    """Parsuje jedną fakturę dystrybucyjną PDF i wpisuje jej pozycje do arkusza 'Duże odbiory',
    dopasowując po Kodzie PPE. Zapisuje plik Excela na miejscu."""
    wynik_faktury = wczytaj_fakture_duzy_odbior(sciezka_faktury)

    wb = openpyxl.load_workbook(sciezka_excel, data_only=False)
    ws = wb[SHEET_NAME_DUZE]

    name_col = find_name_column_duze(ws)
    kolumny_startowe = find_block_starts_duze(ws)
    pierwszy_blok = min(kolumny_startowe) if kolumny_startowe else ws.max_column + 1
    identity_headers = find_identity_headers_duze(ws, pierwszy_blok)

    bloki_po_miesiacu = _bloki_po_miesiacu_duze(ws, kolumny_startowe)
    wiersze_po_ppe = _wiersze_po_ppe_duze(ws, name_col, identity_headers.get("Kod PPE"))

    wyniki, zapisy = _wpisz_pozycje_duze(ws, wynik_faktury.pozycje, bloki_po_miesiacu, wiersze_po_ppe, nadpisuj)

    for sekcja in wynik_faktury.pominiete:
        wyniki.append(
            WynikWpisu(
                kategoria=sekcja.kategoria,
                ppe=sekcja.ppe,
                wiersz=None,
                nazwa_obiektu=None,
                miesiac=sekcja.okres_do.month if sekcja.okres_do else 0,
                okres_od=sekcja.okres_od,
                okres_do=sekcja.okres_do,
                opis=sekcja.opis,
                arkusz=SHEET_NAME_DUZE,
            )
        )

    if zapisy:
        xlsx_patch.wpisz_wartosci(sciezka_excel, SHEET_NAME_DUZE, zapisy)
        xlsx_patch.wymus_przeliczenie_formul(sciezka_excel)

    return wyniki


def polacz_pozycje_wielookresowe(
    pozycje_ze_zrodlem: list[tuple[Path, PozycjaFakturyDuze]],
) -> list[tuple[list[Path], PozycjaFakturyDuze]]:
    """Łączy pozycje tego samego PPE i tego samego miesiąca docelowego (`okres_do.month`) z RÓŻNYCH
    plików w jedną, zsumowaną pozycję - potwierdzone na Kórnicka 82: taryfa zmieniła się w środku
    lutego, więc ENEA wystawiła dwie osobne faktury za połówki miesiąca (1-19 i 20-28) zamiast
    jednej z dwiema parami stref w środku (tak jak to bywa w Małe odbiory - patrz
    faktura_reader.py, FAKTURA_ZE_ZMIANA_TARYFY). Bez tego druga faktura dostałaby "już wypełnione"
    i jej połowa miesiąca zostałaby bezpowrotnie zgubiona.

    P-S1/P-S2/P-S3, energia bierna, opłaty i zużycie z faktury sumują się (to addytywne wielkości
    za kawałek okresu - zweryfikowane liczbowo na Kórnicka 82, suma obu połówek zgadza się co do
    grosza z danymi już w arkuszu). `moc_pobrana` bierze MAKSIMUM, nie sumę - to szczyt poboru mocy
    w danym momencie, nie wielkość addytywna (potwierdzone: druga połówka lutego miała moc_pobrana
    wyższą niż suma, i to ona - nie suma - zgadzała się z arkuszem).

    Zwraca listę (pliki_źródłowe, pozycja_połączona), po jednej na (PPE, miesiąc) w kolejności
    pierwszego wystąpienia - dla PPE/miesięcy z jednym plikiem to ten sam plik i ta sama pozycja
    bez żadnych zmian."""
    grupy: dict[tuple[str, int], list[tuple[Path, PozycjaFakturyDuze]]] = {}
    kolejnosc: list[tuple[str, int]] = []
    for plik, pozycja in pozycje_ze_zrodlem:
        klucz = (pozycja.ppe, pozycja.okres_do.month)
        if klucz not in grupy:
            grupy[klucz] = []
            kolejnosc.append(klucz)
        grupy[klucz].append((plik, pozycja))

    polaczone: list[tuple[list[Path], PozycjaFakturyDuze]] = []
    for klucz in kolejnosc:
        czlonkowie = grupy[klucz]
        pliki = [plik for plik, _ in czlonkowie]
        if len(czlonkowie) == 1:
            polaczone.append((pliki, czlonkowie[0][1]))
            continue

        pozycje = [pozycja for _, pozycja in czlonkowie]
        polaczone.append(
            (
                pliki,
                PozycjaFakturyDuze(
                    ppe=pozycje[0].ppe,
                    okres_od=min(p.okres_od for p in pozycje),
                    okres_do=max(p.okres_do for p in pozycje),
                    moc_pobrana=max(p.moc_pobrana for p in pozycje),
                    p_s1=sum(p.p_s1 for p in pozycje),
                    p_s2=sum(p.p_s2 for p in pozycje),
                    p_s3=sum(p.p_s3 for p in pozycje),
                    q_plus_s1=sum(p.q_plus_s1 for p in pozycje),
                    q_plus_s2=sum(p.q_plus_s2 for p in pozycje),
                    q_plus_s3=sum(p.q_plus_s3 for p in pozycje),
                    q_minus_s1=sum(p.q_minus_s1 for p in pozycje),
                    q_minus_s2=sum(p.q_minus_s2 for p in pozycje),
                    q_minus_s3=sum(p.q_minus_s3 for p in pozycje),
                    q_plus_zl=sum(p.q_plus_zl for p in pozycje),
                    q_minus_zl=sum(p.q_minus_zl for p in pozycje),
                    oplata_dystrybucja=sum(p.oplata_dystrybucja for p in pozycje),
                    zuzycie_razem_faktura=sum(p.zuzycie_razem_faktura for p in pozycje),
                    trzy_strefy=pozycje[0].trzy_strefy,
                ),
            )
        )
    return polaczone


def wpisz_polaczone_pozycje_duze(
    sciezka_excel: str | Path, sciezki_faktur: list[str | Path], nadpisuj: bool
) -> tuple[dict[Path, list[WynikWpisu]], dict[Path, dict[str, date]]]:
    """Parsuje WSZYSTKIE podane faktury naraz (bez zapisu), łączy pozycje tego samego PPE/miesiąca
    rozbite na kilka plików (patrz polacz_pozycje_wielookresowe) i zapisuje połączony wynik do
    arkusza 'Duże odbiory' jednym zapisem.

    Zwraca (wynik per plik źródłowy, własny okres_do per PPE per plik źródłowy):
    - pliki, które wspólnie złożyły się na tę samą (połączoną) pozycję, dostają identyczne wpisy
      w pierwszej mapie, każdy do własnego routingu/kolejki w foldery_faktur.py;
    - druga mapa (plik -> {PPE: własny okres_do}) niesie WŁASNY (nie połączony) okres_do każdego
      PPE z TEGO KONKRETNEGO pliku - do nazwy pliku w archiwum obiektu (patrz foldery_obiektow.py)
      i do rozpoznania "ten PPE poszedł przez Duże odbiory" bez zgadywania po strukturze folderów
      (użytkownik mógł ręcznie założyć folder gdziekolwiek, niekoniecznie pod 'DUŻE ODBIORY/').
      Bez tego obie połówki miesiąca dostałyby tę samą nazwę pliku w archiwum (kolizja)."""
    sciezki = [Path(p) for p in sciezki_faktur]
    pozycje_ze_zrodlem: list[tuple[Path, PozycjaFakturyDuze]] = []
    pominiete_ze_zrodlem: list[tuple[Path, PominietaSekcja]] = []
    for sciezka in sciezki:
        try:
            wynik_faktury = wczytaj_fakture_duzy_odbior(sciezka)
        except NieRozpoznanoFaktury:
            continue  # w ogóle nie faktura dystrybucyjna - zgłosi to osobno przebieg Małe odbiory
        pozycje_ze_zrodlem.extend((sciezka, p) for p in wynik_faktury.pozycje)
        pominiete_ze_zrodlem.extend((sciezka, s) for s in wynik_faktury.pominiete)

    grupy = polacz_pozycje_wielookresowe(pozycje_ze_zrodlem)

    wb = openpyxl.load_workbook(sciezka_excel, data_only=False)
    ws = wb[SHEET_NAME_DUZE]
    name_col = find_name_column_duze(ws)
    kolumny_startowe = find_block_starts_duze(ws)
    pierwszy_blok = min(kolumny_startowe) if kolumny_startowe else ws.max_column + 1
    identity_headers = find_identity_headers_duze(ws, pierwszy_blok)
    bloki_po_miesiacu = _bloki_po_miesiacu_duze(ws, kolumny_startowe)
    wiersze_po_ppe = _wiersze_po_ppe_duze(ws, name_col, identity_headers.get("Kod PPE"))

    pozycje_polaczone = [pozycja for _, pozycja in grupy]
    wyniki, zapisy = _wpisz_pozycje_duze(ws, pozycje_polaczone, bloki_po_miesiacu, wiersze_po_ppe, nadpisuj)

    wynik_per_plik: dict[Path, list[WynikWpisu]] = {plik: [] for plik in sciezki}
    for (pliki_grupy, _pozycja), wpis in zip(grupy, wyniki):
        for plik in pliki_grupy:
            wynik_per_plik[plik].append(wpis)
    for plik, sekcja in pominiete_ze_zrodlem:
        wynik_per_plik[plik].append(
            WynikWpisu(
                kategoria=sekcja.kategoria,
                ppe=sekcja.ppe,
                wiersz=None,
                nazwa_obiektu=None,
                miesiac=sekcja.okres_do.month if sekcja.okres_do else 0,
                okres_od=sekcja.okres_od,
                okres_do=sekcja.okres_do,
                opis=sekcja.opis,
                arkusz=SHEET_NAME_DUZE,
            )
        )

    if zapisy:
        xlsx_patch.wpisz_wartosci(sciezka_excel, SHEET_NAME_DUZE, zapisy)
        xlsx_patch.wymus_przeliczenie_formul(sciezka_excel)

    wlasny_okres_do: dict[Path, dict[str, date]] = {}
    for plik, pozycja in pozycje_ze_zrodlem:
        wlasny_okres_do.setdefault(plik, {})[pozycja.ppe] = pozycja.okres_do
    return wynik_per_plik, wlasny_okres_do
