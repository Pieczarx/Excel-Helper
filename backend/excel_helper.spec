# -*- mode: python ; coding: utf-8 -*-
# Build: pyinstaller excel_helper.spec  (z katalogu backend/)
# Wynik: dist/Excel Helper.exe - jeden plik, bez wymaganego Pythona u klienta.
#
# --collect-all na keyring/pystray: obie biblioteki dobierają backend systemowy dynamicznie
# (importlib w czasie działania, nie statyczny import na górze pliku) - bez tego PyInstaller
# nie znajduje właściwego backendu Windows i appka wysypuje się dopiero przy pierwszym użyciu
# (logowanie / ikona w zasobniku), nie przy starcie.
from PyInstaller.utils.hooks import collect_all

datas = [("assets/icon.ico", "assets")]
binaries = []
hiddenimports = []

for pakiet in ("keyring", "pystray"):
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
    name="Excel Helper",
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
