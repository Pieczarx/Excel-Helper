"""Jednorazowy skrypt: usuwa excelHelper z Harmonogramu zadań Windows.

Uruchom z katalogu backend/:  python odinstaluj_autostart.py
"""
from app.autostart import NAZWA_ZADANIA, odinstaluj

if __name__ == "__main__":
    odinstaluj()
    print(f"Usunięto zadanie {NAZWA_ZADANIA!r} z Harmonogramu zadań.")
