"""Testy magazynu Supabase na fałszywym kliencie - nie łączą się z prawdziwym Supabase."""
from types import SimpleNamespace

import pytest
from postgrest.exceptions import APIError

from app.alerts import Alert
from app.config import wczytaj_sesje_supabase, zapisz_sesje_supabase
from app.supabase_store import BledneDaneLogowania, SupabaseAlertStore, przywroc_sesje, zaloguj

EMAIL_TESTOWY = "test@przyklad.pl"


class _FakeTabela:
    def __init__(self, dane: dict, klient: "_FakeClient"):
        self._dane = dane
        self._klient = klient
        self._operacja = None
        self._payload = None
        self._warunek = None

    def upsert(self, payload):
        self._operacja, self._payload = "upsert", payload
        return self

    def select(self, *_args):
        self._operacja = "select"
        return self

    def delete(self):
        self._operacja = "delete"
        return self

    def eq(self, kolumna, wartosc):
        self._warunek = (kolumna, wartosc)
        return self

    def execute(self):
        if self._klient.wygasniecia_pozostale > 0:
            self._klient.wygasniecia_pozostale -= 1
            raise APIError({"message": "JWT expired", "code": "PGRST303", "hint": None, "details": None})

        if self._operacja == "upsert":
            self._dane[self._payload["klucz"]] = self._payload
        elif self._operacja == "select":
            return SimpleNamespace(data=list(self._dane.values()))
        elif self._operacja == "delete":
            kolumna, wartosc = self._warunek
            for klucz in [k for k, w in self._dane.items() if w.get(kolumna) == wartosc]:
                del self._dane[klucz]
        return SimpleNamespace(data=[])


class _FakeAuth:
    def __init__(self, udane_logowanie: bool = True):
        self.udane_logowanie = udane_logowanie
        self.zalogowany = False
        self.odswiezono = 0

    def sign_in_with_password(self, _dane):
        if not self.udane_logowanie:
            raise Exception("Invalid login credentials")
        self.zalogowany = True
        return SimpleNamespace(
            session=SimpleNamespace(access_token="tok-a", refresh_token="tok-r"),
            user=SimpleNamespace(id="user-1", email=EMAIL_TESTOWY),
        )

    def set_session(self, access_token, refresh_token):
        self.zalogowany = True
        return SimpleNamespace(
            session=SimpleNamespace(access_token=access_token, refresh_token=refresh_token),
            user=SimpleNamespace(id="user-1", email=EMAIL_TESTOWY),
        )

    def get_user(self):
        if not self.zalogowany:
            raise Exception("brak waznej sesji")
        return SimpleNamespace(user=SimpleNamespace(id="user-1", email=EMAIL_TESTOWY))

    def refresh_session(self):
        self.odswiezono += 1
        return SimpleNamespace(session=SimpleNamespace(access_token="tok-a2", refresh_token="tok-r2"))

    def sign_out(self):
        self.zalogowany = False


class _FakeClient:
    def __init__(self, udane_logowanie: bool = True, wygasniecia_pozostale: int = 0):
        self.auth = _FakeAuth(udane_logowanie)
        self.wygasniecia_pozostale = wygasniecia_pozostale
        self._tabele: dict[str, dict] = {}

    def table(self, nazwa: str) -> _FakeTabela:
        return _FakeTabela(self._tabele.setdefault(nazwa, {}), self)


def _alert(klucz_pomocniczy: str = "a") -> Alert:
    return Alert(
        rodzaj="ODCHYLENIE",
        obiekt_wiersz=3,
        obiekt_nazwa="Testowy obiekt",
        opis=f"opis {klucz_pomocniczy}",
        pole="zuzycie_razem",
        wartosc_poprzednia=10.0,
        wartosc_biezaca=25.0,
    )


def test_oznacz_jako_prawidlowy_wycisza_alert():
    magazyn = SupabaseAlertStore(_FakeClient())
    alert = _alert()

    assert magazyn.odfiltruj_aktywne([alert]) == [alert]
    magazyn.oznacz_jako_prawidlowy(alert)
    assert magazyn.odfiltruj_aktywne([alert]) == []


def test_wygasly_token_odswieza_sie_sam_i_ponawia_wywolanie(tmp_path):
    fake = _FakeClient(wygasniecia_pozostale=1)
    sciezka_sesji = tmp_path / "sesja.json"
    magazyn = SupabaseAlertStore(fake, session_path=sciezka_sesji)
    alert = _alert()

    magazyn.oznacz_jako_prawidlowy(alert)  # pierwsze API wywolanie rzuca PGRST303 - powinno sie samo naprawic

    assert fake.auth.odswiezono == 1
    assert magazyn.odfiltruj_aktywne([alert]) == []  # dowod ze upsert faktycznie przeszedl za drugim razem
    assert wczytaj_sesje_supabase(sciezka_sesji) == {"access_token": "tok-a2", "refresh_token": "tok-r2"}


def test_zaloguj_zapisuje_sesje_i_zwraca_magazyn(tmp_path, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr("app.supabase_store.create_client", lambda url, key: fake)
    sciezka_sesji = tmp_path / "sesja.json"

    magazyn = zaloguj("https://x.supabase.co", "anon", "a@b.pl", "haslo", session_path=sciezka_sesji)

    assert isinstance(magazyn, SupabaseAlertStore)
    assert wczytaj_sesje_supabase(sciezka_sesji) == {"access_token": "tok-a", "refresh_token": "tok-r"}


def test_zaloguj_ze_zlym_haslem_rzuca_bledne_dane_logowania(tmp_path, monkeypatch):
    fake = _FakeClient(udane_logowanie=False)
    monkeypatch.setattr("app.supabase_store.create_client", lambda url, key: fake)

    with pytest.raises(BledneDaneLogowania):
        zaloguj("https://x.supabase.co", "anon", "a@b.pl", "zle-haslo", session_path=tmp_path / "sesja.json")


def test_przywroc_sesje_dziala_gdy_jest_zapisana(tmp_path, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr("app.supabase_store.create_client", lambda url, key: fake)
    sciezka_sesji = tmp_path / "sesja.json"
    zapisz_sesje_supabase("tok-a", "tok-r", sciezka_sesji)

    magazyn = przywroc_sesje("https://x.supabase.co", "anon", sciezka_sesji)

    assert isinstance(magazyn, SupabaseAlertStore)


def test_przywroc_sesje_bez_zapisanej_sesji_zwraca_none(tmp_path, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr("app.supabase_store.create_client", lambda url, key: fake)

    assert przywroc_sesje("https://x.supabase.co", "anon", tmp_path / "brak.json") is None


def test_zaloguj_zapamietuje_email(tmp_path, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr("app.supabase_store.create_client", lambda url, key: fake)

    magazyn = zaloguj("https://x.supabase.co", "anon", "a@b.pl", "haslo", session_path=tmp_path / "sesja.json")

    assert magazyn.email == EMAIL_TESTOWY


def test_przywroc_sesje_zapamietuje_email(tmp_path, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr("app.supabase_store.create_client", lambda url, key: fake)
    sciezka_sesji = tmp_path / "sesja.json"
    zapisz_sesje_supabase("tok-a", "tok-r", sciezka_sesji)

    magazyn = przywroc_sesje("https://x.supabase.co", "anon", sciezka_sesji)

    assert magazyn.email == EMAIL_TESTOWY


def test_przywroc_sesje_zapisuje_odswiezony_token_z_powrotem_na_dysk(tmp_path, monkeypatch):
    # Bug: set_session() sam odświeża wygasły access_token, ale stary kod przywroc_sesje nigdy nie
    # zapisywał świeżej pary z powrotem - a refresh_token w Supabase rotuje przy każdym użyciu, więc
    # drugi restart z rzędu próbował użyć już zużytego tokenu i się wywalał (user musiał się logować
    # ręcznie). Ten test symuluje set_session zwracające INNĄ parę niż ta z dysku (jak przy realnym
    # odświeżeniu) i sprawdza, że nowa para faktycznie ląduje w pliku sesji.
    class _FakeAuthOdswiezajace(_FakeAuth):
        def set_session(self, _access_token, _refresh_token):
            self.zalogowany = True
            return SimpleNamespace(
                session=SimpleNamespace(access_token="tok-a-nowy", refresh_token="tok-r-nowy"),
                user=SimpleNamespace(id="user-1", email=EMAIL_TESTOWY),
            )

    fake = _FakeClient()
    fake.auth = _FakeAuthOdswiezajace()
    monkeypatch.setattr("app.supabase_store.create_client", lambda url, key: fake)
    sciezka_sesji = tmp_path / "sesja.json"
    zapisz_sesje_supabase("tok-a-stary", "tok-r-stary", sciezka_sesji)

    magazyn = przywroc_sesje("https://x.supabase.co", "anon", sciezka_sesji)

    assert isinstance(magazyn, SupabaseAlertStore)
    assert wczytaj_sesje_supabase(sciezka_sesji) == {"access_token": "tok-a-nowy", "refresh_token": "tok-r-nowy"}


def test_wyloguj_usuwa_sesje_i_wylogowuje_klienta(tmp_path, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr("app.supabase_store.create_client", lambda url, key: fake)
    sciezka_sesji = tmp_path / "sesja.json"

    magazyn = zaloguj("https://x.supabase.co", "anon", "a@b.pl", "haslo", session_path=sciezka_sesji)
    assert wczytaj_sesje_supabase(sciezka_sesji) is not None

    magazyn.wyloguj()

    assert wczytaj_sesje_supabase(sciezka_sesji) is None
    assert fake.auth.zalogowany is False
