"""Rejestracja/wyrejestrowanie autostartu w Harmonogramie zadań Windows (trigger: przy logowaniu).

Uruchamia aplikację przez małe wrapper .vbs (WScript.Shell.Run z drugim argumentem 0), żeby przy
logowaniu nie mignęło okno konsoli - schtasks samo w sobie nie ma opcji "bez okna" dla /tr.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

NAZWA_ZADANIA = "Excel Helper"
BACKEND_DIR = Path(__file__).resolve().parents[1]
VBS_PATH = BACKEND_DIR / "scripts" / "uruchom_ukryte.vbs"


def _pythonw() -> Path:
    return Path(sys.executable).with_name("pythonw.exe")


def zawartosc_vbs(backend_dir: Path = BACKEND_DIR, pythonw: Path | None = None) -> str:
    pythonw = pythonw or _pythonw()
    return (
        'Set objShell = CreateObject("WScript.Shell")\n'
        f'objShell.CurrentDirectory = "{backend_dir}"\n'
        f'objShell.Run """{pythonw}"" -m app.main", 0, False\n'
    )


def polecenie_instalacji(vbs_path: Path = VBS_PATH) -> list[str]:
    return [
        "schtasks", "/create", "/tn", NAZWA_ZADANIA,
        "/tr", f'wscript.exe "{vbs_path}"',
        "/sc", "onlogon",
        "/f",
    ]


def polecenie_odinstalowania() -> list[str]:
    return ["schtasks", "/delete", "/tn", NAZWA_ZADANIA, "/f"]


def zainstaluj() -> None:
    VBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    VBS_PATH.write_text(zawartosc_vbs(), encoding="utf-8")
    subprocess.run(polecenie_instalacji(), check=True)


def odinstaluj() -> None:
    subprocess.run(polecenie_odinstalowania(), check=True)
