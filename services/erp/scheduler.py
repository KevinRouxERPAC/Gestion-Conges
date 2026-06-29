"""Planificateur in-app (APScheduler) pour la synchro ERP hebdomadaire.

Démarré explicitement par run_wsgi.py au lancement de Waitress.
PAS démarré lors des migrations Alembic, des tests, ou des commandes CLI.

Le planificateur tourne dans un thread de fond du processus Waitress.
Quand le serveur s'arrête, arreter_scheduler() est appelé proprement.
"""
from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    _apscheduler_ok = True
except ImportError:
    _apscheduler_ok = False

_scheduler = None  # instance globale unique


def demarrer_scheduler(app) -> None:
    """Démarre le planificateur de fond. Idempotent (sans effet si déjà démarré)."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return

    if not _apscheduler_ok:
        logger.warning("APScheduler non installé — synchro auto ERP désactivée.")
        return

    jour = app.config.get("ERP_SYNC_JOUR", "fri")
    heure = app.config.get("ERP_SYNC_HEURE", 17)
    minute = app.config.get("ERP_SYNC_MINUTE", 30)

    def _job_sync():
        with app.app_context():
            from services.erp.connexion import erp_active
            if not erp_active():
                return
            from services.erp.sync_heures import synchroniser_semaine
            try:
                rapport = synchroniser_semaine(recalculer_rtt=True)
                logger.info(
                    "Synchro ERP auto — semaine %s : %d ligne(s) importée(s), "
                    "%d avertissement(s).",
                    rapport.semaine_erp,
                    rapport.nb_importes,
                    len(rapport.avertissements),
                )
                for w in rapport.avertissements:
                    logger.warning("Synchro ERP : %s", w)
            except Exception:
                logger.exception("Synchro ERP auto : erreur non gérée.")

    _scheduler = BackgroundScheduler(timezone="Europe/Paris")
    _scheduler.add_job(
        _job_sync,
        CronTrigger(
            day_of_week=jour,
            hour=heure,
            minute=minute,
            timezone="Europe/Paris",
        ),
        id="sync_erp_heures",
        name="Synchro ERP heures hebdomadaires",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Planificateur ERP démarré : synchro automatique chaque %s à %02d:%02d (Europe/Paris).",
        jour,
        int(heure),
        int(minute),
    )


def arreter_scheduler() -> None:
    """Arrête proprement le planificateur (appelé à l'arrêt du serveur)."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Planificateur ERP arrêté.")
    _scheduler = None


def prochain_passage() -> datetime | None:
    """Retourne la datetime du prochain déclenchement, ou None si inactif."""
    if _scheduler is None or not _scheduler.running:
        return None
    job = _scheduler.get_job("sync_erp_heures")
    return job.next_run_time if job else None


def scheduler_actif() -> bool:
    return bool(_scheduler and _scheduler.running)
