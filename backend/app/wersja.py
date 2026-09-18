"""Numer wersji aplikacji i changelog pokazywany po kliknięciu w stopkę okna."""
from __future__ import annotations

WERSJA = "1.0.12"

CHANGELOG: list[dict] = [
    {
        "wersja": "1.0.12",
        "data": "2026-09-18",
        "zmiany": [
            "Naprawiono błąd, przez który automatyczny restart po aktualizacji czasem kończył się "
            "oknem błędu (\"No module named pyexpat\") zamiast działającą aplikacją - mechanizm "
            "ponawiania prób nie wykrywał poprawnie takiego nieudanego uruchomienia",
        ],
    },
    {
        "wersja": "1.0.11",
        "data": "2026-09-18",
        "zmiany": [
            "Wydanie testowe - bez zmian funkcjonalnych (weryfikacja mechanizmu aktualizacji "
            "po naprawie brakującego modułu Excel)",
        ],
    },
    {
        "wersja": "1.0.10",
        "data": "2026-09-18",
        "zmiany": [
            "Naprawiono błąd uniemożliwiający otwarcie aplikacji po aktualizacji - brakujący "
            "moduł do obsługi plików Excel w spakowanej wersji",
            "Aplikacja teraz sprawdza, czy pobrana aktualizacja jest kompletna, zanim się na nią "
            "podmieni - zabezpieczenie na wypadek przerwanego pobierania",
        ],
    },
    {
        "wersja": "1.0.9",
        "data": "2026-09-18",
        "zmiany": [
            "Wydanie testowe - bez zmian funkcjonalnych (weryfikacja mechanizmu aktualizacji "
            "po naprawie CERTIFICATE_VERIFY_FAILED)",
        ],
    },
    {
        "wersja": "1.0.8",
        "data": "2026-09-18",
        "zmiany": [
            "Naprawiono błąd uniemożliwiający sprawdzanie i pobieranie aktualizacji na niektórych "
            "komputerach (\"CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate\") - "
            "spakowana aplikacja nie miała dostępu do tego samego zestawu zaufanych certyfikatów, "
            "co zwykła przeglądarka",
        ],
    },
    {
        "wersja": "1.0.7",
        "data": "2026-09-18",
        "zmiany": [
            "Komunikat o nieudanym sprawdzeniu aktualizacji pokazuje teraz dokładny powód "
            "(np. przekroczony limit zapytań GitHub), zamiast tylko ogólnego \"spróbuj ponownie\"",
        ],
    },
    {
        "wersja": "1.0.6",
        "data": "2026-09-18",
        "zmiany": [
            "Naprawiono mylący komunikat przy sprawdzaniu aktualizacji - gdy nie udawało się "
            "połączyć z GitHubem, aplikacja błędnie pokazywała \"masz już najnowszą wersję\" "
            "zamiast poinformować, że sprawdzenie się nie powiodło",
            "Komunikat \"brak aktualizacji\" pokazuje teraz też, jaką wersję aplikacja faktycznie "
            "wykryła jako najnowszą na GitHubie",
        ],
    },
    {
        "wersja": "1.0.5",
        "data": "2026-09-18",
        "zmiany": [
            "W menu konta (po zalogowaniu) dodano przycisk \"Sprawdź aktualizacje\" - obok "
            "\"Wyloguj\" - który od razu mówi, czy jest dostępna nowa wersja",
        ],
    },
    {
        "wersja": "1.0.4",
        "data": "2026-09-18",
        "zmiany": [
            "Naprawiono błąd, przez który ręczne uruchomienie aplikacji czasem w ogóle nie "
            "pokazywało okna (trzeba było otwierać ją dwa razy)",
            "Dodano ekran startowy z paskiem postępu, pokazywany podczas uruchamiania aplikacji",
        ],
    },
    {
        "wersja": "1.0.3",
        "data": "2026-09-18",
        "zmiany": [
            "Naprawiono rzadki przypadek, w którym dwie próby uruchomienia aplikacji tuż po sobie "
            "(np. szybki podwójny klik) mogły uruchomić więcej niż jedną jej kopię naraz",
        ],
    },
    {
        "wersja": "1.0.2",
        "data": "2026-09-18",
        "zmiany": [
            "Folder \"Do aktualizacji\" zastąpiony checkboksem \"Aktualizuj uzupełnione dane\" pod "
            "polem do wrzucania faktur - wszystkie faktury trafiają teraz w jedno miejsce, a to, "
            "czy nadpisać już wpisane dane, wybiera się zaznaczeniem tej opcji przed kliknięciem "
            "\"Uzupełnij Excel\"",
            "Zakładka drugiej firmy (UK) oznaczona jako wkrótce dostępna",
            "Naprawiono godzinę wpisania faktury w historii - pokazywała się przesunięta względem "
            "czasu lokalnego",
            "Z nagłówka wpisanej faktury usunięto miesiąc - jest on i tak widoczny po rozwinięciu, "
            "przy każdym obiekcie osobno",
            "Naprawiono błąd uniemożliwiający ponowne otwarcie aplikacji po zamknięciu okna - "
            "kolejne próby uruchomienia mnożyły procesy w tle zamiast pokazać już działające okno",
            "Zaznaczony checkbox \"Aktualizuj uzupełnione dane\" pokazuje teraz zielony ptaszek "
            "zamiast wypełniać się na zielono",
        ],
    },
    {
        "wersja": "1.0.1",
        "data": "2026-09-18",
        "zmiany": [
            "Naprawiono logowanie na nowo zainstalowanej aplikacji - przycisk logowania czasem "
            "się nie pokazywał na innym komputerze niż ten, na którym aplikacja była pierwotnie "
            "skonfigurowana",
            "Aplikacja uruchamia się teraz automatycznie razem z systemem, bez potrzeby ręcznego "
            "włączania tej opcji",
        ],
    },
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
