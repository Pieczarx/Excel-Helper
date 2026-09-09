import re
from pathlib import Path

from app.autostart import NAZWA_ZADANIA, polecenie_instalacji, polecenie_odinstalowania, zawartosc_vbs


def _dekoduj_argument_run(vbs: str) -> str:
    """Wyciąga argument z 'objShell.Run "...", 0, False' i dekoduje podwojone cudzysłowy VBS ("" -> ")."""
    dopasowanie = re.search(r'objShell\.Run "(.*)", 0, False', vbs)
    assert dopasowanie, f"nie znaleziono linii Run w:\n{vbs}"
    return dopasowanie.group(1).replace('""', '"')


def test_zawartosc_vbs_ustawia_katalog_roboczy():
    backend_dir = Path(r"C:\proj\backend")
    vbs = zawartosc_vbs(backend_dir, Path(r"C:\Python\pythonw.exe"))
    assert f'objShell.CurrentDirectory = "{backend_dir}"' in vbs


def test_zawartosc_vbs_koduje_polecenie_z_cudzyslowami_poprawnie():
    pythonw = Path(r"C:\Program Files\Python\pythonw.exe")  # spacja w sciezce - warto sprawdzic
    vbs = zawartosc_vbs(Path(r"C:\proj\backend"), pythonw)
    polecenie = _dekoduj_argument_run(vbs)
    assert polecenie == f'"{pythonw}" -m app.main'


def test_polecenie_instalacji_wskazuje_wscript_i_plik_vbs():
    vbs_path = Path(r"C:\proj\backend\scripts\uruchom_ukryte.vbs")
    polecenie = polecenie_instalacji(vbs_path)
    assert polecenie[:2] == ["schtasks", "/create"]
    assert NAZWA_ZADANIA in polecenie
    assert f'wscript.exe "{vbs_path}"' in polecenie
    assert "onlogon" in polecenie


def test_polecenie_odinstalowania_usuwa_to_samo_zadanie():
    polecenie = polecenie_odinstalowania()
    assert polecenie == ["schtasks", "/delete", "/tn", NAZWA_ZADANIA, "/f"]
