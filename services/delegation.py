"""Helpers pour résoudre les délégations de validation niveau 1."""
from datetime import date as _date
from typing import Optional

from models.delegation import Delegation
from models.user import User


def suppleants_de(responsable_id: int, at: Optional[_date] = None) -> list[int]:
    """Liste des user_id de suppléants actifs pour un responsable donné."""
    today = at or _date.today()
    rows = (
        Delegation.query
        .filter(
            Delegation.responsable_id == responsable_id,
            Delegation.date_debut <= today,
            Delegation.date_fin >= today,
        )
        .all()
    )
    return [d.suppleant_id for d in rows]


def delegataires_de(suppleant_id: int, at: Optional[_date] = None) -> list[int]:
    """Liste des user_id de responsables dont le user courant est suppléant actif."""
    today = at or _date.today()
    rows = (
        Delegation.query
        .filter(
            Delegation.suppleant_id == suppleant_id,
            Delegation.date_debut <= today,
            Delegation.date_fin >= today,
        )
        .all()
    )
    return [d.responsable_id for d in rows]


def peut_valider_pour(valideur: User, subordonne: User, at: Optional[_date] = None) -> bool:
    """True si `valideur` peut valider niveau 1 pour `subordonne` aujourd'hui."""
    if not subordonne.responsable_id:
        return False
    if valideur.id == subordonne.responsable_id:
        return True
    return subordonne.responsable_id in delegataires_de(valideur.id, at=at)


def subordonnes_effectifs(valideur: User, at: Optional[_date] = None) -> list[User]:
    """Liste des subordonnés que `valideur` peut effectivement valider :
    ses propres subordonnés directs + ceux des responsables dont il est suppléant.
    """
    ids_responsables = [valideur.id] + delegataires_de(valideur.id, at=at)
    return (
        User.query
        .filter(User.responsable_id.in_(ids_responsables), User.actif == True)
        .order_by(User.nom, User.prenom)
        .all()
    )
