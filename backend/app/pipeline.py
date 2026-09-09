"""Pełny cykl weryfikacji: parsuj plik -> uruchom reguły -> odfiltruj oznaczone -> pogrupuj."""
from __future__ import annotations

from pathlib import Path

from app.alerts import GrupaAlertow, grupuj
from app.excel_reader import parse_workbook
from app.rules import uruchom_wszystkie_reguly
from app.store import AlertStore


def zweryfikuj(sciezka_pliku: str | Path, rok: int, store: AlertStore) -> list[GrupaAlertow]:
    obiekty = parse_workbook(sciezka_pliku, rok=rok)
    alerty = uruchom_wszystkie_reguly(obiekty)
    aktywne = store.odfiltruj_aktywne(alerty)
    return grupuj(aktywne)
