from app.historia_faktur_base import PustyMagazynHistorii


def test_pusty_magazyn_nic_nie_przechowuje():
    magazyn = PustyMagazynHistorii()

    magazyn.zapisz("D 01.pdf", [], powod_odrzucenia="cokolwiek")

    assert magazyn.ostatnie() == []


def test_pusty_magazyn_usun_i_close_nie_rzucaja():
    magazyn = PustyMagazynHistorii()

    magazyn.usun(1)
    magazyn.close()
