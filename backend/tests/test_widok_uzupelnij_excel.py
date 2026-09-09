from datetime import date
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

from app.excel_reader_oddana import SHEET_NAME_ODDANA
from app.faktura_reader import KAT_PPE_NIEZNALEZIONE, KAT_SUKCES
from app.foldery_faktur import WynikPrzetworzeniaPliku
from app.historia_faktur import HistoriaFakturStore
from app.import_faktur import WynikWpisu
from app.kontroler import Kontroler
from app.kontroler_faktur import KontrolerFaktur
from app.store import AlertStore
from app.widok_uzupelnij_excel import WidokUzupelnijExcel

EXAMPLE_FILE = Path(__file__).resolve().parents[2] / "examples" / "MPECWIK 2026.xlsx"


def _app():
    app = QApplication.instance()
    return app or QApplication([])


def _kontroler(tmp_path) -> KontrolerFaktur:
    historia = HistoriaFakturStore(tmp_path / "historia.db")
    return KontrolerFaktur(historia, config_path=tmp_path / "faktury_config.json")


def _kontroler_excela(tmp_path, z_plikiem: bool = False) -> Kontroler:
    store = AlertStore(tmp_path / "alerts.db")
    kontroler = Kontroler(store, config_path=tmp_path / "config.json", supabase_config_path=tmp_path / "supabase.json")
    if z_plikiem:
        kontroler.ustaw_plik(EXAMPLE_FILE)
    return kontroler


def _sukces(nazwa="Obiekt X") -> WynikWpisu:
    return WynikWpisu(
        kategoria=KAT_SUKCES,
        ppe="590310600000423740",
        wiersz=3,
        nazwa_obiektu=nazwa,
        miesiac=1,
        okres_od=date(2026, 1, 1),
        okres_do=date(2026, 1, 20),
    )


def _problem() -> WynikWpisu:
    return WynikWpisu(
        kategoria=KAT_PPE_NIEZNALEZIONE,
        ppe="590310600000000000",
        wiersz=None,
        nazwa_obiektu=None,
        miesiac=1,
        okres_od=date(2026, 1, 1),
        okres_do=date(2026, 1, 20),
        opis="brak obiektu z tym numerem PPE w arkuszu",
    )


def _wszystkie_teksty(widget) -> str:
    return " ".join(label.text() for label in widget.findChildren(QLabel))


def test_bez_folderu_pokazuje_informacje_o_braku(tmp_path):
    _app()
    widok = WidokUzupelnijExcel(_kontroler(tmp_path), _kontroler_excela(tmp_path))
    assert "nie wybrano" in widok._etykieta_folderu.text()


def test_bez_pliku_excel_pokazuje_informacje_o_braku(tmp_path):
    _app()
    widok = WidokUzupelnijExcel(_kontroler(tmp_path), _kontroler_excela(tmp_path))
    assert "nie wybrano" in widok._etykieta_excela.text()


def test_po_ustawieniu_pliku_excel_etykieta_sie_odswieza(tmp_path):
    _app()
    kontroler_excela = _kontroler_excela(tmp_path)
    widok = WidokUzupelnijExcel(_kontroler(tmp_path), kontroler_excela)

    kontroler_excela.ustaw_plik(EXAMPLE_FILE)

    assert "MPECWIK 2026.xlsx" in widok._etykieta_excela.text()


def test_po_ustawieniu_folderu_etykieta_pokazuje_sciezke(tmp_path):
    _app()
    kontroler = _kontroler(tmp_path)
    widok = WidokUzupelnijExcel(kontroler, _kontroler_excela(tmp_path))

    kontroler.ustaw_folder(tmp_path / "Faktury")
    widok._odswiez_pasek_folderu()

    assert str((tmp_path / "Faktury").resolve()) in widok._etykieta_folderu.text()


def test_dodanie_pliku_pokazuje_wiersz_kolejki_i_wlacza_przycisk(tmp_path):
    _app()
    kontroler = _kontroler(tmp_path)
    kontroler.ustaw_folder(tmp_path / "Faktury")
    widok = WidokUzupelnijExcel(kontroler, _kontroler_excela(tmp_path, z_plikiem=True))

    plik = tmp_path / "D 01.pdf"
    plik.write_bytes(b"%PDF-1.4")
    kontroler.dodaj_pliki_do_kolejki([plik])

    assert widok._uklad_kolejki.count() == 1
    assert widok._przycisk_uzupelnij.isEnabled()
    assert "1 faktura czeka" in widok._podpowiedz_akcji.text()


def test_przycisk_wylaczony_dopoki_nie_wybrano_pliku_excel(tmp_path):
    _app()
    kontroler = _kontroler(tmp_path)
    kontroler.ustaw_folder(tmp_path / "Faktury")
    kontroler_excela = _kontroler_excela(tmp_path)  # bez pliku
    widok = WidokUzupelnijExcel(kontroler, kontroler_excela)

    plik = tmp_path / "D 01.pdf"
    plik.write_bytes(b"%PDF-1.4")
    kontroler.dodaj_pliki_do_kolejki([plik])
    assert not widok._przycisk_uzupelnij.isEnabled()  # kolejka niepusta, ale brak pliku Excel

    kontroler_excela.ustaw_plik(EXAMPLE_FILE)
    assert widok._przycisk_uzupelnij.isEnabled()


def test_usuniecie_ostatniego_pliku_z_kolejki_wylacza_przycisk(tmp_path):
    _app()
    kontroler = _kontroler(tmp_path)
    kontroler.ustaw_folder(tmp_path / "Faktury")
    widok = WidokUzupelnijExcel(kontroler, _kontroler_excela(tmp_path, z_plikiem=True))

    plik = tmp_path / "D 01.pdf"
    plik.write_bytes(b"%PDF-1.4")
    kontroler.dodaj_pliki_do_kolejki([plik])
    kontroler.usun_z_kolejki(kontroler.kolejka()[0])

    assert widok._uklad_kolejki.count() == 0
    assert not widok._przycisk_uzupelnij.isEnabled()


def test_pokazanie_widoku_odswieza_kolejke(tmp_path):
    """Plik recznie wrzucony do folderu (np. przez Eksplorator, z pominieciem drag&drop appki)
    ma zostac zauwazony, kiedy uzytkownik wraca na te zakladke."""
    _app()
    kontroler = _kontroler(tmp_path)
    kontroler.ustaw_folder(tmp_path / "Faktury")
    widok = WidokUzupelnijExcel(kontroler, _kontroler_excela(tmp_path, z_plikiem=True))
    assert widok._uklad_kolejki.count() == 0

    # plik podrzucony "z zewnatrz appki", bez przejscia przez dodaj_pliki_do_kolejki
    (tmp_path / "Faktury" / "Do aktualizacji").mkdir(parents=True, exist_ok=True)
    (tmp_path / "Faktury" / "Do aktualizacji" / "D 03.pdf").write_bytes(b"%PDF-1.4")

    widok.show()

    assert widok._uklad_kolejki.count() == 1
    assert widok._przycisk_uzupelnij.isEnabled()


def test_klik_sprawdz_odswieza_kolejke_bez_sygnalu(tmp_path):
    """Plik dodany "z zewnatrz" (pomijajac dodaj_pliki_do_kolejki, wiec bez emitowania sygnalu) -
    klikniecie 'Sprawdz' musi go i tak zauwazyc, skanujac foldery na nowo."""
    _app()
    kontroler = _kontroler(tmp_path)
    kontroler.ustaw_folder(tmp_path / "Faktury")
    widok = WidokUzupelnijExcel(kontroler, _kontroler_excela(tmp_path, z_plikiem=True))
    assert widok._uklad_kolejki.count() == 0

    (tmp_path / "Faktury" / "Do wpisania" / "D 04.pdf").write_bytes(b"%PDF-1.4")

    widok._na_klik_sprawdz()

    assert widok._uklad_kolejki.count() == 1
    assert widok._przycisk_uzupelnij.isEnabled()


def test_klik_uzupelnij_z_otwartym_excelem_pokazuje_ostrzezenie_i_nic_nie_uruchamia(tmp_path, monkeypatch):
    _app()
    kontroler = _kontroler(tmp_path)
    kontroler.ustaw_folder(tmp_path / "Faktury")
    kontroler_excela = _kontroler_excela(tmp_path, z_plikiem=True)
    widok = WidokUzupelnijExcel(kontroler, kontroler_excela)
    plik = tmp_path / "D 01.pdf"
    plik.write_bytes(b"%PDF-1.4")
    kontroler.dodaj_pliki_do_kolejki([plik])

    wywolania = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: wywolania.append(a))
    monkeypatch.setattr(kontroler_excela, "czy_plik_otwarty", lambda: True)
    wywolano_przetworz = []
    monkeypatch.setattr(kontroler, "przetworz_w_tle", lambda *a: wywolano_przetworz.append(a))

    widok._na_klik_uzupelnij()

    assert wywolania
    assert not wywolano_przetworz


def test_klik_uzupelnij_bez_excela_pokazuje_ostrzezenie_i_nic_nie_uruchamia(tmp_path, monkeypatch):
    _app()
    kontroler = _kontroler(tmp_path)
    kontroler.ustaw_folder(tmp_path / "Faktury")
    widok = WidokUzupelnijExcel(kontroler, _kontroler_excela(tmp_path))
    plik = tmp_path / "D 01.pdf"
    plik.write_bytes(b"%PDF-1.4")
    kontroler.dodaj_pliki_do_kolejki([plik])

    wywolania = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: wywolania.append(a))
    wywolano_przetworz = []
    monkeypatch.setattr(kontroler, "przetworz_w_tle", lambda *a: wywolano_przetworz.append(a))

    widok._na_klik_uzupelnij()

    assert wywolania
    assert not wywolano_przetworz


def test_zakonczone_przetwarzanie_pokazuje_sekcje_uzupelnione_dane(tmp_path):
    _app()
    widok = WidokUzupelnijExcel(_kontroler(tmp_path), _kontroler_excela(tmp_path))
    widok.show()  # isVisible() na dziecku odzwierciedla widocznosc dopiero gdy widok tez jest pokazany

    wyniki = [
        WynikPrzetworzeniaPliku(sciezka=tmp_path / "D 01.pdf", wyniki=[_sukces(), _problem()]),
        WynikPrzetworzeniaPliku(sciezka=tmp_path / "D 09.pdf", blad="Nie rozpoznano jako faktura dystrybucyjna"),
    ]

    widok._na_zakonczone_przetwarzanie(wyniki)

    assert widok._kontener_swiezo.isVisible()
    assert widok._uklad_swiezo.count() == 2
    teksty = _wszystkie_teksty(widok._kontener_swiezo)
    assert "Obiekt X" in teksty
    assert "PPE nieznalezione w arkuszu" in teksty
    assert "Nie rozpoznano jako faktura dystrybucyjna" in teksty


def test_wpis_z_arkusza_fotowoltaika_dostaje_plakietke(tmp_path):
    # Ten sam obiekt/PPE/okres może dostać osobny wpis z Dużych odbiorów I z fotowoltaiki z jednej
    # faktury (patrz import_faktur_oddana.py) - bez plakietki wyglądałyby jak duplikat.
    _app()
    widok = WidokUzupelnijExcel(_kontroler(tmp_path), _kontroler_excela(tmp_path))
    widok.show()

    wpis_duze = _sukces("Kórnicka 80")
    wpis_duze.arkusz = "Duże odbiory"
    wpis_foto = _sukces("Kórnicka 80")
    wpis_foto.arkusz = SHEET_NAME_ODDANA

    widok._na_zakonczone_przetwarzanie(
        [WynikPrzetworzeniaPliku(sciezka=tmp_path / "D 01.pdf", wyniki=[wpis_duze, wpis_foto])]
    )

    teksty = [label.text() for label in widok._kontener_swiezo.findChildren(QLabel)]
    assert teksty.count("fotowoltaika") == 1


def test_brak_wynikow_ukrywa_sekcje_uzupelnione_dane(tmp_path):
    _app()
    widok = WidokUzupelnijExcel(_kontroler(tmp_path), _kontroler_excela(tmp_path))
    widok._na_zakonczone_przetwarzanie([WynikPrzetworzeniaPliku(sciezka=tmp_path / "x.pdf", wyniki=[_sukces()])])

    widok._na_zakonczone_przetwarzanie([])

    assert not widok._kontener_swiezo.isVisible()


def test_historia_pusta_pokazuje_komunikat(tmp_path):
    _app()
    widok = WidokUzupelnijExcel(_kontroler(tmp_path), _kontroler_excela(tmp_path))
    assert "Brak historii" in _wszystkie_teksty(widok._kontener_historii)


def test_historia_z_wpisami_pokazuje_karty(tmp_path):
    _app()
    kontroler = _kontroler(tmp_path)
    widok = WidokUzupelnijExcel(kontroler, _kontroler_excela(tmp_path))

    kontroler._historia.zapisz("D 01.pdf", [_sukces()])
    widok._odswiez_historie(kontroler.historia_ostatnich())

    assert widok._uklad_historii.count() == 1
    assert "D 01.pdf" in _wszystkie_teksty(widok._kontener_historii)


def test_klik_usun_na_karcie_historii_usuwa_wpis(tmp_path):
    _app()
    kontroler = _kontroler(tmp_path)
    widok = WidokUzupelnijExcel(kontroler, _kontroler_excela(tmp_path))
    kontroler._historia.zapisz("D 09.pdf", [], powod_odrzucenia="Nie rozpoznano jako faktura dystrybucyjna")
    widok._odswiez_historie(kontroler.historia_ostatnich())

    karta = widok._kontener_historii.findChildren(QPushButton)
    przycisk_usun = next(p for p in karta if p.toolTip() == "Usuń z historii")
    przycisk_usun.click()

    assert kontroler.historia_ostatnich() == []
    assert widok._uklad_historii.count() == 1  # zastapione komunikatem "Brak historii"
