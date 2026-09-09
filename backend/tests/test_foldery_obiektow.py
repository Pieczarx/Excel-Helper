from datetime import date
from pathlib import Path

from app.foldery_obiektow import (
    KAT_BRAK_FOLDERU_OBIEKTU,
    przenies_do_folderow_obiektow,
    zbuduj_mape_ppe_do_folderu,
)
from app.foldery_wspolne import NAZWA_DO_AKTUALIZACJI, NAZWA_DO_WPISANIA
from app.import_faktur import WynikWpisu

PPE_A = "590310600000411983"
PPE_B = "590310600000423740"


def _wynik(ppe: str, wiersz: int | None, miesiac: int = 3, dzien: int = 31) -> WynikWpisu:
    return WynikWpisu(
        kategoria="sukces",
        ppe=ppe,
        wiersz=wiersz,
        nazwa_obiektu="Testowy obiekt",
        miesiac=miesiac,
        okres_od=date(2026, miesiac, 1),
        okres_do=date(2026, miesiac, dzien),
    )


def test_zbuduj_mape_wyciaga_ppe_z_nazwy_folderu(tmp_path):
    (tmp_path / f"Brodowo ({PPE_A})").mkdir()
    (tmp_path / "DUŻE ODBIORY").mkdir()
    (tmp_path / "DUŻE ODBIORY" / f"Chwałkowo ({PPE_B})").mkdir()
    (tmp_path / "Folder bez PPE").mkdir()

    mapa = zbuduj_mape_ppe_do_folderu(tmp_path)

    assert mapa[PPE_A] == tmp_path / f"Brodowo ({PPE_A})"
    assert mapa[PPE_B] == tmp_path / "DUŻE ODBIORY" / f"Chwałkowo ({PPE_B})"
    assert len(mapa) == 2


def test_zbuduj_mape_pomija_foldery_robocze(tmp_path):
    (tmp_path / NAZWA_DO_WPISANIA / f"cos ({PPE_A})").mkdir(parents=True)
    (tmp_path / NAZWA_DO_AKTUALIZACJI / f"cos ({PPE_B})").mkdir(parents=True)

    mapa = zbuduj_mape_ppe_do_folderu(tmp_path)

    assert mapa == {}


def test_kopiuje_do_folderu_male_odbiory_z_nazwa_tylko_miesiac(tmp_path):
    folder_obiektu = tmp_path / f"Obiekt ({PPE_A})"
    folder_obiektu.mkdir()
    faktura = tmp_path / "faktura.pdf"
    faktura.write_bytes(b"tresc")

    wyniki = przenies_do_folderow_obiektow(
        faktura, tmp_path, {PPE_A: folder_obiektu}, [_wynik(PPE_A, wiersz=4, miesiac=3, dzien=31)]
    )

    assert (folder_obiektu / "D 03.pdf").exists()
    assert (folder_obiektu / "D 03.pdf").read_bytes() == b"tresc"
    assert wyniki == [_wynik(PPE_A, wiersz=4, miesiac=3, dzien=31)]  # bez dopisanych alertów


def test_kopiuje_do_folderu_duze_odbiory_z_nazwa_miesiac_i_dzien(tmp_path):
    folder_duze = tmp_path / "DUŻE ODBIORY"
    folder_obiektu = folder_duze / f"Brodowo ({PPE_A})"
    folder_obiektu.mkdir(parents=True)
    faktura = tmp_path / "faktura.pdf"
    faktura.write_bytes(b"tresc")

    przenies_do_folderow_obiektow(
        faktura,
        tmp_path,
        {PPE_A: folder_obiektu},
        [_wynik(PPE_A, wiersz=4, miesiac=3, dzien=31)],
        wlasne_okresy_duzych={PPE_A: date(2026, 3, 31)},
    )

    assert (folder_obiektu / "D 03.31.pdf").exists()


def test_duzy_odbior_rozpoznawany_po_ppe_nie_po_polozeniu_folderu(tmp_path):
    # Regresja: użytkownik zakłada folder nowego obiektu RĘCZNIE, niekoniecznie pod 'DUŻE
    # ODBIORY/' - "czy to duży odbiór" musi wynikać z tego, przez który arkusz PPE się zapisało
    # (wlasne_okresy_duzych), nie z tego, gdzie leży folder w drzewie.
    folder_obiektu = tmp_path / f"Zupełnie inna nazwa użytkownika ({PPE_A})"
    folder_obiektu.mkdir()
    faktura = tmp_path / "faktura.pdf"
    faktura.write_bytes(b"tresc")

    przenies_do_folderow_obiektow(
        faktura,
        tmp_path,
        {PPE_A: folder_obiektu},
        [_wynik(PPE_A, wiersz=4, miesiac=3, dzien=31)],
        wlasne_okresy_duzych={PPE_A: date(2026, 3, 31)},
    )

    assert (folder_obiektu / "D 03.31.pdf").exists()


def test_brak_folderu_dokladamy_alert_bez_kopiowania(tmp_path):
    faktura = tmp_path / "faktura.pdf"
    faktura.write_bytes(b"tresc")

    wyniki = przenies_do_folderow_obiektow(faktura, tmp_path, {}, [_wynik(PPE_A, wiersz=4)])

    assert len(wyniki) == 2
    alert = wyniki[1]
    assert alert.kategoria == KAT_BRAK_FOLDERU_OBIEKTU
    assert alert.ppe == PPE_A
    assert alert.wiersz == 4


def test_wpisy_bez_dopasowanego_wiersza_sa_ignorowane(tmp_path):
    faktura = tmp_path / "faktura.pdf"
    faktura.write_bytes(b"tresc")

    wyniki = przenies_do_folderow_obiektow(faktura, tmp_path, {}, [_wynik(PPE_A, wiersz=None)])

    assert wyniki == [_wynik(PPE_A, wiersz=None)]  # bez alertu - PPE w ogóle nie dopasowano


def test_kopiuje_do_kilku_folderow_naraz_faktura_zbiorcza(tmp_path):
    folder_a = tmp_path / f"Obiekt A ({PPE_A})"
    folder_b = tmp_path / f"Obiekt B ({PPE_B})"
    folder_a.mkdir()
    folder_b.mkdir()
    faktura = tmp_path / "faktura.pdf"
    faktura.write_bytes(b"tresc")

    przenies_do_folderow_obiektow(
        faktura,
        tmp_path,
        {PPE_A: folder_a, PPE_B: folder_b},
        [_wynik(PPE_A, wiersz=4, miesiac=3), _wynik(PPE_B, wiersz=7, miesiac=3)],
    )

    assert (folder_a / "D 03.pdf").exists()
    assert (folder_b / "D 03.pdf").exists()


def test_ten_sam_ppe_trafiony_w_dwoch_arkuszach_kopiuje_tylko_raz(tmp_path):
    # Regresja: od dodania arkusza 'fotowoltaika energia oddana' ten sam PPE może mieć DWA wpisy
    # z dopasowanym wierszem z jednego pliku (Duże odbiory + fotowoltaika) - musi się skopiować
    # tylko raz, nie dostać zbędny "D 03 (2).pdf" jak przy prawdziwej kolizji dwóch różnych plików.
    folder_obiektu = tmp_path / f"Obiekt ({PPE_A})"
    folder_obiektu.mkdir()
    faktura = tmp_path / "faktura.pdf"
    faktura.write_bytes(b"tresc")

    wyniki = przenies_do_folderow_obiektow(
        faktura,
        tmp_path,
        {PPE_A: folder_obiektu},
        [_wynik(PPE_A, wiersz=4, miesiac=3, dzien=31), _wynik(PPE_A, wiersz=4, miesiac=3, dzien=31)],
    )

    assert (folder_obiektu / "D 03.pdf").exists()
    assert not (folder_obiektu / "D 03 (2).pdf").exists()
    assert wyniki == [
        _wynik(PPE_A, wiersz=4, miesiac=3, dzien=31), _wynik(PPE_A, wiersz=4, miesiac=3, dzien=31)
    ]  # oba oryginalne wpisy zachowane, tylko kopiowanie zdedupowane


def test_ten_sam_ppe_bez_folderu_dostaje_tylko_jeden_alert(tmp_path):
    faktura = tmp_path / "faktura.pdf"
    faktura.write_bytes(b"tresc")

    wyniki = przenies_do_folderow_obiektow(
        faktura, tmp_path, {}, [_wynik(PPE_A, wiersz=4), _wynik(PPE_A, wiersz=4)]
    )

    alerty = [w for w in wyniki if w.kategoria == KAT_BRAK_FOLDERU_OBIEKTU]
    assert len(alerty) == 1


def test_kolizja_nazwy_dostaje_licznik(tmp_path):
    folder_obiektu = tmp_path / f"Obiekt ({PPE_A})"
    folder_obiektu.mkdir()
    (folder_obiektu / "D 03.pdf").write_bytes(b"stara faktura")
    faktura = tmp_path / "faktura.pdf"
    faktura.write_bytes(b"nowa tresc")

    przenies_do_folderow_obiektow(faktura, tmp_path, {PPE_A: folder_obiektu}, [_wynik(PPE_A, wiersz=4, miesiac=3)])

    assert (folder_obiektu / "D 03.pdf").read_bytes() == b"stara faktura"
    assert (folder_obiektu / "D 03 (2).pdf").read_bytes() == b"nowa tresc"
