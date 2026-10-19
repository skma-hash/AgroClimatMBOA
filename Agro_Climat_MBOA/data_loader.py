"""
data_loader.py
Chargement des données CSV par ville et préparation pour la modélisation.

Hypothèses sur les fichiers CSV (à ajuster si besoin, ce module n'affecte
pas config.py) :
- Un fichier par ville : data/{NomVille}.csv
- Colonne de date nommée comme config.DATE_COLUMN ("Date")
- Séparateur virgule
- Données déjà agrégées en fréquence hebdomadaire (W-SUN), comme dans le
  reste du pipeline (analyse_ville.py). Si ce n'est pas le cas, dis-le moi
  et j'ajoute un resample() ici.
"""

import os
import pandas as pd

from config import VARIABLES, DATE_COLUMN, DATA_PATH
from utils import load_csv, logger, coerce_numeric


def load_city_data(city, encoding="latin-1", sep=","):
    """
    Charge le CSV de la ville depuis DATA_PATH/{city}.csv
    encoding="latin-1" par défaut ; passe encoding="utf-8" si besoin.
    sep="," par défaut ; passe sep=";" si tes CSV utilisent le point-virgule
    (fréquent avec les exports Excel en français).
    """
    path = os.path.join(DATA_PATH, f"{city}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Fichier introuvable pour {city} : {path}")

    df = load_csv(path, date_column=DATE_COLUMN, encoding=encoding, sep=sep)
    logger(f"[{city}] CSV chargé : {df.shape[0]} lignes, {df.shape[1]} colonnes")
    return df


def prepare_dataframe(df):
    """
    - Convertit/valide la colonne de date
    - Trie chronologiquement
    - Passe la date en index
    - Ne conserve que les colonnes présentes dans config.VARIABLES
    - Force chaque variable en numérique (gère virgule décimale, espaces)
    - Gère les valeurs manquantes (interpolation temporelle + ffill/bfill résiduel)
    """
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    if DATE_COLUMN not in df.columns:
        raise ValueError(
            f"Colonne de date '{DATE_COLUMN}' absente du CSV. "
            f"Colonnes trouvées : {list(df.columns)}"
        )

    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN], errors="coerce")
    df = df.dropna(subset=[DATE_COLUMN])
    df = df.sort_values(DATE_COLUMN)
    df = df.set_index(DATE_COLUMN)

    variables_presentes = [v for v in VARIABLES if v in df.columns]
    manquantes = [v for v in VARIABLES if v not in df.columns]
    if manquantes:
        logger(
            f"Variables absentes du CSV et ignorées : {manquantes}. "
            f"Colonnes réellement présentes dans le fichier : {list(df.columns)}",
            level="warning",
        )

    df = df[variables_presentes]

    # Coercition numérique (gère "23,5" -> 23.5, espaces insécables, etc.)
    for col in df.columns:
        df[col] = coerce_numeric(df[col])

    # Gestion des NA : interpolation temporelle puis comblement des bords
    df = df.interpolate(method="time").ffill().bfill()

    return df
