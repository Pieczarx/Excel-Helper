"""Firmy obsługiwane przez appkę - każda ma własny plik Excel i własny folder faktur (i inne
obiekty w nich), ale WSZYSTKO inne jest wspólne: logowanie/synchronizacja, magazyn oznaczonych
alertów, historia wpisanych faktur - to jedna spójna aplikacja z dwiema zakładkami firm, nie
osobne, odizolowane profile (świadoma decyzja użytkownika, patrz window.py).

MPECWIK zostaje na dotychczasowych, domyślnych ścieżkach configów (DEFAULT_CONFIG_PATH /
DEFAULT_FAKTURY_CONFIG_PATH) - już zapamiętany plik/folder użytkownika ma dalej działać bez
żadnej migracji. UK dostaje własne, nowe pliki configów obok - czeka na plik Excela i faktury,
które użytkownik dostarczy później; do tego czasu po prostu pokazuje "nie wybrano", tak jak
MPECWIK pokazywał na samym początku."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.config import DEFAULT_CONFIG_PATH, DEFAULT_FAKTURY_CONFIG_PATH
from app.styl import KORAL, ZIELEN

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@dataclass(frozen=True)
class Firma:
    id: str
    nazwa: str
    config_path: Path
    faktury_config_path: Path
    akcent: str  # kolor znacznika/podkreślenia w przełączniku firm (window.py) - własna tożsamość firmy


FIRMY: list[Firma] = [
    Firma(
        id="mpecwik",
        nazwa="MPECWIK",
        config_path=DEFAULT_CONFIG_PATH,
        faktury_config_path=DEFAULT_FAKTURY_CONFIG_PATH,
        akcent=ZIELEN,
    ),
    Firma(
        id="uk",
        nazwa="UK",
        config_path=_DATA_DIR / "config_uk.json",
        faktury_config_path=_DATA_DIR / "faktury_config_uk.json",
        akcent=KORAL,
    ),
]
