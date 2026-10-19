"""
Configuration de l'application AgriVision.
============================================
Les valeurs sensibles (cle secrete, URI base de donnees) devraient etre
fournies via variables d'environnement en production -- ici on fournit des
valeurs par defaut pratiques pour le developpement local / la demo.
"""

import os

# config.py est a la racine du projet : BASE_DIR est simplement son dossier
# parent (pas besoin de remonter un niveau supplementaire).
BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # Cle secrete utilisee pour signer les sessions et les jetons CSRF.
    # A DEFINIR VIA VARIABLE D'ENVIRONNEMENT EN PRODUCTION (ne jamais committer
    # une vraie cle secrete dans le code source).
    SECRET_KEY = os.environ.get('SECRET_KEY', 'cle-secrete-dev-a-changer-en-production')

    # Base de donnees SQLite par defaut (suffisant pour la demo / le concours).
    # Pour une mise en production reelle, remplacer par PostgreSQL, ex:
    #   postgresql://utilisateur:motdepasse@hote:5432/agrivision
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', f"sqlite:///{os.path.join(BASE_DIR, 'agrivision.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # desactive un suivi couteux et inutile ici

    # Chemin vers le fichier de donnees climatiques (NASA POWER, 9 villes).
    # Par defaut : le fichier fourni dans le dossier data/ du projet, pour que
    # l'application soit autonome (fonctionne des le telechargement, sans
    # dependance a un chemin propre a l'environnement de developpement).
    DATA_PATH = os.environ.get(
        'DATA_PATH',
        os.path.join(BASE_DIR, 'data', 'Final_Est_Cameroun_Journalier_9villes_Format.xlsx')
    )

    VILLES = ['Bertoua', 'Batouri', 'Abong-Mbang', 'Yokadouma', 'Garoua-Boulai',
              'Moloundou', 'Lomie', 'Ndelele', 'Kette']
