"""Tests de l'email RH envoyé au fil de l'eau à chaque nouvelle demande (Lot 1).

L'email part vers la boîte entreprise MAIL_RH ; il ne doit jamais bloquer le
workflow ni partir si MAIL_RH n'est pas configuré.
"""
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from models import db
from models.conge import Conge


def _fake_conge():
    """Congé minimal (hors base) suffisant pour le rendu de l'email."""
    u = SimpleNamespace(prenom="Jean", nom="Dupont")
    return SimpleNamespace(
        id=1,
        utilisateur=u,
        date_debut=date(2026, 5, 12),
        date_fin=date(2026, 5, 16),
        nb_jours_ouvrables=5,
        type_conge="CP",
    )


@pytest.fixture()
def mail_rh(app):
    """Active temporairement MAIL_RH (la fixture app est session-scoped : on restaure)."""
    old = app.config.get("MAIL_RH")
    app.config["MAIL_RH"] = "rh@erpac.local"
    yield "rh@erpac.local"
    app.config["MAIL_RH"] = old


def test_sans_mail_rh_aucun_envoi(app):
    """MAIL_RH absent → la fonction sort tôt, send_email n'est jamais appelé."""
    from services.email import envoyer_email_demande_rh

    app.config["MAIL_RH"] = None
    with patch("services.email.send_email") as m:
        assert envoyer_email_demande_rh(_fake_conge()) is False
        m.assert_not_called()


def test_avec_mail_rh_un_envoi_vers_la_boite_rh(mail_rh):
    """MAIL_RH configuré → un email vers la boîte RH entreprise."""
    from services.email import envoyer_email_demande_rh

    with patch("services.email.send_email", return_value=True) as m:
        assert envoyer_email_demande_rh(_fake_conge(), evenement="directe") is True
        assert m.call_count == 1
        # Premier argument positionnel de send_email = destinataire.
        assert m.call_args.args[0] == mail_rh


def test_evenement_transmise_dans_le_corps(mail_rh):
    """Le libellé d'événement « transmise » apparaît dans le corps texte."""
    from services.email import envoyer_email_demande_rh

    with patch("services.email.send_email", return_value=True) as m:
        envoyer_email_demande_rh(_fake_conge(), evenement="transmise")
        body_text = m.call_args.args[2]
        assert "transmise par le responsable" in body_text


def test_echec_smtp_ne_propage_pas(mail_rh):
    """Un échec d'envoi est avalé par le wrapper : le workflow n'est pas bloqué."""
    from services import notifications

    with patch("services.email.send_email", side_effect=RuntimeError("smtp down")):
        # Ne doit lever aucune exception.
        notifications._email_demande_rh(_fake_conge(), evenement="directe")


def test_notifier_rh_nouvelle_demande_declenche_un_email(mail_rh, users):
    """Intégration : poser une demande dans la file RH déclenche exactement 1 email."""
    from services.notifications import notifier_rh_nouvelle_demande

    conge = Conge(
        user_id=users["salarie_sans_resp"].id,
        date_debut=date(2026, 5, 12),
        date_fin=date(2026, 5, 16),
        nb_jours_ouvrables=5,
        type_conge="CP",
        statut="en_attente_rh",
    )
    db.session.add(conge)
    db.session.commit()

    with patch("services.email.send_email", return_value=True) as m:
        notifier_rh_nouvelle_demande(conge)
        assert m.call_count == 1
