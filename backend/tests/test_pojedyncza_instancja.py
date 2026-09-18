import time
import uuid

from PySide6.QtCore import QCoreApplication
from PySide6.QtNetwork import QLocalServer

from app.pojedyncza_instancja import czy_juz_dziala_i_aktywowano, uruchom_serwer


def _app():
    app = QCoreApplication.instance()
    return app or QCoreApplication([])


def _nazwa_testowa() -> str:
    # Unikalna nazwa per test - nigdy nazwa prawdziwej appki (NAZWA_SERWERA), żeby test nie
    # kolidował z faktycznie działającą instancją Excel Helpera na tej samej maszynie.
    return f"test-pojedyncza-instancja-{uuid.uuid4().hex}"


def _poczekaj_az(warunek, timeout: float = 5.0) -> bool:
    koniec = time.time() + timeout
    while time.time() < koniec:
        QCoreApplication.processEvents()
        if warunek():
            return True
        time.sleep(0.02)
    return False


def test_czy_juz_dziala_false_gdy_nikt_nie_nasluchuje():
    _app()
    nazwa = _nazwa_testowa()

    assert czy_juz_dziala_i_aktywowano(nazwa) is False


def test_druga_proba_wysyla_sygnal_do_pierwszej_i_zwraca_true():
    _app()
    nazwa = _nazwa_testowa()

    wywolania = []
    serwer = uruchom_serwer(lambda: wywolania.append(True), nazwa)
    try:
        wynik = czy_juz_dziala_i_aktywowano(nazwa)

        assert wynik is True
        assert _poczekaj_az(lambda: wywolania)
    finally:
        serwer.close()
        QLocalServer.removeServer(nazwa)


def test_serwer_obsluguje_wiele_kolejnych_prob():
    _app()
    nazwa = _nazwa_testowa()

    wywolania = []
    serwer = uruchom_serwer(lambda: wywolania.append(True), nazwa)
    try:
        for oczekiwana_liczba in (1, 2, 3):
            assert czy_juz_dziala_i_aktywowano(nazwa) is True
            assert _poczekaj_az(lambda: len(wywolania) == oczekiwana_liczba)
    finally:
        serwer.close()
        QLocalServer.removeServer(nazwa)
