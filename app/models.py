"""
Modeles de donnees.
=====================
Quatre roles d'acteurs : agriculteur, conseiller, admin, partenaire.
Voir la conversation de conception : l'admin peut creer/modifier/desactiver
n'importe quel compte ; un conseiller supervise plusieurs agriculteurs.
"""

from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db

ROLES = ['agriculteur', 'conseiller', 'admin', 'partenaire']


class Zone(db.Model):
    __tablename__ = 'zones'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(80), unique=True, nullable=False)

    def __repr__(self):
        return f"<Zone {self.nom}>"


# Table d'association : un conseiller supervise plusieurs agriculteurs (many-to-many)
affectations = db.Table(
    'affectations',
    db.Column('conseiller_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('agriculteur_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mot_de_passe_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='agriculteur')
    zone_id = db.Column(db.Integer, db.ForeignKey('zones.id'), nullable=True)
    actif = db.Column(db.Boolean, default=True, nullable=False)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)

    zone = db.relationship('Zone', backref='utilisateurs')

    agriculteurs_supervises = db.relationship(
        'User', secondary=affectations,
        primaryjoin=(affectations.c.conseiller_id == id),
        secondaryjoin=(affectations.c.agriculteur_id == id),
        backref='conseillers',
    )

    def set_password(self, mot_de_passe):
        """Ne jamais stocker un mot de passe en clair : on stocke un hash sale
        (werkzeug utilise PBKDF2 par defaut)."""
        self.mot_de_passe_hash = generate_password_hash(mot_de_passe)

    def check_password(self, mot_de_passe):
        return check_password_hash(self.mot_de_passe_hash, mot_de_passe)

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class JournalActivite(db.Model):
    """Journal d'audit simple : trace les actions administratives sensibles."""
    __tablename__ = 'journal_activite'
    id = db.Column(db.Integer, primary_key=True)
    auteur_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(255), nullable=False)
    date_action = db.Column(db.DateTime, default=datetime.utcnow)

    auteur = db.relationship('User')


class MessageContact(db.Model):
    """Messages soumis via le formulaire de contact du site public."""
    __tablename__ = 'messages_contact'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    sujet = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    date_envoi = db.Column(db.DateTime, default=datetime.utcnow)
    traite = db.Column(db.Boolean, default=False)
