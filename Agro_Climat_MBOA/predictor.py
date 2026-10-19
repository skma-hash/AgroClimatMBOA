"""
predictor.py
Génération de prévisions à partir d'un modèle VARMAX sauvegardé (bundle
par groupes de variables) et mise en forme du résultat.
"""

import pandas as pd
import numpy as np

from utils import logger, invert_diff
from model_manager import load_model


def forecast_steps(last_date, end_date, freq="W-SUN"):
    """
    Calcule le nombre de pas (semaines) entre last_date (dernière date
    d'entraînement) et end_date (date cible de fin de prévision).
    """
    future_index = pd.date_range(start=last_date, end=end_date, freq=freq)
    # On exclut last_date elle-même (déjà connue)
    n_steps = max(0, len(future_index) - 1)
    return n_steps


def predict(city, start_date, end_date, exog_future=None):
    """
    Prévoit chaque variable de `city` entre start_date et end_date.

    exog_future : non utilisé pour l'instant (VARMAX ici est purement
    endogène, sans régresseurs exogènes). Conservé pour compatibilité
    d'interface avec un futur SARIMAX/VARMAX-X.
    """
    bundle = load_model(city)
    last_date = bundle["last_date"]
    freq = bundle["freq"]

    n_steps = forecast_steps(last_date, end_date, freq=freq)
    if n_steps <= 0:
        raise ValueError(
            f"end_date ({end_date}) doit être postérieure à la dernière date "
            f"d'entraînement ({last_date})."
        )

    future_index = pd.date_range(
        start=last_date, periods=n_steps + 1, freq=freq
    )[1:]

    predictions = pd.DataFrame(index=future_index)

    for group, fit in bundle["models"].items():
        group = list(group)
        forecast_diff = fit.forecast(steps=n_steps)
        forecast_diff = pd.DataFrame(forecast_diff, columns=group, index=future_index)

        for col in group:
            d = bundle["diff_orders"].get(col, 0)
            if d == 0:
                predictions[col] = forecast_diff[col].values
            else:
                inverted = invert_diff(
                    bundle["level_seeds"][col], forecast_diff[col].values, d
                )
                predictions[col] = inverted

    # Recadrage sur la fenêtre [start_date, end_date] demandée
    start_ts = pd.to_datetime(start_date)
    end_ts = pd.to_datetime(end_date)
    predictions = predictions.loc[
        (predictions.index >= start_ts) & (predictions.index <= end_ts)
    ]

    logger(f"[{city}] Prévisions générées pour {len(predictions)} semaines "
           f"({start_date} -> {end_date})")

    return predictions


def format_predictions(predictions):
    """
    Met en forme le DataFrame de prévisions pour l'affichage / export :
    - index renommé 'Date'
    - arrondi à 2 décimales
    - colonnes triées comme dans config.VARIABLES si possible
    """
    df = predictions.copy()
    df = df.round(2)
    df.index.name = "Date"
    df = df.reset_index()
    return df
