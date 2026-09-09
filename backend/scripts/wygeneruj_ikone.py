"""Jednorazowy/generuj-na-żądanie skrypt: renderuje app/ikona.py do statycznych plików w assets/
(icon.ico wielorozdzielczy do ikony okna, icon_256.png jako referencja/PNG).

Uruchom z katalogu backend/:  python scripts/wygeneruj_ikone.py
"""
from pathlib import Path

from app.ikona import rysuj_ikone_bazowa

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
ROZMIARY_ICO = [16, 24, 32, 48, 64, 128, 256]


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    obraz_256 = rysuj_ikone_bazowa(256)
    obraz_256.save(ASSETS_DIR / "icon_256.png")

    obraz_256.save(
        ASSETS_DIR / "icon.ico",
        sizes=[(r, r) for r in ROZMIARY_ICO],
    )
    print(f"Zapisano {ASSETS_DIR / 'icon.ico'} i {ASSETS_DIR / 'icon_256.png'}")


if __name__ == "__main__":
    main()
