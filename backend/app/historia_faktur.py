"""Lokalny magazyn historii wpisanych faktur (SQLite), na wzór store.py (AlertStore).

Historia jest dziś per konto (patrz historia_faktur_base.py) i idzie przez Supabase
(supabase_historia_store.py) - ten lokalny magazyn nie jest już podpięty do żywej appki
(main.py startuje z PustyMagazynHistorii, dopóki user się nie zaloguje), zostaje w kodzie
(i testach) jako gotowa, działająca implementacja na przyszłość."""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from app.import_faktur import WynikWpisu

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "historia_faktur.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS historia_faktur (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa_pliku TEXT NOT NULL,
    wpisano_dnia TEXT NOT NULL DEFAULT (datetime('now')),
    nierozpoznana INTEGER NOT NULL,
    powod_odrzucenia TEXT,
    pozycje_json TEXT NOT NULL
);
"""


@dataclass
class WpisHistorii:
    id: int
    nazwa_pliku: str
    czas: datetime
    nierozpoznana: bool
    powod_odrzucenia: str | None
    pozycje: list[WynikWpisu]


def pozycja_do_json(w: WynikWpisu) -> dict:
    return {
        "kategoria": w.kategoria,
        "ppe": w.ppe,
        "wiersz": w.wiersz,
        "nazwa_obiektu": w.nazwa_obiektu,
        "miesiac": w.miesiac,
        "okres_od": w.okres_od.isoformat() if w.okres_od else None,
        "okres_do": w.okres_do.isoformat() if w.okres_do else None,
        "opis": w.opis,
        "arkusz": w.arkusz,
    }


def pozycja_z_json(d: dict) -> WynikWpisu:
    return WynikWpisu(
        kategoria=d["kategoria"],
        ppe=d["ppe"],
        wiersz=d["wiersz"],
        nazwa_obiektu=d["nazwa_obiektu"],
        miesiac=d["miesiac"],
        okres_od=date.fromisoformat(d["okres_od"]) if d["okres_od"] else None,
        okres_do=date.fromisoformat(d["okres_do"]) if d["okres_do"] else None,
        opis=d["opis"],
        # .get, nie [] - wpisy z historii zapisane PRZED dodaniem tego pola nie mają go w JSON-ie.
        arkusz=d.get("arkusz"),
    )


class HistoriaFakturStore:
    """`check_same_thread=False` + lock - tak samo jak AlertStore, bo przetwarzanie faktur
    (KontrolerFaktur.przetworz_w_tle) też działa w osobnym wątku, żeby nie mrozić UI."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def zapisz(self, nazwa_pliku: str, wyniki: list[WynikWpisu], powod_odrzucenia: str | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO historia_faktur (nazwa_pliku, nierozpoznana, powod_odrzucenia, pozycje_json) "
                "VALUES (?, ?, ?, ?)",
                (
                    nazwa_pliku,
                    1 if powod_odrzucenia else 0,
                    powod_odrzucenia,
                    json.dumps([pozycja_do_json(w) for w in wyniki], ensure_ascii=False),
                ),
            )
            self._conn.commit()

    def ostatnie(self, limit: int = 20) -> list[WpisHistorii]:
        with self._lock:
            wiersze = self._conn.execute(
                "SELECT id, nazwa_pliku, wpisano_dnia, nierozpoznana, powod_odrzucenia, pozycje_json "
                "FROM historia_faktur ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            WpisHistorii(
                id=wiersz[0],
                nazwa_pliku=wiersz[1],
                czas=datetime.fromisoformat(wiersz[2]),
                nierozpoznana=bool(wiersz[3]),
                powod_odrzucenia=wiersz[4],
                pozycje=[pozycja_z_json(d) for d in json.loads(wiersz[5])],
            )
            for wiersz in wiersze
        ]

    def usun(self, wpis_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM historia_faktur WHERE id = ?", (wpis_id,))
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "HistoriaFakturStore":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
