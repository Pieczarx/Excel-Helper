"""Bazowy rysunek ikony aplikacji: zielony dokument ze złożonym rogiem, dwiema liniami tekstu
i napisem 'FV' (wariant "A" wybrany przez użytkownika z sześciu zaproponowanych). Wspólne dla:
- ikony okna/tray na sztywno (assets/icon.ico, generowany z tego modułu przez
  scripts/wygeneruj_ikone.py),
- ikony tray na żywo (tray_icon.py), gdzie na tę bazę nakładany jest jeszcze czerwony badge
  z liczbą obiektów z problemem.

Współdzielenie jednego rysunku (zamiast dwóch osobnych) gwarantuje, że okno i tray zawsze
pokazują dokładnie ten sam znak firmowy. Tło jest celowo przezroczyste (bez podkładki) - tak
wyglądał zatwierdzony wariant A, kontur dokumentu sam w sobie jest sylwetką ikony."""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

KOLOR_DOKUMENTU = (31, 109, 67, 255)  # #1f6d43 - ten sam zielony co reszta UI (KOLOR_ZIELEN)
KOLOR_ZAGIECIA = (15, 63, 39, 255)  # #0f3f27 - ciemniejszy odcień na złożonym rogu
KOLOR_TEKSTU = (255, 255, 255, 255)

_czcionka_cache: dict[int, ImageFont.ImageFont] = {}


def czcionka(rozmiar: int) -> ImageFont.ImageFont:
    if rozmiar not in _czcionka_cache:
        for nazwa in ("arialbd.ttf", "arial.ttf"):
            try:
                _czcionka_cache[rozmiar] = ImageFont.truetype(nazwa, rozmiar)
                break
            except OSError:
                continue
        else:
            _czcionka_cache[rozmiar] = ImageFont.load_default()
    return _czcionka_cache[rozmiar]


def rysuj_ikone_bazowa(rozmiar: int) -> Image.Image:
    """Zielony dokument ze złożonym górnym prawym rogiem, dwiema białymi liniami (tekst faktury)
    i napisem 'FV' - na przezroczystym tle.

    Współrzędne dokumentu są ułamkami `rozmiar` (kalibrowane na siatce 64x64), więc rysunek
    skaluje się bez utraty proporcji do dowolnego rozmiaru (tray = 64px, .ico = do 256px)."""
    obraz = Image.new("RGBA", (rozmiar, rozmiar), (0, 0, 0, 0))
    rysunek = ImageDraw.Draw(obraz)

    def p(x: float, y: float) -> tuple[float, float]:
        return (x * rozmiar, y * rozmiar)

    # Kartka (bez górnego prawego rogu - ten dochodzi jako osobny, ciemniejszy trójkąt zagięcia).
    rysunek.polygon(
        [p(0.25, 0.125), p(0.59375, 0.125), p(0.75, 0.28125), p(0.75, 0.875), p(0.25, 0.875)],
        fill=KOLOR_DOKUMENTU,
    )
    rysunek.polygon(
        [p(0.59375, 0.125), p(0.75, 0.28125), p(0.59375, 0.28125)],
        fill=KOLOR_ZAGIECIA,
    )

    grubosc_linii = max(1, round(rozmiar * 2.5 / 64))
    for y in (0.40625, 0.5):
        rysunek.line([p(0.328125, y), p(0.671875, y)], fill=KOLOR_TEKSTU, width=grubosc_linii)

    rysunek.text(
        p(0.5, 0.765625), "FV", fill=KOLOR_TEKSTU, anchor="mm", font=czcionka(round(rozmiar * 15 / 64))
    )
    return obraz
