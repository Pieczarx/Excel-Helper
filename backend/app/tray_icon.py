"""Rysowanie ikony tray z dynamicznym badge'em liczby obiektów z problemem.

Wydzielone od pystray/tray.py celowo - ta logika jest czystym PIL-em, więc da się przetestować
bez uruchamiania prawdziwego zasobnika systemowego. Bazowy rysunek (dokument 'FV') jest
współdzielony z ikoną okna - patrz app/ikona.py.
"""
from __future__ import annotations

from PIL import Image, ImageDraw

from app.ikona import KOLOR_TEKSTU, czcionka, rysuj_ikone_bazowa

ROZMIAR = 64
KOLOR_BADGE = (214, 40, 40, 255)


def _etykieta_badge(liczba: int) -> str:
    return str(liczba) if liczba < 100 else "99+"


def rysuj_ikone(liczba_obiektow_z_problemem: int) -> Image.Image:
    """Bazowa ikona 'FV' + czerwony okrągły badge z liczbą w prawym górnym rogu, jeśli liczba > 0."""
    obraz = rysuj_ikone_bazowa(ROZMIAR)
    rysunek = ImageDraw.Draw(obraz)

    if liczba_obiektow_z_problemem > 0:
        promien = ROZMIAR * 0.32
        cx, cy = ROZMIAR - promien * 0.85, promien * 0.85
        rysunek.ellipse((cx - promien, cy - promien, cx + promien, cy + promien), fill=KOLOR_BADGE)
        tekst = _etykieta_badge(liczba_obiektow_z_problemem)
        rozmiar_fontu = int(promien * (1.05 if len(tekst) == 1 else 0.75))
        rysunek.text((cx, cy), tekst, fill=KOLOR_TEKSTU, anchor="mm", font=czcionka(rozmiar_fontu))

    return obraz
