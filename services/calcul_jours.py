from datetime import date, timedelta
from models.jour_ferie import JourFerie
from models.conge import Conge


def get_dates_feries_set(date_debut, date_fin):
    """Retourne un set des dates fériées entre deux dates."""
    feries = JourFerie.query.filter(
        JourFerie.date_ferie >= date_debut,
        JourFerie.date_ferie <= date_fin,
    ).all()
    return {f.date_ferie for f in feries}


def _est_ouvrable(d, feries):
    return d.weekday() < 5 and d not in feries


def compter_jours_ouvrables(date_debut, date_fin):
    """Compte le nombre de jours ouvrables entre deux dates (incluses).
    Exclut les week-ends (samedi, dimanche) et les jours fériés.
    Retour : int.
    """
    if date_fin < date_debut:
        return 0

    feries = get_dates_feries_set(date_debut, date_fin)
    jours = 0
    current = date_debut
    while current <= date_fin:
        if _est_ouvrable(current, feries):
            jours += 1
        current += timedelta(days=1)
    return jours


def compter_jours_ouvrables_avec_demi(date_debut, date_fin, demi_debut=None, demi_fin=None):
    """Compte le nb de jours ouvrables avec gestion des demi-journées aux bordures.

    Sémantique :
    - Mono-jour (date_debut == date_fin) :
        * `demi_debut` ou `demi_fin` ∈ {"matin", "apres_midi"} → 0,5 si jour ouvrable.
        * sinon → 1 si jour ouvrable.
    - Multi-jours :
        * `demi_debut == "apres_midi"` : le matin du date_debut est travaillé → -0,5 si date_debut ouvrable.
        * `demi_fin == "matin"` : l'après-midi du date_fin est travaillé → -0,5 si date_fin ouvrable.

    Retour : float (potentiellement 0, 0.5, 1, 1.5, ...).
    """
    if date_fin < date_debut:
        return 0.0

    feries = get_dates_feries_set(date_debut, date_fin)

    # Mono-jour
    if date_debut == date_fin:
        if not _est_ouvrable(date_debut, feries):
            return 0.0
        if demi_debut in ("matin", "apres_midi") or demi_fin in ("matin", "apres_midi"):
            return 0.5
        return 1.0

    # Multi-jours : on part du total plein puis on retire les bordures partielles.
    total = float(compter_jours_ouvrables(date_debut, date_fin))
    if demi_debut == "apres_midi" and _est_ouvrable(date_debut, feries):
        total -= 0.5
    if demi_fin == "matin" and _est_ouvrable(date_fin, feries):
        total -= 0.5
    return max(0.0, total)


def detecter_chevauchement(user_id, date_debut, date_fin, conge_id_exclu=None):
    """Détecte si un congé chevauche un congé existant (validé ou en attente) pour un utilisateur.
    Retourne le congé en conflit ou None.
    """
    query = Conge.query.filter(
        Conge.user_id == user_id,
        Conge.date_debut <= date_fin,
        Conge.date_fin >= date_debut,
        Conge.statut.in_(["valide", "en_attente_responsable", "en_attente_rh"]),
    )
    if conge_id_exclu:
        query = query.filter(Conge.id != conge_id_exclu)

    return query.first()
