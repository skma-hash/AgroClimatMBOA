"""
test_predictions.py
Script de test rapide pour vérifier que les modèles VARMAX entraînés
produisent des prévisions cohérentes, ville par ville.

Usage :
    python test_predictions.py
    python test_predictions.py Bertoua
    python test_predictions.py Bertoua 2026-08-01 2026-10-01
"""

import sys
from datetime import timedelta

import pandas as pd

from config import VILLES
from model_manager import model_exists, load_model
from predictor import predict, format_predictions
from utils import logger


def test_one_city(city, start_date=None, end_date=None, n_weeks=8):
    """
    Teste la prédiction pour une ville et affiche un diagnostic complet :
    - existence du modèle
    - dates réellement couvertes
    - valeurs manquantes éventuelles
    - aperçu des prévisions
    - alerte si des valeurs semblent physiquement aberrantes
    """
    print(f"\n{'='*60}")
    print(f"TEST : {city}")
    print(f"{'='*60}")

    if not model_exists(city):
        print(f"[ÉCHEC] Aucun modèle sauvegardé pour {city}.")
        return False

    bundle = load_model(city)
    last_date = bundle["last_date"]
    print(f"Dernière date d'entraînement : {last_date}")
    print(f"Groupes de variables : {bundle['groups']}")
    print(f"Ordres (p,q) retenus : {bundle['orders']}")

    # Par défaut : prévoit les n_weeks semaines suivant la fin d'entraînement
    if start_date is None:
        start_date = last_date + timedelta(weeks=1)
    if end_date is None:
        end_date = pd.to_datetime(start_date) + timedelta(weeks=n_weeks - 1)

    try:
        raw_predictions = predict(city, start_date, end_date)
    except Exception as e:
        print(f"[ÉCHEC] La prédiction a levé une exception : {e}")
        return False

    if raw_predictions.empty:
        print("[ÉCHEC] Le DataFrame de prévisions est vide.")
        return False

    n_na = raw_predictions.isna().sum().sum()
    print(f"\nLignes prévues : {len(raw_predictions)}")
    print(f"Valeurs manquantes (NaN) dans les prévisions : {n_na}")
    if n_na > 0:
        print("  -> colonnes concernées :")
        print(raw_predictions.isna().sum()[raw_predictions.isna().sum() > 0])

    # Alerte simple sur des valeurs physiquement improbables
    alertes = []
    checks = {
        "Humidite_relative(%)": (0, 100),
        "Précipitations (mm/j)": (0, 200),
        "Vent_(m/s)": (0, 30),
    }
    for col, (vmin, vmax) in checks.items():
        if col in raw_predictions.columns:
            hors_bornes = raw_predictions[
                (raw_predictions[col] < vmin) | (raw_predictions[col] > vmax)
            ]
            if not hors_bornes.empty:
                alertes.append(f"{col} : {len(hors_bornes)} valeur(s) hors [{vmin}, {vmax}]")

    if alertes:
        print("\n[ATTENTION] Valeurs suspectes détectées :")
        for a in alertes:
            print(f"  - {a}")
    else:
        print("\nAucune valeur suspecte détectée sur les bornes physiques testées.")

    formatted = format_predictions(raw_predictions)
    print(f"\nAperçu des prévisions ({city}) :")
    print(formatted.head(10).to_string(index=False))

    print(f"\n[OK] Test réussi pour {city}.")
    return True


def test_all_cities(start_date=None, end_date=None, n_weeks=8):
    resultats = {}
    for city in VILLES:
        resultats[city] = test_one_city(city, start_date, end_date, n_weeks)

    print(f"\n{'='*60}")
    print("BILAN")
    print(f"{'='*60}")
    for city, ok in resultats.items():
        statut = "OK" if ok else "ÉCHEC"
        print(f"  {city:20s} -> {statut}")

    n_ok = sum(resultats.values())
    print(f"\n{n_ok}/{len(resultats)} villes testées avec succès.")
    return resultats


if __name__ == "__main__":
    args = sys.argv[1:]

    if len(args) == 0:
        test_all_cities()
    elif len(args) == 1:
        test_one_city(args[0])
    elif len(args) == 3:
        test_one_city(args[0], args[1], args[2])
    else:
        print("Usage : python test_predictions.py [ville] [start_date] [end_date]")
