"""
Blueprint 'calendrier' -- fenetres de semis specifiques a la variete (Module A x C).
=======================================================================================
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64

from flask import Blueprint, render_template, current_app, abort
from flask_login import login_required

from modele_prevision_climatique import load_city
from module_production import VARIETES, detect_semis_par_variete

calendrier_bp = Blueprint('calendrier', __name__, template_folder='../templates/calendrier')

_cache = {}  # {(ville, variete): DataFrame des fenetres validees}

SEASON_SEGMENTS = [
    {'nom': 'Saison sèche', 'mois': [12, 1, 2], 'couleur': '#f0c040'},
    {'nom': 'Première saison des pluies', 'mois': [3, 4, 5, 6], 'couleur': '#8cc152'},
    {'nom': 'Coupure de saison', 'mois': [7, 8], 'couleur': '#f7a35c'},
    {'nom': 'Deuxième saison des pluies', 'mois': [9, 10, 11], 'couleur': '#4f86f7'},
]


def _fig_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=110, bbox_inches='tight')
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return encoded


@calendrier_bp.route('/')
@calendrier_bp.route('/<ville>/<variete>')
@login_required
def index(ville=None, variete=None):
    villes = current_app.config['VILLES']
    ville = ville or villes[0]
    variete = variete or list(VARIETES.keys())[1]  # CMS_8704 (recommandee) par defaut

    if ville not in villes or variete not in VARIETES:
        abort(404)

    cle = (ville, variete)
    if cle not in _cache:
        daily = load_city(ville, path=current_app.config['DATA_PATH'])
        fenetres, _ = detect_semis_par_variete(daily, VARIETES[variete])
        _cache[cle] = fenetres
    fenetres = _cache[cle]

    # Graphique : distribution mensuelle des fenetres validees
    mois_labels = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']
    counts = fenetres['Mois'].value_counts().reindex(range(1, 13), fill_value=0)
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.bar([mois_labels[m - 1] for m in counts.index], counts.values, color='#2ca02c', alpha=0.85)
    ax.set_ylabel("Nb de jours favorables (cumul 16 ans)")
    img_calendrier = _fig_to_base64(fig)

    meilleur_mois_idx = counts.idxmax()
    meilleur_mois = mois_labels[meilleur_mois_idx - 1] if counts.max() > 0 else "aucun"

    saison_map = {}
    for segment in SEASON_SEGMENTS:
        for m in segment['mois']:
            saison_map[m] = segment

    mois_info = []
    for numero in range(1, 13):
        saison = saison_map[numero]
        mois_info.append({
            'numero': numero,
            'nom': mois_labels[numero - 1],
            'count': int(counts.loc[numero]),
            'saison': saison['nom'],
            'couleur': saison['couleur'],
            'favorable': bool(counts.loc[numero] > 0),
        })

    season_counts = []
    for segment in SEASON_SEGMENTS:
        total = int(counts.loc[segment['mois']].sum())
        season_counts.append({'nom': segment['nom'], 'total': total, 'couleur': segment['couleur'], 'mois': segment['mois']})

    return render_template('calendrier/index.html', villes=villes, varietes=VARIETES,
                            ville_selectionnee=ville, variete_selectionnee=variete,
                            img_calendrier=img_calendrier, meilleur_mois=meilleur_mois,
                            nb_fenetres=len(fenetres), mois_info=mois_info,
                            seasons=season_counts)
