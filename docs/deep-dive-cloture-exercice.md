# Clôture d'exercice — risques résiduels

Référence technique pour les développeurs. Dernière mise à jour : 2026-06-26.

Périmètre : `routes/rh.py:cloture_exercice`, `services/solde.py:cloturer_exercice_et_reporter`,
`templates/rh/cloture_exercice.html`, `tests/test_cloture.py`.

## Ce qui est correct ✅

- **Atomicité** : service sans `commit`, route qui `commit`/`rollback` → tout ou rien.
- **Config RTT préservée** (`rtt_calc_mode/reference/coef`) sur le nouvel exercice.
- **Report négatif** : un déficit est reporté tel quel (cf. `docs/DECISIONS.md`).
- **Plafond de report** fonctionnel (intégral, plafonné) — couvert par `test_cloture.py`.
- **Audit** complet (ancien/nouveau exercice, plafonds, totaux, nb salariés).
- **Aperçu GET** avant action + accès `rh_required`.
- **R1 (congés à cheval)** : corrigé — décompte au prorata dans `services/consommation.py`
  (`somme_consommation` / `_prorata_fenetre`).

## Risques résiduels ⚠️

### 🟠 R2 — Plafond de report négatif accepté

Dans la route (`routes/rh.py:810`), `int(plafond_cp_str)` n'est pas contrôlé en signe. Une
saisie `-3` avec un solde positif de `5 j` donne `min(5, -3) = -3` → `jours_report = -3`
(report négatif sur un solde positif). Le helper `_parse_plafond` (ligne 1279) est réutilisable
mais ne valide pas non plus la positivité — il faudra lui ajouter ce contrôle.

**Correction recommandée** : dans la route de clôture, valider que les plafonds sont `>= 0`
avant de les passer au service (ou étendre `_parse_plafond` avec un contrôle de signe).

### 🟠 R3 — Ancienneté remise à zéro sur le nouvel exercice

`cloturer_exercice_et_reporter` (`services/solde.py:324`) crée la nouvelle allocation avec
`jours_anciennete=0` quand elle n'existe pas encore — ce qui est le cas normal à la clôture
(le nouveau paramétrage vient d'être créé). En pratique, tous les salariés repartent à 0 sauf
si leurs allocations avaient été pré-générées avant la clôture. `generer_allocations_pour_parametrage`
(ligne 365), lui, préserve l'ancienneté existante avec `allocation.jours_anciennete or 0`.
Incohérence de comportement entre les deux chemins. Voir `docs/DECISIONS.md` §Ancienneté.

**Correction recommandée** : décider d'une règle unique (reporter, recalculer depuis
`date_embauche`, ou forcer l'action manuelle) et aligner les deux fonctions.

### 🟠 R4 — Pas de garde contre une double clôture

Chaque POST crée un nouvel exercice. Un double-clic ou une ré-exécution crée un exercice de trop
et re-reporte depuis l'exercice fraîchement activé. Aucun contrôle d'idempotence.

**Correction recommandée** : étape de confirmation + vérifier l'absence d'un exercice futur avant
de créer (ou verrou anti double-submit HTTP).

### 🟡 R5 — Report CP arrondi à l'entier

Le report **RTT** est décimal (`Numeric(6,2)`). Le report **CP** reste `int(cp_a_reporter)` :
4,5 j restants → 4 j reportés. Comportement assumé côté politique RH.

**À revoir** uniquement si le report de demi-journées CP devient nécessaire.

### 🟡 R6 — Pas de validation de cohérence des dates

Aucun contrôle que `debut` du nouvel exercice est postérieur à `fin` de l'ancien (chevauchement
possible).

**Correction recommandée** : avertir si `debut <= ancien.fin_exercice`.

### 🟡 R7 — Salariés inactifs exclus du report

`User.filter_by(actif=True)` : un salarié désactivé puis réactivé après la clôture n'a aucune
allocation sur le nouvel exercice.

**À confirmer avec le métier** : comportement probablement voulu, mais à documenter explicitement.
