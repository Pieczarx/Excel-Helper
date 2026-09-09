import time
import zipfile
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from app.aktualizator import (
    BladInstalacji,
    Instalator,
    _podmien_pliki,
    _znajdz_katalog_backend,
    zainstaluj,
)


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


def _zbuduj_archiwum_wydania(tmp_path: Path, tresc_pliku: str = "WERSJA = '1.2.3'\n") -> Path:
    """Symuluje archiwum, jakie GitHub generuje dla taga: jeden folder najwyzszego poziomu,
    w srodku struktura repo (backend/app/..., backend/requirements.txt)."""
    archiwum = tmp_path / "wydanie.zip"
    with zipfile.ZipFile(archiwum, "w") as zf:
        zf.writestr("excelHelper-1.2.3/backend/app/wersja.py", tresc_pliku)
        zf.writestr("excelHelper-1.2.3/backend/app/__init__.py", "")
        zf.writestr("excelHelper-1.2.3/backend/requirements.txt", "openpyxl\npymupdf\n")
        zf.writestr("excelHelper-1.2.3/examples/nie_powinno_zostac_ruszone.txt", "dane usera")
    return archiwum


def _rozpakuj(archiwum: Path, cel: Path) -> Path:
    with zipfile.ZipFile(archiwum) as zf:
        zf.extractall(cel)
    return cel


def test_znajdz_katalog_backend_w_jednym_folderze_najwyzszego_poziomu(tmp_path):
    rozpakowane = _rozpakuj(_zbuduj_archiwum_wydania(tmp_path), tmp_path / "rozpakowane")
    backend = _znajdz_katalog_backend(rozpakowane)
    assert backend.name == "backend"
    assert (backend / "app" / "wersja.py").exists()


def test_znajdz_katalog_backend_brak_folderu_rzuca_blad(tmp_path):
    pusty = tmp_path / "pusty"
    pusty.mkdir()
    (pusty / "cos_innego.txt").write_text("x")
    with pytest.raises(BladInstalacji):
        _znajdz_katalog_backend(pusty)


def test_podmien_pliki_nadpisuje_istniejace_i_dodaje_nowe(tmp_path):
    nowy_backend = tmp_path / "nowy" / "backend"
    (nowy_backend / "app").mkdir(parents=True)
    (nowy_backend / "app" / "wersja.py").write_text("WERSJA = '9.9.9'\n")
    (nowy_backend / "requirements.txt").write_text("pymupdf\n")

    docelowy_backend = tmp_path / "docelowy" / "backend"
    (docelowy_backend / "app").mkdir(parents=True)
    (docelowy_backend / "app" / "wersja.py").write_text("WERSJA = '1.0.0'\n")
    (docelowy_backend / "app" / "modul_usuniety_w_nowej_wersji.py").write_text("# stary kod\n")
    (docelowy_backend / "luzny_plik_poza_folderami_nowej_wersji.txt").write_text("zostanie")

    _podmien_pliki(nowy_backend, docelowy_backend)

    assert (docelowy_backend / "app" / "wersja.py").read_text() == "WERSJA = '9.9.9'\n"
    assert (docelowy_backend / "requirements.txt").read_text() == "pymupdf\n"
    # cale foldery top-level (np. "app/") sa podmieniane atomowo, wiec plik ktory zniknal z
    # nowej wersji wewnatrz takiego folderu faktycznie znika - to jest pozadane (czysta podmiana)
    assert not (docelowy_backend / "app" / "modul_usuniety_w_nowej_wersji.py").exists()
    # ale luzny plik LEZACY BEZPOSREDNIO w backend/ (poza folderami z nowej wersji) nie jest
    # ruszany, bo iterujemy tylko po tym, co faktycznie jest w nowej wersji
    assert (docelowy_backend / "luzny_plik_poza_folderami_nowej_wersji.txt").exists()


def test_zainstaluj_podmienia_pliki_i_nie_rusza_rodzenstwa_katalogu_aplikacji(tmp_path, monkeypatch):
    archiwum = _zbuduj_archiwum_wydania(tmp_path)
    monkeypatch.setattr(
        "app.aktualizator.urllib.request.urlretrieve", lambda url, cel: __import__("shutil").copy(archiwum, cel)
    )

    root = tmp_path / "instalacja"
    katalog_aplikacji = root / "backend"
    (katalog_aplikacji / "app").mkdir(parents=True)
    (katalog_aplikacji / "app" / "wersja.py").write_text("WERSJA = '1.0.0'\n")
    dane_usera = root / "data" / "alerts.db"
    dane_usera.parent.mkdir(parents=True)
    dane_usera.write_text("nie ruszac")

    zainstaluj("http://przykladowy-url/wydanie.zip", katalog_aplikacji=katalog_aplikacji)

    assert (katalog_aplikacji / "app" / "wersja.py").read_text() == "WERSJA = '1.2.3'\n"
    assert dane_usera.read_text() == "nie ruszac"  # poza katalog_aplikacji - nietkniete


def test_zainstaluj_przywraca_kopie_zapasowa_gdy_podmiana_sie_nie_powiedzie(tmp_path, monkeypatch):
    archiwum = _zbuduj_archiwum_wydania(tmp_path)
    monkeypatch.setattr(
        "app.aktualizator.urllib.request.urlretrieve", lambda url, cel: __import__("shutil").copy(archiwum, cel)
    )
    monkeypatch.setattr(
        "app.aktualizator._podmien_pliki",
        lambda *a: (_ for _ in ()).throw(RuntimeError("dysk pelny")),
    )

    katalog_aplikacji = tmp_path / "instalacja" / "backend"
    (katalog_aplikacji / "app").mkdir(parents=True)
    (katalog_aplikacji / "app" / "wersja.py").write_text("WERSJA = '1.0.0'\n")

    with pytest.raises(BladInstalacji):
        zainstaluj("http://przykladowy-url/wydanie.zip", katalog_aplikacji=katalog_aplikacji)

    assert (katalog_aplikacji / "app" / "wersja.py").read_text() == "WERSJA = '1.0.0'\n"


def test_zainstaluj_blad_pobierania_rzuca_blad_instalacji(tmp_path, monkeypatch):
    def _rzuc(url, cel):
        raise OSError("brak polaczenia")

    monkeypatch.setattr("app.aktualizator.urllib.request.urlretrieve", _rzuc)
    katalog_aplikacji = tmp_path / "instalacja" / "backend"
    katalog_aplikacji.mkdir(parents=True)

    with pytest.raises(BladInstalacji):
        zainstaluj("http://przykladowy-url/wydanie.zip", katalog_aplikacji=katalog_aplikacji)


def test_instalator_emituje_zakonczono_po_udanej_instalacji(tmp_path, monkeypatch):
    _app()
    monkeypatch.setattr("app.aktualizator.zainstaluj", lambda url: None)
    instalator = Instalator()
    odebrane = []
    instalator.zakonczono.connect(lambda: odebrane.append(True))

    instalator.instaluj_w_tle("http://przykladowy-url/wydanie.zip")

    assert _poczekaj_az(lambda: odebrane == [True])


def test_instalator_emituje_blad_gdy_instalacja_sie_nie_powiedzie(tmp_path, monkeypatch):
    _app()

    def _rzuc(url):
        raise BladInstalacji("cos poszlo nie tak")

    monkeypatch.setattr("app.aktualizator.zainstaluj", _rzuc)
    instalator = Instalator()
    odebrane = []
    instalator.blad.connect(odebrane.append)

    instalator.instaluj_w_tle("http://przykladowy-url/wydanie.zip")

    assert _poczekaj_az(lambda: odebrane == ["cos poszlo nie tak"])
