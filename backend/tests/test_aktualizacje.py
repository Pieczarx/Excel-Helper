import json
import time
from urllib.error import URLError

from PySide6.QtCore import QCoreApplication

import app.aktualizacje as aktualizacje
from app.aktualizacje import SprawdzarkaAktualizacji, Wydanie, czy_nowsza, pobierz_najnowsze_wydanie


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


def test_czy_nowsza_porownuje_semver():
    assert czy_nowsza("1.0.2", "1.0.1") is True
    assert czy_nowsza("1.0.1", "1.0.1") is False
    assert czy_nowsza("1.0.0", "1.0.1") is False
    assert czy_nowsza("v1.1.0", "1.0.9") is True


def test_czy_nowsza_niepoprawny_format_zwraca_false():
    assert czy_nowsza("niepoprawna-wersja", "1.0.1") is False


def test_pobierz_bez_skonfigurowanego_repo_zwraca_none(monkeypatch):
    # repo=None oznacza "użyj REPO_GITHUB z modułu" - żeby przetestować brak konfiguracji
    # niezależnie od tego, co appka ma dziś realnie wpisane, podmieniamy moduł na pusty.
    monkeypatch.setattr(aktualizacje, "REPO_GITHUB", None)
    assert pobierz_najnowsze_wydanie(repo=None) is None
    assert pobierz_najnowsze_wydanie(repo="") is None


def test_pobierz_parsuje_tag_i_buduje_url_archiwum(monkeypatch):
    class _FakeOdpowiedz:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps({"tag_name": "v1.2.3"}).encode("utf-8")

    monkeypatch.setattr("app.aktualizacje.urllib.request.urlopen", lambda *a, **k: _FakeOdpowiedz())

    wydanie = pobierz_najnowsze_wydanie(repo="ktos/repo")

    assert wydanie == Wydanie(
        tag="v1.2.3", wersja="1.2.3", url_zip="https://github.com/ktos/repo/archive/refs/tags/v1.2.3.zip"
    )


def test_pobierz_blad_sieci_zwraca_none_nie_rzuca(monkeypatch):
    def _rzuc(*a, **k):
        raise URLError("brak polaczenia")

    monkeypatch.setattr("app.aktualizacje.urllib.request.urlopen", _rzuc)

    assert pobierz_najnowsze_wydanie(repo="ktos/repo") is None


def test_sprawdzarka_emituje_sygnal_gdy_jest_nowsza_wersja(monkeypatch):
    _app()
    wydanie = Wydanie(tag="v2.0.0", wersja="2.0.0", url_zip="http://x/v2.0.0.zip")
    monkeypatch.setattr("app.aktualizacje.pobierz_najnowsze_wydanie", lambda repo=None: wydanie)
    sprawdzarka = SprawdzarkaAktualizacji()
    odebrane = []
    sprawdzarka.znaleziono_nowsza.connect(odebrane.append)

    sprawdzarka.sprawdz_w_tle("1.0.1", repo="ktos/repo")

    assert _poczekaj_az(lambda: odebrane == [wydanie])


def test_sprawdzarka_nie_emituje_gdy_wersja_aktualna(monkeypatch):
    _app()
    wydanie = Wydanie(tag="1.0.1", wersja="1.0.1", url_zip="http://x/1.0.1.zip")
    monkeypatch.setattr("app.aktualizacje.pobierz_najnowsze_wydanie", lambda repo=None: wydanie)
    sprawdzarka = SprawdzarkaAktualizacji()
    odebrane = []
    sprawdzarka.znaleziono_nowsza.connect(odebrane.append)

    sprawdzarka.sprawdz_w_tle("1.0.1", repo="ktos/repo")
    time.sleep(0.3)
    QCoreApplication.processEvents()

    assert odebrane == []
