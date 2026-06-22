---
title: "Analyse d'utilité des fonctionnalités — ERPAC Gestion des Congés"
date: 2026-06-02
auteur: "Mary (Business Analyst, BMAD)"
methode: "Deep scan de routes/ services/ models/ templates/ + app.py/config.py"
---

# Analyse d'utilité des fonctionnalités

> **⚠️ Audit daté (2026-06-02).** Plusieurs constats/manques ci-dessous ont depuis été traités
> (mise à jour 2026-06-16) :
> - ✅ **Changement de mot de passe self-service** livré (`/changer-mot-de-passe`, tous rôles).
> - ✅ **Calcul de consommation factorisé** en une source de vérité unique (`services/consommation.py`,
>   `somme_consommation`) — et fiabilisé pour les **congés à cheval** sur l'exercice (prorata, R1).
> - ✅ **Archivage des congés anciens** livré (flag `Conge.archive`).
> - ✅ **RTT hebdomadaire** : le mode « heures fixes » a été remplacé par un calcul hebdomadaire
>   décimal (`services/rtt_hebdo.py`, `models/heures_hebdo.py`). Les « fichiers fantômes » mentionnés
>   au §11 **existent désormais** et sont le moteur RTT actif.
> - ✅ **Sécurité** : cookie de session durci (R2) et anti-énumération par timing (R4).
>
> Restent des **décisions produit** (intéressement, Web Push, email RH : garder/mettre en veille).
> Détail d'implémentation : [PLAN_IMPLEMENTATION.md](PLAN_IMPLEMENTATION.md).

Ce document évalue **l'utilité de chaque fonctionnalité** de l'application, du point de vue
métier (gestion RH des congés). Objectif : aider à décider **quoi garder, renforcer, simplifier
ou retirer**, et garantir que *« l'application fonctionne correctement »*.

## Légende des niveaux d'utilité

| Niveau | Signification |
|---|---|
| 🟢 **Essentielle** | Cœur du produit. Sans elle, l'app perd sa raison d'être. |
| 🔵 **Importante** | Forte valeur, utilisée régulièrement par un rôle clé. |
| 🟡 **Confort** | Pratique mais non vitale ; gain d'ergonomie ou de productivité. |
| 🟠 **Faible / Optionnelle** | Valeur limitée, usage occasionnel, ou dépendante d'une config absente. |
| ⚫ **Morte / Inexploitée** | Code présent mais non appelé / non atteignable. À nettoyer. |

---

## 1. Authentification & sécurité

| Fonctionnalité | Utilité | Usage | Valeur & remarques |
|---|---|---|---|
| Connexion identifiant + mot de passe (bcrypt) | 🟢 Essentielle | Tous | Porte d'entrée. Rate-limiting `/login` (10/min, 50/h) + CSRF global = bon socle. |
| Redirection par rôle (rh/responsable/salarié) | 🟢 Essentielle | Tous | Aiguille chaque rôle vers son espace. |
| Déconnexion | 🟢 Essentielle | Tous | — |
| En-têtes de sécurité (CSP, X-Frame, HSTS conditionnel) | 🔵 Importante | Transversal | Bonne hygiène intranet. CSP avec `unsafe-inline` (compromis Alpine.js) à durcir plus tard via nonces. |
| Politique mot de passe (`valider_mot_de_passe`, ≥ 8) | 🟡 Confort | RH (création) | Présente dans `auth_utils`, mais **pas de changement de mot de passe en self-service** (cf. §11 manques). |

**Constat** : socle d'auth solide. **Manque notable** : aucun écran « changer mon mot de passe » pour
l'utilisateur (seul le RH peut réinitialiser via édition du salarié).

---

## 2. Gestion des congés (cœur métier)

| Fonctionnalité | Utilité | Usage | Valeur & remarques |
|---|---|---|---|
| Demande de congé (salarié) | 🟢 Essentielle | Salarié | Raison d'être de l'app. Centralisée dans `creer_conge.construire_conge`. |
| Workflow 2 niveaux (responsable → RH) | 🟢 Essentielle | Resp./RH | Reflète l'organisation réelle. Statuts clairs : `en_attente_responsable → en_attente_rh → valide/refuse`. |
| Création directe RH (validée d'emblée) | 🔵 Importante | RH | Saisie a posteriori / cas particuliers. |
| Création par le responsable pour un subordonné | 🟡 Confort | Responsable | Pratique, mais double avec la saisie RH. 2 URLs (avec/sans accent) = dette à unifier. |
| Modification / suppression d'un congé (RH) | 🔵 Importante | RH | Corrections. Suppression auditée. |
| Annulation d'une demande en attente (salarié) | 🔵 Importante | Salarié | Autonomie de l'employé, réduit la charge RH. |
| Validation / refus (unitaire + **par lots**) | 🔵 Importante | Resp./RH | Le traitement par lots est un vrai gain de productivité en période de pointe. |
| Demi-journées aux bornes | 🟡 Confort | Tous | Précision du décompte ; bien testé (`test_demi_journees`). |
| Détection de chevauchement | 🔵 Importante | Tous | Évite les doublons/erreurs de saisie. |
| Décompte jours ouvrables (hors week-ends + fériés) | 🟢 Essentielle | Tous | Brique de calcul réutilisée partout (`calcul_jours`). |

**Constat** : c'est la colonne vertébrale, bien factorisée. La centralisation dans `construire_conge`
est un atout (évite les divergences entre les 4 points de création).

---

## 3. Types d'absences & soldes

| Fonctionnalité | Utilité | Usage | Valeur & remarques |
|---|---|---|---|
| Types de base : CP, Ancienneté, RTT, Sans solde, Maladie | 🟢 Essentielle | Tous | Couvre les cas courants. |
| Solde CP (jours) : alloué / consommé / en attente / projeté | 🟢 Essentielle | Tous | Cœur du suivi. `solde.py` bien structuré. |
| Solde RTT (heures) séparé | 🔵 Importante | Tous | Distinction jours/heures pertinente. |
| **Congés exceptionnels** paramétrables (jours/heures + plafond) | 🔵 Importante | RH | Flexibilité (mariage, enfant malade…). Plafond contrôlé à la création **et** re-vérifié à la validation RH. Récemment fiabilisé (demi-journées non tronquées). |
| Alerte « salariés à risque » (solde élevé en fin d'exercice) | 🟡 Confort | RH | Bon outil proactif anti-perte de CP. |

**Constat** : modèle de solde complet et cohérent. Les congés exceptionnels ajoutent une vraie
souplesse sans polluer les soldes CP/RTT.

---

## 4. Paramétrage annuel, allocations & clôture

| Fonctionnalité | Utilité | Usage | Valeur & remarques |
|---|---|---|---|
| Paramétrage de l'exercice (dates, CP/RTT par défaut) | 🟢 Essentielle | RH | Prérequis de tout calcul de solde. |
| Génération des allocations CP/RTT par salarié | 🟢 Essentielle | RH | Initialise les droits de l'exercice. |
| Édition d'allocation individuelle (CP/ancienneté/report/RTT) | 🔵 Importante | RH | Ajustements au cas par cas. |
| **Clôture d'exercice + report plafonné** (CP & RTT) | 🔵 Importante | RH | Opération annuelle critique. Plafond de report paramétrable. |
| Jours fériés : auto (français) + ajout/suppression manuels | 🔵 Importante | RH | Impacte directement le décompte. Calcul de Pâques inclus. |

**Constat** : tout le cycle annuel est couvert. La clôture est le point le plus sensible —
à tester avant chaque fin d'exercice (voir recommandations).

---

## 5. Heures & RTT calculées

| Fonctionnalité | Utilité | Usage | Valeur & remarques |
|---|---|---|---|
| Saisie mensuelle d'heures (payées/trajet/travaillées) | 🟡 Confort | RH | Alimente le calcul RTT « mode heures ». Saisie manuelle = charge RH. |
| Calcul RTT depuis les heures (`mode='heures'`) | 🟠 Faible/Optionnelle | RH | Utile **seulement** si `rtt_calc_mode='heures'`. Sinon le mode `fixe` suffit. Fonctionnalité avancée, probablement peu utilisée. |
| Consultation de ses heures (salarié) | 🟡 Confort | Salarié | Transparence pour l'employé. |

**Constat** : volet le plus « optionnel ». À confirmer : est-il réellement exploité (mode `heures`
activé) ? Si non, candidat à **simplification/mise en veille**.

---

## 6. Intéressement

| Fonctionnalité | Utilité | Usage | Valeur & remarques |
|---|---|---|---|
| Périodes d'intéressement (CRUD) | 🟠 Faible/Optionnelle | RH | Fonctionnalité métier annexe (calcul de points selon absences). |
| Règles de malus par type d'absence (CRUD) | 🟠 Faible/Optionnelle | RH | Paramétrage fin. |
| Calcul + export Excel de l'intéressement | 🟠 Faible/Optionnelle | RH | Valeur réelle mais usage ponctuel (1×/période). |

**Constat** : module **cohérent mais périphérique** par rapport au cœur « congés ». Forte valeur
pour qui s'en sert, nulle sinon. À garder si utilisé ; sinon, candidat à isolement/documentation.

---

## 7. Exports & reporting

| Fonctionnalité | Utilité | Usage | Valeur & remarques |
|---|---|---|---|
| Export Excel salarié / équipe | 🔵 Importante | Salarié/RH | Demandé en pratique (archivage, contrôle). |
| Export PDF salarié (avec solde) | 🟡 Confort | Salarié/RH | Document présentable. |
| **Export comptable CP/RTT à une date** | 🔵 Importante | RH | Interface avec la paie/compta = forte valeur. |
| Export intéressement | 🟠 Faible/Optionnelle | RH | Lié au module §6. |

**Dette technique** : helpers `_style_header_xlsx` / `_autosize_columns` **dupliqués** dans 3 modules
d'export → à factoriser.

---

## 8. Notifications

| Fonctionnalité | Utilité | Usage | Valeur & remarques |
|---|---|---|---|
| Notifications in-app + badge compteur | 🔵 Importante | Tous | Feedback immédiat du workflow. Fiable (pas de dépendance externe). |
| Web Push (VAPID / service worker) | 🟠 Faible/Optionnelle | Tous | **Dépend du HTTPS** : en HTTP, le push part mais n'est pas affiché. Valeur réelle conditionnée au déploiement HTTPS + abonnement navigateur. |
| Email récap hebdo RH (`MAIL_RH`) | 🟡 Confort | RH | Utile **si** `MAIL_RH` configuré et tâche planifiée active (`scripts/recap_hebdo.py`). |

**Constat** : l'in-app est le canal robuste. Web Push et email sont des **bonus conditionnels** ;
ne pas surinvestir tant que HTTPS/SMTP ne sont pas garantis en prod.

---

## 9. Délégations

| Fonctionnalité | Utilité | Usage | Valeur & remarques |
|---|---|---|---|
| Délégation temporaire de validation N1 (suppléant) | 🟡 Confort | Responsable | Gère les absences du responsable (congés, etc.). Bien intégré au périmètre de validation (`subordonnes_effectifs`). |

**Constat** : fonctionnalité de **continuité de service** appréciable dès qu'il y a des responsables.

---

## 10. Audit & administration

| Fonctionnalité | Utilité | Usage | Valeur & remarques |
|---|---|---|---|
| Journal d'audit (`log_action` + écran paginé/filtré) | 🔵 Importante | RH | Traçabilité des actions sensibles (création/validation/suppression/clôture/import). Précieux en cas de litige RH. |
| Import salariés (CSV/Excel, dry-run) | 🔵 Importante | RH | Gain énorme à l'initialisation / mises à jour de masse. Le dry-run sécurise. |
| CRUD salariés + activation/désactivation | 🟢 Essentielle | RH | Gestion du référentiel utilisateurs. |
| API interne (`/api/jours-feries`, `/api/jours-ouvrables`) | 🟡 Confort | Front | Évite de dupliquer le décompte côté JS. Bonne pratique. |

---

## 11. Code mort, redondances & manques (axe « fonctionner correctement »)

### ⚫ Code mort / inexploité (à nettoyer)
- `services/email.py` → `envoyer_notification_validation()` et `envoyer_notification_refus()` :
  **jamais appelés** (les notifs salarié passent par in-app/Web Push, choix RGPD). → Supprimer ou documenter.
- **Fichiers fantômes** dans l'index (absents du disque) : `services/rtt_hebdo.py`, `models/heures_hebdo.py`,
  `tests/test_rtt_hebdo.py`, `templates/auth/changer_mot_de_passe.html`, migrations `*_seuil_hebdo` / `*_drop_rtt_obsolete`.
  → Vestiges d'un ancien calcul RTT « hebdomadaire » supprimé. Rien à corriger dans le code vivant ; rafraîchir l'index/VCS.
- Champ `User.email` : collecté à l'import mais **sous-exploité** (sert seulement au récap RH).

### ♻️ Redondances (à factoriser)
- **Calcul de consommation** (somme jours/heures validés) ré-implémenté dans `solde.py`,
  `conges_exceptionnels.py`, `export_comptable.py`, `interessement.py` → **risque de divergence** des filtres/bornes.
  *Recommandation : extraire une primitive commune `sommer_consommation(...)`.*
- Helpers d'export Excel dupliqués (3 modules) → utilitaire partagé.
- 2 URLs pour `ajouter_conge_subordonne` (avec/sans accent) → en garder une.

### 🧩 Manques fonctionnels
- **Changement de mot de passe self-service** : absent (seul le RH réinitialise).
- **Archivage des congés anciens** : non implémenté (cf. checklist §10).
- **Rapports additionnels** (par service / type / période) : non implémentés.

---

## 12. Synthèse : quoi garder, renforcer, surveiller

### 🟢 Garder & protéger (cœur)
Auth, demande/validation 2 niveaux, soldes CP/RTT, paramétrage+allocations, clôture d'exercice,
jours fériés, décompte ouvrables, CRUD salariés, audit, import salariés.

### 🔵 Renforcer (forte valeur, à fiabiliser)
Exports (dont comptable), congés exceptionnels, traitement par lots, notifications in-app.
→ Action : factoriser le calcul de consommation pour éviter les écarts de chiffres entre écrans/exports.

### 🟠 Décider explicitement (optionnelles / conditionnelles)
RTT « mode heures » + saisie d'heures, **intéressement**, Web Push, email récap RH.
→ Action : confirmer avec les utilisateurs RH si chacune est réellement utilisée. Sinon, mettre en veille/documenter
pour réduire la surface de maintenance.

### ⚫ Nettoyer
Fonctions email mortes, helpers dupliqués, double URL, fichiers fantômes de l'index.

---

## 13. Recommandations pour « que l'application fonctionne correctement »

1. **Tests ciblés sur les zones à risque** : clôture d'exercice + report (opération annuelle, peu jouée),
   et cohérence des chiffres entre `solde`, `export_comptable` et `interessement` (calcul de consommation dupliqué).
2. **Factoriser le calcul de consommation** en une seule fonction source de vérité.
3. **Clarifier les fonctionnalités optionnelles** (RTT heures, intéressement, Web Push, email) :
   activées ou non en prod ? Documenter la config requise (HTTPS pour Web Push, SMTP/`MAIL_RH` pour l'email).
4. **Ajouter le changement de mot de passe self-service** (manque le plus visible côté utilisateur).
5. **Nettoyer le code mort** et l'index désynchronisé pour réduire la confusion de maintenance.
6. **Unifier la création de congé** (responsable vs RH) et les routes en double.

> Tout cela sans remettre en cause l'architecture : le socle est sain, bien testé sur le cœur,
> et la dette est localisée et maîtrisable.
