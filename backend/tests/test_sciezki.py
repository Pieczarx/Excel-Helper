import sys

from app.sciezki import czy_zamrozona, katalog_aplikacji, katalog_danych, katalog_zasobow


def test_czy_zamrozona_false_w_trybie_zrodlowym():
    assert czy_zamrozona() is False


def test_czy_zamrozona_true_gdy_ustawiony_atrybut_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert czy_zamrozona() is True


def test_katalog_aplikacji_w_trybie_zrodlowym_to_backend():
    assert katalog_aplikacji().name == "backend"


def test_katalog_aplikacji_w_trybie_zamrozonym_to_folder_pliku_exe(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    exe = tmp_path / "Excel Helper.exe"
    exe.write_text("")
    monkeypatch.setattr(sys, "executable", str(exe))

    assert katalog_aplikacji() == tmp_path


def test_katalog_danych_w_trybie_zrodlowym_jest_piatro_wyzej_niz_backend():
    assert katalog_danych() == katalog_aplikacji().parent / "data"


def test_katalog_danych_w_trybie_zamrozonym_jest_obok_pliku_exe(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    exe = tmp_path / "Excel Helper.exe"
    exe.write_text("")
    monkeypatch.setattr(sys, "executable", str(exe))

    assert katalog_danych() == tmp_path / "data"


def test_katalog_zasobow_w_trybie_zrodlowym_to_assets_obok_app():
    assert katalog_zasobow().name == "assets"
    assert (katalog_zasobow() / "icon.ico").exists()


def test_katalog_zasobow_w_trybie_zamrozonym_to_katalog_tymczasowy_pyinstallera(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert katalog_zasobow() == tmp_path / "assets"
