import shutil
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from app.foldery_faktur import NAZWA_DO_AKTUALIZACJI, NAZWA_DO_WPISANIA
from app.historia_faktur import HistoriaFakturStore
from app.kontroler_faktur import KontrolerFaktur

TESTY_FILE = Path(__file__).resolve().parents[2] / "examples" / "MPECWIK 2026_testy.xlsx"
FAKTURY_ROOT = Path(__file__).resolve().parents[2] / "examples" / "Faktury MPECWIK 2026"
FAKTURA_20_PAZDZIERNIKA = next(p for p in FAKTURY_ROOT.rglob("D 01.pdf") if "Pa" in p.parent.name)


def _app():
    app = QCoreApplication.instance()
    return app or QCoreApplication([])


def _poczekaj_az(warunek, timeout: float = 5.0) -> bool:
    koniec = time.time() + timeout
    while time.time() < koniec:
        QCoreApplication.processEvents()
        if warunek():
            return True
        time.sleep(0.02)
    return False


def _kopia_excel(tmp_path) -> Path:
    cel = tmp_path / "excel.xlsx"
    shutil.copy(TESTY_FILE, cel)
    return cel


def test_ustaw_folder_tworzy_podfoldery_i_zapamietuje_sciezke(tmp_path):
    _app()
    with HistoriaFakturStore(tmp_path / "historia.db") as historia:
        kontroler = KontrolerFaktur(historia, config_path=tmp_path / "faktury_config.json")
        root = tmp_path / "Faktury"

        kontroler.ustaw_folder(root)

        assert (root / NAZWA_DO_WPISANIA).is_dir()
        assert (root / NAZWA_DO_AKTUALIZACJI).is_dir()

        # nowy kontroler z tym samym config_path powinien odtworzyc folder bez ponownego wywolania
        kontroler2 = KontrolerFaktur(historia, config_path=tmp_path / "faktury_config.json")
        assert kontroler2.folder == root.resolve()


def test_dodaj_pliki_do_kolejki_trafiaja_do_do_wpisania_i_widac_je_w_kolejce(tmp_path):
    _app()
    with HistoriaFakturStore(tmp_path / "historia.db") as historia:
        kontroler = KontrolerFaktur(historia, config_path=tmp_path / "faktury_config.json")
        kontroler.ustaw_folder(tmp_path / "Faktury")

        odebrane = []
        kontroler.kolejka_zmieniona.connect(odebrane.append)
        kontroler.dodaj_pliki_do_kolejki([FAKTURA_20_PAZDZIERNIKA])

        assert len(kontroler.kolejka()) == 1
        assert kontroler.kolejka()[0].parent.name == NAZWA_DO_WPISANIA
        assert odebrane[-1] == kontroler.kolejka()


def test_usun_z_kolejki_usuwa_plik_i_emituje_zmiane(tmp_path):
    _app()
    with HistoriaFakturStore(tmp_path / "historia.db") as historia:
        kontroler = KontrolerFaktur(historia, config_path=tmp_path / "faktury_config.json")
        kontroler.ustaw_folder(tmp_path / "Faktury")
        kontroler.dodaj_pliki_do_kolejki([FAKTURA_20_PAZDZIERNIKA])
        plik = kontroler.kolejka()[0]

        odebrane = []
        kontroler.kolejka_zmieniona.connect(odebrane.append)
        kontroler.usun_z_kolejki(plik)

        assert not plik.exists()
        assert kontroler.kolejka() == []
        assert odebrane[-1] == []


def test_przetworz_w_tle_zapisuje_do_historii_i_emituje_sygnaly(tmp_path):
    _app()
    excel = _kopia_excel(tmp_path)
    with HistoriaFakturStore(tmp_path / "historia.db") as historia:
        kontroler = KontrolerFaktur(historia, config_path=tmp_path / "faktury_config.json")
        kontroler.ustaw_folder(tmp_path / "Faktury")
        kontroler.dodaj_pliki_do_kolejki([FAKTURA_20_PAZDZIERNIKA])

        stany: list[bool] = []
        wyniki_koncowe = []
        historie = []
        kontroler.w_trakcie.connect(stany.append)
        kontroler.zakonczono_przetwarzanie.connect(wyniki_koncowe.append)
        kontroler.historia_zmieniona.connect(historie.append)

        kontroler.przetworz_w_tle(excel)

        assert _poczekaj_az(lambda: stany == [True, False])
        assert len(wyniki_koncowe[-1]) == 1
        # 5 zapisanych pozycji + 5 dopisanych alertów "brak folderu obiektu" (folder testowy nie ma
        # żadnych folderów obiektów z PPE w nazwie - patrz foldery_obiektow.py)
        assert len(wyniki_koncowe[-1][0].wyniki) == 10
        assert sum(1 for w in wyniki_koncowe[-1][0].wyniki if w.zapisano) == 5
        assert kontroler.kolejka() == []

        assert len(historie[-1]) == 1
        assert historie[-1][0].nazwa_pliku == "D 01.pdf"
        assert len(kontroler.historia_ostatnich()) == 1


def test_usun_z_historii_usuwa_wpis_i_emituje_zmiane(tmp_path):
    _app()
    with HistoriaFakturStore(tmp_path / "historia.db") as historia:
        kontroler = KontrolerFaktur(historia, config_path=tmp_path / "faktury_config.json")
        historia.zapisz("D 09.pdf", [], powod_odrzucenia="Nie rozpoznano jako faktura dystrybucyjna")
        wpis_id = kontroler.historia_ostatnich()[0].id

        odebrane = []
        kontroler.historia_zmieniona.connect(odebrane.append)
        kontroler.usun_z_historii(wpis_id)

        assert kontroler.historia_ostatnich() == []
        assert odebrane[-1] == []


def test_ustaw_magazyn_podmienia_historie_i_emituje_zmiane(tmp_path):
    _app()
    with (
        HistoriaFakturStore(tmp_path / "historia1.db") as historia1,
        HistoriaFakturStore(tmp_path / "historia2.db") as historia2,
    ):
        historia2.zapisz("D 05.pdf", [], powod_odrzucenia="Nie rozpoznano jako faktura dystrybucyjna")
        kontroler = KontrolerFaktur(historia1, config_path=tmp_path / "faktury_config.json")

        odebrane = []
        kontroler.historia_zmieniona.connect(odebrane.append)
        kontroler.ustaw_magazyn(historia2)

        assert kontroler.historia_ostatnich()[0].nazwa_pliku == "D 05.pdf"
        assert odebrane[-1][0].nazwa_pliku == "D 05.pdf"


def test_przetworz_bez_folderu_emituje_blad(tmp_path):
    _app()
    excel = _kopia_excel(tmp_path)
    with HistoriaFakturStore(tmp_path / "historia.db") as historia:
        kontroler = KontrolerFaktur(historia, config_path=tmp_path / "brak.json")

        bledy = []
        kontroler.blad.connect(bledy.append)
        kontroler.przetworz_w_tle(excel)

        assert _poczekaj_az(lambda: bledy)
