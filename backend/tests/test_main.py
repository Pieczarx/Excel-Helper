import subprocess

from app.main import _czy_pokazac_okno_od_razu, _zapewnij_autostart


def test_zapewnij_autostart_instaluje_zawsze(monkeypatch):
    """Nie tylko gdy zadania jeszcze nie ma - `schtasks /create /f` jest bezpieczne do powtórzenia
    i ma naprawiać samo siebie na starych instalacjach (np. sprzed FLAGA_AUTOSTART)."""
    wywolania = []
    monkeypatch.setattr("app.main.autostart.zainstaluj", lambda: wywolania.append("zainstaluj"))

    _zapewnij_autostart()

    assert wywolania == ["zainstaluj"]


def test_zapewnij_autostart_cicho_ignoruje_blad_instalacji(monkeypatch):
    def _rzuc():
        raise subprocess.CalledProcessError(1, "schtasks")

    monkeypatch.setattr("app.main.autostart.zainstaluj", _rzuc)

    _zapewnij_autostart()  # nie powinno rzucic - appka ma dzialac dalej mimo bledu


def test_czy_pokazac_okno_recznie_uruchomiona_z_juz_skonfigurowanym_plikiem():
    """To byl sedno zgloszonego bledu: rozroznianie recznego uruchomienia appki od autostartu
    samym tym, czy stdout jest terminalem, dawalo identyczny (falszywy) wynik w obu przypadkach -
    recznie uruchomiona appka z juz skonfigurowanym plikiem w ogole nie pokazywala okna."""
    assert _czy_pokazac_okno_od_razu(uruchomiono_przez_autostart=False, zaden_plik_nie_wybrany=False) is True


def test_czy_pokazac_okno_autostart_z_juz_skonfigurowanym_plikiem_zostaje_cicho():
    assert _czy_pokazac_okno_od_razu(uruchomiono_przez_autostart=True, zaden_plik_nie_wybrany=False) is False


def test_czy_pokazac_okno_autostart_bez_konfiguracji_i_tak_pokazuje():
    assert _czy_pokazac_okno_od_razu(uruchomiono_przez_autostart=True, zaden_plik_nie_wybrany=True) is True


def test_czy_pokazac_okno_recznie_bez_konfiguracji_pokazuje():
    assert _czy_pokazac_okno_od_razu(uruchomiono_przez_autostart=False, zaden_plik_nie_wybrany=True) is True
