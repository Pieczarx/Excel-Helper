import shutil
from pathlib import Path

from app.faktura_reader import KAT_PPE_NIEZNALEZIONE
from app.foldery_faktur import (
    NAZWA_DO_AKTUALIZACJI,
    NAZWA_DO_WPISANIA,
    NAZWA_PRZETWORZONE,
    przetworz_folder,
    przetworz_foldery_faktur,
    upewnij_sie_ze_foldery_istnieja,
)
from app.import_faktur import WynikWpisu

TESTY_FILE = Path(__file__).resolve().parents[2] / "examples" / "MPECWIK 2026_testy.xlsx"
FAKTURY_ROOT = Path(__file__).resolve().parents[2] / "examples" / "Faktury MPECWIK 2026"
FAKTURA_20_PAZDZIERNIKA = next(p for p in FAKTURY_ROOT.rglob("D 01.pdf") if "Pa" in p.parent.name)
FAKTURA_JEDNOSTREFOWA = next(p for p in FAKTURY_ROOT.rglob("D 02.pdf") if p.parent.name.startswith("Azaliowa"))
FAKTURA_NIEWLASCIWEGO_TYPU = next(
    p for p in FAKTURY_ROOT.rglob("D 02.pdf") if p.parent.name.startswith("Mączniki Sklep 4A")
)

# 5 PPE, na które rozbija się FAKTURA_20_PAZDZIERNIKA (faktura zbiorcza) w MPECWIK 2026_testy.xlsx.
PPE_20_PAZDZIERNIKA = [
    "590310600000423740",  # 20 Października 40B
    "590310600000433237",  # Bieganowo
    "590310600000433633",  # Janowo jezioro
    "590310600000433640",  # Janowo szosa
    "590310600000433626",  # Janowo cmentarz
]


def _kopia_excel(tmp_path) -> Path:
    cel = tmp_path / "excel.xlsx"
    shutil.copy(TESTY_FILE, cel)
    return cel


def _drzewo_z_folderami_obiektow(tmp_path, ppe_lista: list[str]) -> Path:
    root = tmp_path / "Faktury"
    (root / NAZWA_DO_WPISANIA).mkdir(parents=True)
    (root / NAZWA_DO_AKTUALIZACJI).mkdir(parents=True)
    for ppe in ppe_lista:
        (root / f"Obiekt ({ppe})").mkdir()
    return root


def test_upewnij_sie_ze_foldery_istnieja_tworzy_obie_pary(tmp_path):
    root = tmp_path / "Faktury"
    upewnij_sie_ze_foldery_istnieja(root)

    assert (root / NAZWA_DO_WPISANIA / NAZWA_PRZETWORZONE).is_dir()
    assert (root / NAZWA_DO_AKTUALIZACJI / NAZWA_PRZETWORZONE).is_dir()


def test_upewnij_sie_ze_foldery_istnieja_jest_idempotentne(tmp_path):
    root = tmp_path / "Faktury"
    upewnij_sie_ze_foldery_istnieja(root)
    upewnij_sie_ze_foldery_istnieja(root)  # nie powinno rzucić błędu za drugim razem


def test_zapisana_faktura_trafia_do_folderow_obiektow_i_znika_z_kolejki(tmp_path):
    excel = _kopia_excel(tmp_path)
    root = _drzewo_z_folderami_obiektow(tmp_path, PPE_20_PAZDZIERNIKA)
    folder = root / NAZWA_DO_WPISANIA
    shutil.copy(FAKTURA_20_PAZDZIERNIKA, folder / "D 01.pdf")

    wyniki = przetworz_folder(excel, folder, nadpisuj=False, sciezka_faktur_root=root)

    assert len(wyniki) == 1
    wynik_pliku = wyniki[0]
    assert wynik_pliku.blad is None
    assert len(wynik_pliku.wyniki) == 5
    assert all(w.zapisano for w in wynik_pliku.wyniki)
    # oryginał zniknął z kolejki - nie ma go ani na miejscu, ani w Przetworzone
    assert not (folder / "D 01.pdf").exists()
    assert not (folder / NAZWA_PRZETWORZONE / "D 01.pdf").exists()
    # trafił do KAŻDEGO z 5 folderów obiektów, pod nazwą opartą o miesiąc końca okresu (styczeń)
    for ppe in PPE_20_PAZDZIERNIKA:
        assert (root / f"Obiekt ({ppe})" / "D 01.pdf").exists()


def test_ppe_bez_folderu_obiektu_dostaje_alert_ale_i_tak_znika_z_kolejki(tmp_path):
    excel = _kopia_excel(tmp_path)
    root = _drzewo_z_folderami_obiektow(tmp_path, [])  # żadnych folderów obiektów
    folder = root / NAZWA_DO_WPISANIA
    shutil.copy(FAKTURA_20_PAZDZIERNIKA, folder / "D 01.pdf")

    wyniki = przetworz_folder(excel, folder, nadpisuj=False, sciezka_faktur_root=root)

    assert len(wyniki) == 1
    from app.foldery_obiektow import KAT_BRAK_FOLDERU_OBIEKTU

    # 5 oryginalnych wpisów (sukces w Excelu) + 5 dopisanych alertów "brak folderu"
    assert len(wyniki[0].wyniki) == 10
    alerty = [w for w in wyniki[0].wyniki if w.kategoria == KAT_BRAK_FOLDERU_OBIEKTU]
    assert len(alerty) == 5
    assert {w.ppe for w in alerty} == set(PPE_20_PAZDZIERNIKA)
    # mimo braku folderów, oryginał i tak zniknął z kolejki (potwierdzone z użytkownikiem)
    assert not (folder / "D 01.pdf").exists()


def test_kolizja_nazwy_w_folderze_obiektu_dostaje_licznik(tmp_path):
    excel = _kopia_excel(tmp_path)
    root = _drzewo_z_folderami_obiektow(tmp_path, PPE_20_PAZDZIERNIKA)
    folder = root / NAZWA_DO_WPISANIA
    folder_obiektu = root / f"Obiekt ({PPE_20_PAZDZIERNIKA[0]})"

    shutil.copy(FAKTURA_20_PAZDZIERNIKA, folder / "D 01.pdf")
    przetworz_folder(excel, folder, nadpisuj=False, sciezka_faktur_root=root)
    # ta sama faktura raz jeszcze (np. wrzucona pomyłkowo drugi raz) - komórki już wypełnione,
    # ale PPE nadal dopasowuje się do wiersza, więc kopiowanie do folderu obiektu i tak zachodzi
    shutil.copy(FAKTURA_20_PAZDZIERNIKA, folder / "D 01.pdf")
    przetworz_folder(excel, folder, nadpisuj=False, sciezka_faktur_root=root)

    assert (folder_obiektu / "D 01.pdf").exists()
    assert (folder_obiektu / "D 01 (2).pdf").exists()


def test_nic_nie_zapisane_zostaje_w_przetworzone(tmp_path, monkeypatch):
    # Plik, który się sparsował, ale żadna pozycja nie dopasowała PPE do wiersza w arkuszu (sam
    # szum) - nie ma dokąd go skopiować, więc zachowanie sprzed tej funkcji: ląduje w Przetworzone.
    excel = _kopia_excel(tmp_path)
    root = _drzewo_z_folderami_obiektow(tmp_path, [])
    folder = root / NAZWA_DO_WPISANIA
    shutil.copy(FAKTURA_20_PAZDZIERNIKA, folder / "D 01.pdf")

    falszywe_wyniki = [
        WynikWpisu(
            kategoria=KAT_PPE_NIEZNALEZIONE, ppe="000", wiersz=None, nazwa_obiektu=None, miesiac=1
        )
    ]
    monkeypatch.setattr("app.foldery_faktur.wpisz_fakture_do_arkusza", lambda *a, **k: falszywe_wyniki)
    monkeypatch.setattr("app.foldery_faktur.wpisz_polaczone_pozycje_duze", lambda *a, **k: ({}, {}))

    wyniki = przetworz_folder(excel, folder, nadpisuj=False, sciezka_faktur_root=root)

    assert wyniki[0].sciezka == folder / NAZWA_PRZETWORZONE / "D 01.pdf"
    assert wyniki[0].sciezka.exists()
    assert not (folder / "D 01.pdf").exists()


def test_nie_przetwarza_ponownie_plikow_z_przetworzone(tmp_path):
    excel = _kopia_excel(tmp_path)
    root = _drzewo_z_folderami_obiektow(tmp_path, PPE_20_PAZDZIERNIKA)
    folder = root / NAZWA_DO_WPISANIA
    shutil.copy(FAKTURA_20_PAZDZIERNIKA, folder / "D 01.pdf")

    przetworz_folder(excel, folder, nadpisuj=False, sciezka_faktur_root=root)
    wyniki_drugi_raz = przetworz_folder(excel, folder, nadpisuj=False, sciezka_faktur_root=root)

    assert wyniki_drugi_raz == []


def test_plik_o_nieznanym_formacie_zostaje_na_miejscu(tmp_path):
    excel = _kopia_excel(tmp_path)
    root = _drzewo_z_folderami_obiektow(tmp_path, [])
    folder = root / NAZWA_DO_WPISANIA
    shutil.copy(FAKTURA_NIEWLASCIWEGO_TYPU, folder / "zla_faktura.pdf")

    wyniki = przetworz_folder(excel, folder, nadpisuj=False, sciezka_faktur_root=root)

    assert len(wyniki) == 1
    assert wyniki[0].blad is not None
    assert (folder / "zla_faktura.pdf").exists()  # nie przeniesiony
    assert not (folder / NAZWA_PRZETWORZONE / "zla_faktura.pdf").exists()


def test_przetworz_foldery_faktur_obsluguje_oba_foldery_z_odpowiednim_nadpisywaniem(tmp_path):
    excel = _kopia_excel(tmp_path)
    root = _drzewo_z_folderami_obiektow(tmp_path, PPE_20_PAZDZIERNIKA)
    shutil.copy(FAKTURA_20_PAZDZIERNIKA, root / NAZWA_DO_WPISANIA / "D 01.pdf")

    wynik = przetworz_foldery_faktur(excel, root)

    assert NAZWA_DO_WPISANIA in wynik and NAZWA_DO_AKTUALIZACJI in wynik
    assert len(wynik[NAZWA_DO_WPISANIA]) == 1
    assert all(w.zapisano for w in wynik[NAZWA_DO_WPISANIA][0].wyniki)
    assert wynik[NAZWA_DO_AKTUALIZACJI] == []

    # druga faktura tej samej treści w "Do aktualizacji" powinna nadpisac (komorki juz wypelnione)
    shutil.copy(FAKTURA_20_PAZDZIERNIKA, root / NAZWA_DO_AKTUALIZACJI / "D 01.pdf")
    wynik2 = przetworz_foldery_faktur(excel, root)
    assert all(w.zapisano for w in wynik2[NAZWA_DO_AKTUALIZACJI][0].wyniki)
