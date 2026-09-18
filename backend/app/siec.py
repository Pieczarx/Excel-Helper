"""Wspólny, jawny kontekst SSL (certifi) dla wszystkich zapytań HTTPS appki do GitHuba.

Domyślne ładowanie zaufanych certyfikatów przez Pythona na Windows (przez magazyn certyfikatów
systemu) potrafi zawieść w spakowanej appce (.exe) z "CERTIFICATE_VERIFY_FAILED: unable to get
local issuer certificate" - mimo że ta sama przeglądarka na tym samym komputerze łączy się bez
problemu (potwierdzone realnie przez usera, patrz historia zmian - zgłoszony błąd sprawdzania
aktualizacji). certifi niesie własny, znany-dobry zestaw certyfikatów CA jako zwykły plik danych
w paczce, więc appka już nie zależy od tego, co (i czy w ogóle) znajdzie w systemowym magazynie
po rozpakowaniu.

Używane przez aktualizacje.py (sprawdzanie wersji) i aktualizator.py (pobieranie samej
aktualizacji) - oba muszą pamiętać, żeby przekazać ten kontekst do urlopen (nie urlretrieve, które
go nie przyjmuje)."""
from __future__ import annotations

import ssl

import certifi

KONTEKST_SSL = ssl.create_default_context(cafile=certifi.where())
