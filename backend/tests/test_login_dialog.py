from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from app.login_dialog import OknoLogowania


def _app():
    return QApplication.instance() or QApplication([])


def _zamknij_aktywny_messagebox() -> None:
    aktywny = QApplication.activeModalWidget()
    if isinstance(aktywny, QMessageBox):
        aktywny.close()


def test_pusty_email_lub_haslo_nie_zamyka_okna():
    _app()
    dialog = OknoLogowania()

    # QMessageBox.warning() jest modalny i normalnie czeka na klik - symulujemy go timerem,
    # zeby test nie wisial w nieskonczonosc czekajac na uzytkownika.
    QTimer.singleShot(0, _zamknij_aktywny_messagebox)
    dialog._na_zaloguj()

    assert dialog.result() == 0  # nie zaakceptowano
    assert dialog.email == ""


def test_wypelnione_dane_akceptuja_okno():
    _app()
    dialog = OknoLogowania()
    dialog._pole_email.setText(" test@przyklad.pl ")
    dialog._pole_haslo.setText("haslo123")

    dialog._na_zaloguj()

    assert dialog.email == "test@przyklad.pl"
    assert dialog.haslo == "haslo123"
    assert dialog.zapamietaj_haslo is False  # checkbox domyslnie odznaczony


def test_domyslny_email_i_haslo_wypelniaja_pola_i_zaznaczaja_checkbox():
    _app()
    dialog = OknoLogowania(domyslny_email="a@b.pl", domyslne_haslo="stare-haslo")

    assert dialog._pole_email.text() == "a@b.pl"
    assert dialog._pole_haslo.text() == "stare-haslo"
    assert dialog._checkbox_zapamietaj.isChecked() is True

    dialog._na_zaloguj()

    assert dialog.zapamietaj_haslo is True


def test_bez_domyslnego_hasla_checkbox_jest_odznaczony():
    _app()
    dialog = OknoLogowania(domyslny_email="a@b.pl")
    assert dialog._checkbox_zapamietaj.isChecked() is False
