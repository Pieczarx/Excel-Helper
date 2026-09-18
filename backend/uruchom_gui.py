"""Punkt wejścia dla PyInstallera - cienki wrapper na app.main.main().

PyInstaller potrzebuje skryptu top-level (nie modułu odpalanego przez `python -m`), ale importy
w całej aplikacji są bezwzględne względem pakietu `app` (np. `from app.config import ...`) - ten
plik musi więc leżeć w `backend/`, obok folderu `app/`, żeby ten pakiet był importowalny.
"""
import os
import sys
import traceback
from pathlib import Path


def _zaloguj_i_zakoncz(typ, wartosc, tb) -> None:
    """Wlasny excepthook - aktywny TYLKO na czas importu ponizej (patrz przywrocenie domyslnego
    zaraz po nim), bo tylko tam jest potrzebny i tylko tam jego skutki uboczne sa bezpieczne.

    Appka jest okienkowa (console=False) - domyslnie PyInstaller na nieobsluzony wyjatek pokazuje
    natywne okno dialogowe z tracebackiem i NIE konczy przy tym procesu, dopoki ktos go recznie nie
    zamknie. To psulo retry w aktualizator.uruchom_ponownie(): swiezo podmieniony .exe po
    samoaktualizacji potrafi sie wywalic przy pierwszym starcie, w trakcie samego importu (np.
    antywirus skanuje w tle nierozpoznany plik w trakcie samorozpakowywania onefile - obserwowane
    jako "ModuleNotFoundError: No module named 'pyexpat'"), ale subprocess.Popen(...).poll() widzial
    taki proces jako dalej "zywy" (czekal na dialog), wiec petla ponownych prob uznawala to za
    sukces i nigdy faktycznie nie probowala ponownie - uzytkownik zostawal z samym dialogiem bledu
    zamiast dzialajacej appki (stary proces juz sie tymczasem zamknal).

    Zamiast dialogu: loguje do pliku obok danych appki i konczy proces NATYCHMIAST (os._exit, nie
    sys.exit - gwarancja, ze nic dalej nie zdazy zablokowac procesu), zeby retry mogl faktycznie
    zobaczyc krach i sprobowac ponownie.

    WAZNE: ten hook NIE moze zostac aktywny na cala reszte dzialania appki (po imporcie/w trakcie
    normalnej pracy) - inaczej KAZDY nieobsluzony wyjatek gdziekolwiek w appce (np. w handlerze po
    zalogowaniu) konczylby caly proces natychmiast i bez sladu, zamiast dac appce szanse dzialac
    dalej albo chociaz pokazac dialog z informacja co sie stalo. Dokladnie to sie stalo w 1.0.13 -
    stad przywrocenie domyslnego sys.excepthook zaraz po ryzykownym imporcie ponizej."""
    try:
        katalog_danych = (
            Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parent
        ) / "data"
        katalog_danych.mkdir(parents=True, exist_ok=True)
        with open(katalog_danych / "crash.log", "a", encoding="utf-8") as plik:
            traceback.print_exception(typ, wartosc, tb, file=plik)
            plik.write("\n")
    except Exception:
        pass
    os._exit(1)


sys.excepthook = _zaloguj_i_zakoncz

from app.main import main  # noqa: E402 - musi byc PO ustawieniu excepthooka wyzej

# Ryzykowny import juz za nami (to jedyne miejsce, gdzie zaobserwowano opisany wyzej krach) -
# appka od teraz dziala normalnie, wiec wraca domyslna obsluga nieobsluzonych wyjatkow.
sys.excepthook = sys.__excepthook__

if __name__ == "__main__":
    main()
