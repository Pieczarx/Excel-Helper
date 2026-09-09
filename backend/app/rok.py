"""Automatyczne wykrywanie roku kalendarzowego z nazwy pliku - user nie wybiera roku ręcznie."""
from __future__ import annotations

import re
from pathlib import Path

_WZORZEC_ROKU = re.compile(r"(19|20)\d{2}")


class NieRozpoznanoRoku(ValueError):
    pass


def wykryj_rok(sciezka: str | Path) -> int:
    """Szuka czterocyfrowego roku (19xx/20xx) w nazwie pliku, np. 'MPECWIK 2026.xlsx' -> 2026."""
    nazwa = Path(sciezka).stem
    lata = sorted({int(m.group()) for m in _WZORZEC_ROKU.finditer(nazwa)})
    if len(lata) == 0:
        raise NieRozpoznanoRoku(f"Nie znaleziono roku w nazwie pliku {nazwa!r} - dopisz rok do nazwy pliku.")
    if len(lata) > 1:
        raise NieRozpoznanoRoku(f"Znaleziono więcej niż jeden możliwy rok w nazwie pliku {nazwa!r}: {lata}.")
    return lata[0]
