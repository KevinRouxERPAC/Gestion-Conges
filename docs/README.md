# Documentation — Gestion des absences (ERPAC)

Index de la documentation du projet. Dernière mise à jour : 2026-06-26.

## Documentation de référence (à jour)

| Fichier | Description |
| ------- | ----------- |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Architecture technique : modèles SQLAlchemy, services métier, blueprints, sécurité, conventions. **Point d'entrée développeur.** |
| [FEATURES_CHECKLIST.md](FEATURES_CHECKLIST.md) | Checklist fonctionnelle (rôles, soldes CP/RTT, workflows, exports, tests). |
| [DECISIONS.md](DECISIONS.md) | Décisions durables : cap intranet, RTT Numeric, RGPD, SECRET_KEY, règles de clôture. |
| [PLAN_AMELIORATIONS_2026-06.md](PLAN_AMELIORATIONS_2026-06.md) | Backlog : lots terminés (email RH, perf dashboard, CSP) et lots à venir (ERP heures, HTTPS). |
| [deep-dive-cloture-exercice.md](deep-dive-cloture-exercice.md) | Risques résiduels de la clôture d'exercice (R2–R7) et corrections recommandées. |

## Guides opérationnels

| Fichier | Description |
| ------- | ----------- |
| [VERIFIER-WEBPUSH.md](VERIFIER-WEBPUSH.md) | Vérifier les notifications Web Push (clés VAPID, activation, test bout en bout). |
| [HTTPS-LOCAL-KASPERSKY.md](HTTPS-LOCAL-KASPERSKY.md) | HTTPS en local : contournement blocage Kaspersky, mkcert, IIS. |

## Voir aussi

- [README principal](../README.md) : installation, configuration, fonctionnalités, déploiement.
- [deploy/README.md](../deploy/README.md) : déploiement Linux (nginx + Gunicorn).
- [deploy/README-IIS.md](../deploy/README-IIS.md) : déploiement Windows Server (IIS + Waitress).
- [deploy/CERTIFICAT-HTTPS-INTRANET.md](../deploy/CERTIFICAT-HTTPS-INTRANET.md) : CA interne ERPAC, confiance des postes clients.
