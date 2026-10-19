"""
Instances des extensions Flask.
=================================
Ces objets sont crees ici (sans application liee) puis initialises dans
create_app() via extension.init_app(app). Ce decoupage est le pattern
standard Flask pour eviter les imports circulaires entre les blueprints
et l'application factory.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = 'auth.login'
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
login_manager.login_message_category = "avertissement"
