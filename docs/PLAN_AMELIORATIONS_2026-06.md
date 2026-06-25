---
title: "Plan d'implémentation — Améliorations & nettoyage"
date: 2026-06-25
auteur: "Kevin Roux (ERPAC) + Claude"
statut: "À valider / en attente d'exécution"
---

# Plan d'implémentation — Améliorations & nettoyage

Ce plan découle de la revue d'utilité des fonctionnalités du 2026-06-25. Les quatre
fonctionnalités optionnelles (saisie heures/RTT, intéressement, Web Push, email RH)
sont **conservées** : le travail consiste à les fiabiliser, à nettoyer la dette, et à
optimiser les points chauds — pas à retirer des modules.

## Légende

| Priorité | Sens |
|---|---|
| **P0** | Rapide, risque nul, gain immédiat. À faire en premier. |
| **P1** | Fonctionnalité décidée ou correctif à valeur directe. |
| **P2** | Optimisation / fiabilité, valeur réelle mais non bloquante. |
| **P3** | Préparation / long terme (design, déploiement). |

Effort indicatif : 🟢 < 1 h · 🟡 ~½ journée · 🔴 > 1 journée.

---

## Lot 0 — Hygiène du dépôt (P0)

Objectif : supprimer le bruit et les fichiers morts. Aucun impact fonctionnel.

### 0.1 Désuivre `node_modules/` 🟢
- **Problème** : 1347 fichiers de `node_modules/` sont suivis par git malgré le `.gitignore`
  (ajouté après coup). C'est la source du bruit massif dans `git status`.
- **Action** : `git rm -r --cached node_modules` puis commit.
- **Vérif** : `git status` propre ; `node_modules/` toujours présent sur disque (Tailwind continue de builder).
- **Risque** : nul.

### 0.2 Supprimer les fichiers morts 🟢
- `maquette-design.html` (racine, 574 lignes) — maquette autonome référencée nulle part.
- `scripts/migrations/migrate_*.py` (8 scripts one-shot) — supersédés par Alembic
  (`migrations/versions/`), « plus rejoués » (cf. commentaire `app.py`).
- **Action** : suppression (l'historique git les conserve). Pour les scripts, alternative :
  les déplacer dans un dossier `scripts/migrations/_archive/` avec un README « obsolètes ».
- **Risque** : nul (vérifier au préalable qu'aucun `import` ne pointe vers ces scripts → déjà confirmé).

### 0.3 Unifier la double route accentuée 🟢
- **Problème** : `ajouter_conge_subordonne` est exposée sur `/subordonne/...` **et**
  `/subordonné/...` (`routes/responsable.py`).
- **Action** : garder `/subordonne/...` (ASCII), retirer la variante accentuée. Vérifier qu'aucun
  template ne génère d'URL via l'endpoint accentué (l'`url_for` utilise le nom de fonction, pas l'URL → sans impact).
- **Risque** : faible (un éventuel favori sur l'ancienne URL casse — négligeable en intranet).

### 0.4 (Optionnel) Sortir les outils de dev du dépôt applicatif 🟡
- `_bmad/` et `.cursor/skills/` (des centaines de fichiers) sont versionnés.
- **Décision requise** : s'ils ne sont pas volontairement partagés en équipe, les ajouter au
  `.gitignore` + `git rm -r --cached`. Sinon, ne rien faire.

---

## Lot 1 — Email RH à chaque demande (P1) 🟡

Objectif : alerter la boîte RH entreprise (`MAIL_RH`) par email **dès qu'une demande entre dans
la file RH**, en plus de l'in-app. C'est le canal fiable tant que le HTTPS (donc le Web Push)
n'est pas garanti.

### Contexte actuel
- Nouvelle demande → in-app + Web Push immédiats (`notifier_rh_nouvelle_demande`,
  `notifier_rh_demande_transmise`), **pas d'email**.
- Email RH = uniquement le récap **hebdomadaire** (`scripts/recap_hebdo.py`).

### Étapes
1. **`services/email.py`** — ajouter `envoyer_email_demande_rh(conge, evenement: str) -> bool` :
   - retourne `False` sans rien faire si `MAIL_RH` non configuré (comme le récap) ;
   - sujet : `ERPAC Conges - Nouvelle demande : {prenom} {nom} ({periode})` ;
   - corps texte + HTML réutilisant le style d'en-tête vert ERPAC déjà présent dans le récap ;
   - `evenement` ∈ `{"directe", "transmise"}` pour nuancer le libellé (« déposée directement » /
     « transmise par le responsable »).
2. **`services/notifications.py`** — appeler la fonction depuis :
   - `notifier_rh_nouvelle_demande` → `evenement="directe"` ;
   - `notifier_rh_demande_transmise` → `evenement="transmise"`.
   L'appel est **entouré d'un `try/except`** (comme le Web Push) : un échec SMTP ne doit jamais
   bloquer la création/validation de la demande.
3. **Anti-doublon** : chaque entrée dans la file RH déclenche exactement un email (demande directe :
   1 ; transmission N1 : 1 ; création par responsable pour subordonné : 1 via `notifier_rh_nouvelle_demande`).

### Tests (`tests/`)
- Nouveau `tests/test_email_demande_rh.py` :
  - `MAIL_RH` absent → aucun envoi, pas d'erreur ;
  - `MAIL_RH` présent + `MAIL_SUPPRESS_SEND` → `send_email` appelé une fois par événement
    (mock/patch de `send_email`) ;
  - un échec SMTP simulé ne propage pas d'exception et ne bloque pas le commit de la demande.
- Vérifier la non-régression de `tests/test_workflow.py` (création/validation).

### Effort : 🟡 (½ journée avec tests). **Périmètre validé : les deux événements.**

---

## Lot 2 — Performance du dashboard RH (P2) 🟡

Objectif : éliminer le N+1 qui fait exploser le nombre de requêtes SQL à l'ouverture du dashboard.

### Problème
`routes/rh.py` (dashboard) boucle sur tous les salariés actifs et appelle `calculer_solde(s.id)`
**sans passer le `param` déjà chargé** ; chaque `calculer_solde` réinterroge le paramétrage 4×
(`_get_param`) + 4 sommes de consommation, plus une requête `conges_en_cours` par salarié.
→ ordre de grandeur : **5-9 requêtes × N salariés** (≈ 200-300 requêtes pour 30 salariés).

### Étapes
1. Passer `parametrage_id=param.id` à `calculer_solde(...)` dans la boucle dashboard → supprime
   les re-lookups de paramétrage.
2. Pré-calculer les consommations en **un seul** `somme_consommation(..., group_by="user_type")`
   (la primitive existe déjà, utilisée par l'intéressement) pour CP et RTT, validés et en attente,
   sur tous les `user_ids` en une passe ; alimenter les soldes depuis ce dict.
3. Remplacer la boucle de `count()` `conges_en_cours` par une seule requête agrégée
   (`GROUP BY user_id` sur les congés validés chevauchant aujourd'hui).
4. Idéalement, exposer une variante `calculer_soldes_lot(user_ids, param)` dans `services/solde.py`
   pour factoriser et rester testable.

### Tests
- `tests/test_solde.py` : ajouter un cas vérifiant que `calculer_soldes_lot` rend les mêmes chiffres
  que `calculer_solde` appelé individuellement (parité), pour ne pas régresser le calcul.
- Vérifier que le dashboard RH se rend toujours correctement (test d'intégration léger).

### Effort : 🟡→🔴 selon la factorisation choisie. **Mesurer avant/après** (nombre de requêtes).

---

## Lot 3 — Fiabilité production (P2) 🟢

### 3.1 Neutraliser `db.create_all()` en production 🟢
- **Problème** : `app.py` appelle `db.create_all()` au démarrage **en plus** d'Alembic → risque de
  divergence de schéma silencieuse (une table créée par `create_all` masque une migration oubliée).
- **Action** : documenter et imposer `SKIP_DB_CREATE_ALL=1` dans l'environnement de prod
  (`deploy/gestion-conges.env.example` + README IIS). `create_all` reste actif pour les tests et le
  premier démarrage local uniquement.
- **Risque** : faible (la prod passe déjà par `flask db upgrade`).

### 3.2 Validation/refus par lots : requête `IN` au lieu de `get()` en boucle 🟢
- **Problème** : `routes/rh.py` et `routes/responsable.py` font `Conge.query.get(int(cid))` par
  identifiant sélectionné → N requêtes.
- **Action** : charger l'ensemble en une fois (`Conge.query.filter(Conge.id.in_(ids))`), puis itérer.
- **Risque** : faible. Gain modeste mais gratuit.

---

## Lot 4 — Préparation passerelle ERP des heures (P3, design) 🔴

Objectif : préparer la récupération automatique des heures travaillées depuis la base de l'ERP,
pour supprimer la saisie hebdomadaire manuelle (sans changer le moteur RTT).

### Points d'ancrage déjà présents
- `models/heures_hebdo.py` : champ **`source`** (défaut `"manuel"`) → écrire `source="erp"` pour
  les lignes importées. Le moteur `services/rtt_hebdo.py` les consomme sans modification.

### À concevoir (hors de ce lot, à spécifier séparément)
1. **Schéma** : passer `HeuresHebdo.heures_travaillees` de `Integer` à `Numeric(6,2)` si l'ERP
   renvoie des heures décimales (37,5 h). Migration Alembic dédiée.
2. **Service `services/import_heures_erp.py`** : connexion à la base ERP (read-only), mapping
   salarié ERPAC ↔ ERP (clé à définir : matricule ? identifiant ?), agrégation par semaine ISO,
   upsert `HeuresHebdo(source="erp")`.
3. **Déclenchement** : tâche planifiée (comme `recap_hebdo.py`) hebdomadaire, + bouton RH « resynchroniser ».
4. **Idempotence & priorité** : règle si une semaine a à la fois une saisie `manuel` et un import
   `erp` (l'ERP écrase-t-il le manuel ?). À trancher avec le métier.

### Prérequis : accès et schéma de la base ERP (à discuter — mentionné par Kevin).
### Effort : 🔴 (chantier à part entière, à cadrer après les lots 0-3).

---

## Lot 5 — Sécurité & déploiement (P3) 🟡

### 5.1 HTTPS intranet → débloque le Web Push (déploiement, pas de code)
- Le Web Push ne s'affiche qu'en **HTTPS** (exigence navigateur). HTTPS actuellement non garanti.
- **Action** : suivre `docs/HTTPS-LOCAL-KASPERSKY.md` et `deploy/CERTIFICAT-HTTPS-INTRANET.md` ;
  vérifier ensuite les clés VAPID (`scripts/gen_vapid_keys.py`) et l'abonnement navigateur
  (`docs/VERIFIER-WEBPUSH.md`).
- Tant que ce n'est pas fait, **le Lot 1 (email RH) est le canal fiable**.

### 5.2 Durcir la CSP (long terme) 🔴
- `app.py` autorise `unsafe-inline` + `unsafe-eval` (compromis Alpine.js / FullCalendar).
- **Action future** : migrer vers Alpine **CSP build** + nonces par requête, retirer `unsafe-eval`.
- **Risque** : élevé en effort de validation UI ; faible priorité sur intranet. À planifier isolément.

---

## Ordonnancement conseillé

1. **Lot 0** (hygiène) — immédiat, débloque un dépôt propre.
2. **Lot 1** (email RH par demande) — fonctionnalité décidée, valeur directe.
3. **Lot 3** (fiabilité prod : create_all, lots IN) — rapide.
4. **Lot 2** (perf dashboard) — après mesure, factorisation propre.
5. **Lot 5.1** (HTTPS/push) — déploiement, en parallèle.
6. **Lot 4** (ERP heures) et **Lot 5.2** (CSP) — chantiers à cadrer séparément.

## Critères de « fini » globaux
- `pytest` vert (suite existante + nouveaux tests des lots 1 et 2).
- `git status` propre (Lot 0).
- Dashboard RH : nombre de requêtes SQL mesuré en baisse nette (Lot 2).
- Un email de test reçu sur `MAIL_RH` lors d'une demande, en environnement SMTP configuré (Lot 1).
