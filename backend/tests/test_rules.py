from pathlib import Path

from app.excel_reader import parse_workbook
from app.rules import sprawdz_ciaglosc, sprawdz_odchylenia
from app.rules.deviation import WAGA_KRYTYCZNA, WAGA_PODWYZSZONA, _waga_ze_stosunku

EXAMPLE_FILE = Path(__file__).resolve().parents[2] / "examples" / "MPECWIK 2026.xlsx"


def test_odchylenia_sprawdzaja_tylko_zuzycie_i_koszty_razem():
    obiekty = parse_workbook(EXAMPLE_FILE, rok=2026)
    alerty = sprawdz_odchylenia(obiekty)
    assert alerty  # w danych przykladowych na pewno cos sie znajdzie
    assert {a.pole for a in alerty} <= {"zuzycie_razem", "koszty_razem"}


def test_odchylenia_nie_wspominaja_normalizacji_w_opisie():
    obiekty = parse_workbook(EXAMPLE_FILE, rok=2026)
    alerty = sprawdz_odchylenia(obiekty)
    assert all("znormalizowana" not in a.opis for a in alerty)


def test_odchylenia_maja_wage_i_adresy_komorek():
    obiekty = parse_workbook(EXAMPLE_FILE, rok=2026)
    alerty = sprawdz_odchylenia(obiekty)
    for a in alerty:
        assert a.waga in (WAGA_PODWYZSZONA, WAGA_KRYTYCZNA)
        assert a.komorka_poprzednia and a.komorka_biezaca


def test_odchylenia_opis_ma_cztery_linie():
    obiekty = parse_workbook(EXAMPLE_FILE, rok=2026)
    alerty = sprawdz_odchylenia(obiekty)
    for a in alerty:
        linie = a.opis.split("\n")
        assert len(linie) == 4
        assert linie[0] in ("Zużycie:", "Koszty razem:")
        assert linie[1].startswith("Poprzednia faktura (")
        assert linie[2].startswith("Następna faktura (")
        assert linie[3].endswith("poprzedniej wartości") or linie[3] == "wzrost z zera"


def test_waga_ze_stosunku_progi():
    assert _waga_ze_stosunku(2.0) == WAGA_PODWYZSZONA
    assert _waga_ze_stosunku(5.0) == WAGA_PODWYZSZONA  # dokladnie 5x to jeszcze nie "wiecej niz 5x"
    assert _waga_ze_stosunku(5.01) == WAGA_KRYTYCZNA
    assert _waga_ze_stosunku(0.5) == WAGA_PODWYZSZONA  # odwrotnosc 2x
    assert _waga_ze_stosunku(0.19) == WAGA_KRYTYCZNA  # odwrotnosc >5x
    assert _waga_ze_stosunku(0.0) == WAGA_KRYTYCZNA  # spadek do zera


def test_ciaglosc_wykrywa_luke_po_bledzie_w_dacie():
    obiekty = parse_workbook(EXAMPLE_FILE, rok=2026)
    alerty = sprawdz_ciaglosc(obiekty)
    luka = next(a for a in alerty if a.obiekt_wiersz == 76)
    assert luka.okres_od.isoformat() == "2026-01-02"
    assert luka.okres_do.isoformat() == "2026-03-11"
    assert luka.komorka_poprzednia and luka.komorka_biezaca


def test_ciaglosc_opis_ma_trzy_linie():
    obiekty = parse_workbook(EXAMPLE_FILE, rok=2026)
    alerty = sprawdz_ciaglosc(obiekty)
    luka = next(a for a in alerty if a.obiekt_wiersz == 76)
    linie = luka.opis.split("\n")
    assert linie[0] == "Brak faktury za okres (69 dni - 02.01.2026-11.03.2026)"
    assert linie[1] == "Koniec poprzedniej faktury: 01.01.2026"
    assert linie[2] == "Początek następnej faktury: 12.03.2026"
