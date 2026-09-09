"""Wspólny interfejs magazynu historii wpisanych faktur - implementują go: lokalny SQLite
(historia_faktur.py, dziś niepodpięty do żywej appki), Supabase per-konto (supabase_historia_store.py)
i `PustyMagazynHistorii` poniżej - używany, dopóki user nie jest zalogowany.

Historia faktur jest PER KONTO (w przeciwieństwie do alertów w store_base.py/supabase_store.py,
które są współdzielone między wszystkimi zalogowanymi) - z decyzji użytkownika nic nie jest
zapisywane, dopóki nie ma aktywnej, zalogowanej sesji Supabase."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.import_faktur import WynikWpisu

if TYPE_CHECKING:
    from app.historia_faktur import WpisHistorii


class MagazynHistorii(Protocol):
    def zapisz(self, nazwa_pliku: str, wyniki: list[WynikWpisu], powod_odrzucenia: str | None = None) -> None: ...

    def ostatnie(self, limit: int = 20) -> list["WpisHistorii"]: ...

    def usun(self, wpis_id) -> None: ...

    def close(self) -> None: ...


class PustyMagazynHistorii:
    """Magazyn "wyłączony" - dla usera, który nie jest zalogowany. Historia jest per konto, więc
    zamiast zapisywać cokolwiek lokalnie/anonimowo, po prostu nic nie zapisujemy i nic nie
    pokazujemy, dopóki user się nie zaloguje (patrz odswiez_widocznosc_historii w window.py)."""

    def zapisz(self, nazwa_pliku: str, wyniki: list[WynikWpisu], powod_odrzucenia: str | None = None) -> None:
        pass

    def ostatnie(self, limit: int = 20) -> list["WpisHistorii"]:
        return []

    def usun(self, wpis_id) -> None:
        pass

    def close(self) -> None:
        pass
