"""
Application factory.
=======================
On utilise le pattern "application factory" (create_app()) plutot qu'une
instance Flask() globale : ca permet de creer plusieurs instances de l'app
(utile pour les tests), et ca evite les imports circulaires puisque chaque
blueprint importe les extensions deja initialisees depuis app.extensions
plutot que depuis un module app.py qui les creerait lui-meme.
"""

from flask import Flask, render_template

from config import Config
from app.extensions import db, login_manager, csrf


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # --- Initialisation des extensions ---
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return User.query.get(int(user_id))

    # --- Enregistrement des blueprints (un par domaine fonctionnel) ---
    from app.main.routes import main_bp
    from app.auth.routes import auth_bp
    from app.admin.routes import admin_bp
    from app.climat.routes import climat_bp
    from app.calendrier.routes import calendrier_bp
    from app.production.routes import production_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(climat_bp, url_prefix='/climat')
    app.register_blueprint(calendrier_bp, url_prefix='/calendrier')
    app.register_blueprint(production_bp, url_prefix='/production')

    # --- Gestion des erreurs -------------------------------------------------
    # Chaque handler renvoie une page dediee avec un message clair pour
    # l'utilisateur, plutot que la page d'erreur brute par defaut de Flask
    # (qui expose des details techniques inutiles/inappropries pour un
    # utilisateur final).
    register_error_handlers(app)

    return app


def register_error_handlers(app):
    @app.errorhandler(400)
    def erreur_requete_invalide(e):
        return render_template('errors/erreur.html',
                                code=400, titre="Requête invalide",
                                message="La requête envoyée est incorrecte ou incomplète."), 400

    @app.errorhandler(401)
    def erreur_non_authentifie(e):
        return render_template('errors/erreur.html',
                                code=401, titre="Connexion requise",
                                message="Vous devez être connecté pour accéder à cette page."), 401

    @app.errorhandler(403)
    def erreur_acces_refuse(e):
        return render_template('errors/erreur.html',
                                code=403, titre="Accès refusé",
                                message="Vous n'avez pas les droits nécessaires pour accéder à cette page."), 403

    @app.errorhandler(404)
    def erreur_page_introuvable(e):
        return render_template('errors/erreur.html',
                                code=404, titre="Page introuvable",
                                message="La page que vous cherchez n'existe pas ou a été déplacée."), 404

    @app.errorhandler(500)
    def erreur_serveur(e):
        # En production, on ne montre jamais le detail de l'exception a
        # l'utilisateur (fuite d'information) -- seulement un message generique.
        # Le detail technique reste disponible cote serveur (logs).
        db.session.rollback()  # annule toute transaction en cours restee incoherente
        return render_template('errors/erreur.html',
                                code=500, titre="Erreur interne",
                                message="Une erreur inattendue est survenue. Notre équipe a été notifiée."), 500
