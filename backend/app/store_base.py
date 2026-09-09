"""Wspólny interfejs magazynu alertów - implementują go zarówno lokalny (SQLite, store.py),
jak i współdzielony (Supabase, supabase_store.py). Kontroler pracuje na tym interfejsie i nie wie,
z którego magazynu faktycznie korzysta."""
from __future__ import annotations

from typing import Protocol

from app.alerts import Alert


class MagazynAlertow(Protocol):
    def oznacz_jako_prawidlowy(self, alert: Alert) -> None: ...

    def odfiltruj_aktywne(self, alerty: list[Alert]) -> list[Alert]: ...

    def close(self) -> None: ...
