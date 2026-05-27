"""Envoie un récap hebdomadaire à la boîte RH entreprise (MAIL_RH).

Le récap liste toutes les demandes de congé en attente (validation responsable
ou validation RH). Si aucune demande n'est en attente : aucun email envoyé.

Usage en production (Windows IIS, planificateur de tâches) :

    cd C:\\inetpub\\ERPAC\\Gestion_Conges
    .venv\\Scripts\\python.exe scripts\\recap_hebdo.py

Programmer dans le Planificateur de tâches Windows : tous les lundis à 08:00.
Sur Linux : crontab "0 8 * * 1 cd /opt/gestion-conges && venv/bin/python scripts/recap_hebdo.py".

Sortie console : code retour 0 si succès (email envoyé ou rien à envoyer),
1 si erreur de configuration.
"""
import os
import sys
from datetime import datetime, timezone

# Permet de lancer le script depuis n'importe où en ajoutant la racine du projet au sys.path.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def main() -> int:
    from app import create_app
    from models import db  # noqa: F401 (assure l'import des modèles)
    from models.conge import Conge

    app = create_app()
    with app.app_context():
        mail_rh = (app.config.get("MAIL_RH") or "").strip()
        if not mail_rh:
            app.logger.warning("MAIL_RH non configuré : récap hebdo ignoré.")
            return 1

        demandes_rows = (
            Conge.query.filter(
                Conge.statut.in_(["en_attente_responsable", "en_attente_rh"])
            )
            .order_by(Conge.cree_le.asc())
            .all()
        )

        if not demandes_rows:
            app.logger.info("Récap hebdo : aucune demande en attente, pas d'envoi.")
            return 0

        now = datetime.now(timezone.utc)
        demandes = []
        for c in demandes_rows:
            u = c.utilisateur
            nom_salarie = f"{u.prenom} {u.nom}" if u else "Salarié supprimé"
            periode = f"{c.date_debut.strftime('%d/%m/%Y')} - {c.date_fin.strftime('%d/%m/%Y')}"
            # cree_le peut être naïf (sqlite) → on l'aligne sur UTC pour la soustraction
            cree_le = c.cree_le
            if cree_le is not None and cree_le.tzinfo is None:
                cree_le = cree_le.replace(tzinfo=timezone.utc)
            age_jours = (now - cree_le).days if cree_le else 0
            demandes.append({
                "nom_salarie": nom_salarie,
                "periode": periode,
                "nb_jours": c.nb_jours_ouvrables or 0,
                "type_conge": c.type_conge or "CP",
                "statut": c.statut,
                "age_jours": age_jours,
            })

        from services.email import envoyer_recap_hebdo_rh
        ok = envoyer_recap_hebdo_rh(demandes)
        if ok:
            app.logger.info("Récap hebdo envoyé à %s (%d demande(s)).", mail_rh, len(demandes))
            return 0
        else:
            app.logger.error("Récap hebdo : échec d'envoi.")
            return 1


if __name__ == "__main__":
    sys.exit(main())
