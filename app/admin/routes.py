"""
Blueprint 'admin' -- gestion des acteurs de la plateforme.
=============================================================
Toutes les routes de ce blueprint sont protegees par @require_role('admin').
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import User, Zone, JournalActivite
from app.forms import UtilisateurForm
from app.utils import require_role

admin_bp = Blueprint('admin', __name__, template_folder='../templates/admin')


def log_action(auteur, action):
    """Enregistre une action sensible dans le journal d'audit."""
    db.session.add(JournalActivite(auteur_id=auteur.id, action=action))
    db.session.commit()


@admin_bp.route('/utilisateurs')
@login_required
@require_role('admin')
def liste_utilisateurs():
    role_filtre = request.args.get('role', '')
    requete = User.query
    if role_filtre:
        requete = requete.filter_by(role=role_filtre)
    utilisateurs = requete.order_by(User.date_creation.desc()).all()
    from app.models import ROLES
    return render_template('admin/liste_utilisateurs.html', utilisateurs=utilisateurs,
                            roles=ROLES, role_filtre=role_filtre)


@admin_bp.route('/utilisateurs/nouveau', methods=['GET', 'POST'])
@login_required
@require_role('admin')
def nouvel_utilisateur():
    form = UtilisateurForm()
    form.zone_id.choices = [(0, '— Aucune —')] + [(z.id, z.nom) for z in Zone.query.all()]

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if User.query.filter_by(email=email).first():
            flash("Un compte existe déjà avec cet email.", "erreur")
        elif not form.mot_de_passe.data:
            flash("Le mot de passe est obligatoire à la création.", "erreur")
        else:
            u = User(nom=form.nom.data.strip(), email=email, role=form.role.data,
                      zone_id=form.zone_id.data or None, actif=True)
            u.set_password(form.mot_de_passe.data)
            db.session.add(u)
            db.session.commit()
            log_action(current_user, f"Création du compte {u.email} (rôle: {u.role})")
            flash(f"Compte créé pour {u.nom}.", "succes")
            return redirect(url_for('admin.liste_utilisateurs'))

    return render_template('admin/formulaire_utilisateur.html', form=form, utilisateur=None)


@admin_bp.route('/utilisateurs/<int:user_id>/modifier', methods=['GET', 'POST'])
@login_required
@require_role('admin')
def modifier_utilisateur(user_id):
    u = User.query.get_or_404(user_id)  # get_or_404 : renvoie une 404 propre si l'id n'existe pas
    form = UtilisateurForm(obj=u)
    form.zone_id.choices = [(0, '— Aucune —')] + [(z.id, z.nom) for z in Zone.query.all()]

    if form.validate_on_submit():
        u.nom = form.nom.data.strip()
        u.role = form.role.data
        u.zone_id = form.zone_id.data or None
        if form.mot_de_passe.data:
            u.set_password(form.mot_de_passe.data)
            log_action(current_user, f"Réinitialisation du mot de passe de {u.email}")
        db.session.commit()
        log_action(current_user, f"Modification du compte {u.email} (rôle: {u.role})")
        flash(f"Compte de {u.nom} mis à jour.", "succes")
        return redirect(url_for('admin.liste_utilisateurs'))

    return render_template('admin/formulaire_utilisateur.html', form=form, utilisateur=u)


@admin_bp.route('/utilisateurs/<int:user_id>/basculer-statut', methods=['POST'])
@login_required
@require_role('admin')
def basculer_statut(user_id):
    u = User.query.get_or_404(user_id)
    if u.id == current_user.id:
        flash("Vous ne pouvez pas désactiver votre propre compte.", "erreur")
        return redirect(url_for('admin.liste_utilisateurs'))
    u.actif = not u.actif
    db.session.commit()
    log_action(current_user, f"{'Réactivation' if u.actif else 'Désactivation'} du compte {u.email}")
    flash(f"Compte de {u.nom} {'réactivé' if u.actif else 'désactivé'}.", "succes")
    return redirect(url_for('admin.liste_utilisateurs'))


@admin_bp.route('/journal')
@login_required
@require_role('admin')
def journal():
    entrees = JournalActivite.query.order_by(JournalActivite.date_action.desc()).limit(100).all()
    return render_template('admin/journal.html', entrees=entrees)
