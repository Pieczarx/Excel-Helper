"""Reguła: alert gdy wartość faktury jest >=2x lub <=0.5x poprzedniej faktury tego obiektu.

Przed porównaniem wartość bieżącej faktury jest normalizowana do długości okresu poprzedniej
faktury (żeby rzadka faktura dwumiesięczna nie generowała fałszywego alertu przy zwykłym,
proporcjonalnym wzroście zużycia/kosztów) - normalizacja jest tylko wewnętrznym krokiem obliczeń,
nie pokazujemy jej w opisie alertu (user: "bez sensu").
"""
from __future__ import annotations

from app.alerts import Alert
from app.excel_reader import Obiekt

PROG_GORNY = 2.0
PROG_DOLNY = 0.5
PROG_KRYTYCZNY = 5.0

WAGA_PODWYZSZONA = "PODWYZSZONA"
WAGA_KRYTYCZNA = "KRYTYCZNA"

FIELD_LABELS = {
    "zuzycie_razem": "Zużycie",
    "koszty_razem": "Koszty razem",
}


def _dni(okres) -> int:
    return (okres.data_do - okres.data_od).days + 1


def _zakres(okres) -> str:
    return f"{okres.data_od:%d.%m.%Y}-{okres.data_do:%d.%m.%Y}"


def _waga_ze_stosunku(stosunek: float) -> str:
    """Ekstremalność odchylenia w jedną stronę (1x = brak odchylenia), niezależnie od kierunku."""
    ekstremalnosc = stosunek if stosunek >= 1 else (float("inf") if stosunek == 0 else 1 / stosunek)
    return WAGA_KRYTYCZNA if ekstremalnosc > PROG_KRYTYCZNY else WAGA_PODWYZSZONA


def sprawdz_odchylenia(obiekty: list[Obiekt]) -> list[Alert]:
    alerty: list[Alert] = []
    for obiekt in obiekty:
        for poprzedni, biezacy in zip(obiekt.okresy, obiekt.okresy[1:]):
            dni_poprzedni = _dni(poprzedni)
            dni_biezacy = _dni(biezacy)
            if dni_poprzedni <= 0 or dni_biezacy <= 0:
                continue
            wspolczynnik_dni = dni_biezacy / dni_poprzedni

            for pole, etykieta in FIELD_LABELS.items():
                wartosc_poprzednia = getattr(poprzedni, pole)
                wartosc_biezaca_surowa = getattr(biezacy, pole)
                wartosc_biezaca = wartosc_biezaca_surowa / wspolczynnik_dni

                if wartosc_poprzednia == 0:
                    if wartosc_biezaca == 0:
                        continue
                    opis = (
                        f"{etykieta}:\n"
                        f"Poprzednia faktura ({_zakres(poprzedni)}) - {wartosc_poprzednia:g}\n"
                        f"Następna faktura ({_zakres(biezacy)}) - {wartosc_biezaca_surowa:g}\n"
                        f"wzrost z zera"
                    )
                    waga = WAGA_KRYTYCZNA
                else:
                    stosunek = wartosc_biezaca / wartosc_poprzednia
                    if not (stosunek >= PROG_GORNY or stosunek <= PROG_DOLNY):
                        continue
                    opis = (
                        f"{etykieta}:\n"
                        f"Poprzednia faktura ({_zakres(poprzedni)}) - {wartosc_poprzednia:g}\n"
                        f"Następna faktura ({_zakres(biezacy)}) - {wartosc_biezaca_surowa:g}\n"
                        f"{stosunek:.2f}x poprzedniej wartości"
                    )
                    waga = _waga_ze_stosunku(stosunek)

                alerty.append(
                    Alert(
                        rodzaj="ODCHYLENIE",
                        obiekt_wiersz=obiekt.wiersz,
                        obiekt_nazwa=obiekt.nazwa,
                        opis=opis,
                        okres_od=biezacy.data_od,
                        okres_do=biezacy.data_do,
                        pole=pole,
                        wartosc_poprzednia=wartosc_poprzednia,
                        wartosc_biezaca=wartosc_biezaca_surowa,
                        waga=waga,
                        komorka_poprzednia=poprzedni.komorka(pole),
                        komorka_biezaca=biezacy.komorka(pole),
                    )
                )
    return alerty
