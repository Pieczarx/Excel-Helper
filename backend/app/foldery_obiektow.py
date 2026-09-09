"""Rozdziela wpisane faktury do folderów obiektów w drzewie faktur (np. `Faktury MPECWIK 2026/`),
kopiując je pod nazwą opartą o datę końcową okresu. Foldery obiektów mają PPE dopisane do nazwy
(`<nazwa> (<PPE>)` - patrz scripts/dopisz_ppe_do_folderow.py), więc dopasowanie jest tanim
skanowaniem drzewa i wyciągnięciem PPE z nazwy folderu, bez żadnego fuzzy matchingu na produkcji -
w szczególności folder może leżeć GDZIEKOLWIEK w drzewie i nazywać się zupełnie inaczej niż obiekt
w Excelu, wystarczy zgodne PPE w nazwie (np. użytkownik zakłada folder ręcznie dla nowego obiektu).

Duże odbiory dostają nazwę `D {MM}.{DD}.pdf` (miesiąc i dzień końca okresu - tak użytkownik już
ręcznie nazywał te pliki), Małe odbiory `D {MM}.pdf` (sam miesiąc). "Czy to duży odbiór" NIE jest
zgadywane po położeniu folderu w drzewie (np. czy leży pod 'DUŻE ODBIORY/') - to zawodzi, gdy
użytkownik założy folder nowego obiektu gdzie indziej. Zamiast tego opiera się na tym, przez który
arkusz PPE faktycznie zostało zapisane (patrz `wlasne_okresy_duzych` niżej, z
import_faktur_duze.wpisz_polaczone_pozycje_duze)."""
from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path

from app.foldery_wspolne import NAZWA_DO_AKTUALIZACJI, NAZWA_DO_WPISANIA, wolna_sciezka_docelowa
from app.import_faktur import WynikWpisu

KAT_BRAK_FOLDERU_OBIEKTU = "brak_folderu_obiektu"

# Foldery robocze/pomocnicze pod korzeniem drzewa faktur, które nie są folderami obiektów - nie
# skanujemy ich w poszukiwaniu PPE w nazwie.
WYKLUCZ = {NAZWA_DO_WPISANIA, NAZWA_DO_AKTUALIZACJI, "Faktury powyżej 16"}

_WZORZEC_PPE_W_NAZWIE = re.compile(r"\((\d+)\)$")


def zbuduj_mape_ppe_do_folderu(sciezka_faktur_root: str | Path) -> dict[str, Path]:
    """Kod PPE -> folder obiektu, wyciągnięte z nazw folderów kończących się na '(<PPE>)'."""
    root = Path(sciezka_faktur_root)
    mapa: dict[str, Path] = {}
    for folder in root.rglob("*"):
        if not folder.is_dir():
            continue
        if any(czesc in WYKLUCZ for czesc in folder.relative_to(root).parts):
            continue
        dopasowanie = _WZORZEC_PPE_W_NAZWIE.search(folder.name)
        if dopasowanie:
            mapa[dopasowanie.group(1)] = folder
    return mapa


def _nazwa_docelowa(jest_duzy_odbior: bool, okres_do: date) -> str:
    if jest_duzy_odbior:
        return f"D {okres_do.month:02d}.{okres_do.day:02d}.pdf"
    return f"D {okres_do.month:02d}.pdf"


def przenies_do_folderow_obiektow(
    sciezka_faktury: str | Path,
    sciezka_faktur_root: str | Path,
    mapa_ppe: dict[str, Path],
    wyniki: list[WynikWpisu],
    wlasne_okresy_duzych: dict[str, date] | None = None,
) -> list[WynikWpisu]:
    """Kopiuje `sciezka_faktury` do folderu każdego obiektu, którego PPE zostało dopasowane do
    wiersza w arkuszu (`wynik.wiersz is not None` - ten sam sygnał co w import_faktur_polaczony.py).
    Dla PPE bez folderu dokłada do wyniku alert `KAT_BRAK_FOLDERU_OBIEKTU` zamiast kopiować.
    Zwraca `wyniki` z dopisanymi alertami (oryginalne wpisy nietknięte).

    Lokalizacja obiektu jest zawsze po PPE, więc kopiowanie/alert też - RAZ na unikalny PPE, nie
    raz na wpis w `wyniki`. Od dodania arkusza 'fotowoltaika energia oddana' ten sam PPE może mieć
    DWA wpisy z dopasowanym wierszem z tego samego pliku (Duże odbiory + fotowoltaika, patrz
    foldery_faktur.py) - bez dedupu po PPE druga trafiona pozycja skopiowałaby tę samą fakturę
    jeszcze raz do tego samego folderu obiektu (kolizja nazwy -> zbędny "D MM.DD (1).pdf").

    `wlasne_okresy_duzych` to {PPE: własny okres_do TEGO pliku} dla PPE zapisanych przez Duże
    odbiory (z import_faktur_duze.wpisz_polaczone_pozycje_duze) - obecność PPE w tej mapie mówi
    "to zapisało się przez Duże odbiory" (stąd nazwa D MM.DD.pdf), a jego wartość to WŁASNY (nie
    połączony z innym plikiem) okres_do - gdy faktury tego samego PPE/miesiąca rozbite na kilka
    plików zostały połączone w jedną pozycję, `wynik.okres_do` niesie okres CAŁEJ połączonej
    pozycji, nie tego konkretnego pliku (bez tego obie połówki miesiąca dostałyby tę samą nazwę
    pliku w archiwum - kolizja). PPE spoza tej mapy to Małe odbiory (nazwa D MM.pdf, `wynik.okres_do`
    jak dotąd) - `None`/pusta mapa dla plików bez żadnego wkładu do Dużych odbiorów."""
    sciezka_faktury = Path(sciezka_faktury)
    wlasne_okresy_duzych = wlasne_okresy_duzych or {}
    wyniki_z_alertami = list(wyniki)
    ppe_juz_obsluzone: set[str] = set()

    for wynik in wyniki:
        if wynik.wiersz is None or wynik.ppe is None:
            continue
        if wynik.ppe in ppe_juz_obsluzone:
            continue
        ppe_juz_obsluzone.add(wynik.ppe)

        folder_obiektu = mapa_ppe.get(wynik.ppe)
        if folder_obiektu is None:
            wyniki_z_alertami.append(
                WynikWpisu(
                    kategoria=KAT_BRAK_FOLDERU_OBIEKTU,
                    ppe=wynik.ppe,
                    wiersz=wynik.wiersz,
                    nazwa_obiektu=wynik.nazwa_obiektu,
                    miesiac=wynik.miesiac,
                    okres_od=wynik.okres_od,
                    okres_do=wynik.okres_do,
                    opis="brak folderu obiektu z tym PPE w drzewie faktur - dopisz PPE do folderu ręcznie",
                    arkusz=wynik.arkusz,
                )
            )
            continue

        jest_duzy_odbior = wynik.ppe in wlasne_okresy_duzych
        okres_do = wlasne_okresy_duzych.get(wynik.ppe, wynik.okres_do)
        nazwa_docelowa = _nazwa_docelowa(jest_duzy_odbior, okres_do)
        cel = wolna_sciezka_docelowa(folder_obiektu, nazwa_docelowa)
        shutil.copy(sciezka_faktury, cel)

    return wyniki_z_alertami
