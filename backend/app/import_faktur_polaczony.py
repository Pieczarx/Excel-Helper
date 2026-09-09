"""Łączy zapis do 'Małe odbiory' i 'Duże odbiory' z jednej faktury PDF.

Który Kod PPE należy do którego arkusza nie jest wiadome z góry - obie sekcje-parsery
(wczytaj_fakture_dystrybucyjna / wczytaj_fakture_duzy_odbior, faktura_reader.py) próbują
odczytać KAŻDĄ sekcję faktury, niezależnie od tego, do którego arkusza faktycznie pasuje jej PPE
(np. faktura dużego odbioru ma też sekcję "Opłata zmienna sieciowa", więc parser Małych odbiorów
"poprawnie" ją odczyta, tylko potem nie znajdzie PPE w arkuszu Małe odbiory). Więc wołamy oba
zapisywacze i scalamy wyniki: `wiersz is not None` jest niezawodnym sygnałem "PPE faktycznie
dopasowano do wiersza w TYM arkuszu" (ustawiane tylko po trafieniu w mapie PPE->wiersz, patrz
_wpisz_pozycje/_wpisz_pozycje_duze) - więc wynik z drugiego przebiegu dla tego samego PPE bez
dopasowanego wiersza jest tylko szumem "nie tutaj" i można go bezpiecznie odrzucić."""
from __future__ import annotations

from pathlib import Path

from app.import_faktur import WynikWpisu, wpisz_fakture_do_arkusza
from app.import_faktur_duze import wpisz_fakture_duzy_odbior_do_arkusza


def polacz_i_wyczysc_szum(wyniki_male: list[WynikWpisu], wyniki_duze: list[WynikWpisu]) -> list[WynikWpisu]:
    """Scala wyniki obu arkuszy i odrzuca szum "nie tutaj" (patrz docstring modułu). Wydzielone
    z wpisz_fakture_do_wszystkich_arkuszy, żeby dało się użyć tej samej logiki, gdy `wyniki_duze`
    pochodzi z zapisu POŁĄCZONEGO z kilku plików naraz (patrz import_faktur_duze.py,
    wpisz_polaczone_pozycje_duze) - foldery_faktur.py woła to bezpośrednio w takim przypadku."""
    wszystkie = wyniki_male + wyniki_duze
    ppe_ze_znalezionym_wierszem = {w.ppe for w in wszystkie if w.wiersz is not None}

    polaczone: list[WynikWpisu] = []
    widziane: set[tuple] = set()
    for wynik in wszystkie:
        if wynik.wiersz is None and wynik.ppe in ppe_ze_znalezionym_wierszem:
            continue  # PPE poprawnie znaleziony w DRUGIM arkuszu - to tylko szum "nie tutaj"
        klucz = (wynik.kategoria, wynik.ppe, wynik.opis, wynik.miesiac)
        if klucz in widziane:
            continue  # oba parsery zgłosiły identyczny problem na tym samym tekście faktury
        widziane.add(klucz)
        polaczone.append(wynik)
    return polaczone


def wpisz_fakture_do_wszystkich_arkuszy(
    sciezka_excel: str | Path, sciezka_faktury: str | Path, nadpisuj: bool
) -> list[WynikWpisu]:
    """Parsuje jedną fakturę PDF i wpisuje jej pozycje zarówno do 'Małe odbiory', jak i 'Duże
    odbiory' (każda sekcja/PPE trafia do dokładnie jednego z nich). Zwraca połączoną, oczyszczoną
    z szumu listę wyników - do pokazania użytkownikowi jedną kartą na plik, tak jak dziś."""
    wyniki_male = wpisz_fakture_do_arkusza(sciezka_excel, sciezka_faktury, nadpisuj=nadpisuj)
    wyniki_duze = wpisz_fakture_duzy_odbior_do_arkusza(sciezka_excel, sciezka_faktury, nadpisuj=nadpisuj)
    return polacz_i_wyczysc_szum(wyniki_male, wyniki_duze)
