"""
Blueprint 'climat' -- previsions climatiques (Module B).
============================================================
Reutilise directement modele_prevision_climatique.py (deja construit et
valide precedemment). Un cache memoire simple evite de relancer Prophet
(quelques secondes) a chaque requete -- suffisant pour une demo ; en
production on precalculerait ces previsions via une tache planifiee
(voir suggestions de librairies : APScheduler / Celery).
"""

import io
import base64
import matplotlib
matplotlib.use('Agg')  # pas d'interface graphique disponible sur un serveur web
import matplotlib.pyplot as plt

from flask import Blueprint, render_template, current_app
from flask_login import login_required

from modele_prevision_climatique import load_city, monthly_aggregate, seasonal_forecast, calibrate_interval

climat_bp = Blueprint('climat', __name__, template_folder='../templates/climat')

_cache = {}  # {ville: (monthly, fc_T, fc_P)}


def _fig_to_base64(fig):
    """Convertit une figure matplotlib en chaine base64 pour l'inserer
    directement dans le HTML (evite d'ecrire des fichiers images sur disque)."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=110, bbox_inches='tight')
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return encoded


def _get_forecast(ville):
    if ville in _cache:
        return _cache[ville]
    daily = load_city(ville, path=current_app.config['DATA_PATH'])
    monthly = monthly_aggregate(daily)
    fc_T, model_T = seasonal_forecast(monthly, 'T_moy', periods=12)
    cal_T = calibrate_interval(monthly, 'T_moy', model_T)
    fc_T['yhat_lower'] = fc_T['yhat'] + cal_T['decalage_bas']
    fc_T['yhat_upper'] = fc_T['yhat'] + cal_T['decalage_haut']
    fc_P, _ = seasonal_forecast(monthly, 'Precip', periods=12, non_negative=True)
    _cache[ville] = (monthly, fc_T, fc_P)
    return _cache[ville]


@climat_bp.route('/')
@climat_bp.route('/<ville>')
@login_required
def index(ville=None):
    villes = current_app.config['VILLES']
    ville = ville or villes[0]
    if ville not in villes:
        # Ville inconnue dans l'URL -> 404 propre plutot qu'une KeyError brute
        from flask import abort
        abort(404)

    monthly, fc_T, fc_P = _get_forecast(ville)

    fig1, ax1 = plt.subplots(figsize=(9, 3.4))
    ax1.plot(monthly['ds'], monthly['T_moy'], '.', color='#888', alpha=0.4, label='Observé')
    ax1.plot(fc_T['ds'], fc_T['yhat'], color='#d62728', label='Prévision')
    ax1.fill_between(fc_T['ds'], fc_T['yhat_lower'], fc_T['yhat_upper'], color='#d62728', alpha=0.18, label='Intervalle 80%')
    ax1.legend(fontsize=8)
    ax1.set_ylabel("°C")
    img_temp = _fig_to_base64(fig1)

    fig2, ax2 = plt.subplots(figsize=(9, 3.4))
    ax2.bar(monthly['ds'], monthly['Precip'], width=20, color='#888', alpha=0.4, label='Observé')
    ax2.plot(fc_P['ds'], fc_P['yhat'], color='#1f77b4', label='Prévision')
    ax2.fill_between(fc_P['ds'], fc_P['yhat_lower'], fc_P['yhat_upper'], color='#1f77b4', alpha=0.18)
    ax2.legend(fontsize=8)
    ax2.set_ylabel("mm/mois")
    img_precip = _fig_to_base64(fig2)

    # Indicateurs basés sur les prévisions Prophet (12 prochains mois)
    indicateurs = {
        'temp_moy': f"{fc_T['yhat'].iloc[-12:].mean():.1f}",
        'precip_moy': f"{fc_P['yhat'].iloc[-12:].mean():.0f}",
    }

    return render_template('climat/index.html', villes=villes, ville_selectionnee=ville,
                            img_temp=img_temp, img_precip=img_precip, indicateurs=indicateurs)
