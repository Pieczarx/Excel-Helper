from app.config import (
    usun_sesje_supabase,
    wczytaj_konfiguracje_supabase,
    wczytaj_ostatni_email,
    wczytaj_sciezke_faktur,
    wczytaj_sciezke_pliku,
    wczytaj_sesje_supabase,
    zapisz_konfiguracje_supabase,
    zapisz_ostatni_email,
    zapisz_sciezke_faktur,
    zapisz_sciezke_pliku,
    zapisz_sesje_supabase,
)


def test_brak_pliku_konfiguracji_zwraca_none(tmp_path):
    assert wczytaj_sciezke_pliku(tmp_path / "brak.json") is None


def test_zapisz_i_wczytaj_sciezke(tmp_path):
    config_path = tmp_path / "config.json"
    plik = tmp_path / "MPECWIK 2026.xlsx"
    plik.write_text("dummy")

    zapisz_sciezke_pliku(plik, config_path)
    assert wczytaj_sciezke_pliku(config_path) == plik.resolve()


def test_uszkodzony_plik_konfiguracji_zwraca_none(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{ to nie jest poprawny json")
    assert wczytaj_sciezke_pliku(config_path) is None


def test_brak_sciezki_faktur_zwraca_none(tmp_path):
    assert wczytaj_sciezke_faktur(tmp_path / "brak.json") is None


def test_zapisz_i_wczytaj_sciezke_faktur(tmp_path):
    config_path = tmp_path / "faktury_config.json"
    folder = tmp_path / "Faktury"
    folder.mkdir()

    zapisz_sciezke_faktur(folder, config_path)
    assert wczytaj_sciezke_faktur(config_path) == folder.resolve()


def test_brak_konfiguracji_supabase_zwraca_none(tmp_path):
    assert wczytaj_konfiguracje_supabase(tmp_path / "brak.json") is None


def test_zapisz_i_wczytaj_konfiguracje_supabase(tmp_path):
    sciezka = tmp_path / "supabase.json"
    zapisz_konfiguracje_supabase("https://x.supabase.co", "anon-key", sciezka)
    assert wczytaj_konfiguracje_supabase(sciezka) == ("https://x.supabase.co", "anon-key")


def test_zapisz_wczytaj_i_usun_sesje_supabase(tmp_path):
    sciezka = tmp_path / "sesja.json"
    assert wczytaj_sesje_supabase(sciezka) is None

    zapisz_sesje_supabase("tok-a", "tok-r", sciezka)
    assert wczytaj_sesje_supabase(sciezka) == {"access_token": "tok-a", "refresh_token": "tok-r"}

    usun_sesje_supabase(sciezka)
    assert wczytaj_sesje_supabase(sciezka) is None


def test_brak_ostatniego_emaila_zwraca_none(tmp_path):
    assert wczytaj_ostatni_email(tmp_path / "brak.json") is None


def test_zapisz_i_wczytaj_ostatni_email(tmp_path):
    sciezka = tmp_path / "ostatni_login.json"
    zapisz_ostatni_email("a@b.pl", sciezka)
    assert wczytaj_ostatni_email(sciezka) == "a@b.pl"
