# Documentation — Gestion des absences (ERPAC)

Index de la documentation du projet. Dernière mise à jour : 2026-06-16.

## Documentation de référence (à jour)

| Fichier | Description |
| ------- | ----------- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Architecture technique : modèles SQLAlchemy, services métier, blueprints, sécurité, conventions. **Point d'entrée développeur.** |
| [FEATURES_CHECKLIST.md](FEATURES_CHECKLIST.md) | Checklist fonctionnelle (rôles, soldes CP/RTT, workflows, exports, tests). |
| [PLAN_IMPLEMENTATION.md](PLAN_IMPLEMENTATION.md) | Plan des corrections d'audit (R1–R7) — **implémenté**, avec décisions tranchées (cap intranet, RTT décimal). |
| [VERIFIER-WEBPUSH.md](VERIFIER-WEBPUSH.md) | Vérifier les notifications Web Push (clés VAPID, activation, test). |
| [HTTPS-LOCAL-KASPERSKY.md](HTTPS-LOCAL-KASPERSKY.md) | HTTPS en local (certificat, contournement blocage Kaspersky). |

## Analyses datées (audit 2026-06-02, valeur historique)

| Fichier | Description |
| ------- | ----------- |
| [feature-utility-analysis.md](feature-utility-analysis.md) | Analyse d'utilité des fonctionnalités (garder / renforcer / décider). Bandeau de mise à jour en tête. |
| [project-overview.md](project-overview.md) | Vue d'ensemble du projet (stack, couches, workflow). |
| [deep-dive-cloture-exercice.md](deep-dive-cloture-exercice.md) | Analyse approfondie de la clôture d'exercice + report (R1 corrigé). |

## Données

- `Heures2025-2026/` : exports CSV mensuels d'heures (données de référence).

## Voir aussi

- [README principal](../README.md) : installation, configuration, fonctionnalités, déploiement.
- [deploy/README.md](../deploy/README.md) : déploiement Linux (nginx + Gunicorn).
- [deploy/README-IIS.md](../deploy/README-IIS.md) : déploiement Windows Server (IIS + Waitress).
