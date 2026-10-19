"""
Blueprint 'main' -- pages publiques generales.
=================================================
Accueil, A propos, Contact. Ces pages ne necessitent pas de connexion :
elles constituent la vitrine publique du projet.
"""

from flask import Blueprint, render_template, flash, redirect, url_for, current_app

from app.extensions import db
from app.forms import ContactForm
from app.models import MessageContact

main_bp = Blueprint('main', __name__, template_folder='../templates/main')


@main_bp.route('/')
def accueil():
    return render_template('main/accueil.html')


@main_bp.route('/a-propos')
def a_propos():
    return render_template('main/a_propos.html')


@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    # form.validate_on_submit() verifie a la fois que c'est une requete POST
    # ET que les validateurs (DataRequired, Email, Length...) passent tous.
    if form.validate_on_submit():
        msg = MessageContact(
            nom=form.nom.data,
            email=form.email.data,
            sujet=form.sujet.data,
            message=form.message.data,
        )
        db.session.add(msg)
        db.session.commit()
        flash("Votre message a bien été envoyé. Nous vous répondrons rapidement.", "succes")
        # Redirect apres POST reussi (pattern Post/Redirect/Get) : evite qu'un
        # rechargement de page (F5) ne soumette le formulaire une seconde fois.
        return redirect(url_for('main.contact'))
    return render_template('main/contact.html', form=form)
