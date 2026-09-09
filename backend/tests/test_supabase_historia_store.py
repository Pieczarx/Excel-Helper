"""Testy magazynu Supabase historii faktur (per konto) na fałszywym kliencie - nie łączą się
z prawdziwym Supabase. Wzorowane na test_supabase_store.py (alerty)."""
from types import SimpleNamespace

from postgrest.exceptions import APIError

from app.import_faktur import WynikWpisu
from app.supabase_historia_store import SupabaseHistoriaFakturStore


class _FakeTabela:
    def __init__(self, wiersze: dict, klient: "_FakeClient"):
        self._wiersze = wiersze
        self._klient = klient
        self._operacja = None
        self._payload = None
        self._warunek = None
        self._limit = None

    def insert(self, payload):
        self._operacja, self._payload = "insert", payload
        return self

    def select(self, *_args):
        self._operacja = "select"
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, n):
        self._limit = n
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

        if self._operacja == "insert":
            nowe_id = self._klient.nastepne_id
            self._klient.nastepne_id += 1
            wiersz = {**self._payload, "id": nowe_id, "wpisano_dnia": "2026-08-28T12:00:00+00:00"}
            self._wiersze[nowe_id] = wiersz
            return SimpleNamespace(data=[wiersz])
        if self._operacja == "select":
            wiersze = sorted(self._wiersze.values(), key=lambda w: w["id"], reverse=True)
            if self._limit is not None:
                wiersze = wiersze[: self._limit]
            return SimpleNamespace(data=wiersze)
        if self._operacja == "delete":
            kolumna, wartosc = self._warunek
            for klucz in [k for k, w in self._wiersze.items() if w.get(kolumna) == wartosc]:
                del self._wiersze[klucz]
        return SimpleNamespace(data=[])


class _FakeAuth:
    def __init__(self):
        self.odswiezono = 0

    def refresh_session(self):
        self.odswiezono += 1
        return SimpleNamespace(session=SimpleNamespace(access_token="tok-a2", refresh_token="tok-r2"))


class _FakeClient:
    def __init__(self, wygasniecia_pozostale: int = 0):
        self.auth = _FakeAuth()
        self.wygasniecia_pozostale = wygasniecia_pozostale
        self.nastepne_id = 1
        self._tabele: dict[str, dict] = {}

    def table(self, nazwa: str) -> _FakeTabela:
        return _FakeTabela(self._tabele.setdefault(nazwa, {}), self)


def _wynik(ppe: str = "PPE-1") -> WynikWpisu:
    return WynikWpisu(kategoria="sukces", ppe=ppe, wiersz=3, nazwa_obiektu="Testowy obiekt", miesiac=3)


def test_zapisz_i_ostatnie_zwraca_wpis(tmp_path):
    magazyn = SupabaseHistoriaFakturStore(_FakeClient(), session_path=tmp_path / "sesja.json")

    magazyn.zapisz("D 01.pdf", [_wynik()])

    ostatnie = magazyn.ostatnie()
    assert len(ostatnie) == 1
    assert ostatnie[0].nazwa_pliku == "D 01.pdf"
    assert ostatnie[0].nierozpoznana is False
    assert ostatnie[0].pozycje[0].ppe == "PPE-1"


def test_ostatnie_sa_w_kolejnosci_od_najnowszych(tmp_path):
    magazyn = SupabaseHistoriaFakturStore(_FakeClient(), session_path=tmp_path / "sesja.json")

    magazyn.zapisz("D 01.pdf", [_wynik()])
    magazyn.zapisz("D 02.pdf", [_wynik()])

    assert [w.nazwa_pliku for w in magazyn.ostatnie()] == ["D 02.pdf", "D 01.pdf"]


def test_usun_usuwa_wpis(tmp_path):
    magazyn = SupabaseHistoriaFakturStore(_FakeClient(), session_path=tmp_path / "sesja.json")
    magazyn.zapisz("D 01.pdf", [_wynik()])
    wpis_id = magazyn.ostatnie()[0].id

    magazyn.usun(wpis_id)

    assert magazyn.ostatnie() == []


def test_wygasly_token_odswieza_sie_sam_i_ponawia_wywolanie(tmp_path):
    fake = _FakeClient(wygasniecia_pozostale=1)
    magazyn = SupabaseHistoriaFakturStore(fake, session_path=tmp_path / "sesja.json")

    magazyn.zapisz("D 01.pdf", [_wynik()])

    assert fake.auth.odswiezono == 1
    assert len(magazyn.ostatnie()) == 1
