from app.ikona import rysuj_ikone_bazowa


def test_rozmiar_i_tryb_obrazu():
    obraz = rysuj_ikone_bazowa(64)
    assert obraz.size == (64, 64)
    assert obraz.mode == "RGBA"


def test_skaluje_sie_do_innych_rozmiarow():
    for rozmiar in (16, 32, 128, 256):
        assert rysuj_ikone_bazowa(rozmiar).size == (rozmiar, rozmiar)


def test_rysuje_cos_nieprzezroczyste():
    obraz = rysuj_ikone_bazowa(64)
    piksele = obraz.load()
    srodek = piksele[32, 32]
    assert srodek[3] > 0  # kanal alfa - w centrum dokumentu nie moze byc calkiem przezroczyscie
