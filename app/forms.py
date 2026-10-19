"""
Formulaires (Flask-WTF).
==========================
Flask-WTF ajoute automatiquement un jeton CSRF a chaque formulaire et permet
une validation cote serveur declarative (obligatoire pour la securite : la
validation cote client/JS peut toujours etre contournee).
"""

from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, PasswordField, SelectField, FloatField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange

from app.models import ROLES


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    mot_de_passe = PasswordField("Mot de passe", validators=[DataRequired()])


class ContactForm(FlaskForm):
    """Formulaire de la page Contact (public, sans connexion requise)."""
    nom = StringField("Nom complet", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    sujet = StringField("Sujet", validators=[DataRequired(), Length(min=3, max=200)])
    message = TextAreaField("Message", validators=[DataRequired(), Length(min=10, max=3000)])


class UtilisateurForm(FlaskForm):
    """Formulaire admin de creation/modification d'un compte acteur."""
    nom = StringField("Nom complet", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    role = SelectField("Rôle", choices=[(r, r.capitalize()) for r in ROLES], validators=[DataRequired()])
    zone_id = SelectField("Zone", coerce=int, validators=[Optional()])
    # Mot de passe optionnel en modification (vide = ne pas changer), obligatoire en creation
    # -- cette regle conditionnelle est appliquee manuellement dans la route, pas ici.
    mot_de_passe = PasswordField("Mot de passe", validators=[Optional(), Length(min=6)])


class SelectionForm(FlaskForm):
    """Formulaire reutilise sur les pages Climat / Calendrier / Production
    pour choisir une ville (et une variete, si applicable)."""
    ville = SelectField("Ville", validators=[DataRequired()])
    variete = SelectField("Variété de maïs", validators=[Optional()])
    surface_ha = FloatField("Surface (hectares)", validators=[Optional(), NumberRange(min=0.1, max=10000)])
