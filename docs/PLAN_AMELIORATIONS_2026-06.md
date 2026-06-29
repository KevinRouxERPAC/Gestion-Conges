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
| 4 — Passerelle ERP des heures | Import automatique des heures depuis l'ERP | ⏳ À cadrer |
| 5.1 — HTTPS intranet | Déploiement HTTPS → débloque le Web Push natif | ⏳ Déploiement |
| 5.2 — Durcir la CSP | Retirer `unsafe-inline` / `unsafe-eval` (nonces Alpine.js) | ✅ Fait (Lot 5.2 livré — PR #3) |

Suite de tests actuelle : **244 passed, 0 failed**.

---

## Lot 4 — Passerelle ERP des heures (P3) 🔴

Objectif : récupérer automatiquement les heures travaillées depuis la base de l'ERP pour
supprimer la saisie hebdomadaire manuelle, sans changer le moteur RTT.

### Points d'ancrage déjà présents

- `models/heures_hebdo.py` : champ `source` (défaut `"manuel"`) → écrire `source="erp"` pour les
  lignes importées. `services/rtt_hebdo.py` les consomme sans modification.

### À concevoir

1. **Schéma** : passer `HeuresHebdo.heures_travaillees` de `Integer` à `Numeric(6,2)` si l'ERP
   renvoie des heures décimales (37,5 h). Migration Alembic dédiée.
2. **Service `services/import_heures_erp.py`** : connexion read-only à la base ERP, mapping
   salarié ERPAC ↔ ERP (clé à définir : matricule ?), agrégation par semaine ISO, upsert
   `HeuresHebdo(source="erp")`.
3. **Déclenchement** : tâche planifiée hebdomadaire (comme `recap_hebdo.py`) + bouton RH
   « Resynchroniser ».
4. **Idempotence** : trancher la priorité si une semaine a à la fois une saisie `manuel` et un
   import `erp` (l'ERP écrase-t-il le manuel ?).

**Prérequis** : accès et schéma de la base ERP (à discuter).

---

## Lot 5.1 — HTTPS intranet (P3, déploiement)

Le Web Push natif (notification système hors onglet) nécessite **HTTPS**. Le site est actuellement
accessible via `https://conges.erpac.com` (certificat `*.erpac.com`, CA `ERPAC-SRV18150RD1-CA`).

**Actions restantes :**

- S'assurer que la CA est installée en racine de confiance sur tous les postes clients
  (voir `deploy/CERTIFICAT-HTTPS-INTRANET.md`).
- Vérifier les clés VAPID et l'abonnement navigateur (`docs/VERIFIER-WEBPUSH.md`).
- Poser `PREFERRED_URL_SCHEME=https` dans `web.config` → active les cookies `Secure` et HSTS.

Tant que HTTPS n'est pas garanti sur tous les postes, **le Lot 1 (email RH)** est le canal fiable
pour alerter la RH.

---

## Risques résiduels de la clôture d'exercice

Indépendants de ce backlog — voir `docs/deep-dive-cloture-exercice.md` pour les détails et
corrections recommandées (R2 plafond négatif, R3 ancienneté, R4 double clôture, R5-R7).
