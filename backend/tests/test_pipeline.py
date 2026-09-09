from pathlib import Path

from app.alerts import liczba_obiektow_z_alertami
from app.pipeline import zweryfikuj
from app.store import AlertStore

EXAMPLE_FILE = Path(__file__).resolve().parents[2] / "examples" / "MPECWIK 2026.xlsx"


def test_zweryfikuj_zwraca_pogrupowane_alerty(tmp_path):
    with AlertStore(tmp_path / "alerts.db") as store:
        grupy = zweryfikuj(EXAMPLE_FILE, rok=2026, store=store)
        assert grupy
        liczba_alertow = sum(len(g.alerty) for g in grupy)
        assert liczba_alertow > len(grupy)  # co najmniej jedna karta ma wiecej niz 1 alert w tych danych


def test_oznaczenie_prawidlowego_usuwa_go_z_kolejnej_weryfikacji(tmp_path):
    with AlertStore(tmp_path / "alerts.db") as store:
        grupy_przed = zweryfikuj(EXAMPLE_FILE, rok=2026, store=store)
        pierwszy_alert = grupy_przed[0].alerty[0]

        store.oznacz_jako_prawidlowy(pierwszy_alert)
        grupy_po = zweryfikuj(EXAMPLE_FILE, rok=2026, store=store)

        wszystkie_klucze_po = {a.klucz for g in grupy_po for a in g.alerty}
        assert pierwszy_alert.klucz not in wszystkie_klucze_po
        assert sum(len(g.alerty) for g in grupy_po) == sum(len(g.alerty) for g in grupy_przed) - 1


def test_badge_liczy_obiekty_nie_pola(tmp_path):
    with AlertStore(tmp_path / "alerts.db") as store:
        grupy = zweryfikuj(EXAMPLE_FILE, rok=2026, store=store)
        badge = liczba_obiektow_z_alertami(grupy)
        liczba_kart = len(grupy)
        assert 0 < badge <= liczba_kart  # jeden obiekt moze miec wiecej niz 1 karte (wiecej niz 1 miesiac z problemem)
