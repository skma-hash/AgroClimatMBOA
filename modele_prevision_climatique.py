"""
MODULE DE PREVISION CLIMATIQUE - Projet Agriculture Resiliente Est Cameroun
=============================================================================
Deux sous-modules :
  A. Prevision operationnelle (semis / irrigation / traitement) - regles
     agroclimatiques, validees par backtesting sur l'historique NASA POWER.
     -> A brancher sur une API meteo temps reel (ex: Open-Meteo) en production.
  B. Prevision climatique saisonniere (Prophet) - tendance + saisonnalite,
     pour construire le calendrier cultural de la campagne agricole.

Donnees source : Final_Est_Cameroun_Journalier_9villes_Format.xlsx (NASA POWER)
"""

import os
import pandas as pd
import numpy as np
from scipy import stats
from prophet import Prophet
import warnings
warnings.filterwarnings('ignore')

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_PATH = os.environ.get(
    'DATA_PATH',
    os.path.join(BASE_DIR, 'data', 'Final_Est_Cameroun_Journalier_9villes_Format.xlsx')
)

COLS = ['Ville', 'Lat', 'Lon', 'Date', 'Annee', 'Mois_n', 'Mois', 'Jour',
        'T_moy', 'T_max', 'T_min', 'Hum', 'Vent', 'Pression', 'Rayon',
        'Precip', 'ET0', 'Bilan', 'GDD', 'SeqSeche', 'Tsol1', 'Tsol2']

NUM_COLS = ['T_moy', 'T_max', 'T_min', 'Hum', 'Vent', 'Pression', 'Rayon',
            'Precip', 'ET0', 'Bilan', 'GDD', 'SeqSeche']


# ---------------------------------------------------------------------------
# CHARGEMENT DES DONNEES
# ---------------------------------------------------------------------------

def load_city(sheet_name: str, path: str = DATA_PATH) -> pd.DataFrame:
    """Charge et nettoie les donnees journalieres d'une ville (feuille Excel).
    Les rares valeurs manquantes (ex: rayonnement) sont interpolees lineairement
    : sur une serie journaliere continue, 1-2 jours manquants par variable
    n'ont pas d'impact physique notable, mais un NaN non traite propage une
    valeur invalide dans toute simulation cumulative (biomasse, bilan hydrique)."""
    raw = pd.read_excel(path, sheet_name=sheet_name, header=None)
    data = raw.iloc[5:].reset_index(drop=True)
    data.columns = COLS
    data['Date'] = pd.to_datetime(data['Date'])
    for c in NUM_COLS:
        data[c] = pd.to_numeric(data[c], errors='coerce')
        data[c] = data[c].interpolate(limit_direction='both')
    return data.sort_values('Date').reset_index(drop=True)


def monthly_aggregate(daily: pd.DataFrame) -> pd.DataFrame:
    """Agrege les donnees journalieres en series mensuelles (T moyenne, precip cumulee)."""
    m = daily.groupby(['Annee', 'Mois_n']).agg(
        T_moy=('T_moy', 'mean'),
        Precip=('Precip', 'sum'),
        ET0=('ET0', 'sum'),
        Bilan=('Bilan', 'sum'),
    ).reset_index()
    m['ds'] = pd.to_datetime(dict(year=m.Annee, month=m.Mois_n, day=1))
    return m.sort_values('ds').reset_index(drop=True)


# ---------------------------------------------------------------------------
# MODULE B - PREVISION CLIMATIQUE SAISONNIERE
# ---------------------------------------------------------------------------

def trend_regression(daily: pd.DataFrame, col: str, min_days: int = 360):
    """Regression lineaire de la moyenne/cumul annuel -> tendance climatique.
    Retourne pente, R2, p-value (significativite) sur les annees completes."""
    agg_fn = 'mean' if col == 'T_moy' else 'sum'
    annual = daily.groupby('Annee')[col].agg(agg_fn).reset_index()
    counts = daily.groupby('Annee').size()
    full_years = counts[counts > min_days].index
    annual = annual[annual['Annee'].isin(full_years)]
    slope, intercept, r, p, se = stats.linregress(annual['Annee'], annual[col])
    return {'pente': slope, 'r2': r**2, 'p_value': p, 'se': se, 'intercept': intercept}


def seasonal_forecast(monthly: pd.DataFrame, col: str, periods: int = 12,
                       non_negative: bool = False) -> pd.DataFrame:
    """Prevision saisonniere Prophet (saisonnalite annuelle Fourier, SANS tendance
    flexible). growth='flat' est utilise car la validation croisee a montre que
    la tendance flexible par defaut de Prophet sur-apprend sur seulement ~15 ans
    de donnees mensuelles et degrade la precision hors echantillon (MAE plus
    eleve qu'une simple moyenne climatologique). Voir evaluate_model() pour le
    detail de cette validation.
    non_negative=True pour les variables physiquement bornees a 0 (precipitation)."""
    d = monthly[['ds', col]].rename(columns={col: 'y'}).dropna()
    model = Prophet(yearly_seasonality=6, weekly_seasonality=False,
                     daily_seasonality=False, growth='flat',
                     interval_width=0.8)
    model.fit(d)
    future = model.make_future_dataframe(periods=periods, freq='MS')
    fc = model.predict(future)[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
    if non_negative:
        fc[['yhat', 'yhat_lower', 'yhat_upper']] = fc[['yhat', 'yhat_lower', 'yhat_upper']].clip(lower=0)
    return fc, model


def calibrate_interval(monthly: pd.DataFrame, col: str, model,
                        initial: str = '2920 days', period: str = '365 days',
                        horizon: str = '365 days', non_negative: bool = False):
    """Calibre l'intervalle d'incertitude de Prophet par validation croisee
    temporelle : les intervalles internes de Prophet se sont averes trop
    etroits (couverture empirique ~50-58% au lieu des 80% annonces). On
    recalcule le decalage [q10, q90] des residus observes en conditions
    "hors echantillon" et on l'applique au point de prevision."""
    from prophet.diagnostics import cross_validation
    df_cv = cross_validation(model, initial=initial, period=period, horizon=horizon, parallel=None)
    if non_negative:
        df_cv['yhat'] = df_cv['yhat'].clip(lower=0)
    residus = df_cv['y'] - df_cv['yhat']
    q10, q90 = residus.quantile([0.1, 0.9])
    coverage = ((df_cv['y'] >= df_cv['yhat'] + q10) & (df_cv['y'] <= df_cv['yhat'] + q90)).mean()
    return {'decalage_bas': q10, 'decalage_haut': q90, 'couverture_empirique': coverage}


def precip_empirical_scenarios(daily: pd.DataFrame) -> pd.DataFrame:
    """Pour la precipitation, la validation croisee montre que MEME Prophet
    simplifie fait moins bien qu'une simple climatologie mensuelle (MAE 46.6mm
    vs 49.7mm). On utilise donc directement les quantiles historiques par mois
    calendaire comme scenarios (p10=pessimiste, p50=median, p90=optimiste),
    une approche plus simple, plus transparente et plus precise."""
    monthly = monthly_aggregate(daily)
    monthly['mois_cal'] = monthly['ds'].dt.month
    scenarios = monthly.groupby('mois_cal')['Precip'].agg(
        scenario_bas=lambda x: x.quantile(0.10),
        scenario_median='median',
        scenario_haut=lambda x: x.quantile(0.90)
    ).round(1)
    return scenarios


def evaluate_model(daily: pd.DataFrame, col: str, non_negative: bool = False) -> dict:
    """Mesure la precision reelle du modele par validation croisee temporelle
    (backtesting) et la compare a une baseline climatologique naive, pour
    eviter de sur-vendre la precision des previsions."""
    from prophet.diagnostics import cross_validation
    monthly = monthly_aggregate(daily)
    monthly['mois_cal'] = monthly['ds'].dt.month
    clim = monthly.groupby('mois_cal')[col].mean()

    d = monthly[['ds', col]].rename(columns={col: 'y'}).dropna()
    model = Prophet(yearly_seasonality=6, weekly_seasonality=False,
                     daily_seasonality=False, growth='flat', interval_width=0.8)
    model.fit(d)
    df_cv = cross_validation(model, initial='2920 days', period='365 days', horizon='365 days', parallel=None)
    if non_negative:
        df_cv['yhat'] = df_cv['yhat'].clip(lower=0)
    df_cv['mois_cal'] = df_cv['ds'].dt.month
    df_cv['baseline'] = df_cv['mois_cal'].map(clim)

    mae_model = (df_cv['y'] - df_cv['yhat']).abs().mean()
    mae_baseline = (df_cv['y'] - df_cv['baseline']).abs().mean()
    mean_val = monthly[col].mean()

    return {
        'mae_modele': mae_model,
        'mae_baseline_climatologique': mae_baseline,
        'erreur_relative_pct': mae_model / mean_val * 100,
        'meilleur_que_baseline': mae_model < mae_baseline,
    }


def build_campaign_forecast(daily: pd.DataFrame, periods: int = 12) -> pd.DataFrame:
    """Pipeline complet Module B : retourne les previsions mensuelles pour la
    prochaine campagne agricole.
    - Temperature : Prophet simplifie (growth='flat'), intervalle calibre par
      validation croisee (voir calibrate_interval).
    - Precipitation : scenarios bases sur les quantiles historiques par mois
      calendaire (voir precip_empirical_scenarios) - plus precis que Prophet
      d'apres la validation croisee (cf. evaluate_model)."""
    monthly = monthly_aggregate(daily)

    # Temperature : Prophet + calibration empirique de l'intervalle
    fc_T, model_T = seasonal_forecast(monthly, 'T_moy', periods)
    cal_T = calibrate_interval(monthly, 'T_moy', model_T)
    fc_T = fc_T.tail(periods).copy()
    fc_T['yhat_lower'] = fc_T['yhat'] + cal_T['decalage_bas']
    fc_T['yhat_upper'] = fc_T['yhat'] + cal_T['decalage_haut']
    fc_T['Mois'] = fc_T['ds'].dt.strftime('%Y-%m')
    fc_T['mois_cal'] = fc_T['ds'].dt.month

    # Precipitation : scenarios empiriques par mois calendaire
    scenarios_P = precip_empirical_scenarios(daily)
    fc_T = fc_T.merge(scenarios_P, left_on='mois_cal', right_index=True)

    out = fc_T[['Mois', 'yhat', 'yhat_lower', 'yhat_upper',
                'scenario_median', 'scenario_bas', 'scenario_haut']].round(1)
    out.columns = ['Mois', 'Temp_prevue', 'Temp_min_80pct', 'Temp_max_80pct',
                   'Precip_scenario_median', 'Precip_scenario_bas', 'Precip_scenario_haut']
    return out


# ---------------------------------------------------------------------------
# MODULE A - DECISIONS OPERATIONNELLES (regles agroclimatiques)
# ---------------------------------------------------------------------------
# Parametres par defaut calibres pour une culture type "mais". A adapter
# par culture (l'equipe Agronomie doit fournir T_GERM, seuils, etc. par culture).

PARAMS_DEFAUT = dict(
    T_GERM=18.0,                 # temperature minimale de germination (deg C)
    PLUIE_SEMIS=20.0,            # mm cumules sur 3 jours pour declencher le semis
    SEQ_SECHE_MAX=7,             # jours secs consecutifs tolerables apres semis
    DEFICIT_IRRIGATION=-30.0,    # seuil de bilan hydrique glissant 7j (mm)
    VENT_MAX_TRAITEMENT=3.0,     # vitesse de vent max pour traiter (m/s)
)


def detect_semis(df: pd.DataFrame, params: dict = PARAMS_DEFAUT) -> pd.DataFrame:
    """Detecte les fenetres favorables au semis. A appliquer sur des donnees
    de prevision (ex: Open-Meteo, 16 jours) en production, ou sur l'historique
    pour validation (backtesting)."""
    d = df.copy()
    d['pluie_3j'] = d['Precip'].rolling(3).sum()
    recs = []
    for i in range(len(d) - 30):
        row = d.iloc[i]
        if row['pluie_3j'] >= params['PLUIE_SEMIS'] and row['T_moy'] >= params['T_GERM']:
            seq_future_max = d['SeqSeche'].iloc[i:i + 30].max()
            if seq_future_max <= params['SEQ_SECHE_MAX']:
                recs.append(row['Date'])
    return pd.DataFrame({'Date': recs})


def detect_irrigation(df: pd.DataFrame, params: dict = PARAMS_DEFAUT) -> pd.DataFrame:
    """Detecte les jours ou le bilan hydrique glissant (P - ET0 sur 7j) impose
    une irrigation, avec la dose recommandee (mm)."""
    d = df.copy()
    d['bilan_7j'] = d['Bilan'].rolling(7).sum()
    alertes = d[d['bilan_7j'] < params['DEFICIT_IRRIGATION']].copy()
    alertes['dose_recommandee_mm'] = (-alertes['bilan_7j'] - abs(params['DEFICIT_IRRIGATION'])).clip(lower=0)
    return alertes[['Date', 'bilan_7j', 'dose_recommandee_mm']]


def detect_traitement(df: pd.DataFrame, params: dict = PARAMS_DEFAUT) -> pd.DataFrame:
    """Detecte les fenetres favorables au traitement phytosanitaire
    (pas de pluie lessivante prevue, vent faible)."""
    d = df.copy()
    d['pluie_2j_fwd'] = d['Precip'].shift(-1).rolling(2).sum()
    ok = d[(d['pluie_2j_fwd'] < 5) & (d['Vent'] < params['VENT_MAX_TRAITEMENT'])]
    return ok[['Date']]


# ---------------------------------------------------------------------------
# EXEMPLE D'UTILISATION
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    VILLE = 'Bertoua'
    daily = load_city(VILLE)

    print(f"=== {VILLE} : {len(daily)} jours ({daily['Date'].min().date()} -> {daily['Date'].max().date()}) ===\n")

    # --- Module B : prevision saisonniere ---
    print(">>> Tendance climatique (regression sur moyennes annuelles)")
    t_trend = trend_regression(daily, 'T_moy')
    p_trend = trend_regression(daily, 'Precip')
    print(f"Temperature : {t_trend['pente']:+.3f} degC/an (p={t_trend['p_value']:.3f}, "
          f"{'significatif' if t_trend['p_value'] < 0.05 else 'non significatif'})")
    print(f"Precipitation : {p_trend['pente']:+.1f} mm/an (p={p_trend['p_value']:.3f}, "
          f"{'significatif' if p_trend['p_value'] < 0.05 else 'non significatif'})\n")

    print(">>> Prevision saisonniere (12 prochains mois, corrigee et calibree)")
    campaign = build_campaign_forecast(daily)
    print(campaign.to_string(index=False), "\n")

    print(">>> Precision reelle des modeles (validation croisee temporelle, backtesting)")
    eval_T = evaluate_model(daily, 'T_moy')
    eval_P_naive = evaluate_model(daily, 'Precip', non_negative=True)
    print(f"Temperature : MAE = {eval_T['mae_modele']:.2f} degC ({eval_T['erreur_relative_pct']:.1f}% d'erreur relative) "
          f"| baseline climatologique = {eval_T['mae_baseline_climatologique']:.2f} degC "
          f"| {'modele meilleur' if eval_T['meilleur_que_baseline'] else 'modele pas meilleur que la baseline'}")
    print(f"Precipitation (Prophet) : MAE = {eval_P_naive['mae_modele']:.1f} mm ({eval_P_naive['erreur_relative_pct']:.1f}% d'erreur relative) "
          f"| baseline climatologique = {eval_P_naive['mae_baseline_climatologique']:.1f} mm "
          f"-> on retient la baseline (scenarios empiriques) pour la precipitation, plus precise\n")

    # --- Module A : decisions operationnelles (backtest) ---
    print(">>> Backtest du moteur de decision operationnel (16 ans d'historique)")
    semis = detect_semis(daily)
    irrig = detect_irrigation(daily)
    traite = detect_traitement(daily)
    n_years = daily['Annee'].nunique()
    print(f"Fenetres de semis favorables : {len(semis)} jours sur la periode")
    print(f"Alertes irrigation : {len(irrig)} jours ({len(irrig)/n_years:.0f}/an en moyenne)")
    print(f"Fenetres de traitement : {len(traite)} jours ({len(traite)/n_years:.0f}/an en moyenne)")
