"""Jednorazowy skrypt: rejestruje excelHelper w Harmonogramie zadań Windows (start przy logowaniu).

Uruchom z katalogu backend/:  python zainstaluj_autostart.py
Cofnięcie:                    python odinstaluj_autostart.py
"""
from app.autostart import NAZWA_ZADANIA, VBS_PATH, zainstaluj

if __name__ == "__main__":
    zainstaluj()
    print(f"Zarejestrowano zadanie {NAZWA_ZADANIA!r} w Harmonogramie zadań (uruchomienie przy logowaniu).")
    print(f"Skrypt startowy: {VBS_PATH}")
