"""Reguła: alert gdy między kolejnymi fakturami tego samego obiektu jest luka w datach."""
from __future__ import annotations

from datetime import timedelta

from app.alerts import Alert
from app.excel_reader import Obiekt


def sprawdz_ciaglosc(obiekty: list[Obiekt]) -> list[Alert]:
    alerty: list[Alert] = []
    for obiekt in obiekty:
        for poprzedni, biezacy in zip(obiekt.okresy, obiekt.okresy[1:]):
            oczekiwany_start = poprzedni.data_do + timedelta(days=1)
            if biezacy.data_od <= oczekiwany_start:
                continue  # bez luki (albo faktury się stykają/nakładają - nie jest to scope tej reguły)

            luka_koniec = biezacy.data_od - timedelta(days=1)
            luka_dni = (luka_koniec - oczekiwany_start).days + 1
            opis = (
                f"Brak faktury za okres ({luka_dni} dni - {oczekiwany_start:%d.%m.%Y}-{luka_koniec:%d.%m.%Y})\n"
                f"Koniec poprzedniej faktury: {poprzedni.data_do:%d.%m.%Y}\n"
                f"Początek następnej faktury: {biezacy.data_od:%d.%m.%Y}"
            )
            alerty.append(
                Alert(
                    rodzaj="LUKA_CIAGLOSCI",
                    obiekt_wiersz=obiekt.wiersz,
                    obiekt_nazwa=obiekt.nazwa,
                    opis=opis,
                    okres_od=oczekiwany_start,
                    okres_do=luka_koniec,
                    komorka_poprzednia=poprzedni.komorka("data_raw"),
                    komorka_biezaca=biezacy.komorka("data_raw"),
                )
            )
    return alerty
