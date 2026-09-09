"""Testy na fałszywym keyringu - nie dotykają prawdziwego magazynu poświadczeń Windows."""
import pytest

from app import haslo_store


class _FakeKeyringErrors:
    class PasswordDeleteError(Exception):
        pass


class _FakeKeyring:
    def __init__(self):
        self._dane: dict[tuple[str, str], str] = {}
        self.errors = _FakeKeyringErrors()

    def set_password(self, serwis, username, haslo):
        self._dane[(serwis, username)] = haslo

    def get_password(self, serwis, username):
        return self._dane.get((serwis, username))

    def delete_password(self, serwis, username):
        if (serwis, username) not in self._dane:
            raise self.errors.PasswordDeleteError()
        del self._dane[(serwis, username)]


@pytest.fixture
def fake_keyring(monkeypatch):
    fake = _FakeKeyring()
    monkeypatch.setattr(haslo_store, "keyring", fake)
    return fake


def test_zapisz_i_wczytaj_haslo(fake_keyring):
    haslo_store.zapisz_haslo("a@b.pl", "tajne123", serwis="test-serwis")
    assert haslo_store.wczytaj_haslo("a@b.pl", serwis="test-serwis") == "tajne123"


def test_brak_hasla_zwraca_none(fake_keyring):
    assert haslo_store.wczytaj_haslo("nikt@nigdzie.pl", serwis="test-serwis") is None


def test_usun_haslo_dziala_i_jest_bezpieczne_gdy_nic_nie_ma(fake_keyring):
    haslo_store.zapisz_haslo("a@b.pl", "tajne123", serwis="test-serwis")
    haslo_store.usun_haslo("a@b.pl", serwis="test-serwis")
    assert haslo_store.wczytaj_haslo("a@b.pl", serwis="test-serwis") is None

    haslo_store.usun_haslo("a@b.pl", serwis="test-serwis")  # nie rzuca, mimo ze juz nie ma
