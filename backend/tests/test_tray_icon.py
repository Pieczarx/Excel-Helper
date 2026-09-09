from app.tray_icon import rysuj_ikone


def test_rozmiar_i_tryb_obrazu():
    obraz = rysuj_ikone(0)
    assert obraz.size == (64, 64)
    assert obraz.mode == "RGBA"


def test_bez_alertow_nie_rysuje_badge():
    bez_alertow = rysuj_ikone(0)
    z_alertami = rysuj_ikone(5)
    assert bez_alertow.tobytes() != z_alertami.tobytes()


def test_duza_liczba_nie_wywala_sie():
    # samo wywolanie nie powinno rzucic wyjatku dla duzej liczby (etykieta "99+")
    rysuj_ikone(250)
