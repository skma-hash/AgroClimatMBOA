"""
model_manager.py
Gestion (chargement / existence / suppression) des modèles VARMAX sauvegardés.
"""

import os

from config import MODEL_PATH
from utils import load_pickle, logger


def _model_path(city):
    return f"{MODEL_PATH}/{city}_varmax.pkl"


def model_exists(city):
    return os.path.exists(_model_path(city))


def load_model(city):
    path = _model_path(city)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Aucun modèle sauvegardé pour {city} ({path})")
    bundle = load_pickle(path)
    logger(f"[{city}] Modèle VARMAX chargé depuis {path}")
    return bundle


def delete_model(city):
    path = _model_path(city)
    if os.path.exists(path):
        os.remove(path)
        logger(f"[{city}] Modèle supprimé : {path}")
        return True
    logger(f"[{city}] Aucun modèle à supprimer", level="warning")
    return False
