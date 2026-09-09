from PySide6.QtWidgets import QApplication, QMessageBox

from app.aktualizacje import Wydanie
from app.firmy import Firma
from app.historia_faktur import HistoriaFakturStore
from app.kontroler import Kontroler
from app.kontroler_faktur import KontrolerFaktur
from app.store import AlertStore
from app.widok_uzupelnij_excel import WidokUzupelnijExcel
from app.widok_weryfikacji import WidokWeryfikacji
from app.window import ZAKLADKA_UZUPELNIJ, ZAKLADKA_WERYFIKACJA, GlowneOkno


def _app():
    app = QApplication.instance()
    return app or QApplication([])


def _firmy_testowe(tmp_path) -> list[Firma]:
    return [
        Firma(
            id="a", nazwa="Firma A", akcent="#2FA968",
            config_path=tmp_path / "config_a.json", faktury_config_path=tmp_path / "faktury_a.json",
        ),
        Firma(
            id="b", nazwa="Firma B", akcent="#FF6F51",
            config_path=tmp_path / "config_b.json", faktury_config_path=tmp_path / "faktury_b.json",
        ),
    ]


def _pary(tmp_path, store=None, historia=None, supabase_config_path=None, haslo_serwis=None):
    """Dwie firmy testowe, dzielące (jak w main.py) jeden magazyn alertów i jedną historię faktur -
    tylko `config_path`/`faktury_config_path` (plik Excela/folder faktur) różnią się per firma."""
    store = store or AlertStore(tmp_path / "alerts.db")
    historia = historia or HistoriaFakturStore(tmp_path / "historia.db")
    supabase_config_path = supabase_config_path or tmp_path / "supabase.json"
    pary = []
    for i, firma in enumerate(_firmy_testowe(tmp_path)):
        kwargs = {"supabase_config_path": supabase_config_path}
        if i == 0 and haslo_serwis is not None:
            kwargs["haslo_serwis"] = haslo_serwis
        kontroler = Kontroler(store, config_path=firma.config_path, **kwargs)
        kontroler_faktur = KontrolerFaktur(historia, config_path=firma.faktury_config_path)
        pary.append((firma, kontroler, kontroler_faktur))
    return pary


def _okno(tmp_path) -> GlowneOkno:
    return GlowneOkno(_pary(tmp_path))


def test_uzupelnij_excel_jest_domyslna_zakladka(tmp_path):
    _app()
    okno = _okno(tmp_path)
    stos = okno._widoki["a"]["stos"]

    assert stos.currentIndex() == ZAKLADKA_UZUPELNIJ
    assert isinstance(stos.currentWidget(), WidokUzupelnijExcel)


def test_klik_w_zakladke_weryfikacja_przelacza_widok(tmp_path):
    _app()
    okno = _okno(tmp_path)
    dane = okno._widoki["a"]

    dane["zakladki"][ZAKLADKA_WERYFIKACJA].click()

    assert dane["stos"].currentIndex() == ZAKLADKA_WERYFIKACJA
    assert isinstance(dane["stos"].currentWidget(), WidokWeryfikacji)


def test_pierwsza_firma_jest_domyslnie_aktywna_a_klik_przelacza(tmp_path):
    _app()
    okno = _okno(tmp_path)

    assert okno._stos_firm.currentIndex() == 0

    okno._widgety_firm["b"]["przycisk"].click()

    assert okno._stos_firm.currentIndex() == 1


def test_kazda_firma_ma_wlasny_niezalezny_stos_zakladek(tmp_path):
    """Przełączenie zakładki w jednej firmie nie rusza drugiej - to dwie osobne pary
    (stos, zakladki), nie jedna dzielona."""
    _app()
    okno = _okno(tmp_path)

    okno._widoki["a"]["zakladki"][ZAKLADKA_WERYFIKACJA].click()

    assert okno._widoki["a"]["stos"].currentIndex() == ZAKLADKA_WERYFIKACJA
    assert okno._widoki["b"]["stos"].currentIndex() == ZAKLADKA_UZUPELNIJ


def test_przycisk_logowania_zawsze_widoczny_gdy_skonfigurowany(tmp_path):
    from app.config import zapisz_konfiguracje_supabase

    _app()
    supabase_config = tmp_path / "supabase.json"
    zapisz_konfiguracje_supabase("https://x.supabase.co", "anon", supabase_config)
    okno = GlowneOkno(_pary(tmp_path, supabase_config_path=supabase_config))

    assert not okno._przycisk_zaloguj.isHidden()
    assert okno._przycisk_zaloguj.text() == "Zaloguj"
    assert okno._przycisk_zaloguj.isEnabled()


def test_pasek_aktualizacji_ukryty_domyslnie(tmp_path):
    _app()
    okno = _okno(tmp_path)
    assert okno._pasek_aktualizacji.isHidden()


def _wydanie(wersja="9.9.9") -> Wydanie:
    return Wydanie(tag=f"v{wersja}", wersja=wersja, url_zip=f"http://przykladowy-url/v{wersja}.zip")


def test_pasek_aktualizacji_pokazuje_sie_po_znalezieniu_nowszej_wersji(tmp_path):
    _app()
    okno = _okno(tmp_path)

    okno._na_znaleziono_nowsza_wersje(_wydanie("9.9.9"))

    assert not okno._pasek_aktualizacji.isHidden()
    assert "9.9.9" in okno._etykieta_aktualizacji.text()
    assert okno._przycisk_zainstaluj.text() == "Zainstaluj"


def test_klik_zainstaluj_uruchamia_instalacje_w_tle_i_blokuje_przycisk(tmp_path, monkeypatch):
    _app()
    okno = _okno(tmp_path)
    okno._na_znaleziono_nowsza_wersje(_wydanie("9.9.9"))

    wywolania = []
    monkeypatch.setattr(okno._instalator, "instaluj_w_tle", lambda url: wywolania.append(url))

    okno._na_klik_zainstaluj()

    assert wywolania == ["http://przykladowy-url/v9.9.9.zip"]
    assert not okno._przycisk_zainstaluj.isEnabled()
    assert okno._przycisk_zainstaluj.text() == "Instalowanie..."


def test_instalacja_zakonczona_restartuje_i_zamyka_aplikacje(tmp_path, monkeypatch):
    _app()
    okno = _okno(tmp_path)

    wywolano_restart = []
    monkeypatch.setattr("app.window.uruchom_ponownie", lambda: wywolano_restart.append(True))
    wywolano_quit = []
    monkeypatch.setattr(QApplication, "quit", lambda self=None: wywolano_quit.append(True))

    okno._na_instalacja_zakonczona()

    assert wywolano_restart == [True]
    assert wywolano_quit == [True]


def test_blad_instalacji_odblokowuje_przycisk_i_pokazuje_ostrzezenie(tmp_path, monkeypatch):
    _app()
    okno = _okno(tmp_path)
    okno._na_znaleziono_nowsza_wersje(_wydanie("9.9.9"))
    okno._przycisk_zainstaluj.setEnabled(False)
    okno._przycisk_zainstaluj.setText("Instalowanie...")

    wywolania = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: wywolania.append(a))

    okno._na_blad_instalacji("dysk pelny")

    assert okno._przycisk_zainstaluj.isEnabled()
    assert okno._przycisk_zainstaluj.text() == "Zainstaluj"
    assert wywolania


def test_historia_ukryta_domyslnie_a_po_zalogowaniu_pokazana_dla_obu_firm(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from app.config import zapisz_konfiguracje_supabase
    from app.supabase_historia_store import SupabaseHistoriaFakturStore

    class _FakeZapytanie:
        def select(self, *_args):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, *_args):
            return self

        def execute(self):
            return SimpleNamespace(data=[])

    class _FakeAuth:
        def sign_in_with_password(self, _dane):
            return SimpleNamespace(
                session=SimpleNamespace(access_token="tok-a", refresh_token="tok-r"),
                user=SimpleNamespace(email="a@b.pl"),
            )

        def sign_out(self):
            pass

    class _FakeKlient:
        auth = _FakeAuth()

        def table(self, _nazwa):
            return _FakeZapytanie()

    class _FakeKeyring:
        def __init__(self):
            self._dane = {}

        def set_password(self, serwis, username, haslo):
            self._dane[(serwis, username)] = haslo

        def get_password(self, serwis, username):
            return self._dane.get((serwis, username))

        def delete_password(self, serwis, username):
            self._dane.pop((serwis, username), None)

    monkeypatch.setattr("app.supabase_store.create_client", lambda url, key: _FakeKlient())
    # Bez tego kontroler.zaloguj_supabase() niżej naprawdę woła keyring na PRAWDZIWYM Windows
    # Credential Managerze - zapamietaj_haslo domyślnie False -> usun_haslo skasowałoby realnie
    # zapamiętane hasło użytkownika do konta "a@b.pl" pod produkcyjnym serwisem (HASLO_SERWIS),
    # gdyby haslo_serwis też nie było nadpisane - potwierdzone jako realny incydent.
    monkeypatch.setattr("app.haslo_store.keyring", _FakeKeyring())

    _app()
    supabase_config = tmp_path / "supabase.json"
    zapisz_konfiguracje_supabase("https://x.supabase.co", "anon", supabase_config)
    okno = GlowneOkno(_pary(tmp_path, supabase_config_path=supabase_config, haslo_serwis="test-serwis"))

    assert okno._widoki["a"]["widok_uzupelnij"]._naglowek_historii.isHidden()
    assert okno._widoki["b"]["widok_uzupelnij"]._naglowek_historii.isHidden()

    # Logowanie idzie sieciowo tylko przez pierwszą (główną) firmę - druga dostaje ten sam
    # magazyn bez drugiego logowania, patrz GlowneOkno._propaguj_magazyn_do_pozostalych_firm.
    okno._kontroler_glowny.zaloguj_supabase("a@b.pl", "sekret123")
    okno._propaguj_magazyn_do_pozostalych_firm()
    okno._synchronizuj_historie_faktur()

    for firma_id in ("a", "b"):
        dane = okno._widoki[firma_id]
        assert not dane["widok_uzupelnij"]._naglowek_historii.isHidden()
        assert not dane["widok_uzupelnij"]._kontener_historii.isHidden()
        assert isinstance(dane["kontroler_faktur"]._historia, SupabaseHistoriaFakturStore)
        assert isinstance(dane["kontroler"].store, type(okno._kontroler_glowny.store))

    okno._na_klik_wyloguj()

    for firma_id in ("a", "b"):
        assert okno._widoki[firma_id]["widok_uzupelnij"]._naglowek_historii.isHidden()


def test_zamkniecie_okna_nie_zamyka_go_naprawde(tmp_path):
    _app()
    okno = _okno(tmp_path)
    okno.show()

    okno.close()

    assert not okno.isVisible()
    assert okno.isHidden()  # okno istnieje dalej (nie zniszczone), tylko ukryte
