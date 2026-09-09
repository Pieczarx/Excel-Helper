import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

# Trzeba to utworzyc jako QApplication (nie QCoreApplication) zanim jakikolwiek test dotknie Qt -
# gdyby ktorys plik testowy stworzyl najpierw "gola" QCoreApplication, kolejne proby zbudowania
# prawdziwych widgetow (QMainWindow itp.) w innym pliku wisialyby w nieskonczonosc pod offscreen.
_APP = QApplication.instance() or QApplication([])
