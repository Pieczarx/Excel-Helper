# Excel Helper

Aplikacja desktopowa (Windows, PySide6) do uzupełniania i weryfikacji arkuszy Excel na
podstawie faktur dystrybucyjnych PDF — dopasowanie po numerze PPE.

## Co robi

- **Uzupełnianie z faktur** — wrzucasz PDF-y faktur (dystrybucja energii, w tym fotowoltaika
  "energia oddana"), aplikacja czyta z nich zużycie/koszty i wpisuje je do właściwych wierszy
  i miesięcy w arkuszu Excel, dopasowując obiekt po numerze PPE (nigdy po nazwie ani pozycji
  wiersza).
- **Weryfikacja danych** — wykrywa odchylenia (nagłe skoki zużycia/kosztów) i przerwy w
  ciągłości odczytów, z dwupoziomową wagą alertów; odrzucone alerty są zapamiętywane po
  odcisku wartości, więc wracają, jeśli dane się zmienią.
- **Wiele firm** — jedna aplikacja, wspólne logowanie/historia/alerty, osobne pliki Excel i
  foldery faktur per firma (przełącznik nad zakładkami Uzupełnienie/Weryfikacja).
- **Synchronizacja przez Supabase** — logowanie, historia wpisanych faktur i odrzucone alerty
  synchronizują się między stanowiskami.
- **Tray + autostart** — ikona w zasobniku systemowym z odznaką liczby alertów, opcjonalny
  autostart przez Harmonogram zadań Windows.

## Struktura

```
backend/
  app/            kod aplikacji (Kontroler, GlowneOkno, czytniki/zapisywacze Excela i PDF-ów)
  tests/          testy pytest
  scripts/        skrypty pomocnicze (instalacja autostartu, generowanie ikony)
  supabase/       schemat bazy (SQL)
data/             lokalny stan uruchomieniowy (config, historia, poświadczenia) - gitignored
examples/         przykładowe pliki Excel - gitignored (dane klienta)
```

## Uruchomienie

```bash
cd backend
pip install -r requirements-dev.txt
python -m app.main
```

## Testy

```bash
cd backend
python -m pytest -q
```

## Stos technologiczny

Python, PySide6 (UI), openpyxl (odczyt/zapis Excela), pymupdf (parsowanie PDF faktur),
Supabase (synchronizacja), watchdog (obserwacja folderu faktur), pystray (ikona w zasobniku).

## Licencja

Proprietary — wszystkie prawa zastrzeżone, patrz [LICENSE](LICENSE).
