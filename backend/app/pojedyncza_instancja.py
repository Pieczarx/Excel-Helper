"""Zapewnia, że naraz działa tylko JEDNA instancja appki - patrz main.py.

Zamknięcie okna (X) celowo NIE kończy procesu - appka ma dalej działać w zasobniku (patrz
app.setQuitOnLastWindowClosed(False) w main.py). Bez blokady z tego modułu każda kolejna próba
uruchomienia (np. podwójny klik w .exe, żeby "znowu otworzyć" appkę) odpalała NOWY, niezależny
proces zamiast pokazać już działające okno - procesy mnożyły się w Menedżerze zadań i żaden z
nich nie kończył się sam (zgłoszone: appka po zamknięciu okna "nie dawała się odpalić ponownie").

Mechanizm: QLocalServer/QLocalSocket pod ustaloną nazwą. Pierwsza instancja zakłada serwer i
nasłuchuje; każda kolejna próba uruchomienia łączy się jako klient - jeśli się uda, wysyła krótki
sygnał do pierwszej instancji (która wtedy pokazuje/aktywuje swoje okno) i od razu kończy WŁASNY,
nowy proces, zamiast budować resztę appki od zera."""
from __future__ import annotations

from typing import Callable

from PySide6.QtNetwork import QLocalServer, QLocalSocket

NAZWA_SERWERA = "ExcelHelperPojedynczaInstancja"
SYGNAL_POKAZ = b"POKAZ"
TIMEOUT_MS = 300


def czy_juz_dziala_i_aktywowano(nazwa: str = NAZWA_SERWERA) -> bool:
    """Próbuje połączyć się z już działającą instancją - jeśli się uda, wysyła sygnał "pokaż
    okno" i zwraca True. Wywołujący ma wtedy natychmiast zakończyć TEN proces, bez budowania
    reszty appki (Kontroler/GlówneOkno/tray) - to i tak byłaby druga, zbędna kopia.

    `nazwa` parametryzowana (nie na sztywno NAZWA_SERWERA) - żeby testy mogły użyć unikalnej nazwy
    zamiast prawdziwej appki, gdyby akurat działała na tej samej maszynie."""
    gniazdo = QLocalSocket()
    gniazdo.connectToServer(nazwa)
    if not gniazdo.waitForConnected(TIMEOUT_MS):
        return False
    gniazdo.write(SYGNAL_POKAZ)
    gniazdo.waitForBytesWritten(TIMEOUT_MS)
    gniazdo.disconnectFromServer()
    return True


def uruchom_serwer(na_sygnal_pokaz: Callable[[], None], nazwa: str = NAZWA_SERWERA) -> QLocalServer:
    """Zakłada serwer nasłuchujący na kolejne próby uruchomienia - wywołuje `na_sygnal_pokaz` za
    każdym razem, gdy taka próba nadejdzie (typowo: pokazanie/aktywowanie głównego okna).
    Zwrócony obiekt trzeba trzymać żywym (referencja) przez cały czas działania appki - inaczej
    Python od razu by go posprzątał i serwer przestałby nasłuchiwać."""
    QLocalServer.removeServer(nazwa)  # posprząta po ewentualnym wcześniej ubitym procesie

    serwer = QLocalServer()
    serwer.listen(nazwa)

    def _na_nowe_polaczenie() -> None:
        polaczenie = serwer.nextPendingConnection()
        if polaczenie is None:
            return
        polaczenie.waitForReadyRead(TIMEOUT_MS)
        polaczenie.readAll()
        polaczenie.disconnectFromServer()
        na_sygnal_pokaz()

    serwer.newConnection.connect(_na_nowe_polaczenie)
    return serwer
