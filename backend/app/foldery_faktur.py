"""Dwa foldery robocze do wpisywania faktur - patrz [[project_excelhelper_invoice_import_feasibility]]:

- "Do wpisania"    - wpisuje tylko do pustych komórek (nadpisuj=False)
- "Do aktualizacji" - wolno nadpisać istniejące dane (nadpisuj=True)

To jest cały mechanizm "skąd wziąć faktury" - użytkownik ręcznie wrzuca PDF-y do właściwego
folderu, nie ma żadnego zgadywania po nazwie/dacie pliku. Po przetworzeniu, jeśli faktura zapisała
choć jedną pozycję do Excela, plik trafia (kopiowany, patrz foldery_obiektow.py) do folderów
obiektów, których dotyczy, i znika stąd - nie zostaje kopia w "Do wpisania"/"Do aktualizacji".
Plik, który w ogóle nie zapisał niczego (ani jedna pozycja nie dopasowała PPE do wiersza w
arkuszu), wędruje do podfolderu "Przetworzone" jak dawniej - nie ma dokąd go skopiować, a bez
śladu byłby stratą. Plik, którego w ogóle nie udało się rozpoznać jako fakturę dystrybucyjną,
zostaje w miejscu (nie w Przetworzone) - to sygnał dla użytkownika, że coś w nim wymaga uwagi.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from app.faktura_reader import NieRozpoznanoFaktury
from app.foldery_obiektow import przenies_do_folderow_obiektow, zbuduj_mape_ppe_do_folderu
from app.foldery_wspolne import NAZWA_DO_AKTUALIZACJI, NAZWA_DO_WPISANIA, NAZWA_PRZETWORZONE, wolna_sciezka_docelowa
from app.import_faktur import WynikWpisu, wpisz_fakture_do_arkusza
from app.import_faktur_duze import wpisz_polaczone_pozycje_duze
from app.import_faktur_oddana import wpisz_polaczone_pozycje_oddana
from app.import_faktur_polaczony import polacz_i_wyczysc_szum


@dataclass
class WynikPrzetworzeniaPliku:
    sciezka: Path
    wyniki: list[WynikWpisu] = field(default_factory=list)
    blad: str | None = None


def upewnij_sie_ze_foldery_istnieja(sciezka_faktur: str | Path) -> None:
    """Tworzy 'Do wpisania'/'Do aktualizacji' (i ich podfoldery 'Przetworzone') pod wskazanym
    folderem, jeśli jeszcze nie istnieją. Bezpieczne do wywołania wielokrotnie."""
    root = Path(sciezka_faktur)
    for nazwa in (NAZWA_DO_WPISANIA, NAZWA_DO_AKTUALIZACJI):
        (root / nazwa / NAZWA_PRZETWORZONE).mkdir(parents=True, exist_ok=True)


def znajdz_faktury(folder: Path) -> list[Path]:
    """PDF-y bezpośrednio w folderze (i podfolderach), z pominięciem 'Przetworzone'."""
    return sorted(
        p
        for p in folder.rglob("*.pdf")
        if NAZWA_PRZETWORZONE not in p.relative_to(folder).parts
    )


def dodaj_do_kolejki(sciezka_zrodlowa: str | Path, folder_docelowy: str | Path) -> Path:
    """Kopiuje upuszczony/wybrany PDF do 'Do wpisania' albo 'Do aktualizacji' (kopia, nie
    przeniesienie - upuszczenie pliku np. z załącznika e-maila nie powinno go stamtąd usuwać).
    Kolizja nazwy z plikiem już czekającym w kolejce dostaje licznik, tak samo jak w 'Przetworzone'."""
    folder_docelowy = Path(folder_docelowy)
    folder_docelowy.mkdir(parents=True, exist_ok=True)
    cel = wolna_sciezka_docelowa(folder_docelowy, Path(sciezka_zrodlowa).name)
    shutil.copy(sciezka_zrodlowa, cel)
    return cel


def przetworz_folder(
    sciezka_excel: str | Path, folder: str | Path, nadpisuj: bool, sciezka_faktur_root: str | Path
) -> list[WynikPrzetworzeniaPliku]:
    """Przetwarza wszystkie faktury PDF w `folder` (poza 'Przetworzone').

    Duże odbiory i fotowoltaika (energia oddana) są zapisywane w przebiegach po WSZYSTKICH plikach
    naraz (wpisz_polaczone_pozycje_duze / wpisz_polaczone_pozycje_oddana - żeby połączyć faktury
    tego samego PPE/miesiąca rozbite na kilka plików, patrz import_faktur_duze.py, potwierdzone na
    Kórnicka 82: zmiana taryfy w środku miesiąca dała dwie osobne faktury za połówki miesiąca),
    potem Małe odbiory per plik jak dawniej. Wynik Małe+Duże łączy polacz_i_wyczysc_szum (ten sam
    mechanizm "nie tutaj" co wcześniej w wpisz_fakture_do_wszystkich_arkuszy) - fotowoltaika NIE
    przechodzi przez to czyszczenie szumu i jest dopisywana osobno: jej PPE to zawsze podzbiór
    Dużych odbiorów, więc udany zapis fotowoltaiki i udany zapis Dużych odbiorów dla tego samego
    PPE/miesiąca miałyby identyczny klucz dedupu (kategoria, ppe, opis, miesiąc) i jeden z dwóch
    prawdziwych sukcesów zostałby błędnie odrzucony jako "duplikat".

    Plik, który zapisał choć jedną pozycję do Excela (`wynik.wiersz is not None` dla choć jednego
    wpisu), zostaje skopiowany do folderów obiektów pod `sciezka_faktur_root` (patrz
    foldery_obiektow.py - PPE bez folderu dostaje tam alert `KAT_BRAK_FOLDERU_OBIEKTU`; ten sam PPE
    trafiony jednocześnie w Dużych odbiorach i fotowoltaice kopiuje plik tylko RAZ - patrz dedup po
    PPE w przenies_do_folderow_obiektow) i USUNIĘTY stąd - nie zostaje kopia w kolejce. Plik, który
    sparsował się, ale nic nie zapisał (same PPE nieznalezione), wędruje do 'Przetworzone' jak
    dawniej. Plik, którego w ogóle nie dało się rozpoznać, zostaje na miejscu."""
    folder = Path(folder)
    folder_przetworzonych = folder / NAZWA_PRZETWORZONE
    folder_przetworzonych.mkdir(parents=True, exist_ok=True)
    mapa_ppe = zbuduj_mape_ppe_do_folderu(sciezka_faktur_root)

    pliki = znajdz_faktury(folder)
    if pliki:
        wyniki_duze_per_plik, wlasne_okresy_duze_per_plik = wpisz_polaczone_pozycje_duze(sciezka_excel, pliki, nadpisuj)
        wyniki_oddana_per_plik = wpisz_polaczone_pozycje_oddana(sciezka_excel, pliki, nadpisuj)
    else:
        wyniki_duze_per_plik, wlasne_okresy_duze_per_plik = {}, {}
        wyniki_oddana_per_plik = {}

    wyniki_plikow: list[WynikPrzetworzeniaPliku] = []
    for sciezka_faktury in pliki:
        try:
            wyniki_male = wpisz_fakture_do_arkusza(sciezka_excel, sciezka_faktury, nadpisuj=nadpisuj)
        except NieRozpoznanoFaktury as exc:
            wyniki_plikow.append(WynikPrzetworzeniaPliku(sciezka=sciezka_faktury, blad=str(exc)))
            continue

        wyniki = polacz_i_wyczysc_szum(wyniki_male, wyniki_duze_per_plik.get(sciezka_faktury, []))
        wyniki += wyniki_oddana_per_plik.get(sciezka_faktury, [])

        if any(w.wiersz is not None for w in wyniki):
            wyniki = przenies_do_folderow_obiektow(
                sciezka_faktury, sciezka_faktur_root, mapa_ppe, wyniki,
                wlasne_okresy_duzych=wlasne_okresy_duze_per_plik.get(sciezka_faktury),
            )
            sciezka_faktury.unlink()
            wyniki_plikow.append(WynikPrzetworzeniaPliku(sciezka=sciezka_faktury, wyniki=wyniki))
        else:
            cel = wolna_sciezka_docelowa(folder_przetworzonych, sciezka_faktury.name)
            sciezka_faktury.rename(cel)
            wyniki_plikow.append(WynikPrzetworzeniaPliku(sciezka=cel, wyniki=wyniki))

    return wyniki_plikow


def przetworz_foldery_faktur(
    sciezka_excel: str | Path, sciezka_faktur: str | Path
) -> dict[str, list[WynikPrzetworzeniaPliku]]:
    """Przetwarza po kolei 'Do wpisania' (bez nadpisywania) i 'Do aktualizacji' (z nadpisywaniem)
    pod `sciezka_faktur`. To jest funkcja, którą docelowo wywoła przycisk 'Aktualizuj dane'."""
    root = Path(sciezka_faktur)
    upewnij_sie_ze_foldery_istnieja(root)
    return {
        NAZWA_DO_WPISANIA: przetworz_folder(sciezka_excel, root / NAZWA_DO_WPISANIA, nadpisuj=False, sciezka_faktur_root=root),
        NAZWA_DO_AKTUALIZACJI: przetworz_folder(sciezka_excel, root / NAZWA_DO_AKTUALIZACJI, nadpisuj=True, sciezka_faktur_root=root),
    }
