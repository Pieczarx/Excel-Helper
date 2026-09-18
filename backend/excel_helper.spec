# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller excel_helper.spec  (z katalogu backend/)
# Wynik: dist/ExcelHelper.exe - jeden plik, bez wymaganego Pythona u klienta.
#
# Nazwa pliku CELOWO bez spacji (ExcelHelper, nie "Excel Helper") - GitHub Releases i tak zamienia
# spacje w nazwach załączników na kropki przy uploadzie (np. "Excel Helper.exe" -> "Excel.Helper.exe",
# potwierdzone przez surowe API), więc plik bez spacji zostaje zachowany dokładnie taki, jaki jest.
# Nazwa wyświetlana w appce (tytuł okna, tray) zostaje "Excel Helper" ze spacją - to osobna sprawa,
# patrz window.py/tray.py.
#
# --collect-all na keyring/pystray: obie biblioteki dobierają backend systemowy dynamicznie
# (importlib w czasie działania, nie statyczny import na górze pliku) - bez tego PyInstaller
# nie znajduje właściwego backendu Windows i appka wysypuje się dopiero przy pierwszym użyciu
# (logowanie / ikona w zasobniku), nie przy starcie.
#
# --collect-all na certifi: appka jawnie używa certifi.where() (patrz app/siec.py) do CA bundla
# przy zapytaniach do GitHuba - bez tego wpisu PyInstaller nie bierze pod uwagę, że plik danych
# cacert.pem jest w ogóle potrzebny (żadna statyczna analiza importów tego nie wychwyci), więc
# certifi.where() w spakowanej appce wskazywałby na ścieżkę, której tam po prostu nie ma.
#
# pyexpat jawnie w hiddenimports: openpyxl (przez xml.etree.ElementTree) go potrzebuje, a
# zaobserwowane realnie: "ModuleNotFoundError: No module named 'pyexpat'" w appce zainstalowanej
# przez WŁASNY mechanizm samoaktualizacji appki (choć nie w exe budowanym i uruchamianym wprost
# tutaj) - PyInstaller zwykle wykrywa to sam, ale nie zawsze niezawodnie, więc wymuszamy jawnie.
from PyInstaller.utils.hooks import collect_all

datas = [("assets/icon.ico", "assets")]
binaries = []
hiddenimports = ["pyexpat", "xml.parsers.expat", "xml.etree.ElementTree"]

for pakiet in ("keyring", "pystray", "certifi"):
    _datas, _binaries, _hiddenimports = collect_all(pakiet)
    datas += _datas
    binaries += _binaries
    hiddenimports += _hiddenimports

a = Analysis(
    ["uruchom_gui.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ExcelHelper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon="assets/icon.ico",
)
