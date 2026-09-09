"""Wspólny model alertu zwracanego przez silnik reguł."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date


@dataclass
class Alert:
    rodzaj: str  # "ODCHYLENIE" | "LUKA_CIAGLOSCI"
    obiekt_wiersz: int
    obiekt_nazwa: str
    opis: str
    okres_od: date | None = None
    okres_do: date | None = None
    pole: str | None = None
    wartosc_poprzednia: float | None = None
    wartosc_biezaca: float | None = None
    waga: str | None = None  # "PODWYZSZONA" | "KRYTYCZNA" - tylko dla ODCHYLENIE, patrz rules/deviation.py
    komorka_poprzednia: str | None = None
    komorka_biezaca: str | None = None

    @property
    def klucz(self) -> str:
        """Stabilny identyfikator alertu, używany do zapamiętania 'oznaczone jako prawidłowe'.

        Zawiera wartości wejściowe (nie tylko obiekt+okres+pole) — jeśli którakolwiek z danych,
        na podstawie których alert powstał, zostanie później zmieniona w źródle, klucz się zmieni
        i alert wróci jako nowy, mimo że dotyczy tego samego obiektu/okresu/pola.
        """
        czesci = [
            self.rodzaj,
            str(self.obiekt_wiersz),
            self.okres_od.isoformat() if self.okres_od else "",
            self.okres_do.isoformat() if self.okres_do else "",
            self.pole or "",
            f"{self.wartosc_poprzednia:.4f}" if self.wartosc_poprzednia is not None else "",
            f"{self.wartosc_biezaca:.4f}" if self.wartosc_biezaca is not None else "",
        ]
        return hashlib.sha256("|".join(czesci).encode("utf-8")).hexdigest()[:16]


@dataclass
class GrupaAlertow:
    """Alerty dla tego samego obiektu i tego samego okresu, pokazywane w UI jako jedna karta."""

    obiekt_wiersz: int
    obiekt_nazwa: str
    okres_od: date | None
    okres_do: date | None
    alerty: list[Alert]


def grupuj(alerty: list[Alert]) -> list[GrupaAlertow]:
    grupy: dict[tuple, GrupaAlertow] = {}
    kolejnosc: list[tuple] = []
    for a in alerty:
        klucz_grupy = (a.obiekt_wiersz, a.okres_od, a.okres_do)
        if klucz_grupy not in grupy:
            grupy[klucz_grupy] = GrupaAlertow(
                obiekt_wiersz=a.obiekt_wiersz,
                obiekt_nazwa=a.obiekt_nazwa,
                okres_od=a.okres_od,
                okres_do=a.okres_do,
                alerty=[],
            )
            kolejnosc.append(klucz_grupy)
        grupy[klucz_grupy].alerty.append(a)
    return [grupy[k] for k in kolejnosc]


def liczba_obiektow_z_alertami(grupy: list[GrupaAlertow]) -> int:
    """Liczba różnych obiektów mających choć jeden aktywny alert — to ma pokazywać badge na ikonie."""
    return len({g.obiekt_wiersz for g in grupy})
