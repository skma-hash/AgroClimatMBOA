# AgroClimat-Mboa

Solution numérique d'aide à la décision agricole pour une agriculture résiliente
au changement climatique dans la région de l'Est du Cameroun.

## Structure du projet

```
agrivision/
├── run.py                  # point d'entrée (lancement de l'app)
├── init_db.py               # initialise la base + comptes de démo
├── config.py                 # configuration (clé secrète, DB, chemins)
├── requirements.txt
├── data/
│   └── Final_Est_Cameroun_Journalier_9villes_Format.xlsx
├── modele_prevision_climatique.py   # Module B (climat) — déjà validé
├── module_production.py             # Module C (production/variétés) — déjà validé
└── app/
    ├── __init__.py           # application factory + gestion des erreurs
    ├── extensions.py         # instances SQLAlchemy / Login / CSRF
    ├── models.py             # User, Zone, JournalActivite, MessageContact
    ├── forms.py               # formulaires Flask-WTF (validation serveur)
    ├── utils.py                # décorateur @require_role
    ├── main/                  # accueil, à propos, contact
    ├── auth/                  # connexion / déconnexion
    ├── admin/                 # gestion des acteurs (CRUD utilisateurs)
    ├── climat/                # Module B — prévision climatique
    ├── calendrier/             # Module A×C — fenêtres de semis par variété
    ├── production/             # Module C — rendement et valeur
    ├── static/css/style.css
    └── templates/
```

**Pourquoi cette architecture (blueprints)** : chaque domaine fonctionnel
(climat, calendrier, production, admin...) est un module Flask indépendant.
Ça permet à plusieurs personnes de l'équipe de travailler sur des fonctionnalités
différentes sans conflits, et de désactiver/activer une fonctionnalité facilement.

## Installation et lancement

```bash
pip install -r requirements.txt
python init_db.py      # à faire une seule fois (crée la base + comptes de démo)
python run.py
# ouvrir http://localhost:5000
```

## Comptes de démonstration

| Email | Mot de passe | Rôle |
|---|---|---|
| admin@agrivision.cm | admin123 | Administrateur |
| conseiller@agrivision.cm | conseiller123 | Conseiller agricole |
| agriculteur@agrivision.cm | agri123 | Agriculteur |
| partenaire@agrivision.cm | partenaire123 | Partenaire institutionnel |

## Fonctionnalités par page

- **Accueil** : présentation du projet, mise en avant des 3 modules
- **À propos** : méthodologie, sources de données, limites de précision
- **Contact** : formulaire validé côté serveur (Flask-WTF), messages stockés en base
- **Climat** *(connecté)* : prévisions Prophet par ville, température + précipitation
- **Calendrier** *(connecté)* : fenêtres de semis validées par variété de maïs
- **Production** *(connecté)* : rendement, volume et valeur estimés par ville/variété/surface
- **Gestion des acteurs** *(admin uniquement)* : CRUD complet des comptes, changement de rôle, désactivation, journal d'audit

## Gestion des erreurs

Toutes les erreurs HTTP (400, 401, 403, 404, 500) passent par un template unique
(`templates/errors/erreur.html`) avec un message clair, pas de détail technique
exposé à l'utilisateur. Les erreurs de formulaire (email invalide, champ trop
court...) s'affichent en rouge sous chaque champ concerné (validation Flask-WTF).

## Sécurité incluse

- Mots de passe hashés (jamais stockés en clair)
- Protection CSRF automatique sur tous les formulaires
- Contrôle d'accès par rôle vérifié côté serveur (pas seulement caché dans le menu)
- Message d'erreur de connexion volontairement générique (anti-énumération de comptes)

## Limites connues (transparence)

- Cache de prévisions en mémoire simple (redémarrer le serveur vide le cache) —
  suffisant pour la démo, à remplacer par Redis en production (voir suggestions ci-dessous).
- Base SQLite : très bien pour la démo/le concours, à migrer vers PostgreSQL pour
  un usage multi-utilisateurs réel.
- Le formulaire de contact stocke les messages en base mais ne les envoie pas
  par email — à ajouter avec Flask-Mail si besoin.

## Bibliothèques et outils suggérés pour la suite

| Besoin | Outil recommandé | Pourquoi |
|---|---|---|
| Migrations de base de données | **Flask-Migrate** (Alembic) | Modifier les modèles sans perdre les données existantes |
| Envoi d'emails (contact, réinitialisation mdp) | **Flask-Mail** + un service SMTP (ex. Brevo, Mailgun) | Le formulaire contact stocke actuellement sans notifier |
| Cache performant | **Flask-Caching** + Redis | Remplace le dict Python actuel, survit aux redémarrages, partageable entre plusieurs workers |
| Tâches planifiées (recalcul nocturne des prévisions) | **APScheduler** ou **Celery** | Évite de recalculer Prophet à chaque requête |
| Protection anti-spam du formulaire contact | **Flask-WTF Recaptcha** | Simple à ajouter, évite les soumissions automatisées |
| Limitation de débit (anti brute-force login) | **Flask-Limiter** | Protège `/login` contre les tentatives répétées |
| Variables d'environnement / secrets | **python-dotenv** | Garde `SECRET_KEY`, mots de passe DB hors du code source |
| Suivi des erreurs en production | **Sentry** | Alerte automatique si une erreur 500 survient en prod (complète le error handler déjà en place) |
| Tests automatisés | **pytest** + **pytest-flask** | Vérifie que les routes/rôles continuent de fonctionner après chaque modification |
| Graphiques interactifs (au lieu d'images statiques) | **Plotly** (via CDN + JS) | Zoom, survol des points ; remplacerait les images matplotlib actuelles |
| Carte régionale interactive | **Leaflet.js** ou **Folium** | Pour la page "carte des 9 villes" évoquée précédemment comme amélioration possible |
| Déploiement | **Gunicorn** + **Nginx**, ou simplement **Render/Railway** | `run.py` avec `debug=True` n'est pas fait pour la production |
| Conteneurisation | **Docker** | Garantit que l'app tourne pareil chez chaque membre de l'équipe et en démo |

