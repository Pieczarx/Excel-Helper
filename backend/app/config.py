"""Zapamiętuje między uruchomieniami: wybrany plik Excela, dane połączenia z Supabase i sesję logowania."""
from __future__ import annotations

import json
from pathlib import Path

from app.sciezki import katalog_danych

_DATA_DIR = katalog_danych()
DEFAULT_CONFIG_PATH = _DATA_DIR / "config.json"
DEFAULT_FAKTURY_CONFIG_PATH = _DATA_DIR / "faktury_config.json"
DEFAULT_SUPABASE_CONFIG_PATH = _DATA_DIR / "supabase.json"
DEFAULT_SUPABASE_SESSION_PATH = _DATA_DIR / "supabase_session.json"
DEFAULT_OSTATNI_LOGIN_PATH = _DATA_DIR / "ostatni_login.json"

# Wbudowane w aplikację dane projektu Supabase - anon_key jest z założenia kluczem PUBLICZNYM,
# bezpiecznym do wbudowania w klienta (ochronę danych daje Row Level Security po stronie
# Supabase, nie tajność klucza - dokładnie tak samo jak w apkach mobilnych/webowych). Bez tego
# świeża instalacja appki (bez ręcznie stworzonego data/supabase.json) w ogóle nie pokazuje
# przycisku logowania - patrz Kontroler.stan_synchronizacji().
DOMYSLNY_SUPABASE_URL = "https://rcutqvqdzrumrbhslwap.supabase.co"
DOMYSLNY_SUPABASE_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJjdXRxdnFkenJ1bXJiaHNsd2FwIiwicm9s"
    "ZSI6ImFub24iLCJpYXQiOjE3ODc1MDI1ODIsImV4cCI6MjEwMzA3ODU4Mn0.zB6JjZeoAPUvC1nCkzXsHcbULy-dthRcAOE9w2HMAB8"
)


def _wczytaj_json(sciezka: str | Path) -> dict | None:
    sciezka = Path(sciezka)
    if not sciezka.exists():
        return None
    try:
        return json.loads(sciezka.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _zapisz_json(sciezka: str | Path, dane: dict) -> None:
    sciezka = Path(sciezka)
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    sciezka.write_text(json.dumps(dane, ensure_ascii=False, indent=2), encoding="utf-8")


def wczytaj_sciezke_pliku(config_path: str | Path = DEFAULT_CONFIG_PATH) -> Path | None:
    dane = _wczytaj_json(config_path)
    sciezka = (dane or {}).get("sciezka_pliku")
    return Path(sciezka) if sciezka else None


def zapisz_sciezke_pliku(sciezka: str | Path, config_path: str | Path = DEFAULT_CONFIG_PATH) -> None:
    _zapisz_json(config_path, {"sciezka_pliku": str(Path(sciezka).resolve())})


def wczytaj_sciezke_faktur(config_path: str | Path = DEFAULT_FAKTURY_CONFIG_PATH) -> Path | None:
    dane = _wczytaj_json(config_path)
    sciezka = (dane or {}).get("sciezka_faktur")
    return Path(sciezka) if sciezka else None


def zapisz_sciezke_faktur(sciezka: str | Path, config_path: str | Path = DEFAULT_FAKTURY_CONFIG_PATH) -> None:
    _zapisz_json(config_path, {"sciezka_faktur": str(Path(sciezka).resolve())})


def wczytaj_konfiguracje_supabase(
    config_path: str | Path = DEFAULT_SUPABASE_CONFIG_PATH,
) -> tuple[str, str]:
    """Zwraca (url, anon_key) - z lokalnego pliku, jeśli tam jest i jest kompletny, inaczej
    wbudowane w aplikację wartości domyślne (patrz DOMYSLNY_SUPABASE_URL wyżej). Dzięki temu
    synchronizacja/logowanie działa od razu na każdym komputerze, bez ręcznego tworzenia tego
    pliku - lokalny plik służy tylko do NADPISANIA wbudowanych danych (np. inny projekt Supabase
    do testów), nie do ich pierwszego skonfigurowania."""
    dane = _wczytaj_json(config_path)
    if dane and dane.get("url") and dane.get("anon_key"):
        return dane["url"], dane["anon_key"]
    return DOMYSLNY_SUPABASE_URL, DOMYSLNY_SUPABASE_ANON_KEY


def zapisz_konfiguracje_supabase(
    url: str, anon_key: str, config_path: str | Path = DEFAULT_SUPABASE_CONFIG_PATH
) -> None:
    _zapisz_json(config_path, {"url": url, "anon_key": anon_key})


def wczytaj_sesje_supabase(session_path: str | Path = DEFAULT_SUPABASE_SESSION_PATH) -> dict | None:
    dane = _wczytaj_json(session_path)
    if not dane or not dane.get("access_token") or not dane.get("refresh_token"):
        return None
    return dane


def zapisz_sesje_supabase(
    access_token: str, refresh_token: str, session_path: str | Path = DEFAULT_SUPABASE_SESSION_PATH
) -> None:
    _zapisz_json(session_path, {"access_token": access_token, "refresh_token": refresh_token})


def usun_sesje_supabase(session_path: str | Path = DEFAULT_SUPABASE_SESSION_PATH) -> None:
    Path(session_path).unlink(missing_ok=True)


def wczytaj_ostatni_email(sciezka: str | Path = DEFAULT_OSTATNI_LOGIN_PATH) -> str | None:
    """E-mail z ostatniego logowania - do wstępnego wypełnienia okna logowania, nie sekret."""
    dane = _wczytaj_json(sciezka)
    return (dane or {}).get("email") or None


def zapisz_ostatni_email(email: str, sciezka: str | Path = DEFAULT_OSTATNI_LOGIN_PATH) -> None:
    _zapisz_json(sciezka, {"email": email})
