"""Numer wersji aplikacji i changelog pokazywany po kliknięciu w stopkę okna."""
from __future__ import annotations

WERSJA = "1.0.2"

CHANGELOG: list[dict] = [
    {
        "wersja": "1.0.2",
        "data": "2026-09-09",
        "zmiany": [
            "Nowy, odświeżony wygląd całej aplikacji",
            "Uzupełnianie faktur obsługuje teraz też arkusz fotowoltaika (energia oddana) - obiekty "
            "z instalacją PV dostają dodatkowo swoją plakietkę przy wpisanych danych",
            "Przygotowanie pod drugą firmę: nad zakładkami „Uzupełnienie faktur”/„Weryfikacja” pojawił "
            "się przełącznik MPECWIK/UK - druga firma czeka na dostarczenie pliku i faktur",
        ],
    },
    {
        "wersja": "1.0.1",
        "data": "2026-08-25",
        "zmiany": [
            "Nowa główna funkcja: wpisywanie faktur do Excela. Przeciągnij plik PDF faktury do okna "
            "(albo wybierz go ręcznie) i kliknij „Uzupełnij Excel” - dane trafią do arkusza automatycznie",
            "Aplikacja pokazuje historię wszystkich wpisanych faktur oraz ostrzega, gdy jakiejś "
            "pozycji nie da się jednoznacznie dopasować albo odczytać",
            "Dotychczasowa weryfikacja arkusza (ostrzeżenia o podejrzanych zmianach zużycia) działa "
            "teraz jako druga zakładka, obok nowej głównej",
        ],
    },
    {
        "wersja": "1.0.0",
        "data": "2026-08-23",
        "zmiany": [],
    },
]
