# Plan d'implémentation — Corrections issues de l'audit

> Document de cadrage technique. Référence : rapport d'analyse du projet « Gestion des absences » (ERPAC).
> Statut : **✅ implémenté** (R1 à R7 livrés, `pytest` au vert — 225 tests).
> Dernière mise à jour : 2026-06-16.

## ✅ État de réalisation (synthèse)

| ID | Correctif | Statut | Où |
|----|-----------|--------|----|
| R1 | Prorata des congés à cheval sur l'exercice | ✅ Fait | `services/consommation.py` (`somme_consommation`, `_prorata_fenetre`) + tests `test_consommation.py`, `test_cloture.py` |
| R2 | Cookie de session durci (HttpOnly/SameSite/Secure) | ✅ Fait | `config.py` + tests `test_securite.py` |
| R3 | RTT en décimal (`Numeric(6,2)`) | ✅ Fait | `models/conge.py`, `models/parametrage.py`, `services/rtt_hebdo.py`, migration `e3f1a2b4c5d6` + tests |
| R4 | Anti-énumération de comptes par timing | ✅ Fait | `services/auth_utils.py` (`DUMMY_HASH`), `routes/auth.py` + tests `test_auth_et_roles.py` |
| R5 | Nettoyage dette (code mort, `except: pass`) | ✅ Fait | suppression `verifier_solde_*` (`services/solde.py`), log dans `routes/salarie.py` |
| R6 | Politique mot de passe alignée (8) | ✅ Fait | `README.md`, `scripts/create_admin.py` (via `valider_mot_de_passe`) |
| R7 | Décision de cap | ✅ Tranché : **Scénario A (intranet)** | cf. §4 |

> **Décisions tranchées** : R7 = **Scénario A (rester intranet)** ; R3 = **Option A `Numeric(6,2)`** (heures décimales, `asdecimal=False` pour rester homogène avec le reste des calculs ; arrondi à l'affichage via le filtre `nb_heures`).

## 1. Objectif et périmètre

Ce plan décrit la mise en œuvre des correctifs **R1 à R7** identifiés lors de l'audit. Il est
volontairement séquencé pour livrer d'abord les corrections de **justesse** et de **sécurité**
(impact direct sur les soldes et les sessions), puis la dette technique, enfin la décision de cap.

**Hors périmètre** : refonte UX, migration de base de données (sauf si R7 le tranche), nouvelles
fonctionnalités métier.

**Principe directeur** : chaque correctif doit être couvert par un test automatisé **avant** d'être
considéré comme terminé. Le projet dispose déjà de ~219 tests ; on conserve ce niveau d'exigence.

## 2. Vue d'ensemble (priorisation)

| ID | Correctif | Priorité | Effort estimé | Risque de régression | Bloquant pour |
|----|-----------|----------|---------------|----------------------|---------------|
| R1 | Décompte des congés à cheval sur l'exercice | P1 | M (½–1 j) | Moyen (touche le cœur calcul) | — |
| R2 | Durcissement du cookie de session | P1 | S (< 1 h) | Faible | — |
| R3 | RTT en décimal (fin de la perte d'arrondi) | P2 | M (1 j, migration) | Moyen (migration schéma) | — |
| R4 | Anti-énumération de comptes par timing | P2 | S (< 1 h) | Faible | — |
| R5 | Nettoyage dette (code mort, `except: pass`) | P3 | S (< 1 h) | Faible | — |
| R6 | Politique mot de passe + alignement doc | P3 | S (< 1 h) | Faible | — |
| R7 | Décision de cap (intranet vs montée en charge) | Transverse | Décision | — | R3 (choix colonne), infra |

**Ordre d'exécution recommandé** : R2 → R4 → R6 → R5 (quick wins faible risque) → R1 → R3, R7 traité en parallèle (décision, pas code).

## 3. Phases d'implémentation

### Phase 0 — Préparation (avant tout code)

- [x] Créer une branche dédiée : `git checkout -b fix/audit-corrections`.
- [x] Vérifier que la suite de tests passe au vert sur `main` (baseline) : `pytest -q` → 219 passed.
- [x] Trancher **R7** (cf. §4) → **Scénario A** ; R3 → **Option A `Numeric(6,2)`**.

---

### Phase 1 — Quick wins sécurité & hygiène (R2, R4, R6, R5)

Faible risque, fort rapport bénéfice/effort. Idéalement un seul lot/PR.

#### R2 — Cookie de session `Secure` / `SameSite` / `HttpOnly`
- **Fichier** : `config.py`.
- **Étapes** :
  - Ajouter dans `class Config` :
    ```python
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = PREFERRED_URL_SCHEME == "https"
    ```
  - `SESSION_COOKIE_SECURE` indexé sur `PREFERRED_URL_SCHEME` pour ne pas casser le dev en HTTP.
- **Test** : `tests/test_securite.py` — vérifier la présence des attributs `Secure`/`HttpOnly`/`SameSite`
  sur le cookie de session quand `PREFERRED_URL_SCHEME=https`.
- **Risque** : nul en dev (HTTP) ; en prod, valider que le déploiement est bien en HTTPS.

#### R4 — Neutraliser l'énumération de comptes par timing
- **Fichier** : `routes/auth.py` (fonction `login`).
- **Étapes** :
  - Quand `User.query.filter_by(...).first()` retourne `None`, exécuter un `check_password` factice
    contre un hash bcrypt constant pré-calculé, afin d'égaliser le temps de réponse.
  - Centraliser ce hash bidon dans `services/auth_utils.py` (constante `DUMMY_HASH`).
- **Test** : `tests/test_auth_et_roles.py` — un login avec identifiant inexistant et un login avec
  mauvais mot de passe renvoient le **même** message et le même comportement (pas de test de timing
  strict, mais vérifier que la branche factice est appelée).
- **Risque** : faible. Veiller à ne pas régresser le rate-limit.

#### R6 — Politique mot de passe + documentation
- **Fichiers** : `README.md` (ligne ~83, « 6 caractères » → « 8 caractères »), éventuellement
  `services/auth_utils.py`.
- **Étapes** :
  - Corriger l'incohérence doc/code (le code impose déjà 8, cf. `PASSWORD_MIN_LENGTH`).
  - **Optionnel** (à valider) : ajouter un contrôle anti-mots-de-passe-courants (liste « top N »)
    dans `valider_mot_de_passe`.
- **Test** : `tests/test_password_change.py` / `tests/test_compte.py` si la règle évolue.
- **Risque** : faible. Si on ajoute la liste, prévoir un message d'erreur explicite.

#### R5 — Nettoyage de la dette
- **Fichiers** : `services/solde.py`, `routes/salarie.py`.
- **Étapes** :
  - **Décision** sur `verifier_solde_suffisant` / `verifier_solde_rtt_suffisant` (solde.py:159-182) :
    - soit les **supprimer** (le solde négatif est autorisé par choix métier),
    - soit les **brancher** derrière un futur paramètre « bloquer le solde négatif ».
    > Recommandation : suppression, car non appelées et contraires à la règle actuelle.
  - Remplacer `except Exception: pass` (`routes/salarie.py:253`) par un `current_app.logger.exception(...)`
    pour ne plus masquer un bug de calcul RTT.
- **Test** : la suite existante doit rester verte ; ajouter un test si la branche d'erreur log est
  vérifiable.
- **Risque** : faible.

---

### Phase 2 — Justesse des soldes (R1)

Cœur métier. À traiter isolément (PR dédiée) pour faciliter la revue.

#### R1 — Décompte des congés à cheval sur la fin d'exercice
- **Fichier unique** : `services/consommation.py` (`somme_consommation`).
- **Problème** : un congé n'est compté que s'il est *entièrement contenu* dans la fenêtre
  (`date_debut >= min ET date_fin <= max`). Un congé qui chevauche la bascule d'exercice
  (ex. **30/12 → 03/01**) n'est décompté dans **aucun** exercice.
- **Stratégie** : introduire un décompte **au prorata des jours ouvrables réellement dans la fenêtre**,
  **uniquement** dans cette primitive (garder la « source de vérité unique »).
- **Étapes** :
  1. Identifier les congés débordant une borne (`date_debut < min OR date_fin > max` mais chevauchant
     la fenêtre).
  2. Pour ces congés, recalculer la part de `nb_jours_ouvrables` tombant dans `[min, max]`
     (réutiliser `compter_jours_ouvrables_avec_demi` de `services/calcul_jours.py`).
  3. Garder le chemin SQL agrégé rapide pour les congés entièrement contenus ; n'appliquer le
     prorata Python qu'aux quelques congés frontières.
  4. Valider l'invariant : un même congé n'est jamais compté deux fois entre deux exercices adjacents
     (somme des deux parts = total du congé).
- **Tests** (nouveaux, `tests/test_consommation.py` + `tests/test_cloture.py`) :
  - Congé 30/12/2026 → 03/01/2027 : N jours côté exercice 2026, M jours côté 2027, **N+M = total**.
  - Non-régression : congés entièrement contenus inchangés (comparer aux valeurs actuelles).
  - Cohérence inter-écrans : solde salarié == export comptable == intéressement sur le même périmètre.
- **Risque** : **moyen** — modifie le calcul consommé partout. Atténué par : (a) un seul point de
  modification, (b) tests de non-régression sur les cas non-frontières, (c) revue dédiée.
- **Vérification manuelle** : rejouer un scénario de clôture d'exercice et comparer les soldes
  avant/après sur un jeu de données contenant au moins un congé frontière.

---

### Phase 3 — Précision RTT (R3) — *dépend de R7*

#### R3 — RTT en décimal
- **Fichiers** : `models/conge.py` (`nb_heures_rtt`), `models/parametrage.py`
  (`rtt_heures_allouees`, `rtt_heures_reportees`), `services/rtt_hebdo.py`, migration Alembic.
- **Problème** : total annuel arrondi une seule fois en entier et stocké en `Integer`
  (`int(round(total))`) → perte des fractions (ex. 16,1 h → 16 h).
- **Deux options de stockage** (le choix dépend de R7 / préférence comptable) :
  - **Option A — `Numeric(6,2)`** : stocke des heures décimales (ex. 16,10). Lisible.
  - **Option B — minutes entières** : stocke `int` de minutes (ex. 966), arrondi seulement à l'affichage.
    Évite tout flottant en base. *Recommandée pour la paie.*
- **Étapes** :
  1. Trancher A vs B.
  2. Écrire la migration Alembic (`flask db migrate -m "rtt decimal"`), avec conversion des données
     existantes (entiers → décimaux/minutes sans perte).
  3. Adapter `rtt_hebdo.py` : ne plus arrondir le total ; arrondir/formater seulement à l'affichage
     (`templates/salarie/heures.html`, filtre `nb_jours`/équivalent heures).
  4. Vérifier les exports (`services/export_comptable.py`) et l'intéressement.
- **Tests** : `tests/test_rtt_hebdo.py` — cas `0,35 h/sem × 46 sem` doit donner `16,1 h` (ou 966 min),
  pas 16 h.
- **Risque** : **moyen** — migration de schéma + affichage. Prévoir une sauvegarde de la base avant
  `flask db upgrade` en prod.

---

## 4. Décision transverse — R7 (cap technique)

**À trancher en amont** car elle conditionne R3 et les investissements infra.

| Scénario | Conséquences | Actions induites |
|----------|--------------|------------------|
| **A. Rester intranet** (statu quo assumé) | SQLite + mono-worker documentés comme contraintes officielles. « Marché global » hors périmètre. | Documenter la limite ; R3 peut rester simple (Option A ou B). |
| **B. Viser la montée en charge** | Migration PostgreSQL + rate-limit Redis (déjà anticipés en commentaire dans `app.py`/`config.py`). | Backlog infra séparé ; tester la concurrence d'écriture ; R3 en `Numeric`. |

> **✅ Décision retenue : Scénario A** (rester intranet) tant qu'aucun besoin multi-site/concurrentiel
> n'est formalisé. SQLite + mono-worker sont assumés comme contraintes officielles. La bascule vers B
> reste peu risquée (le code l'anticipe : commentaires Redis/PostgreSQL dans `app.py`/`config.py`).

## 5. Stratégie de tests et de validation

- **Baseline** : `pytest -q` vert avant et après chaque phase.
- **Couverture ciblée** : chaque correctif ajoute/étend un test (cf. fichiers `tests/` cités).
- **Non-régression calcul** : pour R1 et R3, comparer les soldes d'un jeu de données de référence
  avant/après (snapshot).
- **Revue** : R1 et R3 (cœur métier + migration) en PR dédiées et relues ; R2/R4/R5/R6 peuvent être
  groupés.

## 6. Découpage en livrables (PR)

1. **PR-1 — Sécurité & hygiène** : R2 + R4 + R6 + R5. Faible risque, mergeable rapidement.
2. **PR-2 — Justesse des soldes** : R1 seul. Revue attentive + tests frontières.
3. **PR-3 — Précision RTT** : R3 + migration. Après décision R7.

## 7. Risques globaux et mitigations

| Risque | Mitigation |
|--------|------------|
| Régression sur les calculs de solde (R1) | Point de modification unique + tests non-régression + PR dédiée |
| Perte de données à la migration RTT (R3) | Sauvegarde base avant `flask db upgrade` ; migration réversible (`downgrade`) |
| Cookie `Secure` casse l'accès en HTTP résiduel (R2) | Attribut indexé sur `PREFERRED_URL_SCHEME` |
| Décision R7 repoussée | R1, R2, R4, R5, R6 ne dépendent pas de R7 ; seul R3 attend |

## 8. Definition of Done

- [x] Tous les correctifs couverts par au moins un test automatisé.
- [x] `pytest` au vert (225 passed, aucune régression).
- [x] Documentation (`README.md`, `docs/ARCHITECTURE.md`, `docs/FEATURES_CHECKLIST.md`, ce plan) mise à jour.
- [x] Migration Alembic `e3f1a2b4c5d6` fournie et testée en `upgrade`/`downgrade` (R3 + fusion des têtes divergentes).
- [x] R7 tranché et consigné (Scénario A).
