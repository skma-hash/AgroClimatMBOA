"""
Blueprint 'auth' -- connexion / deconnexion.
===============================================
"""

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.forms import LoginForm
from app.models import User

auth_bp = Blueprint('auth', __name__, template_folder='../templates/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.accueil'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        # Message volontairement generique (ne pas reveler si c'est l'email
        # ou le mot de passe qui est incorrect -- limite les attaques par
        # enumeration de comptes existants).
        if user is None or not user.check_password(form.mot_de_passe.data):
            flash("Email ou mot de passe incorrect.", "erreur")
        elif not user.actif:
            flash("Ce compte a été désactivé. Contactez un administrateur.", "erreur")
        else:
            login_user(user)
            flash(f"Bienvenue, {user.nom}.", "succes")
            return redirect(url_for('main.accueil'))

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for('main.accueil'))
