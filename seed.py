"""Script d'initialisation de la base de donnÃ©es.
CrÃ©e le compte admin RH, les salariÃ©s, le paramÃ©trage annuel et les jours fÃ©riÃ©s.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from datetime import date
from app import create_app
from models import db
from models.user import User
from models.parametrage import ParametrageAnnuel, AllocationConge
from models.jour_ferie import JourFerie
from routes.auth import hash_password
from services.jours_feries import get_jours_feries


def seed():
    app = create_app()
    with app.app_context():
        # Check if already seeded
        if User.query.first():
            print("La base de donnÃ©es contient dÃ©jÃ  des donnÃ©es.")
            print("Supprimez le fichier gestion_conges.db pour rÃ©initialiser.")
            return

        print("=== Initialisation de la base de donnÃ©es ===")
        print()

        # 1. Create admin RH account
        admin = User(
            nom="ADMIN",
            prenom="RH",
            identifiant="admin",
            mot_de_passe_hash=hash_password("admin"),
            role="rh",
            actif=True,
        )
        db.session.add(admin)
        print("[OK] Compte admin RH crÃ©Ã© (identifiant: admin / mot de passe: admin)")

        # 2. Create employees
        salaries = [
            ("BLANC", "Pierre"),
            ("BOUSSARD", "MichaÃ«l"),
            ("BRUERRE", "David"),
            ("DE CARVALHO", "Carlos"),
            ("DUNOYE", "StÃ©phane"),
            ("GAUTHE", "SÃ©bastien"),
            ("GUIROUX", "Pascal"),
            ("JEANNESSON", "Quentin"),
            ("KOZAK", "FranÃ§ois"),
            ("LAURENT", "David"),
            ("LOUIS", "SÃ©bastien"),
            ("MONNOIR", "Jean-Marie"),
            ("PETILLOT", "VÃ©ronique"),
            ("PROVOST", "Adrien"),
            ("ROUX", "Isabelle"),
            ("ROUX", "Philippe"),
            ("ROUX", "KÃ©vin"),
            ("TURLIER", "StÃ©phane"),
        ]

        users_created = []
        for nom, prenom in salaries:
            # Generate unique identifier: first letter of prenom + nom in lowercase
            base_id = (prenom[0] + nom).lower().replace(" ", "")
            identifiant = base_id
            # Handle duplicates
            counter = 1
            while User.query.filter_by(identifiant=identifiant).first():
                counter += 1
                identifiant = f"{base_id}{counter}"

            user = User(
                nom=nom,
                prenom=prenom,
                identifiant=identifiant,
                mot_de_passe_hash=hash_password("changeme"),
                role="salarie",
                actif=True,
            )
            db.session.add(user)
            db.session.flush()  # Get the ID
            users_created.append(user)
            print(f"[OK] SalariÃ© crÃ©Ã© : {prenom} {nom} (identifiant: {identifiant})")

        # 3. Create annual parameters (exercise 2025-2026)
        param = ParametrageAnnuel(
            debut_exercice=date(2025, 6, 1),
            fin_exercice=date(2026, 5, 31),
            jours_conges_defaut=25,
            actif=True,
        )
        db.session.add(param)
        db.session.flush()
        print()
        print(f"[OK] ParamÃ©trage annuel crÃ©Ã© : 01/06/2025 - 31/05/2026 (25 jours par dÃ©faut)")

        # 4. Create allocations for each employee from CSV data
        allocations_data = {
            "BLANC": (22, 1),
            "BOUSSARD": (31, 12),
            "BRUERRE": (28, 12),
            "DE CARVALHO": (33, 19),
            "DUNOYE": (30, 0),
            "GAUTHE": (27, 10),
            "GUIROUX": (30, 6),
            "JEANNESSON": (0, 0),
            "KOZAK": (25, 3),
            "LAURENT": (25, 3),
            "LOUIS": (1, 20),
            "MONNOIR": (28, 23),
            "PETILLOT": (0, 2),
            "PROVOST": (9, 0),
            "ROUX_Isabelle": (29, 21),
            "ROUX_Philippe": (0, 0),
            "ROUX_KÃ©vin": (25, 1),
            "TURLIER": (25, 3),
        }

        for user in users_created:
            key = user.nom
            if user.nom == "ROUX":
                key = f"ROUX_{user.prenom}"
            data = allocations_data.get(key, (25, 0))
            jours_cp, jours_anc = data

            alloc = AllocationConge(
                user_id=user.id,
                parametrage_id=param.id,
                jours_alloues=jours_cp,
                jours_anciennete=jours_anc,
                jours_report=0,
            )
            db.session.add(alloc)

        print(f"[OK] Allocations crÃ©Ã©es pour {len(users_created)} salariÃ©s")

        # 5. Load French public holidays for 2025 and 2026
        count = 0
        for annee in [2025, 2026]:
            feries = get_jours_feries(annee)
            for date_f, libelle in feries:
                jf = JourFerie(
                    date_ferie=date_f,
                    libelle=libelle,
                    annee=annee,
                    auto_genere=True,
                )
                db.session.add(jf)
                count += 1

        print(f"[OK] {count} jours fÃ©riÃ©s chargÃ©s (2025-2026)")

        # Commit all
        db.session.commit()
        print()
        print("=== Initialisation terminÃ©e avec succÃ¨s ! ===")
        print()
        print("Pour dÃ©marrer l'application :")
        print("  python app.py")
        print()
        print("Connexion RH : admin / admin")
        print("Connexion salariÃ© : (ex: pblanc / changeme)")


if __name__ == "__main__":
    seed()
