import subprocess

from app.main import _zapewnij_autostart


def test_zapewnij_autostart_instaluje_gdy_nie_ma_zadania(monkeypatch):
    wywolania = []
    monkeypatch.setattr("app.main.autostart.czy_zainstalowany", lambda: False)
    monkeypatch.setattr("app.main.autostart.zainstaluj", lambda: wywolania.append("zainstaluj"))

    _zapewnij_autostart()

    assert wywolania == ["zainstaluj"]


def test_zapewnij_autostart_nie_instaluje_ponownie_gdy_juz_jest(monkeypatch):
    wywolania = []
    monkeypatch.setattr("app.main.autostart.czy_zainstalowany", lambda: True)
    monkeypatch.setattr("app.main.autostart.zainstaluj", lambda: wywolania.append("zainstaluj"))

    _zapewnij_autostart()

    assert wywolania == []


def test_zapewnij_autostart_cicho_ignoruje_blad_instalacji(monkeypatch):
    monkeypatch.setattr("app.main.autostart.czy_zainstalowany", lambda: False)

    def _rzuc():
        raise subprocess.CalledProcessError(1, "schtasks")

    monkeypatch.setattr("app.main.autostart.zainstaluj", _rzuc)

    _zapewnij_autostart()  # nie powinno rzucic - appka ma dzialac dalej mimo bledu
