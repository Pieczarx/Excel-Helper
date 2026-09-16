"""Punkt wejścia dla PyInstallera - cienki wrapper na app.main.main().

PyInstaller potrzebuje skryptu top-level (nie modułu odpalanego przez `python -m`), ale importy
w całej aplikacji są bezwzględne względem pakietu `app` (np. `from app.config import ...`) - ten
plik musi więc leżeć w `backend/`, obok folderu `app/`, żeby ten pakiet był importowalny.
"""
from app.main import main

if __name__ == "__main__":
    main()
