"""Rappels automatiques pour les demandes en attente et la fin d'exercice.

Phase 3b : génère des notifications in-app (+ Web Push si abonné) pour :
- les demandes en attente de validation depuis trop longtemps (responsable
  et RH),
- les salariés ayant un solde CP élevé à l'approche de la fin d'exercice,
- la RH pour le récap des demandes en attente.

Conçu pour être appelé périodiquement (ex. via APScheduler ou un script CLI).
Idempotent : ne notifie pas deux fois la même demande le même jour grâce au
champ `type` des notifications (préfixe `rappel_` + conge_id + date).
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from models import db
from models.conge import Conge
from models.notification import Notification
from models.parametrage import ParametrageAnnuel
from models.user import User
from services.solde import get_parametrage_actif, calculer_solde

logger = logging.getLogger(__name__)

# Délai avant lequel une demande en attente devient "en retard" (en jours).
DELAI_RAPPEL_JOURS = 3
# Seuil de solde CP déclenchant un rappel à l'approche de la fin d'exercice.
SEUIL_CP_RESTANT_RAPPEL = 10
# Fenêtre avant la fin d'exercice pour commencer les rappels (en jours).
FENETRE_FIN_EXERCICE_JOURS = 90


def _deja_notifie_aujourdhui(user_id: int, type_notif: str) -> bool:
    """Un rappel a-t-il déjà été envoyé aujourd'hui pour ce user/type ?

    On compare sur la date du jour local (Europe/Paris) : une notification créée
    à 23h00 Paris (21h00 UTC) ne doit pas être renvoyée à 08h00 Paris le lendemain.
    On stocke donc le début du jour local comme borne basse.
    """
    from datetime import timezone
    aujourd_hui = date.today()
    # Début du jour local en UTC : on prend 00:00 local converti en UTC.
    # Approximation simple : pour Europe/Paris (UTC+1/+2), 00:00 local = 23:00 UTC
    # la veille. On utilise un offset fixe de -1j + minuit pour rester prudent.
    debut_jour_utc = datetime.combine(aujourd_hui, datetime.min.time()) - timedelta(hours=2)
    return (
        Notification.query.filter(
            Notification.user_id == user_id,
            Notification.type == type_notif,
            Notification.cree_le >= debut_jour_utc,
        ).first()
        is not None
    )


def _notifier(user_id: int, type_notif: str, titre: str, message: str, conge_id: int | None = None) -> bool:
    """Crée une notification si pas déjà envoyée aujourd'hui (idempotence).

    Retourne True si une notification a été créée, False sinon.
    """
    if _deja_notifie_aujourdhui(user_id, type_notif):
        return False
    from services.notifications import creer_notification
    creer_notification(
        user_id=user_id, type_notif=type_notif, titre=titre,
        message=message, conge_id=conge_id,
    )
    return True


def rappels_demandes_en_attente() -> int:
    """Notifie les responsables/RH des demandes en attente depuis trop longtemps.

    Retourne le nombre de notifications créées.
    """
    seuil_date = date.today() - timedelta(days=DELAI_RAPPEL_JOURS)
    nb = 0

    # Demandes en attente responsable.
    conges_resp = (
        Conge.query.filter(
            Conge.statut == "en_attente_responsable",
            Conge.cree_le <= seuil_date,
        ).all()
    )
    for c in conges_resp:
        u = c.utilisateur
        if not u or not u.responsable_id:
            continue
        jours_attente = (date.today() - c.cree_le.date()).days
        created = _notifier(
            user_id=u.responsable_id,
            type_notif=f"rappel_attente_resp_{c.id}",
            titre="Demande en attente de validation",
            message=(
                f"{u.prenom} {u.nom} : demande du {c.date_debut.strftime('%d/%m/%Y')} "
                f"en attente depuis {jours_attente} jour(s)."
            ),
            conge_id=c.id,
        )
        if created:
            nb += 1

    # Demandes en attente RH (niveau 2).
    conges_rh = (
        Conge.query.filter(
            Conge.statut == "en_attente_rh",
            Conge.cree_le <= seuil_date,
        ).all()
    )
    rh_users = User.query.filter(
        db.func.lower(User.role) == "rh", User.actif == True
    ).all()
    for c in conges_rh:
        u = c.utilisateur
        if not u:
            continue
        jours_attente = (date.today() - c.cree_le.date()).days
        for rh in rh_users:
            created = _notifier(
                user_id=rh.id,
                type_notif=f"rappel_attente_rh_{c.id}",
                titre="Demande en attente de validation RH",
                message=(
                    f"{u.prenom} {u.nom} : demande du {c.date_debut.strftime('%d/%m/%Y')} "
                    f"en attente depuis {jours_attente} jour(s)."
                ),
                conge_id=c.id,
            )
            if created:
                nb += 1

    db.session.commit()
    return nb


def rappels_fin_exercice() -> int:
    """Notifie les salariés ayant un solde CP élevé à l'approche de la fin d'exercice.

    Retourne le nombre de notifications créées.
    """
    param = get_parametrage_actif()
    if not param:
        return 0

    today = date.today()
    jours_restants = (param.fin_exercice - today).days
    if jours_restants < 0 or jours_restants > FENETRE_FIN_EXERCICE_JOURS:
        return 0

    salaries = User.query.filter_by(actif=True).all()
    nb = 0
    for s in salaries:
        solde = calculer_solde(s.id)
        cp_restant = solde.get("solde_restant", 0)
        if cp_restant < SEUIL_CP_RESTANT_RAPPEL:
            continue
        created = _notifier(
            user_id=s.id,
            type_notif=f"rappel_fin_exercice_{today.isoformat()}",
            titre="Solde CP à prendre",
            message=(
                f"Il vous reste {cp_restant} jour(s) de congés payés et la fin "
                f"d'exercice est dans {jours_restants} jour(s) "
                f"({param.fin_exercice.strftime('%d/%m/%Y')}). "
                f"Pensez à poser vos congés restants."
            ),
        )
        if created:
            nb += 1

    db.session.commit()
    return nb


def envoyer_rappels() -> dict:
    """Point d'entrée unique : envoie tous les rappels et retourne un bilan.

    À appeler périodiquement (ex. une fois par jour via le scheduler APScheduler
    ou un script CLI).
    """
    try:
        n1 = rappels_demandes_en_attente()
    except Exception:
        logger.exception("Rappels demandes en attente : erreur.")
        n1 = 0
    try:
        n2 = rappels_fin_exercice()
    except Exception:
        logger.exception("Rappels fin d'exercice : erreur.")
        n2 = 0
    logger.info("Rappels : %d demande(s) en attente, %d fin d'exercice.", n1, n2)
    return {"en_attente": n1, "fin_exercice": n2}
