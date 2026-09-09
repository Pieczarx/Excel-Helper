import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from app.kontroler import Kontroler
from app.store import AlertStore

EXAMPLE_FILE = Path(__file__).resolve().parents[2] / "examples" / "MPECWIK 2026.xlsx"


def _app():
    # QCoreApplication (nie QApplication - nie potrzebujemy GUI/platformy) musi istniec dla sygnalow Qt.
    app = QCoreApplication.instance()
    return app or QCoreApplication([])


def _poczekaj_az(warunek, timeout: float = 5.0) -> bool:
    # Kolejkowane polaczenia sygnalow (miedzy watkami) dostarczane sa dopiero gdy petla zdarzen
    # tego watku faktycznie sie kreci - processEvents() to wymusza bez wchodzenia w app.exec().
    koniec = time.time() + timeout
    while time.time() < koniec:
        QCoreApplication.processEvents()
        if warunek():
            return True
        time.sleep(0.02)
    return False


def test_ustaw_plik_wyzwala_zmiane_z_pogrupowanymi_alertami(tmp_path):
    _app()
    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "supabase.json")
        odebrane = []
        kontroler.zmiana.connect(odebrane.append)

        kontroler.ustaw_plik(EXAMPLE_FILE)

        assert kontroler.sciezka == EXAMPLE_FILE.resolve()
        assert kontroler.rok == 2026
        assert len(odebrane) == 1
        assert odebrane[0] == kontroler.ostatnie_grupy
        assert odebrane[0]
        kontroler.zamknij()


def test_oznacz_jako_prawidlowy_odswieza_i_usuwa_alert(tmp_path):
    _app()
    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "supabase.json")
        kontroler.ustaw_plik(EXAMPLE_FILE)
        pierwszy_alert = kontroler.ostatnie_grupy[0].alerty[0]

        kontroler.oznacz_jako_prawidlowy(pierwszy_alert)

        wszystkie_klucze = {a.klucz for g in kontroler.ostatnie_grupy for a in g.alerty}
        assert pierwszy_alert.klucz not in wszystkie_klucze
        kontroler.zamknij()


def test_odswiez_w_tle_emituje_w_trakcie_i_aktualizuje_grupy(tmp_path):
    _app()
    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(
            store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "supabase.json"
        )
        kontroler.ustaw_plik(EXAMPLE_FILE)

        stany: list[bool] = []
        kontroler.w_trakcie.connect(stany.append)

        kontroler.odswiez_w_tle()

        assert _poczekaj_az(lambda: stany == [True, False])
        assert kontroler.ostatnie_grupy
        kontroler.zamknij()


def test_ustaw_magazyn_przelacza_i_odswieza(tmp_path):
    _app()
    with AlertStore(tmp_path / "stary.db") as stary_store, AlertStore(tmp_path / "nowy.db") as nowy_store:
        kontroler = Kontroler(
            stary_store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "supabase.json"
        )
        kontroler.ustaw_plik(EXAMPLE_FILE)
        pierwszy_alert = kontroler.ostatnie_grupy[0].alerty[0]

        stary_store.oznacz_jako_prawidlowy(pierwszy_alert)  # oznaczone w STARYM magazynie

        kontroler.ustaw_magazyn(nowy_store)

        assert _poczekaj_az(lambda: kontroler.ostatnie_grupy)
        wszystkie_klucze = {a.klucz for g in kontroler.ostatnie_grupy for a in g.alerty}
        assert pierwszy_alert.klucz in wszystkie_klucze  # nowy magazyn nic o nim nie wie - alert wraca
        kontroler.zamknij()


def test_czy_potrzebuje_logowania_false_gdy_brak_konfiguracji_supabase(tmp_path):
    _app()
    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(
            store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "brak_supabase.json"
        )
        assert kontroler.czy_potrzebuje_logowania() is False
        kontroler.zamknij()


def test_stan_synchronizacji_trzy_stany(tmp_path):
    _app()
    from app.config import zapisz_konfiguracje_supabase

    with AlertStore(tmp_path / "alerts.db") as store:
        # 1. brak konfiguracji supabase w ogole
        kontroler = Kontroler(
            store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "brak.json"
        )
        assert kontroler.stan_synchronizacji() == "NIESKONFIGUROWANY"
        kontroler.zamknij()

    # 2. supabase skonfigurowany, ale magazyn to lokalny AlertStore (nie zalogowano)
    supabase_config = tmp_path / "supabase2.json"
    zapisz_konfiguracje_supabase("https://x.supabase.co", "anon", supabase_config)
    with AlertStore(tmp_path / "alerts2.db") as store2:
        kontroler2 = Kontroler(
            store2, config_path=tmp_path / "config2.json", supabase_config_path=supabase_config
        )
        assert kontroler2.stan_synchronizacji() == "NIEZALOGOWANY"
        kontroler2.zamknij()


def test_email_zalogowanego_i_wyloguj(tmp_path):
    _app()
    from app.config import zapisz_konfiguracje_supabase
    from app.supabase_store import SupabaseAlertStore

    class _FakeAuth:
        def sign_out(self):
            pass

    class _FakeKlient:
        auth = _FakeAuth()

    supabase_config = tmp_path / "supabase.json"
    zapisz_konfiguracje_supabase("https://x.supabase.co", "anon", supabase_config)

    magazyn_supabase = SupabaseAlertStore(
        _FakeKlient(), session_path=tmp_path / "sesja.json", email="test@przyklad.pl"
    )
    kontroler = Kontroler(
        magazyn_supabase,
        config_path=tmp_path / "config.json",
        supabase_config_path=supabase_config,
        local_db_path=tmp_path / "po_wylogowaniu.db",
    )
    assert kontroler.email_zalogowanego() == "test@przyklad.pl"
    assert kontroler.stan_synchronizacji() == "ZALOGOWANY"

    kontroler.wyloguj()

    assert _poczekaj_az(lambda: kontroler.stan_synchronizacji() == "NIEZALOGOWANY")
    assert kontroler.email_zalogowanego() is None
    kontroler.zamknij()


def test_zaloguj_supabase_zapamietuje_email_i_haslo_gdy_zaznaczone(tmp_path, monkeypatch):
    _app()
    from types import SimpleNamespace

    from app.config import wczytaj_ostatni_email, zapisz_konfiguracje_supabase

    class _FakeAuth:
        def sign_in_with_password(self, _dane):
            return SimpleNamespace(
                session=SimpleNamespace(access_token="tok-a", refresh_token="tok-r"),
                user=SimpleNamespace(email="a@b.pl"),
            )

    class _FakeKlient:
        auth = _FakeAuth()

    class _FakeKeyring:
        def __init__(self):
            self._dane = {}

        def set_password(self, serwis, username, haslo):
            self._dane[(serwis, username)] = haslo

        def get_password(self, serwis, username):
            return self._dane.get((serwis, username))

        def delete_password(self, serwis, username):
            del self._dane[(serwis, username)]

    fake_keyring = _FakeKeyring()
    monkeypatch.setattr("app.supabase_store.create_client", lambda url, key: _FakeKlient())
    monkeypatch.setattr("app.haslo_store.keyring", fake_keyring)

    supabase_config = tmp_path / "supabase.json"
    zapisz_konfiguracje_supabase("https://x.supabase.co", "anon", supabase_config)
    ostatni_login_path = tmp_path / "ostatni_login.json"

    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(
            store,
            config_path=tmp_path / "config.json",
            supabase_config_path=supabase_config,
            ostatni_login_path=ostatni_login_path,
            haslo_serwis="test-serwis",
            supabase_session_path=tmp_path / "sesja.json",
        )

        kontroler.zaloguj_supabase("a@b.pl", "sekret123", zapamietaj_haslo=True)

        assert wczytaj_ostatni_email(ostatni_login_path) == "a@b.pl"
        assert fake_keyring.get_password("test-serwis", "a@b.pl") == "sekret123"

        email, haslo = kontroler.dane_do_logowania()
        assert email == "a@b.pl"
        assert haslo == "sekret123"
        kontroler.zamknij()


def test_zaloguj_supabase_bez_zapamietania_nie_zapisuje_hasla(tmp_path, monkeypatch):
    _app()
    from types import SimpleNamespace

    from app.config import zapisz_konfiguracje_supabase

    class _FakeAuth:
        def sign_in_with_password(self, _dane):
            return SimpleNamespace(
                session=SimpleNamespace(access_token="tok-a", refresh_token="tok-r"),
                user=SimpleNamespace(email="a@b.pl"),
            )

    class _FakeKlient:
        auth = _FakeAuth()

    class _FakeKeyring:
        def __init__(self):
            self._dane = {}

        def set_password(self, serwis, username, haslo):
            self._dane[(serwis, username)] = haslo

        def get_password(self, serwis, username):
            return self._dane.get((serwis, username))

        def delete_password(self, serwis, username):
            self._dane.pop((serwis, username), None)

    fake_keyring = _FakeKeyring()
    monkeypatch.setattr("app.supabase_store.create_client", lambda url, key: _FakeKlient())
    monkeypatch.setattr("app.haslo_store.keyring", fake_keyring)

    supabase_config = tmp_path / "supabase.json"
    zapisz_konfiguracje_supabase("https://x.supabase.co", "anon", supabase_config)

    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(
            store,
            config_path=tmp_path / "config.json",
            supabase_config_path=supabase_config,
            ostatni_login_path=tmp_path / "ostatni_login.json",
            haslo_serwis="test-serwis",
            supabase_session_path=tmp_path / "sesja.json",
        )

        kontroler.zaloguj_supabase("a@b.pl", "sekret123", zapamietaj_haslo=False)

        assert fake_keyring.get_password("test-serwis", "a@b.pl") is None
        _, haslo = kontroler.dane_do_logowania()
        assert haslo == ""
        kontroler.zamknij()


def test_czy_plik_otwarty_false_bez_wybranego_pliku(tmp_path):
    _app()
    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "supabase.json")
        assert kontroler.czy_plik_otwarty() is False


def test_czy_plik_otwarty_wykrywa_plik_blokady(tmp_path):
    _app()
    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "supabase.json")
        kontroler.ustaw_plik(EXAMPLE_FILE)
        assert kontroler.czy_plik_otwarty() is False

        plik_blokady = EXAMPLE_FILE.resolve().with_name(f"~${EXAMPLE_FILE.name}")
        plik_blokady.write_text("")
        try:
            assert kontroler.czy_plik_otwarty() is True
        finally:
            plik_blokady.unlink()
        kontroler.zamknij()


def test_identyfikacja_obiektu_dostepna_po_wierszu(tmp_path):
    _app()
    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "supabase.json")
        kontroler.ustaw_plik(EXAMPLE_FILE)

        identyfikacja = kontroler.identyfikacja_obiektu(3)
        assert identyfikacja["Nr licznika"] == "87268444"
        assert kontroler.identyfikacja_obiektu(999999) == {}
        kontroler.zamknij()


def test_klient_supabase_none_dopoki_niezalogowany_potem_klient_potem_znow_none(tmp_path, monkeypatch):
    _app()
    from types import SimpleNamespace

    from app.config import zapisz_konfiguracje_supabase

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

    class _FakeKeyring:
        def __init__(self):
            self._dane = {}

        def set_password(self, serwis, username, haslo):
            self._dane[(serwis, username)] = haslo

        def get_password(self, serwis, username):
            return self._dane.get((serwis, username))

        def delete_password(self, serwis, username):
            self._dane.pop((serwis, username), None)

    fake_klient = _FakeKlient()
    monkeypatch.setattr("app.supabase_store.create_client", lambda url, key: fake_klient)
    # Bez tego kontroler.zaloguj_supabase() niżej naprawdę woła keyring na PRAWDZIWYM Windows
    # Credential Managerze - zapamietaj_haslo domyślnie False -> usun_haslo skasowałoby realnie
    # zapamiętane hasło użytkownika do konta "a@b.pl" pod produkcyjnym serwisem (HASLO_SERWIS),
    # gdyby haslo_serwis też nie było nadpisane - potwierdzone jako realny incydent.
    monkeypatch.setattr("app.haslo_store.keyring", _FakeKeyring())

    supabase_config = tmp_path / "supabase.json"
    zapisz_konfiguracje_supabase("https://x.supabase.co", "anon", supabase_config)

    with AlertStore(tmp_path / "alerts.db") as store:
        kontroler = Kontroler(
            store,
            config_path=tmp_path / "config.json",
            supabase_config_path=supabase_config,
            supabase_session_path=tmp_path / "sesja.json",
            haslo_serwis="test-serwis",
        )

        assert kontroler.klient_supabase() is None

        kontroler.zaloguj_supabase("a@b.pl", "sekret123")
        assert kontroler.klient_supabase() is fake_klient

        kontroler.wyloguj()
        assert kontroler.klient_supabase() is None
        kontroler.zamknij()
