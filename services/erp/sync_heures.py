"""Synchronisation des heures hebdomadaires ERP → base de l'application.

Flux :
  ERP SILOG/PMI (dbo.TEMPAS, lecture seule)
    → aggrégat heures/salarié/semaine
    → heures_hebdo (source='erp', écrase si déjà saisi manuellement)
    → recalcul RTT (maj_rtt_allocations_hebdo)

Sécurité :
  - Aucune écriture vers l'ERP.
  - La correspondance salarié repose sur users.matricule (renseigné côté admin RH).
  - Les salariés sans matricule configuré sont signalés dans le rapport mais pas bloquants.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from models import db
from models.heures_hebdo import HeuresHebdo
from models.parametrage import ParametrageAnnuel
from models.user import User
from services.erp.connexion import erp_connexion
from services.erp.requetes import heures_semaine
from services.rtt_hebdo import maj_rtt_allocations_hebdo

logger = logging.getLogger(__name__)


@dataclass
class RapportSync:
    semaine_erp: str
    date_lundi: date
    nb_importes: int = 0
    nb_skipped_sans_matricule: int = 0
    nb_skipped_sans_user: int = 0
    avertissements: list[str] = field(default_factory=list)
    rtt_recalcule: bool = False

    @property
    def ok(self) -> bool:
        return self.nb_importes >= 0


def _semaine_precedente(reference: date | None = None) -> str:
    """Retourne la semaine ISO de la semaine précédente au format AAAASS."""
    today = reference or date.today()
    # ISO : lundi de la semaine précédente
    lundi_cette_semaine = today - timedelta(days=today.weekday())
    lundi_precedente = lundi_cette_semaine - timedelta(days=7)
    iso = lundi_precedente.isocalendar()
    return f"{iso[0]}{iso[1]:02d}"


def _lundi_depuis_semaine_erp(semaine_erp: str) -> date:
    """Convertit 'AAAASS' → date du lundi de cette semaine ISO."""
    annee = int(semaine_erp[:4])
    semaine = int(semaine_erp[4:])
    return date.fromisocalendar(annee, semaine, 1)


def synchroniser_semaine(
    semaine_erp: str | None = None,
    recalculer_rtt: bool = True,
) -> RapportSync:
    """Importe les heures d'une semaine ERP dans heures_hebdo.

    Args:
        semaine_erp: format AAAASS (ex. '202624'). None = semaine précédente.
        recalculer_rtt: si True, recalcule rtt_heures_allouees après import.

    Retourne un RapportSync avec le bilan (nb importés, avertissements...).
    """
    if semaine_erp is None:
        semaine_erp = _semaine_precedente()

    date_lundi = _lundi_depuis_semaine_erp(semaine_erp)
    rapport = RapportSync(semaine_erp=semaine_erp, date_lundi=date_lundi)

    # Index matricule → user_id (uniquement salariés actifs avec matricule renseigné)
    users_par_matricule: dict[str, int] = {
        u.matricule: u.id
        for u in User.query.filter(User.actif == True, User.matricule.isnot(None)).all()
        if u.matricule
    }

    with erp_connexion() as conn:
        lignes = heures_semaine(conn, semaine_erp)

    if not lignes:
        rapport.avertissements.append(
            f"Aucune heure trouvée dans TEMPAS pour la semaine {semaine_erp}."
        )
        return rapport

    for ligne in lignes:
        mat = ligne.matricule
        if not mat:
            rapport.nb_skipped_sans_matricule += 1
            continue

        user_id = users_par_matricule.get(mat)
        if user_id is None:
            rapport.nb_skipped_sans_user += 1
            rapport.avertissements.append(
                f"Matricule ERP {mat!r} absent de l'app (aucun utilisateur avec ce matricule). "
                "Renseignez le matricule via l'écran RH > Gestion des salariés."
            )
            continue

        # Upsert heures_hebdo : on remplace la valeur source='erp', on laisse
        # source='manuel' en place si la RH l'a déjà corrigée à la main.
        row = HeuresHebdo.query.filter_by(user_id=user_id, date_lundi=date_lundi).first()
        if row is None:
            row = HeuresHebdo(user_id=user_id, date_lundi=date_lundi, source="erp")
            db.session.add(row)
        elif row.source == "manuel":
            # La RH a corrigé manuellement → on ne l'écrase pas.
            rapport.avertissements.append(
                f"Matricule {mat} ({date_lundi}) : valeur manuelle conservée "
                f"({row.heures_travaillees} h saisi, ERP={ligne.heures} h)."
            )
            continue

        row.heures_travaillees = round(ligne.heures, 2)
        row.source = "erp"
        rapport.nb_importes += 1

    db.session.commit()
    logger.info(
        "Synchro ERP semaine %s : %d heures importées, %d avertissements.",
        semaine_erp, rapport.nb_importes, len(rapport.avertissements),
    )

    # Recalcul RTT sur le paramétrage actif.
    if recalculer_rtt and rapport.nb_importes > 0:
        param = ParametrageAnnuel.query.filter_by(actif=True).first()
        if param:
            maj_rtt_allocations_hebdo(param)
            rapport.rtt_recalcule = True

    return rapport
