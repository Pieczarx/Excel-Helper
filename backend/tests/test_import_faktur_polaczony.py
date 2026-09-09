import shutil
from pathlib import Path

from app.faktura_reader import KAT_SUKCES, KAT_ZUZYCIE_NIEZGODNE_Z_FAKTURA
from app.import_faktur_polaczony import wpisz_fakture_do_wszystkich_arkuszy

TESTY_FILE = Path(__file__).resolve().parents[2] / "examples" / "MPECWIK 2026_testy.xlsx"
FAKTURY_ROOT = Path(__file__).resolve().parents[2] / "examples" / "Faktury MPECWIK 2026"
FAKTURA_20_PAZDZIERNIKA = next(p for p in FAKTURY_ROOT.rglob("D 01.pdf") if "Pa" in p.parent.name)
FAKTURA_BRODOWO = next(p for p in FAKTURY_ROOT.rglob("D 03 31.pdf") if p.parent.name.startswith("Brodowo"))


def _kopia_testy(tmp_path) -> Path:
    cel = tmp_path / "testy.xlsx"
    shutil.copy(TESTY_FILE, cel)
    return cel


def test_faktura_duzego_odbioru_trafia_do_duze_odbiory_bez_szumu_ppe_nieznalezione(tmp_path):
    # Brodowo ma tylko sekcję "Duże odbiory" - bez scalania, przebieg "Małe odbiory" zgłosiłby tu
    # dodatkowo fałszywe "PPE nieznalezione" (bo ten PPE poprawnie żyje w DRUGIM arkuszu).
    excel = _kopia_testy(tmp_path)

    wyniki = wpisz_fakture_do_wszystkich_arkuszy(excel, FAKTURA_BRODOWO, nadpisuj=True)

    assert len(wyniki) == 1
    assert wyniki[0].kategoria == KAT_ZUZYCIE_NIEZGODNE_Z_FAKTURA
    assert wyniki[0].wiersz == 4


def test_faktura_malego_odbioru_dziala_bez_zmian_i_bez_szumu_duze_odbiory(tmp_path):
    excel = _kopia_testy(tmp_path)

    wyniki = wpisz_fakture_do_wszystkich_arkuszy(excel, FAKTURA_20_PAZDZIERNIKA, nadpisuj=True)

    assert len(wyniki) == 5
    assert all(w.kategoria == KAT_SUKCES for w in wyniki)
