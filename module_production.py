"""
MODULE C - Estimation de la production et choix varietal (mais)
=================================================================
Adaptation en Python de la logique agronomique du modele STICS (Brisson et al.,
INRAE) pour simuler la croissance et le rendement du mais. Le logiciel officiel
JavaSTICS (Java/Fortran, distribue par l'INRAE) n'est pas installable dans cet
environnement : ce module reimplemente les equations publiees de STICS
(phenologie en temps thermique, dynamique de LAI, interception du rayonnement,
accumulation de biomasse par efficience de conversion du rayonnement, formation
du rendement par indice de recolte), pilotees par les donnees reelles du
dataset (temperature, rayonnement, ET0, precipitation).

Sources parametres varietaux : IRAD Cameroun (cf. litterature IRAD, zones
ecologiques). Sol : ferralitique argileux typique de l'Est Cameroun (cf.
litterature pedologique regionale). Prix : bulletins MINADER 2025-2026.
"""

import pandas as pd
import numpy as np
from modele_prevision_climatique import load_city, detect_semis

# ---------------------------------------------------------------------------
# PARAMETRES VARIETAUX (source : IRAD Cameroun)
# ---------------------------------------------------------------------------
# GDD_total estime a partir du cycle publie (jours) x (T_moyenne_ref - Tbase),
# avec T_moyenne_ref = 24 degC (moyenne typique Est Cameroun) et Tbase = 8 degC.
# C'est une approximation : IRAD publie des cycles en jours, pas en degres-jours.

TBASE = 8.0  # temperature de base de developpement du mais (deg C)
T_REF = 24.0  # temperature de reference utilisee pour convertir cycle(jours) -> GDD

VARIETES = {
    'CMS_8806_precoce': {
        'cycle_jours_ref': 95, 'LAImax': 3.0, 'HI': 0.40,
        'rdt_potentiel_litt': 4.5,  # t/ha (milieu de la fourchette IRAD 4-5 t/ha)
        'zone_ecologique': 'Savane',
    },
    'CMS_8704_intermediaire': {
        'cycle_jours_ref': 108, 'LAImax': 4.0, 'HI': 0.45,
        'rdt_potentiel_litt': 7.0,  # t/ha (milieu de la fourchette IRAD 6-8 t/ha)
        'zone_ecologique': 'Foret humide (= Est Cameroun)',
    },
    'Hybride_41_tardif': {
        'cycle_jours_ref': 148, 'LAImax': 5.5, 'HI': 0.48,
        'rdt_potentiel_litt': 12.5,  # t/ha (milieu de la fourchette IRAD 11-14 t/ha)
        'zone_ecologique': 'Hautes terres (reference hors-zone, comparateur)',
    },
}
for v in VARIETES.values():
    v['GDD_total'] = (T_REF - TBASE) * v['cycle_jours_ref']
    v['GDD_emergence'] = 0.08 * v['GDD_total']
    v['GDD_floraison'] = 0.55 * v['GDD_total']

# ---------------------------------------------------------------------------
# PARAMETRES SOL (ferralitique argileux, Est Cameroun)
# ---------------------------------------------------------------------------
SOL_EST_CAMEROUN = {
    'RU_max_mm': 150.0,     # reserve utile en eau, sol argileux, profondeur racinaire mais (~100cm)
    'seuil_stress_frac': 0.5,  # fraction de la RU en dessous de laquelle le stress hydrique demarre (FAO-56)
}

# Coefficients culturaux Kc (FAO-56, mais) par phase
KC_INITIAL, KC_MID, KC_FIN = 0.35, 1.18, 0.65

# Rayonnement : fraction PAR du rayonnement global, coefficient d'extinction
FRAC_PAR = 0.48
K_EXTINCTION = 0.7
RUE_MAX_DEFAUT = 3.2  # g MS / MJ PAR intercepte (valeur de litterature, sera recalibree)

PRECIP_MIN_CYCLE = 500.0  # mm minimum sur le cycle (seuil agronomique, cf. MINADER)


# ---------------------------------------------------------------------------
# SIMULATION D'UN CYCLE (du semis a la maturite)
# ---------------------------------------------------------------------------

def simulate_cycle(daily: pd.DataFrame, sowing_date, variete: dict, rue_max: float,
                    sol: dict = SOL_EST_CAMEROUN, max_days: int = 200) -> dict:
    """Simule un cycle de mais a partir d'une date de semis donnee.
    Retourne le rendement grain (t/ha), la biomasse totale, le stress hydrique
    moyen autour de la floraison, et la duree reelle du cycle (jours)."""
    d = daily[daily['Date'] >= sowing_date].head(max_days).reset_index(drop=True)
    if len(d) < max_days * 0.5 or d['T_moy'].isna().any():
        return None

    GDD_total = variete['GDD_total']
    GDD_emerg = variete['GDD_emergence']
    GDD_flor = variete['GDD_floraison']
    LAImax = variete['LAImax']
    HI = variete['HI']

    W = sol['RU_max_mm'] * 0.7  # reserve initiale (hypothese : sol pas totalement sec au semis)
    cum_gdd = 0.0
    MS_total = 0.0  # g/m2
    stress_flor = []
    jour_maturite = None

    for i, row in d.iterrows():
        tj = max(0, row['T_moy'] - TBASE)
        cum_gdd += tj
        if cum_gdd >= GDD_total:
            jour_maturite = i
            break

        # --- Phenologie : fraction du cycle ---
        if cum_gdd < GDD_emerg:
            lai = 0.05
            kc = KC_INITIAL
        elif cum_gdd < GDD_flor:
            frac = (cum_gdd - GDD_emerg) / (GDD_flor - GDD_emerg)
            lai = LAImax / (1 + np.exp(-10 * (frac - 0.5)))
            kc = KC_INITIAL + (KC_MID - KC_INITIAL) * frac
        else:
            frac_sen = (cum_gdd - GDD_flor) / (GDD_total - GDD_flor)
            lai = LAImax * (1 - 0.8 * frac_sen)
            kc = KC_MID + (KC_FIN - KC_MID) * frac_sen

        # --- Bilan hydrique (reservoir sol, type FAO-56) ---
        stress = min(1.0, W / (sol['RU_max_mm'] * sol['seuil_stress_frac'])) if sol['RU_max_mm'] > 0 else 1.0
        stress = max(0.15, stress)  # stress residuel minimal (la plante ne meurt pas instantanement)
        etr = row['ET0'] * kc * stress
        W = np.clip(W + row['Precip'] - etr, 0, sol['RU_max_mm'])

        if abs(cum_gdd - GDD_flor) < 0.05 * GDD_total:
            stress_flor.append(stress)

        # --- Interception du rayonnement + biomasse ---
        par_incident = row['Rayon'] * FRAC_PAR
        par_intercepte = par_incident * (1 - np.exp(-K_EXTINCTION * lai))
        MS_total += rue_max * stress * par_intercepte

    if jour_maturite is None:
        return None  # cycle non acheve dans la fenetre (ex: semis trop tardif)

    stress_flor_moy = np.mean(stress_flor) if stress_flor else 1.0
    HI_effectif = HI * (0.5 + 0.5 * stress_flor_moy)  # HI reduit si stress a la floraison
    rendement_g_m2 = MS_total * HI_effectif
    rendement_t_ha = rendement_g_m2 / 100.0  # g/m2 -> t/ha

    precip_cycle = d['Precip'].iloc[:jour_maturite + 1].sum()

    return {
        'rendement_t_ha': rendement_t_ha,
        'biomasse_totale_t_ha': MS_total / 100.0,
        'stress_hydrique_floraison': stress_flor_moy,
        'duree_cycle_jours': jour_maturite + 1,
        'precip_cycle_mm': precip_cycle,
        'precip_suffisante': precip_cycle >= PRECIP_MIN_CYCLE,
    }


# ---------------------------------------------------------------------------
# CALIBRATION DU RUE (pour reproduire le rendement potentiel IRAD, sans stress)
# ---------------------------------------------------------------------------

def calibrate_rue(daily: pd.DataFrame, variete: dict, sowing_dates,
                   rue_range=(1.5, 5.0)) -> float:
    """Calibre RUE_max pour que le rendement simule SANS stress hydrique
    (sol maintenu a 100% de la RU) reproduise le rendement potentiel publie
    par l'IRAD pour cette variete. Recherche par dichotomie simple."""
    sol_sans_stress = {'RU_max_mm': 10000.0, 'seuil_stress_frac': 0.0001}
    target = variete['rdt_potentiel_litt']

    lo, hi = rue_range
    for _ in range(25):
        mid = (lo + hi) / 2
        yields = []
        for sd in sowing_dates[:5]:  # echantillon de dates pour accelerer
            res = simulate_cycle(daily, sd, variete, mid, sol=sol_sans_stress)
            if res:
                yields.append(res['rendement_t_ha'])
        if not yields:
            lo = mid
            continue
        simulated = np.mean(yields)
        if simulated < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ---------------------------------------------------------------------------
# PIPELINE COMPLET PAR VILLE
# ---------------------------------------------------------------------------

def run_production_analysis(ville: str, n_years_sample: int = 16) -> dict:
    """Pour une ville donnee : calibre chaque variete, simule le rendement sur
    les dates de semis favorables detectees historiquement, et retourne les
    resultats (rendement moyen, variabilite, risque) par variete."""
    daily = load_city(ville)
    semis = detect_semis(daily)
    semis['Annee'] = pd.to_datetime(semis['Date']).dt.year

    # Une date de semis par annee (premiere fenetre favorable de l'annee)
    sowing_dates = semis.groupby('Annee')['Date'].min().tolist()
    sowing_dates = [pd.Timestamp(d) for d in sowing_dates]

    results = {}
    for nom, variete in VARIETES.items():
        rue_calibre = calibrate_rue(daily, variete, sowing_dates)
        yields, stress_list, precip_ok_list, durees = [], [], [], []
        for sd in sowing_dates:
            res = simulate_cycle(daily, sd, variete, rue_calibre)
            if res:
                yields.append(res['rendement_t_ha'])
                stress_list.append(res['stress_hydrique_floraison'])
                precip_ok_list.append(res['precip_suffisante'])
                durees.append(res['duree_cycle_jours'])

        if not yields:
            continue

        results[nom] = {
            'rue_calibre': rue_calibre,
            'rendement_moyen_t_ha': np.mean(yields),
            'rendement_std_t_ha': np.std(yields),
            'rendement_min_t_ha': np.min(yields),
            'rendement_max_t_ha': np.max(yields),
            'stress_floraison_moyen': np.mean(stress_list),
            'pct_annees_precip_suffisante': np.mean(precip_ok_list) * 100,
            'duree_cycle_moyenne_jours': np.mean(durees),
            'n_annees_simulees': len(yields),
            'score_risque_ajuste': np.mean(yields) - 0.5 * np.std(yields),
        }
    return {'ville': ville, 'resultats': results}


def estimate_production_value(rendement_t_ha: float, surface_ha: float = 1.0,
                               prix_fcfa_kg: float = 180.0) -> dict:
    """Convertit un rendement en volume et valeur de production, pour une
    surface donnee. Prix par defaut : moyenne indicative MINADER 2025-2026
    (150-230 FCFA/kg selon zone/saison)."""
    volume_t = rendement_t_ha * surface_ha
    valeur_fcfa = volume_t * 1000 * prix_fcfa_kg
    return {'volume_tonnes': volume_t, 'valeur_fcfa': valeur_fcfa, 'valeur_millions_fcfa': valeur_fcfa / 1e6}


# ---------------------------------------------------------------------------
# FENETRES DE SEMIS SPECIFIQUES A LA VARIETE (Module A x Module C)
# ---------------------------------------------------------------------------
# Le Module A initial (detect_semis) utilisait une regle generique "mais" :
# court-terme (pluie sur 3 jours + pas de secheresse dans les 30 jours suivants).
# Cette regle est insuffisante pour differencier les varietes : une variete
# tardive (148j) peut passer le filtre court-terme puis manquer d'eau bien
# plus tard, pres de sa floraison, si elle est semee trop pres de la fin de
# la saison des pluies. On combine donc :
#   1) le filtre court-terme (viabilite de la germination, deja valide)
#   2) une simulation complete du cycle (via simulate_cycle) pour verifier
#      que CETTE variete, semee CE jour, atteint un stress hydrique acceptable
#      a la floraison et une pluviometrie cumulee suffisante sur tout le cycle.

STRESS_FLORAISON_MIN = 0.55  # en-dessous, le stress hydrique a la floraison est juge trop risque


def detect_semis_par_variete(daily: pd.DataFrame, variete: dict,
                              params_court_terme: dict = None,
                              rue_calibre: float = None,
                              pas_echantillonnage: int = 3) -> pd.DataFrame:
    """Version specifique-variete de la detection de fenetres de semis.
    Reprend le filtre court-terme generique (germination) puis ne retient que
    les dates qui, une fois simulees sur tout le cycle de LA VARIETE consideree,
    n'entrainent pas de stress hydrique excessif a la floraison ni de deficit
    pluviometrique cumule.
    pas_echantillonnage : pour limiter le cout de calcul, on simule 1 jour
    candidat sur N (les resultats sont lisses sur le mois, donc peu sensibles
    a ce sous-echantillonnage)."""
    from modele_prevision_climatique import detect_semis, PARAMS_DEFAUT

    params = params_court_terme or PARAMS_DEFAUT
    candidats = detect_semis(daily, params)
    candidats = candidats.iloc[::pas_echantillonnage].reset_index(drop=True)

    if rue_calibre is None:
        rue_calibre = calibrate_rue(daily, variete, list(candidats['Date']))

    validees = []
    for d in candidats['Date']:
        res = simulate_cycle(daily, pd.Timestamp(d), variete, rue_calibre)
        if res is not None and res['stress_hydrique_floraison'] >= STRESS_FLORAISON_MIN and res['precip_suffisante']:
            validees.append(d)

    out = pd.DataFrame({'Date': pd.to_datetime(validees)})
    out['Mois'] = out['Date'].dt.month
    return out, rue_calibre


def comparer_fenetres_semis(ville: str) -> dict:
    """Calcule, pour une ville donnee, la distribution mensuelle des fenetres
    de semis validees pour chacune des 3 varietes, et les compare a la regle
    generique initiale (Module A d'origine, non specifique a la variete)."""
    from modele_prevision_climatique import load_city, detect_semis

    daily = load_city(ville)
    generique = detect_semis(daily)
    generique['Mois'] = pd.to_datetime(generique['Date']).dt.month

    resultats = {'generique': generique}
    for nom, variete in VARIETES.items():
        validees, rue = detect_semis_par_variete(daily, variete)
        resultats[nom] = validees
    return resultats


if __name__ == '__main__':
    VILLES = ['Bertoua', 'Batouri', 'Abong-Mbang', 'Yokadouma', 'Garoua-Boulai',
              'Moloundou', 'Lomie', 'Ndelele', 'Kette']

    all_results = []
    for ville in VILLES:
        print(f"=== {ville} ===")
        try:
            out = run_production_analysis(ville)
        except Exception as e:
            print(f"  Erreur : {e}")
            continue
        for nom, r in out['resultats'].items():
            print(f"  {nom:28s} | rendement = {r['rendement_moyen_t_ha']:.2f} +/- {r['rendement_std_t_ha']:.2f} t/ha "
                  f"| stress floraison = {r['stress_floraison_moyen']:.2f} "
                  f"| pluie suffisante {r['pct_annees_precip_suffisante']:.0f}% des annees")
            all_results.append({'ville': ville, 'variete': nom, **r})

    df_all = pd.DataFrame(all_results)
    df_all.to_csv('resultats_production_toutes_villes.csv', index=False)

    print("\n=== VARIETE OPTIMALE PAR VILLE (score risque-ajuste) ===")
    best = df_all.loc[df_all.groupby('ville')['score_risque_ajuste'].idxmax()]
    print(best[['ville', 'variete', 'rendement_moyen_t_ha', 'rendement_std_t_ha']].to_string(index=False))
