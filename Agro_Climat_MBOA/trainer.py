"""
trainer.py
Entraînement de modèles VARMAX pour une ville.

Stratégie anti-explosion-de-paramètres :
Avec 13 variables, un seul VARMAX(p,q) sur tout le bloc a un nombre de
paramètres qui grossit en (13*p + 13*13*q), ce qui devient vite intraitable
avec des séries hebdomadaires de longueur modeste. On regroupe donc les
variables corrélées en petits clusters (<= 4 variables), et on entraîne un
VARMAX indépendant par cluster. On perd la covariance inter-cluster, mais on
gagne des modèles qui convergent et qui généralisent.
"""

import itertools
import time
import warnings

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.varmax import VARMAX
from statsmodels.tsa.api import VAR

from utils import (
    logger,
    make_stationary,
    cluster_correlated_variables,
    save_pickle,
    create_directory,
)
from config import MODEL_PATH

warnings.filterwarnings("ignore")

MAX_GROUP_SIZE = 4
MAX_P = 3

# VARMA avec terme MA (q>0) est extrêmement coûteux à estimer (filtre de
# Kalman + optimisation numérique sur un espace d'état bien plus grand) et
# apporte rarement un gain décisif en prévision par rapport à un VAR pur
# (q=0). On le désactive par défaut. Mets MAX_Q=1 seulement si tu as du
# temps à y consacrer (des heures par ville sont possibles).
MAX_Q = 0

FIT_MAXITER = 100  # suffisant pour converger sur ces tailles de modèle


def _suggest_order_var(df_group):
    """
    Utilise VAR.select_order comme heuristique rapide pour choisir p,
    avant d'affiner avec VARMAX (qui n'a pas de select_order natif).
    """
    try:
        model = VAR(df_group)
        max_lags = min(MAX_P, max(1, len(df_group) // 10))
        selection = model.select_order(maxlags=max_lags)
        p_aic = selection.aic
        return max(1, p_aic)
    except Exception as e:
        logger(f"select_order VAR a échoué ({e}), repli sur p=1", level="warning")
        return 1


def _grid_search_varmax(df_group, p_hint):
    """
    Petite grid search autour de p_hint pour (p, q), sélection par AIC.
    Retourne (best_model_fit, best_order).
    """
    candidates = []
    # Un seul voisin de chaque côté suffit ; limiter drastiquement le
    # nombre de candidats est ce qui évite les entraînements de plusieurs
    # heures par ville.
    p_values = sorted(set([max(1, p_hint - 1), p_hint]))
    q_values = list(range(0, MAX_Q + 1))

    best_aic = np.inf
    best_fit = None
    best_order = None

    for p, q in itertools.product(p_values, q_values):
        if p == 0 and q == 0:
            continue
        logger(f"  -> Essai VARMAX(p={p}, q={q}) sur {list(df_group.columns)}...")
        t0 = time.time()
        try:
            model = VARMAX(df_group, order=(p, q), enforce_stationarity=False,
                            enforce_invertibility=False)
            # cov_type="none" évite le calcul de la matrice de covariance
            # des paramètres (hessienne numérique), coûteux et inutile ici
            # puisqu'on ne se sert que des prévisions, pas des p-values.
            fit = model.fit(disp=False, maxiter=FIT_MAXITER, cov_type="none",
                             method="lbfgs")
            elapsed = time.time() - t0
            candidates.append((p, q, fit.aic))
            logger(f"     AIC={fit.aic:.2f} (en {elapsed:.1f}s)")
            if fit.aic < best_aic:
                best_aic = fit.aic
                best_fit = fit
                best_order = (p, q)
        except Exception as e:
            elapsed = time.time() - t0
            logger(f"     échec après {elapsed:.1f}s : {e}", level="warning")
            continue

    if best_fit is None:
        raise RuntimeError("Aucun ordre VARMAX n'a convergé pour ce groupe.")

    logger(f"Ordres testés (p,q,AIC) : {candidates}")
    logger(f"Meilleur ordre retenu : {best_order} (AIC={best_aic:.2f})")
    return best_fit, best_order


def create_varmax_model(df_group):
    """
    Construit et entraîne un VARMAX sur un groupe de variables déjà
    stationnarisé. Retourne le fit statsmodels.
    """
    p_hint = _suggest_order_var(df_group)
    fit, order = _grid_search_varmax(df_group, p_hint)
    return fit, order


def train_model(df):
    """
    Pipeline complet pour une ville :
    1. Clustering des variables corrélées
    2. Stationnarisation (différenciation) par variable
    3. Entraînement d'un VARMAX par cluster
    Retourne un dict prêt à être sauvegardé :
    {
        "groups": [...],
        "diff_orders": {...},
        "models": {tuple(group): fit},
        "orders": {tuple(group): (p, q)},
        "level_seeds": {col: [dernière valeur connue à chaque niveau de diff]},
    }
    """
    groups = cluster_correlated_variables(df, max_group_size=MAX_GROUP_SIZE)
    logger(f"Groupes de variables retenus : {groups}")

    df_stationary, diff_orders, level_seeds = make_stationary(df)

    models = {}
    orders = {}

    for group in groups:
        group_key = tuple(group)
        logger(f"--- Entraînement VARMAX pour le groupe {group_key} ---")
        t0_group = time.time()
        df_group = df_stationary[list(group)]
        # Reconstruction explicite d'un tableau numpy writable : sous
        # pandas 2.x (Copy-on-Write), un slice/copy peut laisser le tableau
        # sous-jacent en lecture seule, ce qui fait planter statsmodels
        # avec "Underlying array is read-only".
        df_group = pd.DataFrame(
            df_group.to_numpy(copy=True, dtype=float),
            index=df_group.index,
            columns=df_group.columns,
        )
        try:
            fit, order = create_varmax_model(df_group)
            models[group_key] = fit
            orders[group_key] = order
            logger(f"--- Groupe {group_key} terminé en {time.time() - t0_group:.1f}s ---")
        except Exception as e:
            logger(f"Échec d'entraînement pour le groupe {group_key} : {e}", level="error")

    return {
        "groups": groups,
        "diff_orders": diff_orders,
        "models": models,
        "orders": orders,
        "level_seeds": level_seeds,
        "columns": list(df.columns),
        "last_date": df.index[-1],
        "freq": df.index.freq or "W-SUN",
    }


def save_model(model_bundle, city):
    """
    Sauvegarde le bundle complet (modèles par groupe + métadonnées)
    dans MODEL_PATH/{city}_varmax.pkl
    """
    create_directory(MODEL_PATH)
    path = f"{MODEL_PATH}/{city}_varmax.pkl"
    save_pickle(model_bundle, path)
    logger(f"[{city}] Modèle VARMAX sauvegardé : {path}")
    return path
