---
title: "Backlog — Améliorations en cours et à venir"
date: 2026-06-26
---

# Backlog — Améliorations en cours et à venir

## Statut des lots (branche `chore/ameliorations-2026-06`)

| Lot | Objet | Statut |
|-----|-------|--------|
| 0 — Hygiène dépôt | node_modules désindexé, route accentuée unifiée | ✅ Fait |
| 1 — Email RH à chaque demande | Email `MAIL_RH` à chaque entrée dans la file RH | ✅ Fait (5 tests) |
| 2 — Perf dashboard RH | Anti N+1 (requêtes groupées, `calculer_soldes_lot`) | ✅ Fait (3 tests) |
| 3 — Fiabilité prod | Requêtes `IN` par lots, `SKIP_DB_CREATE_ALL` documenté | ✅ Fait |
| 4 — Passerelle ERP des heures | Import automatique des heures depuis l'ERP | ✅ Livré (9 tests + aperçu) |
| 5.1 — HTTPS intranet | Déploiement HTTPS → débloque le Web Push natif | ⏳ Déploiement (script `verifier_https.py`) |
| 5.2 — Durcir la CSP | Retirer `unsafe-inline` / `unsafe-eval` (nonces Alpine.js) | ✅ Fait (Lot 5.2 livré — PR #3) |
| 6 — RTT : types d'absence exclus | Maladie ne réduit pas le seuil hebdo RTT | ✅ Fait (5 tests) |
| 7 — Reporting absentéisme | Reports par service/type/période + taux d'absentéisme | ✅ Fait (8 tests) |
| 8 — Rappels automatiques | Demandes en attente + soldes CP en fin d'exercice | ✅ Fait (11 tests) |
| 9 — PWA installable | `manifest.webmanifest`, cache offline, icônes, déclaration `base.html` | ✅ Fait |

Suite de tests actuelle : **278 passed, 0 failed**.

---

## Lot 4 — Passerelle ERP des heures (P3) ✅ Livré

Objectif : récupérer automatiquement les heures travaillées depuis la base de l'ERP pour
supprimer la saisie hebdomadaire manuelle, sans changer le moteur RTT.

### Livré

- **Connexion read-only** `services/erp/connexion.py` (3 niveaux de protection : login SQL
  `SELECT`-only, `ApplicationIntent=ReadOnly`, aucune écriture dans le code).
- **Requêtes** `services/erp/requetes.py` : `heures_semaine` (TEMPAS) et `salaries_erp`
  (SALARIES), société 100, mapping matricule `MAKTCODE`.
- **Service** `services/erp/sync_heures.py` : `synchroniser_semaine()` agrège par semaine
  ISO, upsert `HeuresHebdo(source="erp")`, préserve les saisies `manuel` (la RH a priorité).
- **Mode aperçu** (`dry_run=True`) : la RH visualise le diff avant d'écraser.
- **Planificateur in-app** `services/erp/scheduler.py` (APScheduler, vendredi 17h30 par défaut),
  démarré par `run_wsgi.py`.
- **CLI** `flask sync-erp-heures [--semaine AAAASS] [--dry-run] [--no-rtt]`.
- **UI RH** `/rh/heures-hebdo` : bouton import + bouton aperçu + statut planificateur.
- **Tests** `tests/test_erp_sync.py` (9 tests) : mapping, upsert, préservation manuelle, aperçu.
- **Migration** `f1a2b3c4d5e6` : `users.matricule` + `heures_travaillees` en `Numeric(5,2)`.

### À valider opérationnellement

- Accès et schéma de la base Cegid PMI : confirmé (TEMPAS / SALARIES, société 100).
- Mapping matricule : renseigner `users.matricule` côté RH pour chaque salarié (écran
  Gestion des salariés).
- `ERP_DB_PASSWORD` : variable d'environnement **système** sur le serveur IIS (jamais
  dans `web.config` versionné).

---

## Lot 5.1 — HTTPS intranet (P3, déploiement)

Le Web Push natif (notification système hors onglet) nécessite **HTTPS**. Le site est actuellement
accessible via `https://conges.erpac.com` (certificat `*.erpac.com`, CA `ERPAC-SRV18150RD1-CA`).

**Actions restantes :**

- S'assurer que la CA est installée en racine de confiance sur tous les postes clients
  (voir `deploy/CERTIFICAT-HTTPS-INTRANET.md`).
- Vérifier les clés VAPID et l'abonnement navigateur (`docs/VERIFIER-WEBPUSH.md`).
- Poser `PREFERRED_URL_SCHEME=https` dans `web.config` → active les cookies `Secure` et HSTS.

**Vérification finale (un seul script, depuis un poste client) :**

```bash
python scripts/verifier_https.py https://conges.erpac.com
```

Valide en un seul passage : config `PREFERRED_URL_SCHEME=https`, cookies `Secure`, HSTS,
chaîne de confiance du certificat, clés VAPID et endpoint `/notifications/vapid-public`.

Tant que HTTPS n'est pas garanti sur tous les postes, **le Lot 1 (email RH)** est le canal fiable
pour alerter la RH.

---

## Lot 9 — PWA installable (P3) ✅ Fait

Objectif : rendre l'application installable comme une application native (icône sur le bureau,
lancement en standalone, usage hors-ligne pour les pages déjà visitées).

### Livré

- **Manifest** `static/manifest.webmanifest` : nom, icônes (192/512 + maskables), `start_url`,
  `display: standalone`, `theme_color`/`background_color`, raccourcis « Mes congés » / « Calendrier ».
- **Icônes PWA** générées depuis `logo_seul.png` :
  - `static/img/icon-192.png`, `static/img/icon-512.png` (purpose `any`)
  - `static/img/maskable-192.png`, `static/img/maskable-512.png` (purpose `maskable`, fond blanc)
- **Service Worker** `static/sw.js` étendu :
  - cache offline (shell statique pré-caché à l'installation),
  - stratégie **stale-while-revalidate** pour `/static/*`,
  - stratégie **network-first** pour les pages HTML (fallback cache, puis `offline.html`),
  - pas de cache pour `/api/*`, `/notifications/*`, `/auth/*` et requêtes non-GET,
  - conservation des handlers Web Push existants (`push`, `notificationclick`).
- **Page hors-ligne** `static/offline.html` (secours graphé).
- **Déclaration** dans `templates/base.html` : `<link rel="manifest">`, `theme-color`,
  `apple-touch-icon`, métadonnées `apple-mobile-web-app-*`.
- **Enregistrement SW** : `static/js/app.js` enregistre `/sw.js` sur **toutes les pages**
  (pas uniquement sur celles avec bouton push) ; `initWebPush()` réutilise désormais
  `navigator.serviceWorker.ready` (plus de double enregistrement).

### Vérification

- Lighthouse → catégorie PWA : « Installable » coché (manifest + SW + HTTPS).
- `Application` → `Manifest` dans les DevTools : icônes et raccourcis visibles.
- Hors-ligne : recharger une page déjà visitée affiche le cache, puis `offline.html` si absente.

> Note : l'installation native nécessite HTTPS (couvert par le Lot 5.1) sur tous les navigateurs
> sauf Edge intranet en politique permissive.

---

## Risques résiduels de la clôture d'exercice

Indépendants de ce backlog — voir `docs/deep-dive-cloture-exercice.md` pour les détails et
corrections recommandées (R2 plafond négatif, R3 ancienneté, R4 double clôture, R5-R7).
