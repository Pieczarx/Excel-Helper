"""Numer wersji aplikacji i changelog pokazywany po kliknięciu w stopkę okna."""
from __future__ import annotations

WERSJA = "1.0.0"

CHANGELOG: list[dict] = [
    {
        "wersja": "1.0.0",
        "data": "2026-09-16",
        "zmiany": [
            "Automatyczne wpisywanie faktur do Excela - wystarczy przeciągnąć plik PDF faktury do "
            "okna (albo wybrać go ręcznie), a dane trafią do właściwego obiektu i miesiąca w arkuszu",
            "Obsługa faktur za energię oddaną z instalacji fotowoltaicznych, obok standardowych "
            "faktur dystrybucyjnych",
            "Historia wszystkich wpisanych faktur wraz z jasną informacją, gdy jakiejś pozycji nie "
            "udało się jednoznacznie dopasować lub odczytać",
            "Weryfikacja arkusza - ostrzeżenia o podejrzanych zmianach zużycia i kosztów oraz o "
            "przerwach w ciągłości odczytów",
            "Logowanie i synchronizacja danych między stanowiskami",
            "Automatyczne powiadamianie o nowych wersjach aplikacji wraz z instalacją jednym kliknięciem",
        ],
    },
]
