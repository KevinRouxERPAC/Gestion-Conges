from datetime import date, timedelta
from models import db
from models.jour_ferie import JourFerie
from models.conge import Conge


def get_dates_feries_set(date_debut, date_fin):
    """Retourne un set des dates fÃ©riÃ©es entre deux dates."""
    feries = JourFerie.query.filter(
        JourFerie.date_ferie >= date_debut,
        JourFerie.date_ferie <= date_fin,
    ).all()
    return {f.date_ferie for f in feries}


def compter_jours_ouvrables(date_debut, date_fin):
    """Compte le nombre de jours ouvrables entre deux dates (incluses).
    Exclut les week-ends (samedi, dimanche) et les jours fÃ©riÃ©s.
    """
    if date_fin < date_debut:
        return 0

    feries = get_dates_feries_set(date_debut, date_fin)
    jours = 0
    current = date_debut
    while current <= date_fin:
        # 0=lundi, 5=samedi, 6=dimanche
        if current.weekday() < 5 and current not in feries:
            jours += 1
        current += timedelta(days=1)
    return jours


def detecter_chevauchement(user_id, date_debut, date_fin, conge_id_exclu=None):
    """DÃ©tecte si un congÃ© chevauche un congÃ© existant pour un utilisateur.
    Retourne le congÃ© en conflit ou None.
    """
    query = Conge.query.filter(
        Conge.user_id == user_id,
        Conge.date_debut <= date_fin,
        Conge.date_fin >= date_debut,
    )
    if conge_id_exclu:
        query = query.filter(Conge.id != conge_id_exclu)

    return query.first()
