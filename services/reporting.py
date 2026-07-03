"""Reporting d'absentéisme et statistiques agrégées (Phase 3a).

Fournit des vues agrégées des congés sur une période donnée :
- par service (via `responsable_id`),
- par type d'absence,
- par période (mois),
- taux d'absentéisme.

Contrairement à `services/consommation.py` qui somme une colonne précise au
prorata des jours ouvrables dans la fenêtre, ce module agrège des **congés
entiers** (pas de prorata) sur leur période réelle : un congé à cheval compte
dans chaque mois qu'il traverse, pour les jours effectivement dans le mois.
C'est la sémantique attendue pour un tableau de bord d'absentéisme mensuel.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import func

from models import db
from models.conge import Conge
from models.user import User


@dataclass
class StatAbsence:
    """Ligne agrégée d'absence."""

    cle: str  # "CP", "RTT", "Maladie"... ou "service:Chef" pour par service
    nb_conges: int = 0
    nb_jours: float = 0.0
    nb_heures_rtt: float = 0.0


@dataclass
class RapportAbsenteisme:
    periode_debut: date
    periode_fin: date
    nb_salaries_actifs: int = 0
    par_type: list[StatAbsence] = field(default_factory=list)
    par_service: list[StatAbsence] = field(default_factory=list)
    par_mois: list[dict] = field(default_factory=list)
    taux_absenteisme_global: float = 0.0
    # Top consommateurs de CP sur la période.
    top_consommateurs_cp: list[dict] = field(default_factory=list)


def _jours_ouvrables_dans_periode(debut_conge: date, fin_conge: date, debut_periode: date, fin_periode: date) -> float:
    """Compte les jours ouvrables (lun-sam, hors fériés) du congé dans la fenêtre.

    Version simplifiée du calcul (pas de demi-journées) : suffisant pour un
    tableau de bord agrégé. Les demi-journées de bordure sont arrondies au jour
    pour ne pas surcharger ce reporting de synthèse.
    """
    from services.calcul_jours import get_dates_feries_set, _est_ouvrable

    debut = max(debut_conge, debut_periode)
    fin = min(fin_conge, fin_periode)
    if fin < debut:
        return 0.0
    feries = get_dates_feries_set(debut_periode, fin_periode)
    total = 0.0
    j = debut
    while j <= fin:
        if _est_ouvrable(j, feries):
            total += 1.0
        j += timedelta(days=1)
    return total


def generer_rapport(
    periode_debut: date,
    periode_fin: date,
    include_inactifs: bool = False,
) -> RapportAbsenteisme:
    """Génère un rapport d'absentéisme agrégé sur la période [debut, fin].

    Args:
        periode_debut: borne basse incluse.
        periode_fin: borne haute incluse.
        include_inactifs: inclure les salariés désactivés (défaut : actifs seulement).
    """
    rapport = RapportAbsenteisme(periode_debut=periode_debut, periode_fin=periode_fin)

    # Salariés concernés.
    users_q = User.query
    if not include_inactifs:
        users_q = users_q.filter_by(actif=True)
    users = users_q.order_by(User.nom, User.prenom).all()
    rapport.nb_salaries_actifs = len(users)
    users_by_id = {u.id: u for u in users}

    # Congés valides chevauchant la période.
    conges = (
        Conge.query.filter(
            Conge.statut == "valide",
            Conge.date_debut <= periode_fin,
            Conge.date_fin >= periode_debut,
            Conge.user_id.in_([u.id for u in users]) if users else False,
        ).all()
    )

    # --- Agrégats par type ---
    par_type: dict[str, StatAbsence] = {}
    for c in conges:
        cle = c.type_conge or "Autre"
        stat = par_type.setdefault(cle, StatAbsence(cle=cle))
        stat.nb_conges += 1
        if c.type_conge == "RTT":
            # RTT : on compte les heures RTT (proportion de la période).
            jours_dans = _jours_ouvrables_dans_periode(
                c.date_debut, c.date_fin, periode_debut, periode_fin
            )
            jours_total = max(1.0, _jours_ouvrables_dans_periode(
                c.date_debut, c.date_fin, c.date_debut, c.date_fin
            ))
            stat.nb_heures_rtt += (c.nb_heures_rtt or 0) * (jours_dans / jours_total)
            stat.nb_jours += jours_dans
        else:
            stat.nb_jours += _jours_ouvrables_dans_periode(
                c.date_debut, c.date_fin, periode_debut, periode_fin
            )
    rapport.par_type = sorted(par_type.values(), key=lambda s: -s.nb_jours)

    # --- Agrégats par service (responsable) ---
    par_service: dict[str, StatAbsence] = {}
    for c in conges:
        u = users_by_id.get(c.user_id)
        if u is None:
            continue
        if u.responsable_id:
            resp = users_by_id.get(u.responsable_id) or User.query.get(u.responsable_id)
            cle_service = f"Service {resp.prenom} {resp.nom}" if resp else "Sans responsable"
        else:
            cle_service = "Sans responsable"
        stat = par_service.setdefault(cle_service, StatAbsence(cle=cle_service))
        stat.nb_conges += 1
        stat.nb_jours += _jours_ouvrables_dans_periode(
            c.date_debut, c.date_fin, periode_debut, periode_fin
        )
    rapport.par_service = sorted(par_service.values(), key=lambda s: -s.nb_jours)

    # --- Agrégat par mois ---
    par_mois: dict[str, dict] = {}
    for c in conges:
        j = max(c.date_debut, periode_debut).replace(day=1)
        fin = min(c.date_fin, periode_fin)
        while j <= fin:
            cle_mois = j.strftime("%Y-%m")
            mois = par_mois.setdefault(cle_mois, {"mois": cle_mois, "nb_conges": 0, "nb_jours": 0.0})
            debut_mois = j
            fin_mois = min(j.replace(day=28) + timedelta(days=4), fin)
            fin_mois = fin_mois.replace(day=1) - timedelta(days=1)
            mois["nb_conges"] += 1
            mois["nb_jours"] += _jours_ouvrables_dans_periode(
                c.date_debut, c.date_fin, debut_mois, fin_mois
            )
            # Mois suivant.
            if j.month == 12:
                j = j.replace(year=j.year + 1, month=1, day=1)
            else:
                j = j.replace(month=j.month + 1, day=1)
    rapport.par_mois = sorted(par_mois.values(), key=lambda m: m["mois"])

    # --- Taux d'absentéisme global ---
    # = jours d'absence / (nb salariés × jours ouvrables de la période) × 100.
    total_jours_absence = sum(s.nb_jours for s in rapport.par_type)
    jours_ouv_periode = _jours_ouvrables_dans_periode(
        periode_debut, periode_fin, periode_debut, periode_fin
    )
    if rapport.nb_salaries_actifs > 0 and jours_ouv_periode > 0:
        rapport.taux_absenteisme_global = round(
            100.0 * total_jours_absence / (rapport.nb_salaries_actifs * jours_ouv_periode), 2
        )

    # --- Top consommateurs CP ---
    conso_cp: dict[int, float] = {}
    for c in conges:
        if c.type_conge in ("CP", "Anciennete"):
            jours = _jours_ouvrables_dans_periode(
                c.date_debut, c.date_fin, periode_debut, periode_fin
            )
            conso_cp[c.user_id] = conso_cp.get(c.user_id, 0.0) + jours
    top = sorted(conso_cp.items(), key=lambda kv: -kv[1])[:10]
    rapport.top_consommateurs_cp = [
        {
            "user": users_by_id.get(uid),
            "nb_jours": round(jours, 2),
        }
        for uid, jours in top
        if users_by_id.get(uid) is not None
    ]

    return rapport
