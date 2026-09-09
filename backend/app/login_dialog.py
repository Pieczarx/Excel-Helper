"""Okno logowania do Supabase - żeby dwa komputery widziały te same oznaczone alerty."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class OknoLogowania(QDialog):
    def __init__(self, parent=None, domyslny_email: str = "", domyslne_haslo: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Excel Helper — logowanie")
        self.setMinimumWidth(320)
        self.email = ""
        self.haslo = ""
        self.zapamietaj_haslo = False

        uklad = QVBoxLayout(self)
        opis = QLabel("Zaloguj się, żeby zsynchronizować oznaczone alerty między komputerami.")
        opis.setWordWrap(True)
        uklad.addWidget(opis)

        formularz = QFormLayout()
        self._pole_email = QLineEdit(domyslny_email)
        self._pole_haslo = QLineEdit(domyslne_haslo)
        self._pole_haslo.setEchoMode(QLineEdit.Password)
        formularz.addRow("E-mail", self._pole_email)
        formularz.addRow("Hasło", self._pole_haslo)
        uklad.addLayout(formularz)

        self._checkbox_zapamietaj = QCheckBox("Zapamiętaj hasło")
        self._checkbox_zapamietaj.setChecked(bool(domyslne_haslo))
        uklad.addWidget(self._checkbox_zapamietaj)

        przycisk_zaloguj = QPushButton("Zaloguj")
        przycisk_zaloguj.clicked.connect(self._na_zaloguj)
        uklad.addWidget(przycisk_zaloguj)

    def _na_zaloguj(self) -> None:
        email = self._pole_email.text().strip()
        haslo = self._pole_haslo.text()
        if not email or not haslo:
            QMessageBox.warning(self, "Brak danych", "Podaj e-mail i hasło.")
            return
        self.email = email
        self.haslo = haslo
        self.zapamietaj_haslo = self._checkbox_zapamietaj.isChecked()
        self.accept()
