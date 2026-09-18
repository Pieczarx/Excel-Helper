from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from app.styl import EkranStartowy


def _app():
    app = QApplication.instance()
    return app or QApplication([])


def test_ekran_startowy_pokazuje_poczatkowy_tekst():
    _app()
    ekran = EkranStartowy()
    assert ekran._etykieta.text() == "Uruchamianie…"
    assert ekran._pasek.value() == 0


def test_ekran_startowy_ustaw_postep_aktualizuje_pasek_i_tekst():
    _app()
    ekran = EkranStartowy()

    ekran.ustaw_postep(55, "Łączenie z kontem…")

    assert ekran._pasek.value() == 55
    assert ekran._etykieta.text() == "Łączenie z kontem…"


def test_ekran_startowy_dziala_bez_ikony_i_z_pusta_ikona():
    _app()
    EkranStartowy(ikona=None)
    EkranStartowy(ikona=QPixmap())  # pusta pixmapa (isNull() True) - nie powinno rzucic
