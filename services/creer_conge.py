"""Construction et validation d'un congé à partir d'un payload de formulaire.

Cette logique était dupliquée 4 fois (salarie.demander_conge, rh.ajouter_conge,
rh.modifier_conge, responsable.ajouter_conge_subordonne) avec des variantes
subtiles : types autorisés, statut initial, notifications. Centralisée ici
pour éviter les divergences (ex. un bug corrigé dans une route mais pas dans
les autres).

Conventions :
- Cette fonction VALIDE et CONSTRUIT le Conge mais ne le persiste pas.
- Elle ne fait aucun `flash()` ni `redirect` (responsabilité de la route).
- Elle retourne un `CongeBuildResult` exposant `errors` (bloquants) et
  `warnings` (informatifs, ex. solde négatif autorisé).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from models.conge import Conge, DEMI_VALEURS
from models.user import User
from services.calcul_jours import compter_jours_ouvrables_avec_demi, detecter_chevauchement
from services.format_heures import est_multiple_quart, format_heures_min
from services.conges_exceptionnels import (
    get_type_exceptionnel,
    parse_code,
    verifier_plafond,
)
from services.solde import calculer_solde


# Listes blanches selon le contexte d'appel.
# Le salarié n'a accès qu'aux types de base : Anciennete, Maladie et les EXC: sont
# gérés exclusivement par RH/responsable.
TYPES_SALARIE = frozenset({"CP", "RTT", "Sans solde"})
TYPES_RH_RESPONSABLE = frozenset({"CP", "Anciennete", "RTT", "Sans solde", "Maladie"})

# Modes supportés.
MODE_SALARIE = "salarie"
MODE_RH = "rh"
MODE_RESPONSABLE = "responsable"
_MODES_VALIDES = frozenset({MODE_SALARIE, MODE_RH, MODE_RESPONSABLE})


@dataclass
class CongeBuildResult:
    """Résultat de la construction d'un congé depuis un payload de formulaire."""

    conge: Optional[Conge] = None
    errors: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[tuple[str, str]] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.conge is not None and not self.errors

    @property
    def flashes(self) -> list[tuple[str, str]]:
        """Messages à passer à `flash(*tup)` : erreurs puis avertissements."""
        return self.errors + self.warnings


def construire_conge(
    salarie: User,
    payload: dict,
    *,
    mode: str,
    statut_initial: str,
    valide_par: Optional[User] = None,
    valide_par_responsable: Optional[User] = None,
    conge_existant: Optional[Conge] = None,
) -> CongeBuildResult:
    """Valide un payload et retourne un Conge non persistant (création ou édition).

    Args:
        salarie: utilisateur sur lequel le congé est posé.
        payload: dict de champs bruts (form-like). Clés attendues :
            date_debut, date_fin, type_conge, nb_heures_rtt (si RTT),
            nb_heures_exceptionnelles (si EXC en heures), commentaire.
        mode: contexte d'appel (`salarie` | `rh` | `responsable`).
        statut_initial: statut affecté à la création (ignoré en édition).
        valide_par: User RH qui a validé directement (statut="valide" côté RH).
        valide_par_responsable: User responsable qui a validé niveau 1.
        conge_existant: si fourni, mode édition : on met à jour ce congé
            au lieu d'en créer un nouveau. Les champs de validation existants
            sont préservés.
    """
    if mode not in _MODES_VALIDES:
        raise ValueError(f"Mode invalide : {mode!r}. Attendus : {sorted(_MODES_VALIDES)}")

    result = CongeBuildResult()

    # 1. Parsing des dates
    try:
        date_debut = datetime.strptime(payload["date_debut"], "%Y-%m-%d").date()
        date_fin = datetime.strptime(payload["date_fin"], "%Y-%m-%d").date()
    except (ValueError, KeyError, TypeError):
        result.errors.append(("error", "Dates invalides."))
        return result

    if date_fin < date_debut:
        result.errors.append(("error", "La date de fin doit être postérieure à la date de début."))
        return result

    # 2. Type de congé + liste blanche selon le mode
    type_conge = (payload.get("type_conge") or "").strip()
    if not type_conge:
        result.errors.append(("error", "Merci de sélectionner un type de congé."))
        return result

    types_autorises = TYPES_SALARIE if mode == MODE_SALARIE else TYPES_RH_RESPONSABLE
    exc_code = parse_code(type_conge)
    exc_type = None

    if exc_code:
        if mode == MODE_SALARIE:
            # Les congés exceptionnels passent par RH/responsable, pas par auto-saisie.
            result.errors.append(("error", "Type de congé non disponible."))
            return result
        exc_type = get_type_exceptionnel(exc_code)
        if not exc_type or not exc_type.actif:
            result.errors.append(("error", "Type de congé exceptionnel invalide."))
            return result
    elif type_conge not in types_autorises:
        result.errors.append(("error", "Merci de sélectionner un type de congé valide."))
        return result

    # 3. Demi-journées aux bordures (validation des valeurs autorisées)
    demi_debut_raw = (payload.get("demi_journee_debut") or "").strip().lower()
    demi_fin_raw = (payload.get("demi_journee_fin") or "").strip().lower()
    demi_debut = demi_debut_raw if demi_debut_raw in DEMI_VALEURS else None
    demi_fin = demi_fin_raw if demi_fin_raw in DEMI_VALEURS else None

    # Sur un congé mono-jour, on garde au plus une des deux bornes pour éviter
    # une ambiguïté (matin ET après-midi = journée complète, autant ne rien mettre).
    if date_debut == date_fin and demi_debut and demi_fin and demi_debut != demi_fin:
        demi_debut = demi_fin = None  # journée complète
    elif date_debut == date_fin and demi_debut and demi_fin and demi_debut == demi_fin:
        demi_fin = None  # on conserve uniquement debut pour cohérence

    # Règle métier : une demi-journée doit obligatoirement être posée en RTT.
    # (Une demi-journée correspond à des heures, gérées via le compteur RTT.)
    if (demi_debut or demi_fin) and type_conge != "RTT":
        result.errors.append(
            ("error", "Une demi-journée doit obligatoirement être posée en RTT.")
        )
        return result

    # 4. Calcul des jours ouvrables (avec demi-journées)
    nb_jours = compter_jours_ouvrables_avec_demi(date_debut, date_fin, demi_debut, demi_fin)
    if nb_jours == 0:
        result.errors.append(("error", "Aucun jour ouvrable dans la période sélectionnée."))
        return result

    # 5. Chevauchement avec un congé existant (en attente ou validé)
    conge_id_exclu = conge_existant.id if conge_existant else None
    chevauchement = detecter_chevauchement(salarie.id, date_debut, date_fin, conge_id_exclu=conge_id_exclu)
    if chevauchement:
        result.errors.append((
            "error",
            f"Chevauchement détecté avec le congé du {chevauchement.date_debut.strftime('%d/%m/%Y')} "
            f"au {chevauchement.date_fin.strftime('%d/%m/%Y')}.",
        ))
        return result

    # 6. Validation par type + warnings de solde négatif (non bloquants pour CP/RTT,
    #    bloquant pour les exceptionnels via plafond)
    nb_heures_rtt: Optional[float] = None
    nb_heures_exceptionnelles: Optional[int] = None

    if type_conge in ("CP", "Anciennete"):
        solde_info = calculer_solde(salarie.id)
        jours_actuels = (
            conge_existant.nb_jours_ouvrables or 0
            if conge_existant
            and conge_existant.statut == "valide"
            and conge_existant.type_conge in ("CP", "Anciennete")
            else 0
        )
        solde_apres = solde_info["solde_restant"] + jours_actuels - nb_jours
        if solde_apres < 0:
            result.warnings.append((
                "warning",
                f"Solde CP négatif après cette demande : {solde_apres} jour(s).",
            ))

    elif type_conge == "RTT":
        # Les RTT se saisissent au quart d'heure : multiple de 0,25 h, > 0.
        # On accepte la virgule décimale française (« 5,25 ») comme le point.
        raw_rtt = str(payload.get("nb_heures_rtt") or "").strip().replace(",", ".")
        try:
            nb_heures_rtt_val = round(float(raw_rtt), 2)
        except (ValueError, TypeError):
            nb_heures_rtt_val = 0.0
        if nb_heures_rtt_val <= 0 or not est_multiple_quart(nb_heures_rtt_val):
            result.errors.append((
                "error",
                "Merci de saisir un nombre d'heures RTT valide (multiple de 0,25 h, ex. 5,25 = 5 h 15).",
            ))
            return result

        solde_info = calculer_solde(salarie.id)
        heures_actuelles = (
            conge_existant.nb_heures_rtt or 0
            if conge_existant
            and conge_existant.statut == "valide"
            and conge_existant.type_conge == "RTT"
            else 0
        )
        rtt_apres = solde_info.get("rtt_solde_restant", 0) + heures_actuelles - nb_heures_rtt_val
        if rtt_apres < 0:
            result.warnings.append((
                "warning",
                f"Solde RTT négatif après cette demande : {format_heures_min(rtt_apres)}.",
            ))

        nb_heures_rtt = nb_heures_rtt_val

    elif exc_code and exc_type:
        if exc_type.unite == "heures":
            try:
                nb_heures_exceptionnelles = int(payload.get("nb_heures_exceptionnelles") or 0)
            except (ValueError, TypeError):
                nb_heures_exceptionnelles = 0
            if nb_heures_exceptionnelles <= 0:
                result.errors.append(("error", "Merci de saisir un nombre d'heures valide."))
                return result
            quantite = nb_heures_exceptionnelles
        else:
            quantite = nb_jours

        if not verifier_plafond(salarie.id, exc_type, quantite, conge_id_exclu=conge_id_exclu):
            result.errors.append((
                "error",
                f"Plafond dépassé pour le congé exceptionnel « {exc_type.libelle} ».",
            ))
            return result

    commentaire = (payload.get("commentaire") or "").strip()

    # 7. Construction du Conge (mise à jour ou nouveau)
    if conge_existant is not None:
        conge_existant.date_debut = date_debut
        conge_existant.date_fin = date_fin
        conge_existant.nb_jours_ouvrables = nb_jours
        conge_existant.demi_journee_debut = demi_debut
        conge_existant.demi_journee_fin = demi_fin
        conge_existant.type_conge = type_conge
        conge_existant.commentaire = commentaire
        conge_existant.nb_heures_rtt = nb_heures_rtt
        conge_existant.nb_heures_exceptionnelles = nb_heures_exceptionnelles
        result.conge = conge_existant
    else:
        now_utc = datetime.now(timezone.utc)
        result.conge = Conge(
            user_id=salarie.id,
            date_debut=date_debut,
            date_fin=date_fin,
            nb_jours_ouvrables=nb_jours,
            demi_journee_debut=demi_debut,
            demi_journee_fin=demi_fin,
            type_conge=type_conge,
            commentaire=commentaire,
            statut=statut_initial,
            valide_par_id=valide_par.id if valide_par else None,
            valide_le=now_utc if valide_par else None,
            valide_par_responsable_id=valide_par_responsable.id if valide_par_responsable else None,
            valide_par_responsable_le=now_utc if valide_par_responsable else None,
            nb_heures_rtt=nb_heures_rtt,
            nb_heures_exceptionnelles=nb_heures_exceptionnelles,
        )

    return result
