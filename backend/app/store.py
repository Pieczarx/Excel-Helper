"""Lokalny magazyn stanu alertów (SQLite) — pamięta, które alerty user oznaczył jako prawidłowe.

Ponieważ Alert.klucz zawiera wartości, z których alert powstał, ten sam obiekt/okres/pole
z inną wartością wejściową dostanie inny klucz — więc "oznaczone jako prawidłowe" automatycznie
nie obejmuje sytuacji, w której dane źródłowe (np. wcześniej zweryfikowana faktura) zostały
później poprawione.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from app.alerts import Alert

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "alerts.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS oznaczone_prawidlowe (
    klucz TEXT PRIMARY KEY,
    rodzaj TEXT NOT NULL,
    obiekt_wiersz INTEGER NOT NULL,
    obiekt_nazwa TEXT NOT NULL,
    opis TEXT NOT NULL,
    oznaczono_dnia TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class AlertStore:
    """`check_same_thread=False` + własny lock: appka teraz odświeża/oznacza alerty z wątków w tle
    (Kontroler.odswiez_w_tle/oznacz_jako_prawidlowy_w_tle), więc jedno połączenie SQLite musi być
    bezpiecznie używalne z więcej niż jednego wątku, niekoniecznie w tym samym momencie."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()

    def oznacz_jako_prawidlowy(self, alert: Alert) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO oznaczone_prawidlowe (klucz, rodzaj, obiekt_wiersz, obiekt_nazwa, opis) "
                "VALUES (?, ?, ?, ?, ?)",
                (alert.klucz, alert.rodzaj, alert.obiekt_wiersz, alert.obiekt_nazwa, alert.opis),
            )
            self._conn.commit()

    def cofnij_oznaczenie(self, klucz: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM oznaczone_prawidlowe WHERE klucz = ?", (klucz,))
            self._conn.commit()

    def jest_oznaczony(self, klucz: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM oznaczone_prawidlowe WHERE klucz = ?", (klucz,)
            ).fetchone()
            return row is not None

    def odfiltruj_aktywne(self, alerty: list[Alert]) -> list[Alert]:
        """Zwraca tylko te alerty, które nie zostały wcześniej oznaczone jako prawidłowe."""
        return [a for a in alerty if not self.jest_oznaczony(a.klucz)]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "AlertStore":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
