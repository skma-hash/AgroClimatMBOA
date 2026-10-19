"""
Utilitaires partages entre blueprints.
=========================================
"""

from functools import wraps
from flask import abort
from flask_login import current_user


def require_role(*roles_autorises):
    """Decorateur de route : n'autorise l'acces qu'aux roles listes.
    Usage : @require_role('admin')  ou  @require_role('admin', 'conseiller')
    Renvoie 403 (via l'errorhandler global) si l'utilisateur connecte n'a pas
    le bon role, et redirige vers le login s'il n'est pas connecte du tout."""
    def decorateur(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)  # Non authentifie -- Flask-Login interceptera via login_required en amont si utilise conjointement
            if current_user.role not in roles_autorises:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorateur
