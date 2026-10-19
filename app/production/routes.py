"""
Blueprint 'production' -- estimation du rendement et de la valeur (Module C).
================================================================================
"""

from flask import Blueprint, render_template, current_app, abort, request

from flask_login import login_required

from module_production import VARIETES, run_production_analysis, estimate_production_value

production_bp = Blueprint('production', __name__, template_folder='../templates/production')

_cache = {}  # {ville: resultats par variete}


@production_bp.route('/')
@production_bp.route('/<ville>')
@login_required
def index(ville=None):
    villes = current_app.config['VILLES']
    ville = ville or villes[0]
    if ville not in villes:
        abort(404)

    surface_ha = request.args.get('surface', default=1.0, type=float)
    if surface_ha <= 0:
        surface_ha = 1.0  # protection simple contre une valeur absurde/negative dans l'URL

    if ville not in _cache:
        # Calcul potentiellement long (~15-20s, calibration + simulation sur 16 ans
        # x 3 varietes) -- mis en cache memoire pour la duree de vie du serveur.
        out = run_production_analysis(ville)
        _cache[ville] = out['resultats']
    resultats = _cache[ville]

    lignes = []
    for nom, r in resultats.items():
        valeur = estimate_production_value(r['rendement_moyen_t_ha'], surface_ha=surface_ha)
        lignes.append({
            'nom': nom,
            'label': VARIETES[nom].get('zone_ecologique', ''),
            'rendement': round(r['rendement_moyen_t_ha'], 2),
            'ecart_type': round(r['rendement_std_t_ha'], 2),
            'precip_ok_pct': round(r['pct_annees_precip_suffisante']),
            'volume_tonnes': round(valeur['volume_tonnes'], 2),
            'valeur_millions_fcfa': round(valeur['valeur_millions_fcfa'], 2),
            'recommandee': nom == 'CMS_8704_intermediaire',
        })

    return render_template('production/index.html', villes=villes, ville_selectionnee=ville,
                            surface_ha=surface_ha, lignes=lignes)
