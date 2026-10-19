"""
utils.py
Fonctions utilitaires communes au projet Argo_Climat_MBOA.
"""

import os
import pickle
import logging
from datetime import datetime

import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import adfuller
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform


# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------
_LOGGER_CONFIGURED = False


def _configure_logger(log_path="logs/argo_climat.log"):
    global _LOGGER_CONFIGURED
    if _LOGGER_CONFIGURED:
        return
    create_directory(os.path.dirname(log_path) or ".")
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    # On garde aussi une sortie console pour le confort en dev.
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logging.getLogger().addHandler(console)
    _LOGGER_CONFIGURED = True


def logger(message, level="info"):
    """Log un message. Niveaux: info, warning, error, debug."""
    _configure_logger()
    log_fn = getattr(logging, level, logging.info)
    log_fn(message)


# ----------------------------------------------------------------------
# Fichiers / persistance
# ----------------------------------------------------------------------
def create_directory(path):
    """Crée le dossier s'il n'existe pas déjà."""
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def load_excel(path):
    """Conservé pour compatibilité, mais on utilise désormais load_csv."""
    return pd.read_excel(path)


def load_csv(path, date_column="Date", sep=",", encoding="latin-1"):
    """
    Charge un fichier CSV et parse la colonne de date.
    encoding="latin-1" par défaut (utile pour les CSV exportés avec des
    accents/caractères spéciaux depuis Excel/Windows en Europe/Afrique
    francophone). Passe encoding="utf-8" si tes fichiers sont en UTF-8.

    Si le séparateur donné produit une seule colonne (signe qu'il est
    faux), on retente automatiquement avec ';', '\t' puis '|' avant
    d'abandonner.
    """
    df = pd.read_csv(path, sep=sep, encoding=encoding)

    if df.shape[1] == 1:
        for alt_sep in [";", "\t", "|"]:
            if alt_sep == sep:
                continue
            df_try = pd.read_csv(path, sep=alt_sep, encoding=encoding)
            if df_try.shape[1] > 1:
                logger(
                    f"Séparateur '{sep}' donnait 1 seule colonne pour {path}. "
                    f"Détecté automatiquement : '{alt_sep}'.",
                    level="warning",
                )
                df = df_try
                break

    # Nettoyage des noms de colonnes : espaces parasites très fréquents
    # dans les exports "Date; T_moy; T_max" (espace après le séparateur).
    df.columns = [str(c).strip() for c in df.columns]

    if date_column in df.columns:
        df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
    return df


def coerce_numeric(series):
    """
    Force une série en numérique, en gérant le cas fréquent des décimales
    à la française (virgule au lieu du point) et des espaces insécables
    utilisés comme séparateurs de milliers.

    Retourne une série float ; les valeurs non convertibles deviennent NaN
    (elles seront comblées par l'interpolation dans prepare_dataframe).
    """
    if pd.api.types.is_numeric_dtype(series):
        return series

    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace("\u00a0", "", regex=False)  # espace insécable
        .str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def save_pickle(obj, path):
    create_directory(os.path.dirname(path) or ".")
    with open(path, "wb") as f:
        pickle.dump(obj, f)


def load_pickle(path):
    with open(path, "rb") as f:
        return pickle.load(f)


# ----------------------------------------------------------------------
# Stationnarité
# ----------------------------------------------------------------------
def test_stationarity(series, alpha=0.05):
    """
    Test ADF (Augmented Dickey-Fuller).
    Retourne True si la série est stationnaire (p-value < alpha).
    """
    series_clean = series.dropna()
    if len(series_clean) < 10:
        # Pas assez de points pour un test fiable : on suppose non-stationnaire
        # par prudence (une différenciation ne fera pas de mal).
        return False
    try:
        result = adfuller(series_clean, autolag="AIC")
        p_value = result[1]
        return p_value < alpha
    except Exception:
        return False


def make_stationary(df, max_diff=2):
    """
    Différencie chaque colonne jusqu'à stationnarité (ou max_diff atteint).

    Retourne (df_diff, diff_orders, level_seeds) :
    - diff_orders[col] = nombre de différenciations appliquées (d)
    - level_seeds[col] = liste de longueur d, où level_seeds[col][i] est la
      dernière valeur connue de la série différenciée i fois (i=0 -> série
      brute, i=1 -> 1re différence, etc.), nécessaire pour ré-intégrer
      correctement les prévisions niveau par niveau, quel que soit d.
    """
    df_out = df.copy()
    diff_orders = {}
    level_seeds = {}

    for col in df.columns:
        d = 0
        serie = df_out[col]
        seeds = []
        while d < max_diff and not test_stationarity(serie):
            seeds.append(serie.dropna().iloc[-1])
            serie = serie.diff()
            d += 1
        df_out[col] = serie
        diff_orders[col] = d
        level_seeds[col] = seeds

    df_out = df_out.dropna()
    return df_out, diff_orders, level_seeds


def invert_diff(level_seeds, diff_forecast_series, d):
    """
    Inverse une différenciation d'ordre d, niveau par niveau.

    level_seeds : liste de longueur d, level_seeds[i] = dernière valeur
                  connue de la série différenciée i fois (cf make_stationary).
    diff_forecast_series : prévisions dans l'espace complètement différencié
                            (niveau d), array-like.

    Pour repasser du niveau i+1 au niveau i : cumsum des prévisions du
    niveau i+1 en partant du seed du niveau i. On répète de i=d-1 à i=0.
    """
    if d == 0:
        return list(diff_forecast_series)

    current = np.asarray(diff_forecast_series, dtype=float)

    for i in range(d - 1, -1, -1):
        seed = level_seeds[i]
        current = seed + np.cumsum(current)

    return list(current)


# ----------------------------------------------------------------------
# Regroupement de variables corrélées (pour limiter la dimensionnalité VARMAX)
# ----------------------------------------------------------------------
def cluster_correlated_variables(df, max_group_size=4, corr_threshold=0.3):
    """
    Regroupe les variables en clusters de variables corrélées entre elles,
    limités à `max_group_size` variables par groupe.

    Principe : clustering hiérarchique sur (1 - |corrélation|) comme distance,
    puis on découpe l'arbre en autant de clusters que nécessaire pour
    respecter la taille max, en fusionnant les petits clusters restants
    de façon gloutonne.

    Retourne une liste de listes de noms de colonnes.
    """
    corr = df.corr().abs().fillna(0)
    corr_vals = corr.to_numpy(copy=True)  # copie writable, corr.values peut être read-only
    np.fill_diagonal(corr_vals, 1.0)
    distance = 1 - corr_vals
    condensed = squareform(distance, checks=False)

    if len(df.columns) <= max_group_size:
        return [list(df.columns)]

    Z = linkage(condensed, method="average")
    n_clusters_guess = max(2, int(np.ceil(len(df.columns) / max_group_size)))
    labels = fcluster(Z, t=n_clusters_guess, criterion="maxclust")

    groups = {}
    for col, label in zip(df.columns, labels):
        groups.setdefault(label, []).append(col)

    # Découpe les groupes encore trop gros en sous-groupes de taille max_group_size
    final_groups = []
    for cols in groups.values():
        for i in range(0, len(cols), max_group_size):
            final_groups.append(cols[i:i + max_group_size])

    return final_groups
