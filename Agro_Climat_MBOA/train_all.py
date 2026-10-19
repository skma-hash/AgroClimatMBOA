"""
train_all.py
Entraîne le pipeline VARMAX (par groupes de variables) pour toutes les
villes définies dans config.VILLES.
"""

import traceback

from config import VILLES
from data_loader import load_city_data, prepare_dataframe
from trainer import train_model, save_model
from utils import logger


def train_city(city):
    logger(f"===== Entraînement VARMAX : {city} =====")
    try:
        df_raw = load_city_data(city)
        df = prepare_dataframe(df_raw)
        bundle = train_model(df)
        save_model(bundle, city)
        logger(f"===== {city} : terminé avec succès =====")
        return True
    except Exception as e:
        tb = traceback.format_exc()
        logger(f"===== {city} : ÉCHEC ({e}) =====", level="error")
        logger(f"Trace complète :\n{tb}", level="error")
        print(tb)  # affiché aussi directement dans la console/notebook
        return False


def train_all():
    resultats = {}
    for city in VILLES:
        resultats[city] = train_city(city)

    succes = [v for v, ok in resultats.items() if ok]
    echecs = [v for v, ok in resultats.items() if not ok]
    logger(f"Bilan entraînement : {len(succes)} succès, {len(echecs)} échecs")
    if echecs:
        logger(f"Villes en échec : {echecs}", level="warning")
    return resultats


if __name__ == "__main__":
    train_all()
