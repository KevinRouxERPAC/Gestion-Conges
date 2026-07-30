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
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta

from models import db
from models.heures_hebdo import HeuresHebdo
from models.parametrage import ParametrageAnnuel
from models.user import User
from services.erp.connexion import erp_connexion
from services.erp.requetes import (
    heures_periode,
    heures_semaine,
    normaliser_matricule_erp,
    salaries_erp,
)
from services.rtt_hebdo import maj_rtt_allocations_hebdo

logger = logging.getLogger(__name__)


@dataclass
class RapportSyncExercice:
    """Bilan d'un import ERP couvrant plusieurs semaines (ex. tout l'exercice)."""
    semaines: list[str] = field(default_factory=list)
    nb_importes: int = 0
    nb_skipped_sans_matricule: int = 0
    nb_skipped_sans_user: int = 0
    avertissements: list[str] = field(default_factory=list)
    rtt_recalcule: bool = False
    dry_run: bool = False
    preview: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.nb_importes >= 0


@dataclass
class RapportSync:
    semaine_erp: str
    date_lundi: date
    nb_importes: int = 0
    nb_skipped_sans_matricule: int = 0
    nb_skipped_sans_user: int = 0
    avertissements: list[str] = field(default_factory=list)
    rtt_recalcule: bool = False
    # Mode aperçu (dry_run) : aucune écriture en base. Les lignes prévues pour
    # import sont listées dans `preview` pour que la RH valide avant d'écraser.
    dry_run: bool = False
    preview: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.nb_importes >= 0


def _normaliser_nom(nom: str) -> str:
    """Normalise un nom pour rapprochement robuste (accents/casse/espaces)."""
    txt = unicodedata.normalize("NFKD", nom or "")
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    return " ".join(txt.upper().split())


def _index_users_par_matricule() -> dict[str, int]:
    """Index matricule canonique → user_id (salariés actifs)."""
    index: dict[str, int] = {}
    for u in User.query.filter(User.actif == True, User.matricule.isnot(None)).all():
        if not u.matricule:
            continue
        canon = normaliser_matricule_erp(u.matricule)
        if canon:
            index[canon] = u.id
    return index


def _auto_rattacher_matricules(
    *,
    inconnus: set[str],
    users_par_matricule: dict[str, int],
    rapport: RapportSync,
    conn,
    dry_run: bool,
    noms_erp_par_matricule: dict[str, str] | None = None,
) -> None:
    """Rattache automatiquement des matricules ERP à des salariés sans matricule.

    Règle de sécurité : on ne rattache que si le nom complet ERP correspond
    exactement (après normalisation) à un unique salarié actif sans matricule.
    """
    if not inconnus:
        return

    if noms_erp_par_matricule is None:
        rows = salaries_erp(conn)
        nom_erp_par_matricule = {
            r.matricule: r.nom_complet for r in rows if r.matricule in inconnus and r.nom_complet
        }
    else:
        nom_erp_par_matricule = {
            mat: nom for mat, nom in noms_erp_par_matricule.items() if mat in inconnus and nom
        }
    if not nom_erp_par_matricule:
        return

    users_sans_matricule = User.query.filter(
        User.actif == True, User.matricule.is_(None)
    ).all()
    users_par_nom: dict[str, list[User]] = {}
    for u in users_sans_matricule:
        for cle in (
            _normaliser_nom(f"{u.nom} {u.prenom}"),
            _normaliser_nom(f"{u.prenom} {u.nom}"),
        ):
            users_par_nom.setdefault(cle, []).append(u)

    users_deja_rattaches: set[int] = set()
    for mat, nom_erp in nom_erp_par_matricule.items():
        if mat in users_par_matricule:
            continue
        cle = _normaliser_nom(nom_erp)
        candidats = users_par_nom.get(cle, [])
        # Déduplique si le salarié est indexé sous nom prénom ET prénom nom.
        candidats = list({u.id: u for u in candidats}.values())
        if len(candidats) != 1:
            continue
        user = candidats[0]
        if user.id in users_deja_rattaches:
            continue
        users_deja_rattaches.add(user.id)
        if dry_run:
            rapport.avertissements.append(
                f"Matricule ERP {mat!r} : rapprochement possible avec {user.prenom} {user.nom} "
                "(aperçu, non appliqué)."
            )
            continue
        user.matricule = normaliser_matricule_erp(mat)
        users_par_matricule[normaliser_matricule_erp(mat)] = user.id
        rapport.avertissements.append(
            f"Matricule ERP {mat!r} auto-rattaché à {user.prenom} {user.nom}."
        )


def _lundi(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _semaine_erp_depuis_date(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso[0]}{iso[1]:02d}"


def _semaines_erp_exercice(param: ParametrageAnnuel, jusqu_a: date | None = None) -> list[str]:
    """Codes AAAASS des semaines couvrant l'exercice actif, jusqu'à aujourd'hui par défaut."""
    debut = param.debut_exercice
    fin = min(param.fin_exercice, jusqu_a or date.today())
    lundi = _lundi(debut)
    fin_lundi = _lundi(fin)
    semaines: list[str] = []
    while lundi <= fin_lundi:
        semaines.append(_semaine_erp_depuis_date(lundi))
        lundi += timedelta(days=7)
    return semaines


def _preparer_import_erp(
    lignes,
    *,
    rapport,
    conn,
    dry_run: bool,
) -> tuple[dict[str, int], dict[str, str]]:
    """Index matricules + auto-rattachement avant import des lignes ERP."""
    users_par_matricule = _index_users_par_matricule()
    salaries = salaries_erp(conn)
    noms_erp_par_matricule = {
        s.matricule: s.nom_complet for s in salaries if s.matricule and s.nom_complet
    }
    inconnus = {
        normaliser_matricule_erp(l.matricule)
        for l in lignes
        if l.matricule and normaliser_matricule_erp(l.matricule) not in users_par_matricule
    }
    _auto_rattacher_matricules(
        inconnus=inconnus,
        users_par_matricule=users_par_matricule,
        rapport=rapport,
        conn=conn,
        dry_run=dry_run,
        noms_erp_par_matricule=noms_erp_par_matricule,
    )
    return users_par_matricule, noms_erp_par_matricule


def _importer_lignes_erp(
    lignes,
    *,
    users_par_matricule: dict[str, int],
    noms_erp_par_matricule: dict[str, str],
    rapport,
    dry_run: bool,
) -> None:
    """Importe des lignes ERP (une ou plusieurs semaines) dans heures_hebdo."""
    for ligne in lignes:
        mat = normaliser_matricule_erp(ligne.matricule)
        if not mat:
            rapport.nb_skipped_sans_matricule += 1
            continue

        user_id = users_par_matricule.get(mat)
        if user_id is None:
            rapport.nb_skipped_sans_user += 1
            nom_erp = noms_erp_par_matricule.get(mat)
            suffixe_nom = f" (ERP : {nom_erp})" if nom_erp else ""
            rapport.avertissements.append(
                f"Matricule ERP {mat!r}{suffixe_nom} absent de l'app (aucun utilisateur avec ce matricule). "
                "Renseignez-le via RH > Gestion des salariés > Modifier."
            )
            continue

        date_lundi = _lundi_depuis_semaine_erp(ligne.semaine_erp)
        row = HeuresHebdo.query.filter_by(user_id=user_id, date_lundi=date_lundi).first()
        action = "import"
        ancienne_valeur = None
        if row is not None and row.source == "manuel":
            rapport.avertissements.append(
                f"Matricule {mat} ({date_lundi}) : valeur manuelle conservée "
                f"({row.heures_travaillees} h saisi, ERP={ligne.heures} h)."
            )
            action = "skip_manuel"
        elif row is not None:
            ancienne_valeur = row.heures_travaillees

        if dry_run:
            rapport.preview.append({
                "matricule": mat,
                "user_id": user_id,
                "semaine_erp": ligne.semaine_erp,
                "date_lundi": date_lundi,
                "heures_erp": round(ligne.heures, 2),
                "ancienne_valeur": ancienne_valeur,
                "action": action,
            })
            if action == "import":
                rapport.nb_importes += 1
            continue

        if action == "skip_manuel":
            continue

        if row is None:
            row = HeuresHebdo(user_id=user_id, date_lundi=date_lundi, source="erp")
            db.session.add(row)

        row.heures_travaillees = round(ligne.heures, 2)
        row.source = "erp"
        rapport.nb_importes += 1


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
    dry_run: bool = False,
) -> RapportSync:
    """Importe les heures d'une semaine ERP dans heures_hebdo.

    Args:
        semaine_erp: format AAAASS (ex. '202624'). None = semaine précédente.
        recalculer_rtt: si True, recalcule rtt_heures_allouees après import.
        dry_run: si True, n'écrit rien en base et remplit ``rapport.preview``
            avec les lignes qui seraient importées (aperçu avant validation RH).

    Retourne un RapportSync avec le bilan (nb importés, avertissements...).
    """
    if semaine_erp is None:
        semaine_erp = _semaine_precedente()

    date_lundi = _lundi_depuis_semaine_erp(semaine_erp)
    rapport = RapportSync(semaine_erp=semaine_erp, date_lundi=date_lundi, dry_run=dry_run)

    with erp_connexion() as conn:
        lignes = heures_semaine(conn, semaine_erp)
        if not lignes:
            rapport.avertissements.append(
                f"Aucune heure trouvée dans TEMPAS pour la semaine {semaine_erp}."
            )
            return rapport

        users_par_matricule, noms_erp_par_matricule = _preparer_import_erp(
            lignes, rapport=rapport, conn=conn, dry_run=dry_run
        )
        _importer_lignes_erp(
            lignes,
            users_par_matricule=users_par_matricule,
            noms_erp_par_matricule=noms_erp_par_matricule,
            rapport=rapport,
            dry_run=dry_run,
        )

    if dry_run:
        logger.info(
            "Synchro ERP (APERÇU) semaine %s : %d ligne(s) prévue(s), %d avertissement(s).",
            semaine_erp, rapport.nb_importes, len(rapport.avertissements),
        )
        return rapport

    db.session.commit()
    logger.info(
        "Synchro ERP semaine %s : %d heures importées, %d avertissements.",
        semaine_erp, rapport.nb_importes, len(rapport.avertissements),
    )

    if recalculer_rtt and rapport.nb_importes > 0:
        param = ParametrageAnnuel.query.filter_by(actif=True).first()
        if param:
            maj_rtt_allocations_hebdo(param)
            rapport.rtt_recalcule = True

    return rapport


def synchroniser_exercice(
    recalculer_rtt: bool = True,
    dry_run: bool = False,
    jusqu_a: date | None = None,
) -> RapportSyncExercice:
    """Importe toutes les heures ERP depuis le début de l'exercice actif.

    Nécessaire pour un recalcul RTT fiable : le calcul agrège toutes les semaines
    de l'exercice, pas seulement la dernière importée.
    """
    param = ParametrageAnnuel.query.filter_by(actif=True).first()
    if not param:
        rapport = RapportSyncExercice(dry_run=dry_run)
        rapport.avertissements.append("Aucun paramétrage actif. Configurez d'abord l'exercice.")
        return rapport

    semaines = _semaines_erp_exercice(param, jusqu_a=jusqu_a)
    rapport = RapportSyncExercice(semaines=semaines, dry_run=dry_run)
    if not semaines:
        rapport.avertissements.append("Aucune semaine à synchroniser sur l'exercice actif.")
        return rapport

    with erp_connexion() as conn:
        lignes = heures_periode(conn, semaines)
        if not lignes:
            rapport.avertissements.append(
                f"Aucune heure trouvée dans TEMPAS pour l'exercice "
                f"({semaines[0]} → {semaines[-1]})."
            )
            return rapport

        users_par_matricule, noms_erp_par_matricule = _preparer_import_erp(
            lignes, rapport=rapport, conn=conn, dry_run=dry_run
        )
        _importer_lignes_erp(
            lignes,
            users_par_matricule=users_par_matricule,
            noms_erp_par_matricule=noms_erp_par_matricule,
            rapport=rapport,
            dry_run=dry_run,
        )

    if dry_run:
        logger.info(
            "Synchro ERP exercice (APERÇU) %s → %s : %d ligne(s) prévue(s).",
            semaines[0], semaines[-1], rapport.nb_importes,
        )
        return rapport

    db.session.commit()
    logger.info(
        "Synchro ERP exercice %s → %s : %d heures importées.",
        semaines[0], semaines[-1], rapport.nb_importes,
    )

    if recalculer_rtt and rapport.nb_importes > 0:
        maj_rtt_allocations_hebdo(param)
        rapport.rtt_recalcule = True

    return rapport
