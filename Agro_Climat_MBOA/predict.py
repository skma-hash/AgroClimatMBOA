"""
predict.py
Point d'entrée simple pour générer des prévisions pour une ville donnée.

Usage direct en script :
    python predict.py

Ou en import :
    from predict import predict_city
    df = predict_city("Bertoua", "2026-08-01", "2026-10-01")
"""

from predictor import predict, format_predictions
from utils import logger


def predict_city(city, start_date, end_date):
    predictions = predict(city, start_date, end_date)
    return format_predictions(predictions)


if __name__ == "__main__":
    # Exemple d'utilisation - à adapter
    city = "Bertoua"
    start_date = "2026-08-01"
    end_date = "2026-10-01"

    df_result = predict_city(city, start_date, end_date)
    logger(f"Aperçu des prévisions pour {city} :\n{df_result.head()}")
    print(df_result)
