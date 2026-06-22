---
title: "Deep-dive — Clôture d'exercice & report CP/RTT"
date: 2026-06-02
auteur: "Mary (Business Analyst, BMAD)"
perimetre: "routes/rh.py:cloture_exercice ; services/solde.py:cloturer_exercice_et_reporter ; templates/rh/cloture_exercice.html ; tests/test_cloture.py"
---

# Deep-dive : Clôture d'exercice

> **⚠️ Document d'audit daté (2026-06-02).** Plusieurs risques identifiés ci-dessous ont depuis été
> corrigés. Mises à jour 2026-06-16 :
> - **R1 (congés à cheval) → ✅ corrigé** : décompte au prorata dans `services/consommation.py`
>   (`somme_consommation` / `_prorata_fenetre`). Voir [PLAN_IMPLEMENTATION.md](PLAN_IMPLEMENTATION.md) R1.
> - **« Plancher à 0 » → obsolète** : la clôture reporte désormais un solde **négatif** tel quel
>   (report de déficit), le plafond ne s'appliquant qu'au report positif.
> - **R5 (demi-journées RTT) → ✅ corrigé** : les heures RTT sont décimales (`Numeric(6,2)`, R3) et
>   reportées sans troncature. Le report CP en jours reste arrondi à l'entier (politique RH assumée).
> - R2/R3/R4/R6/R7 restent à l'appréciation RH (non bloquants).

## 1. Rôle métier
Opération **annuelle** : on ferme l'exercice actif, on en crée un nouveau, et on **reporte** les soldes
restants (CP en jours, RTT en heures) vers le nouvel exercice, éventuellement **plafonnés**.

## 2. Flux d'exécution
1. **GET** `/rh/cloture-exercice` : aperçu (salariés + soldes qui seraient reportés).
2. **POST** :
   - Parse dates + `jours_conges_defaut` + `rtt_heures_defaut` (try/except).
   - Vérifie `fin > debut`.
   - Parse `plafond_report_cp` / `plafond_report_rtt` (vides → `None` = report intégral).
   - Crée `nouveau` `ParametrageAnnuel` (`actif=False`), **reporte** `rtt_calc_mode/reference/coef` de l'ancien, `flush()`.
   - Appelle `cloturer_exercice_et_reporter(nouveau, plafonds)` dans un `try/except` → `rollback` si erreur.
   - `log_action("exercice.cloturer", …)` + `commit`.
3. **Service** `cloturer_exercice_et_reporter` :
   - `ancien` = paramétrage `actif==True` et `id != nouveau.id`.
   - Pour chaque **salarié actif** : `solde = calculer_solde(s, ancien)`,
     `cp_restant = max(0, solde_restant)`, idem RTT.
   - `cp_a_reporter = min(cp_restant, plafond)` si plafond sinon `cp_restant`.
   - Crée/maj l'`AllocationConge` du nouvel exercice : `jours_report = int(cp_a_reporter)`, `rtt_heures_reportees = int(rtt_a_reporter)`.
   - `ancien.actif = False` ; `nouveau.actif = True`. Retourne totaux.

## 3. Ce qui est bien fait ✅
- **Atomicité** : service sans `commit`, route qui `commit`/`rollback` → tout ou rien.
- **Config RTT préservée** (`rtt_calc_mode/reference/coef`) sur le nouvel exercice.
- **Report de déficit** (depuis 2026) : un solde négatif est reporté tel quel ; le plafond ne borne que le report positif.
- **Plafond de report** fonctionnel et testé (intégral, plafonné, solde négatif).
- **Audit** complet (ancien/nouveau, plafonds, totaux, nb salariés).
- **Aperçu GET** avant action + accès `rh_required`.

## 4. Risques & bugs identifiés ⚠️

### ✅ R1 — Congés à cheval sur la bascule d'exercice (CORRIGÉ 2026-06-16)
*Avant* : `somme_consommation` ne comptait un congé que s'il était entièrement contenu
(`date_debut >= min AND date_fin <= max`) → un congé traversant le 31/12 → 01/01 n'était compté
dans aucun exercice (consommation sous-évaluée, report trop généreux).
*Maintenant* : décompte **au prorata** des jours ouvrables dans chaque fenêtre (`_prorata_fenetre`),
avec l'invariant « somme des deux parts = total du congé ». Couvert par `test_consommation.py`
(`TestProrataFrontiere`) et `test_cloture.py` (`TestClotureProrataFrontiere`).

### 🟠 R2 — Plafond de report négatif accepté
Dans la route, `plafond_cp = int(plafond_cp_str)` sans contrôle de signe. Une saisie `-5` donne
`min(cp_restant, -5) = -5` → `jours_report = -5`. (Le helper `_parse_plafond` existe déjà pour les types
exceptionnels mais **n'est pas réutilisé ici**.)
*Reco : rejeter les plafonds < 0 (réutiliser `_parse_plafond`).*

### 🟠 R3 — Ancienneté remise à zéro sur le nouvel exercice
À la création de l'allocation du nouvel exercice, `jours_anciennete = 0` (en dur). Le bonus d'ancienneté
n'est **pas reporté ni recalculé** → tous les salariés repartent à 0 d'ancienneté tant que le RH ne ré-édite
pas chaque allocation. (À l'inverse, `generer_allocations_pour_parametrage` **préserve** l'ancienneté existante :
incohérence de comportement entre les deux chemins.)
*Reco : décider de la règle (reporter, recalculer selon `date_embauche`, ou documenter l'action manuelle).*

### 🟠 R4 — Pas de garde contre une double clôture
Chaque POST crée **un nouvel exercice**. Un double-clic ou une ré-exécution crée un exercice de trop et
re-reporte depuis l'exercice fraîchement activé. Aucun contrôle d'idempotence ni d'écran de confirmation.
*Reco : étape de confirmation + détecter si un exercice futur existe déjà / verrou anti double-submit.*

### 🟡 R5 — Demi-journées au report (CP)
Le report **RTT** est désormais décimal (`Numeric(6,2)`, plus de troncature — cf. R3). Le report **CP**
en jours reste arrondi à l'entier (`int(cp_a_reporter)`) : 4,5 j restants → 4 j reportés. Comportement
assumé côté politique RH ; à revoir si le report de demi-journées CP devient nécessaire.

### 🟡 R6 — Pas de validation de cohérence des dates du nouvel exercice
Aucun contrôle que `debut` du nouvel exercice est **postérieur** à `fin` de l'ancien (chevauchement possible).
*Reco : avertir si `debut <= ancien.fin_exercice`.*

### 🟡 R7 — Salariés inactifs exclus du report
`User.filter_by(actif=True)` : un salarié désactivé puis réactivé après la clôture n'a aucune allocation
sur le nouvel exercice (solde 0 jusqu'à génération manuelle). Probablement voulu, mais à confirmer.

## 5. Couverture de tests
Bonne base (`tests/test_cloture.py`) : report intégral, report plafonné, solde négatif → 0, accès RH, aperçu.
**Manquants** : congé à cheval (R1), plafond négatif (R2), report de l'ancienneté (R3), double clôture (R4),
demi-journées au report (R5).

## 6. Plan d'action recommandé (par priorité)
1. **R1** (correctness des soldes) : traiter les congés à cheval — impact chiffré direct.
2. **R2** : réutiliser `_parse_plafond` dans la route de clôture (rapide, sûr).
3. **R3** : trancher la règle d'ancienneté et l'aligner entre clôture et génération d'allocations.
4. **R4** : ajouter confirmation + garde anti double clôture.
5. **R5/R6/R7** : décisions de politique RH + petits garde-fous.
6. Compléter les tests pour chaque point ci-dessus.
