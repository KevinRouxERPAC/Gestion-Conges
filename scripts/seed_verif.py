"""Seed d'une base de DEMO pour la vérification fonctionnelle (mixte).

Crée 3 comptes (RH / responsable / salarié rattaché au responsable), un exercice
actif et des allocations CP/RTT. À lancer avec SQLALCHEMY_DATABASE_URI pointant
sur une base jetable, p.ex. :

    SECRET_KEY=dev SQLALCHEMY_DATABASE_URI=sqlite:///verif_demo.db \
        .venv/Scripts/python.exe scripts/seed_verif.py
"""
from datetime import date

from app import create_app
from models import db
from models.user import User
from models.parametrage import ParametrageAnnuel, AllocationConge
from services.auth_utils import hash_password

PWD = "demo1234"


def main():
    app = create_app()
    with app.app_context():
        db.create_all()

        rh = User(nom="RH", prenom="Alice", identifiant="rh",
                  mot_de_passe_hash=hash_password(PWD), role="rh",
                  date_embauche=date(2015, 1, 1))
        resp = User(nom="Resp", prenom="Bob", identifiant="resp",
                    mot_de_passe_hash=hash_password(PWD), role="responsable",
                    date_embauche=date(2016, 1, 1))
        db.session.add_all([rh, resp])
        db.session.flush()

        sal = User(nom="Salarie", prenom="Carla", identifiant="sal",
                   mot_de_passe_hash=hash_password(PWD), role="salarie",
                   date_embauche=date(2020, 6, 1), responsable_id=resp.id)
        db.session.add(sal)
        db.session.flush()

        param = ParametrageAnnuel(
            debut_exercice=date(2026, 1, 1), fin_exercice=date(2026, 12, 31),
            jours_conges_defaut=25, actif=True,
        )
        db.session.add(param)
        db.session.flush()

        for u in (rh, resp, sal):
            db.session.add(AllocationConge(
                user_id=u.id, parametrage_id=param.id,
                jours_alloues=25, jours_anciennete=2, jours_report=3,
                rtt_heures_allouees=70, rtt_heures_reportees=0,
            ))

        db.session.commit()
        print("Seed OK. Comptes (mot de passe = %s):" % PWD)
        for u in User.query.all():
            print(" -", u.identifiant, "/", u.role, "resp=%s" % u.responsable_id)


if __name__ == "__main__":
    main()
