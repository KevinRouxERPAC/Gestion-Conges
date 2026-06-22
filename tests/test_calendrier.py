"""Confidentialité du calendrier « tout le monde ».

Le type d'absence d'un autre salarié ne doit pas fuiter (RGPD : « Maladie » et
les congés exceptionnels sont des données sensibles). Seules les dates et le nom
restent visibles pour anticiper les absences de l'équipe.
"""
import json
import re
from datetime import date

from models import db
from models.conge import Conge
from tests.conftest import login


def _events_from_html(html):
    m = re.search(r'id="calendar-events-data">(.*?)</script>', html, re.S)
    assert m, "bloc d'événements introuvable dans la page"
    return json.loads(m.group(1))


class TestCalendrierConfidentialite:
    def test_type_autrui_masque_en_mode_tous(self, client, db_session, users, parametrage):
        autre = users["salarie_sans_resp"]
        db.session.add(Conge(
            user_id=autre.id,
            date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 3),
            nb_jours_ouvrables=3,
            type_conge="Maladie",
            statut="valide",
        ))
        db.session.commit()

        login(client, "jean1", "jean123")
        resp = client.get("/salarie/calendrier?tous=1&annee=2026")
        assert resp.status_code == 200

        events = _events_from_html(resp.data.decode("utf-8"))
        assert events, "le congé de l'autre salarié devrait apparaître dans le calendrier"
        # Le type réel (Maladie) est anonymisé en « Absent ».
        for e in events:
            assert e["type"] == "Absent"
            assert e["filter_group"] == "Absent"
            assert e["heures_rtt"] is None

    def test_type_visible_pour_ses_propres_conges(self, client, db_session, users, parametrage):
        jean = users["salarie"]
        db.session.add(Conge(
            user_id=jean.id,
            date_debut=date(2026, 6, 1),
            date_fin=date(2026, 6, 3),
            nb_jours_ouvrables=3,
            type_conge="Maladie",
            statut="valide",
        ))
        db.session.commit()

        login(client, "jean1", "jean123")
        resp = client.get("/salarie/calendrier?tous=1&annee=2026")
        assert resp.status_code == 200

        events = _events_from_html(resp.data.decode("utf-8"))
        # Mes propres congés gardent leur type réel, même en vue « tout le monde ».
        assert any(e["type"] == "Maladie" for e in events)
