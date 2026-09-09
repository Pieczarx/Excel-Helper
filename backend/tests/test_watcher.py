import time

from app.watcher import ObserwatorPliku


def _poczekaj_az(warunek, timeout=5.0, krok=0.1):
    koniec = time.time() + timeout
    while time.time() < koniec:
        if warunek():
            return True
        time.sleep(krok)
    return False


def test_wywoluje_callback_gdy_plik_blokady_znika(tmp_path):
    plik = tmp_path / "test.xlsx"
    plik.write_text("dummy")
    blokada = tmp_path / "~$test.xlsx"

    wywolania = []
    obserwator = ObserwatorPliku(plik, callback=lambda: wywolania.append(1))
    obserwator.start()
    try:
        blokada.write_text("lock")
        assert _poczekaj_az(lambda: obserwator.czy_plik_jest_teraz_otwarty())

        blokada.unlink()
        assert _poczekaj_az(lambda: len(wywolania) == 1)
    finally:
        obserwator.stop()

    assert wywolania == [1]


def test_nie_reaguje_na_usuniecie_innego_pliku(tmp_path):
    plik = tmp_path / "test.xlsx"
    plik.write_text("dummy")
    inny_plik = tmp_path / "cos_innego.txt"
    inny_plik.write_text("x")

    wywolania = []
    obserwator = ObserwatorPliku(plik, callback=lambda: wywolania.append(1))
    obserwator.start()
    try:
        inny_plik.unlink()
        time.sleep(0.5)  # dajemy obserwatorowi szanse zareagowac, jesli mialby (nie powinien)
    finally:
        obserwator.stop()

    assert wywolania == []
