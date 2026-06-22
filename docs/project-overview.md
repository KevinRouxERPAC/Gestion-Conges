---
title: "Vue d'ensemble du projet — ERPAC Gestion des Congés"
date: 2026-06-02
---

# Vue d'ensemble du projet

## Objet
Application web **intranet** de gestion des congés pour une équipe (salariés, responsables, RH) :
demandes de congés, validation à 2 niveaux, soldes CP (jours) et RTT (heures), paramétrage annuel,
clôture d'exercice, exports, notifications, audit, délégations et intéressement.

## Classification
- **Type de dépôt** : monolithe
- **Type de projet** : `backend` web server-rendered (Flask)
- **Point d'entrée** : `app.py` → `create_app()` ; production `run_wsgi.py` (Waitress / IIS)

## Stack technique

| Catégorie | Technologie | Détail |
|---|---|---|
| Langage | Python 3.10+ | — |
| Framework | Flask | Blueprints, Jinja2 server-rendered |
| ORM / BDD | SQLAlchemy + SQLite | `gestion_conges.db` (timeout 15 s) |
| Migrations | Flask-Migrate (Alembic) | dossier `migrations/` |
| Auth | Flask-Login + bcrypt | rôles `rh` / `responsable` / `salarie` |
| Sécurité | Flask-WTF (CSRF), Flask-Limiter | rate-limit `/login`, en-têtes CSP/HSTS |
| Front | Jinja2, Tailwind (CDN), Alpine.js, FullCalendar | pas de build JS lourd |
| Notifications | In-app + Web Push (pywebpush / VAPID) | service worker `/sw.js` |
| Exports | openpyxl (Excel), reportlab (PDF) | — |
| Production | Waitress (Windows/IIS) ou Gunicorn (Linux) | `ProxyFix` |

## Architecture (couches)
- **`routes/`** — contrôleurs HTTP (blueprints) : `auth`, `salarie`, `responsable`, `rh`, `notifications`, `api`.
- **`services/`** — logique métier (calcul de solde, RTT, congés exceptionnels, construction de congé,
  délégations, jours fériés, intéressement, exports, notifications, webpush, audit, import…).
- **`models/`** — entités SQLAlchemy (User, Conge, ParametrageAnnuel/AllocationConge, JourFerie,
  Delegation, Notification, PushSubscription, AuditLog, CongeExceptionnelType, HeuresPayees, Intéressement…).
- **`templates/` + `static/`** — UI Jinja par rôle + JS/CSS/service worker.

## Workflow métier central
`salarié` crée une demande → `en_attente_responsable` → (responsable) `en_attente_rh` → (RH) `valide` / `refuse`.
Sans responsable, la demande va directement en `en_attente_rh`. Le RH peut créer un congé déjà `valide`.

## Documentation liée
- [Architecture détaillée](./ARCHITECTURE.md) — **référence développeur à jour** (modèles, services, sécurité)
- [Checklist fonctionnelle](./FEATURES_CHECKLIST.md)
- [Plan d'implémentation (corrections d'audit)](./PLAN_IMPLEMENTATION.md)
- [Analyse d'utilité des fonctionnalités](./feature-utility-analysis.md) — audit daté (2026-06-02)
- [Deep-dive : clôture d'exercice](./deep-dive-cloture-exercice.md)

> Note : l'« arbre source annoté » (snapshot 2026-06-02) a été retiré car factuellement périmé ;
> la structure à jour est décrite dans [ARCHITECTURE.md](./ARCHITECTURE.md).
