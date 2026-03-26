from datetime import date

from sqlalchemy import func

from models import db
from models.conge import Conge
from models.user import User
from services.solde import calculer_soldes_batch, get_parametrage_actif


def build_rh_dashboard_context(today: date | None = None) -> dict:
    """Construit le contexte métier du dashboard RH."""
    if today is None:
        today = date.today()

    salaries = User.query.filter_by(actif=True).order_by(User.nom).all()
    param = get_parametrage_actif()

    user_ids = [s.id for s in salaries]
    soldes_map = calculer_soldes_batch(user_ids)

    en_cours_rows = db.session.query(
        Conge.user_id,
        func.count(Conge.id),
    ).filter(
        Conge.user_id.in_(user_ids),
        Conge.statut == "valide",
        Conge.date_debut <= today,
        Conge.date_fin >= today,
    ).group_by(Conge.user_id).all()
    en_cours_map = {uid: cnt for uid, cnt in en_cours_rows}

    salaries_data = []
    for s in salaries:
        salaries_data.append(
            {
                "user": s,
                "solde": soldes_map.get(s.id, {}),
                "conges_en_cours": en_cours_map.get(s.id, 0),
            }
        )

    chart_labels = []
    chart_soldes_restants = []
    for item in salaries_data:
        user = item["user"]
        solde = item["solde"]
        chart_labels.append(f"{user.prenom} {user.nom}")
        chart_soldes_restants.append(solde.get("solde_restant", 0))

    calendar_events = []
    conges_exercice_rows = []
    if param:
        conges_exercice = Conge.query.filter(
            Conge.statut == "valide",
            Conge.date_debut <= param.fin_exercice,
            Conge.date_fin >= param.debut_exercice,
        ).all()
        for c in conges_exercice:
            if c.utilisateur is None:
                continue
            label = f"{c.date_debut.strftime('%d/%m/%Y')} → {c.date_fin.strftime('%d/%m/%Y')}"
            calendar_events.append(
                {
                    "start": c.date_debut.isoformat(),
                    "end": c.date_fin.isoformat(),
                    "user": f"{c.utilisateur.prenom} {c.utilisateur.nom}",
                    "type_conge": c.type_conge,
                }
            )
            conges_exercice_rows.append(
                {
                    "salarie": f"{c.utilisateur.prenom} {c.utilisateur.nom}",
                    "label": label,
                    "jours": c.nb_jours_ouvrables or 0,
                    "type": c.type_conge,
                }
            )

    demandes_attente = (
        Conge.query.filter_by(statut="en_attente_rh").order_by(Conge.cree_le.asc()).all()
    )

    salaries_inactifs = User.query.filter_by(actif=False).order_by(User.nom).all()
    inactifs_ids = [s.id for s in salaries_inactifs]
    soldes_inactifs_map = calculer_soldes_batch(inactifs_ids) if inactifs_ids else {}
    salaries_data_inactifs = []
    for s in salaries_inactifs:
        salaries_data_inactifs.append({"user": s, "solde": soldes_inactifs_map.get(s.id, {})})

    total_salaries = len(salaries)
    total_en_conge = sum(1 for s in salaries_data if s["conges_en_cours"] > 0)

    compta_31_03 = None
    compta_30_09 = None
    if param:
        year = param.fin_exercice.year
        compta_31_03 = date(year, 3, 31)
        compta_30_09 = date(year, 9, 30)

    return {
        "salaries_data": salaries_data,
        "salaries_data_inactifs": salaries_data_inactifs,
        "total_salaries": total_salaries,
        "total_en_conge": total_en_conge,
        "parametrage": param,
        "chart_labels": chart_labels,
        "chart_soldes_restants": chart_soldes_restants,
        "calendar_events": calendar_events,
        "conges_exercice_rows": conges_exercice_rows,
        "demandes_attente": demandes_attente,
        "today": today,
        "compta_31_03": compta_31_03,
        "compta_30_09": compta_30_09,
    }
