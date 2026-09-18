import io
import time
import zipfile
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication

from app.aktualizacje import Wydanie
from app.aktualizator import (
    BladInstalacji,
    Instalator,
    _podmien_pliki,
    _znajdz_katalog_backend,
    posprzataj_poprzednia_wersje,
    zainstaluj,
    zainstaluj_wydanie,
    zainstaluj_zamrozona,
)


def _app():
    app = QCoreApplication.instance()
    return app or QCoreApplication([])


class _FalszywaOdpowiedz(io.BytesIO):
    """Udaje obiekt zwracany przez urlopen - poza tresc (przez io.BytesIO) niesie tez `.headers`
    z poprawnym Content-Length, zeby test_pobierz_plik... nie wpadal w nowa kontrole integralnosci
    (patrz _pobierz_plik w aktualizator.py) tam, gdzie nie o to akurat chodzi w danym tescie."""

    def __init__(self, zawartosc: bytes, rozmiar_naglowka: int | None = None):
        super().__init__(zawartosc)
        rozmiar = len(zawartosc) if rozmiar_naglowka is None else rozmiar_naglowka
        self.headers = {"Content-Length": str(rozmiar)}


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
        "app.aktualizator.urllib.request.urlopen",
        lambda url, **kwargs: _FalszywaOdpowiedz(archiwum.read_bytes()),
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
        "app.aktualizator.urllib.request.urlopen",
        lambda url, **kwargs: _FalszywaOdpowiedz(archiwum.read_bytes()),
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


def test_zainstaluj_niepelne_pobieranie_rzuca_blad_i_usuwa_plik(tmp_path, monkeypatch):
    """Zgloszony realny blad: appka podmienila sie na niepelny/uszkodzony plik (skutek: appka po
    aktualizacji nie startowala, ModuleNotFoundError przy imporcie). Content-Length z odpowiedzi
    (100) nie zgadza sie z faktycznie zapisana trescia (krotsza) - appka ma to wylapac, zamiast
    cicho zainstalowac niepelny plik."""
    monkeypatch.setattr(
        "app.aktualizator.urllib.request.urlopen",
        lambda url, **kwargs: _FalszywaOdpowiedz(b"za krotka tresc", rozmiar_naglowka=100),
    )
    katalog_aplikacji = tmp_path / "instalacja" / "backend"
    katalog_aplikacji.mkdir(parents=True)

    with pytest.raises(BladInstalacji, match="niepełny"):
        zainstaluj("http://przykladowy-url/wydanie.zip", katalog_aplikacji=katalog_aplikacji)


def test_zainstaluj_blad_pobierania_rzuca_blad_instalacji(tmp_path, monkeypatch):
    def _rzuc(url, **kwargs):
        raise OSError("brak polaczenia")

    monkeypatch.setattr("app.aktualizator.urllib.request.urlopen", _rzuc)
    katalog_aplikacji = tmp_path / "instalacja" / "backend"
    katalog_aplikacji.mkdir(parents=True)

    with pytest.raises(BladInstalacji):
        zainstaluj("http://przykladowy-url/wydanie.zip", katalog_aplikacji=katalog_aplikacji)


def _przykladowe_wydanie() -> Wydanie:
    return Wydanie(tag="v1.2.3", wersja="1.2.3", url_zip="http://przykladowy-url/wydanie.zip")


def test_instalator_emituje_zakonczono_po_udanej_instalacji(tmp_path, monkeypatch):
    _app()
    monkeypatch.setattr("app.aktualizator.zainstaluj_wydanie", lambda wydanie: None)
    instalator = Instalator()
    odebrane = []
    instalator.zakonczono.connect(lambda: odebrane.append(True))

    instalator.instaluj_w_tle(_przykladowe_wydanie())

    assert _poczekaj_az(lambda: odebrane == [True])


def test_instalator_emituje_blad_gdy_instalacja_sie_nie_powiedzie(tmp_path, monkeypatch):
    _app()

    def _rzuc(wydanie):
        raise BladInstalacji("cos poszlo nie tak")

    monkeypatch.setattr("app.aktualizator.zainstaluj_wydanie", _rzuc)
    instalator = Instalator()
    odebrane = []
    instalator.blad.connect(odebrane.append)

    instalator.instaluj_w_tle(_przykladowe_wydanie())

    assert _poczekaj_az(lambda: odebrane == ["cos poszlo nie tak"])


def test_zainstaluj_zamrozona_podmienia_plik_exe(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.aktualizator.urllib.request.urlopen",
        lambda url, **kwargs: _FalszywaOdpowiedz(b"nowa-wersja-exe"),
    )
    biezacy_exe = tmp_path / "Excel Helper.exe"
    biezacy_exe.write_text("stara-wersja-exe")

    zainstaluj_zamrozona("http://przykladowy-url/Excel Helper.exe", biezacy_exe)

    assert biezacy_exe.read_text() == "nowa-wersja-exe"
    assert (tmp_path / "Excel Helper.exe.poprzedni").read_text() == "stara-wersja-exe"


def test_zainstaluj_zamrozona_przywraca_poprzedni_plik_gdy_kopiowanie_sie_nie_powiedzie(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.aktualizator.urllib.request.urlopen",
        lambda url, **kwargs: _FalszywaOdpowiedz(b"nowa-wersja-exe"),
    )
    monkeypatch.setattr(
        "app.aktualizator.shutil.copy2",
        lambda *a: (_ for _ in ()).throw(OSError("dysk pelny")),
    )
    biezacy_exe = tmp_path / "Excel Helper.exe"
    biezacy_exe.write_text("stara-wersja-exe")

    with pytest.raises(BladInstalacji):
        zainstaluj_zamrozona("http://przykladowy-url/Excel Helper.exe", biezacy_exe)

    assert biezacy_exe.read_text() == "stara-wersja-exe"


def test_posprzataj_poprzednia_wersje_usuwa_odsuniety_plik(tmp_path):
    biezacy_exe = tmp_path / "Excel Helper.exe"
    biezacy_exe.write_text("aktualna-wersja")
    poprzedni = tmp_path / "Excel Helper.exe.poprzedni"
    poprzedni.write_text("stara-wersja")

    posprzataj_poprzednia_wersje(biezacy_exe)

    assert not poprzedni.exists()
    assert biezacy_exe.exists()  # sam biezacy plik nietkniety


def test_posprzataj_poprzednia_wersje_bez_niczego_do_posprzatania_nie_rzuca(tmp_path):
    posprzataj_poprzednia_wersje(tmp_path / "Excel Helper.exe")


def test_zainstaluj_wydanie_w_trybie_zrodlowym_woła_zainstaluj(tmp_path, monkeypatch):
    monkeypatch.setattr("app.aktualizator.czy_zamrozona", lambda: False)
    wywolania = []
    monkeypatch.setattr(
        "app.aktualizator.zainstaluj",
        lambda url_zip, katalog_aplikacji: wywolania.append((url_zip, katalog_aplikacji)),
    )

    zainstaluj_wydanie(_przykladowe_wydanie(), katalog_aplikacji=tmp_path)

    assert wywolania == [("http://przykladowy-url/wydanie.zip", tmp_path)]


def test_zainstaluj_wydanie_w_trybie_zamrozonym_bez_exe_rzuca_blad(monkeypatch):
    monkeypatch.setattr("app.aktualizator.czy_zamrozona", lambda: True)

    with pytest.raises(BladInstalacji):
        zainstaluj_wydanie(_przykladowe_wydanie())
