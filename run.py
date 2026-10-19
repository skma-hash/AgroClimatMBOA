"""
Point d'entree de l'application AgriVision.
==============================================
Separer ce fichier de app/__init__.py est une convention Flask standard :
`flask run` et les serveurs WSGI de production (gunicorn, etc.) cherchent
un objet "app" au niveau du module racine.

Lancement local :
    python run.py
Lancement production (exemple) :
    gunicorn run:app
"""

from app import create_app

app = create_app()

if __name__ == '__main__':
    # debug=True : recharge automatique + traceback detaille en developpement
    # uniquement. A retirer/desactiver en production (fuite d'information).
    app.run(debug=True, port=5000)
