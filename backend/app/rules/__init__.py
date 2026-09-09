from app.alerts import Alert
from app.excel_reader import Obiekt
from app.rules.continuity import sprawdz_ciaglosc
from app.rules.deviation import sprawdz_odchylenia


def uruchom_wszystkie_reguly(obiekty: list[Obiekt]) -> list[Alert]:
    return sprawdz_odchylenia(obiekty) + sprawdz_ciaglosc(obiekty)


__all__ = ["Alert", "sprawdz_odchylenia", "sprawdz_ciaglosc", "uruchom_wszystkie_reguly"]
