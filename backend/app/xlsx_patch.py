"""Wpisuje pojedyncze komórki bezpośrednio w skompresowanym XML-u arkusza, zamiast przez
`openpyxl.Workbook.save()`.

openpyxl przy zapisie całego skoroszytu regeneruje go od zera i gubi/psuje części, których w
pełni nie obsługuje - w prawdziwym pliku MPECWIK doszło to do głosu na zewnętrznym łączu
(`xl/externalLinks/`, referencja do starego `MPECWIK 2022.xlsx` na dysku sieciowym, z nowszym
rozszerzeniem `xxl21:alternateUrls`, którego openpyxl nie potrafi w pełni odtworzyć) oraz na
`sharedStrings.xml`/`printerSettings*.bin`/per-arkuszowych `.rels` - po zapisie przez openpyxl
Excel zgłaszał "znaleziono problem z zawartością pliku, naprawić?". Zamiast ryzykować to przy
każdym zapisie, modyfikujemy tylko dotknięte komórki bezpośrednio w XML-u jednego arkusza,
kopiując resztę archiwum zip 1:1, bajt w bajt.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

WORKBOOK_XML = "xl/workbook.xml"
WORKBOOK_RELS = "xl/_rels/workbook.xml.rels"
CALC_CHAIN = "xl/calcChain.xml"
CONTENT_TYPES = "[Content_Types].xml"


class KomorkaNieZnaleziona(ValueError):
    pass


def formatuj_liczbe(wartosc: float) -> str:
    if wartosc == int(wartosc):
        return str(int(wartosc))
    return repr(float(wartosc))


def _sciezka_arkusza(nazwa_arkusza: str, workbook_xml: str, rels_xml: str) -> str:
    dopasowanie = re.search(
        rf'<sheet\b[^>]*\bname="{re.escape(nazwa_arkusza)}"[^>]*\br:id="(?P<rid>[^"]+)"', workbook_xml
    )
    if dopasowanie is None:
        raise KomorkaNieZnaleziona(f"Nie znaleziono arkusza {nazwa_arkusza!r} w {WORKBOOK_XML}")
    rid = dopasowanie.group("rid")
    dopasowanie_rel = re.search(rf'<Relationship\b[^>]*\bId="{re.escape(rid)}"[^>]*\bTarget="([^"]+)"', rels_xml)
    if dopasowanie_rel is None:
        raise KomorkaNieZnaleziona(f"Nie znaleziono relacji {rid!r} w {WORKBOOK_RELS}")
    return "xl/" + dopasowanie_rel.group(1)


def _dopasuj_komorke(xml_arkusza: str, ref: str) -> re.Match:
    wzorzec = re.compile(rf'<c r="{re.escape(ref)}"(?:[^>]*?)(?:/>|>.*?</c>)', re.DOTALL)
    dopasowanie = wzorzec.search(xml_arkusza)
    if dopasowanie is None:
        raise KomorkaNieZnaleziona(
            f"Komórka {ref} nie istnieje w XML-u arkusza (wstawianie zupełnie nowych komórek nieobsługiwane)"
        )
    return dopasowanie


def _styl_komorki(znacznik_komorki: str) -> str | None:
    dopasowanie = re.search(r'\bs="(\d+)"', znacznik_komorki)
    return dopasowanie.group(1) if dopasowanie else None


def _nowy_znacznik(ref: str, wartosc: str | float, styl: str | None) -> str:
    atrybut_stylu = f' s="{styl}"' if styl is not None else ""
    if isinstance(wartosc, str):
        return f'<c r="{ref}"{atrybut_stylu} t="inlineStr"><is><t>{escape(wartosc)}</t></is></c>'
    return f'<c r="{ref}"{atrybut_stylu}><v>{formatuj_liczbe(wartosc)}</v></c>'


def _zamien_czesc_archiwum(sciezka_xlsx: Path, nazwa_czesci: str, nowa_zawartosc: str) -> None:
    tymczasowy = sciezka_xlsx.with_suffix(sciezka_xlsx.suffix + ".tmp")
    with zipfile.ZipFile(sciezka_xlsx) as zrodlo, zipfile.ZipFile(tymczasowy, "w", zipfile.ZIP_DEFLATED) as cel:
        for element in zrodlo.infolist():
            if element.filename == nazwa_czesci:
                cel.writestr(element, nowa_zawartosc.encode("utf-8"))
            else:
                cel.writestr(element, zrodlo.read(element.filename))
    tymczasowy.replace(sciezka_xlsx)


def _usun_calc_chain(sciezka_xlsx: Path) -> None:
    """Usuwa `xl/calcChain.xml` (jeśli jest) razem z jego wpisami w `.rels` i `[Content_Types].xml`.

    To tylko cache kolejności przeliczania formuł - Excel sam go odbuduje przy najbliższym
    otwarciu (i tak wymuszamy `fullCalcOnLoad`). Trzeba go usunąć, kiedy nadpisujemy komórkę,
    która wcześniej zawierała formułę: inaczej calcChain.xml dalej wskazuje na formułę, której
    faktycznie już nie ma w arkuszu, a Excel zgłasza to jako uszkodzoną zawartość ("naprawić plik?")."""
    with zipfile.ZipFile(sciezka_xlsx) as archiwum:
        if CALC_CHAIN not in archiwum.namelist():
            return
        rels_xml = archiwum.read(WORKBOOK_RELS).decode("utf-8")
        content_types_xml = archiwum.read(CONTENT_TYPES).decode("utf-8")

    rels_xml = re.sub(r'<Relationship\b[^>]*\bTarget="calcChain\.xml"[^>]*/>', "", rels_xml)
    content_types_xml = re.sub(r'<Override\b[^>]*\bPartName="/xl/calcChain\.xml"[^>]*/>', "", content_types_xml)

    tymczasowy = sciezka_xlsx.with_suffix(sciezka_xlsx.suffix + ".tmp")
    with zipfile.ZipFile(sciezka_xlsx) as zrodlo, zipfile.ZipFile(tymczasowy, "w", zipfile.ZIP_DEFLATED) as cel:
        for element in zrodlo.infolist():
            if element.filename == CALC_CHAIN:
                continue
            if element.filename == WORKBOOK_RELS:
                cel.writestr(element, rels_xml.encode("utf-8"))
            elif element.filename == CONTENT_TYPES:
                cel.writestr(element, content_types_xml.encode("utf-8"))
            else:
                cel.writestr(element, zrodlo.read(element.filename))
    tymczasowy.replace(sciezka_xlsx)


def wpisz_wartosci(sciezka_xlsx: str | Path, nazwa_arkusza: str, wartosci: dict[str, str | float]) -> None:
    """Wpisuje `wartosci` (adres komórki np. 'P3' -> tekst albo liczba) do arkusza `nazwa_arkusza`,
    zachowując istniejący styl (`s`) każdej komórki i nie ruszając żadnej innej części pliku
    (formuły, externalLinks, sharedStrings, printerSettings, pozostałe arkusze - bez zmian).

    Wyjątek: jeśli nadpisywana komórka WCZEŚNIEJ zawierała formułę (np. ktoś ręcznie wpisał
    "=178.99+387.55" łącząc dwie faktury), usuwamy `xl/calcChain.xml` - patrz `_usun_calc_chain`."""
    if not wartosci:
        return
    sciezka_xlsx = Path(sciezka_xlsx)

    with zipfile.ZipFile(sciezka_xlsx) as archiwum:
        workbook_xml = archiwum.read(WORKBOOK_XML).decode("utf-8")
        rels_xml = archiwum.read(WORKBOOK_RELS).decode("utf-8")
        sciezka_arkusza = _sciezka_arkusza(nazwa_arkusza, workbook_xml, rels_xml)
        xml_arkusza = archiwum.read(sciezka_arkusza).decode("utf-8")

    nadpisano_formule = False
    for ref, wartosc in wartosci.items():
        dopasowanie = _dopasuj_komorke(xml_arkusza, ref)
        if "<f" in dopasowanie.group():
            nadpisano_formule = True
        styl = _styl_komorki(dopasowanie.group())
        nowy = _nowy_znacznik(ref, wartosc, styl)
        xml_arkusza = xml_arkusza[: dopasowanie.start()] + nowy + xml_arkusza[dopasowanie.end():]

    _zamien_czesc_archiwum(sciezka_xlsx, sciezka_arkusza, xml_arkusza)

    if nadpisano_formule:
        _usun_calc_chain(sciezka_xlsx)


def wymus_przeliczenie_formul(sciezka_xlsx: str | Path) -> None:
    """Ustawia fullCalcOnLoad="1" w <calcPr>, żeby Excel przy najbliższym otwarciu przeliczył
    formuły (np. "Razem zużycie") - openpyxl/nasz surowy zapis XML nie liczy formuł same,
    więc bez tego cache'owana wartość formuły zostałaby stara/zerowa aż do ręcznego przeliczenia."""
    sciezka_xlsx = Path(sciezka_xlsx)
    with zipfile.ZipFile(sciezka_xlsx) as archiwum:
        workbook_xml = archiwum.read(WORKBOOK_XML).decode("utf-8")

    if 'fullCalcOnLoad="1"' in workbook_xml:
        return

    if "<calcPr" in workbook_xml:
        nowy_xml, liczba = re.subn(r"<calcPr\b\s*", '<calcPr fullCalcOnLoad="1" ', workbook_xml, count=1)
    else:
        nowy_xml, liczba = re.subn(r"</workbook>", '<calcPr fullCalcOnLoad="1"/></workbook>', workbook_xml, count=1)
    if liczba == 0:
        raise KomorkaNieZnaleziona(f"Nie udało się ustawić fullCalcOnLoad w {WORKBOOK_XML}")

    _zamien_czesc_archiwum(sciezka_xlsx, WORKBOOK_XML, nowy_xml)
