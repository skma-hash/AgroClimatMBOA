"""
Initialise la base de donnees : tables, zones (9 villes), et comptes de
demonstration (un par role). A executer une seule fois avant le premier
lancement, ou pour reinitialiser la demo.

Usage : python init_db.py
"""

from app import create_app
from app.extensions import db
from app.models import User, Zone

app = create_app()

with app.app_context():
    db.drop_all()
    db.create_all()

    zones = {}
    for nom in app.config['VILLES']:
        z = Zone(nom=nom)
        db.session.add(z)
        zones[nom] = z
    db.session.commit()

    comptes = [
        ("Administrateur", "admin@agrivision.cm", "admin123", "admin", None),
        ("Conseiller Bertoua", "conseiller@agrivision.cm", "conseiller123", "conseiller", "Bertoua"),
        ("Agriculteur Test", "agriculteur@agrivision.cm", "agri123", "agriculteur", "Bertoua"),
        ("MINADER (partenaire)", "partenaire@agrivision.cm", "partenaire123", "partenaire", None),
    ]

    utilisateurs = {}
    for nom, email, mdp, role, ville in comptes:
        u = User(nom=nom, email=email, role=role,
                 zone_id=zones[ville].id if ville else None)
        u.set_password(mdp)
        db.session.add(u)
        utilisateurs[email] = u
    db.session.commit()

    # Le conseiller de demo supervise l'agriculteur de demo
    utilisateurs["conseiller@agrivision.cm"].agriculteurs_supervises.append(
        utilisateurs["agriculteur@agrivision.cm"]
    )
    db.session.commit()

    print("Base de donnees initialisee avec succes.\n")
    print("Comptes de demonstration :")
    for nom, email, mdp, role, ville in comptes:
        print(f"  {email:<28} / {mdp:<15} ({role})")
