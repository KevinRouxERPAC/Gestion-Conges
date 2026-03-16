---
stepsCompleted: [1]
inputDocuments: []
session_topic: 'Évolution de Gestion des Congés : rôles et gestion des soldes'
session_goals: 'Clarifier les rôles RH / Responsable / Salarié et définir une gestion propre des soldes CP (jours) et RTT (heures), plus l’auto-allocation annuelle.'
selected_approach: 'Discussion guidée + conseils multi-agents'
techniques_used: []
ideas_generated: []
context_file: ''
---

# Brainstorming Session Results

**Facilitator:** Kévin  
**Date:** 2026-03-13

## Session Overview

**Topic:** Évolution fonctionnelle et technique de l’application de gestion des congés (ERPAC) pour mieux couvrir tous les types d’absences, les rôles (RH, responsable, salarié) et la séparation CP / RTT.

**Goals:**
- Donner une vision claire des responsabilités de chaque rôle (RH, responsable, salarié).
- Séparer proprement la gestion des congés payés (en jours) et des RTT (en heures).
- Définir une mécanique d’allocation automatique des droits en début d’exercice (CP + RTT).
- Encadrer le workflow de validation à deux niveaux (responsable puis RH).

### Contexte projet

- Application Flask + SQLite existante, déjà structurée avec `models/`, `routes/`, `services/`, `templates/`.
- Logique métier déjà centralisée dans `services/solde.py`, `services/calcul_jours.py`, `services/notifications.py`.
- Validation à deux niveaux déjà en place dans le modèle `Conge` (statuts, champs de validation).

## Décisions sur les rôles

### Rôle Salarié

- Peut :
  - Voir son solde de congés CP et RTT (affichage séparé).
  - Voir l’historique de ses absences et un calendrier (avec éventuellement les congés de tous pour l’organisation).
  - Demander un congé :
    - Soit via son responsable (niveau 1) qui valide/refuse puis transmet au RH.
    - Soit directement aux RH s’il n’a pas de responsable.

### Rôle Responsable

- Responsable = salarié avec un menu supplémentaire “Mon équipe”.
- Peut :
  - Voir la liste des demandes de son équipe avec statut `en_attente_responsable`.
  - **Valider** une demande → passe en `en_attente_rh` + notification RH.
  - **Refuser** une demande avec motif obligatoire → statut `refuse` + notification salarié.
  - **Créer une demande de congé pour un membre de son équipe** (statut initial `en_attente_rh`).
- Accès à un calendrier de congés de l’équipe ou global pour organiser le travail.

### Rôle RH

- Peut tout gérer :
  - Utilisateurs (création, modification, statut actif/inactif, rôle, rattachement à un responsable).
  - Tous les types d’absences (CP, RTT, Sans solde, Maladie, Ancienneté, etc.).
  - Paramétrage annuel (exercice, jours de CP par défaut, heures RTT par défaut, jours fériés).
  - Validation niveau 2 : demandes en `en_attente_rh` (valider/refuser).
  - Export des congés (Excel / PDF) par salarié et pour l’équipe.

## Gestion des soldes : CP en jours, RTT en heures

### CP (jours)

- Mesurés en **jours ouvrables** (calcul existant via `compter_jours_ouvrables`).
- Comptent dans le solde :
  - **CP**.
  - **Ancienneté** (jours supplémentaires).
- Le modèle `AllocationConge` conserve :
  - `jours_alloues` (CP de base).
  - `jours_anciennete`.
  - `jours_report`.
- Solde CP :
  - `cp_total_alloue = jours_alloues + jours_anciennete + jours_report`.
  - `cp_total_consomme = somme(nb_jours_ouvrables)` pour les congés validés de type `CP` ou `Anciennete` sur l’exercice actif.
  - `cp_solde_restant = cp_total_alloue - cp_total_consomme`.

### RTT (heures)

- Mesurés en **heures entières** (1, 2, 3…).
- Nouveau découpage dans `AllocationConge` :
  - `rtt_heures_allouees` (heures RTT allouées pour l’exercice).
  - `rtt_heures_reportees` (heures RTT reportées).
  - `rtt_total_alloue = rtt_heures_allouees + rtt_heures_reportees`.
- Nouveau champ dans `Conge` :
  - `nb_heures_rtt` (entier, obligatoire quand `type_conge == "RTT"`, nul sinon).
- Solde RTT :
  - `rtt_total_consomme = somme(nb_heures_rtt)` des congés validés de type RTT sur l’exercice actif.
  - `rtt_solde_restant = rtt_total_alloue - rtt_total_consomme`.

### Typologie des absences

- **Impact sur le solde CP (jours)** :
  - Débitent : `CP`, `Anciennete`.
  - Ne débitent pas : `RTT`, `Sans solde`, `Maladie`, autres types.
- **Impact sur le solde RTT (heures)** :
  - Débitent : uniquement les congés de type `RTT` via `nb_heures_rtt`.
  - Ne débitent pas : tous les autres types.
- Tous les types restent visibles dans :
  - Les listes de congés.
  - Les exports Excel/PDF.
  - Les calendriers (salarié, responsable, RH).

## Auto-allocation annuelle (CP + RTT)

### Paramétrage annuel

- `ParametrageAnnuel` étendu avec :
  - `jours_conges_defaut` (jours CP par défaut).
  - `rtt_heures_defaut` (heures RTT par défaut pour l’exercice).

### Génération des allocations

- Fonction de service `generer_allocations_pour_parametrage(param)` :
  - Pour chaque salarié **actif** :
    - Récupère ou crée une `AllocationConge` pour `(user_id, parametrage_id)`.
    - Règle CP :
      - `jours_alloues = param.jours_conges_defaut`.
      - `jours_anciennete` et `jours_report` initialisés/cohérents.
    - Règle RTT :
      - `rtt_heures_allouees = param.rtt_heures_defaut`.
      - `rtt_heures_reportees` initialisé/cohérent.
- Déclenchée par un bouton côté RH dans l’écran de paramétrage :
  - Action “Générer les allocations pour l’exercice actif”.

## Adaptations techniques (haut niveau)

### Modèles

- `AllocationConge` :
  - Ajouter `rtt_heures_allouees` et `rtt_heures_reportees`.
  - Propriété `total_rtt_heures` pour retourner la somme.
- `ParametrageAnnuel` :
  - Ajouter `rtt_heures_defaut`.
- `Conge` :
  - Ajouter `nb_heures_rtt` (nullable, utilisé uniquement pour RTT).

### Services de solde

- `calculer_jours_cps_consommes(user_id, parametrage_id)` : somme des jours pour `CP` + `Anciennete`.
- `calculer_heures_rtt_consommes(user_id, parametrage_id)` : somme des heures RTT.
- `calculer_solde(user_id, parametrage_id=None)` :
  - Retourne un dict contenant à la fois :
    - les infos CP (total alloué, consommé, restant) pour compatibilité avec les écrans actuels,
    - les infos RTT (heures allouées, consommées, restantes).
- Deux vérifications de solde :
  - `verifier_solde_suffisant(user_id, nb_jours, conge_id_exclu=None)` pour CP.
  - `verifier_solde_rtt_suffisant(user_id, nb_heures, conge_id_exclu=None)` pour RTT.

### Routes et formulaires

- Demande de congé salarié :
  - Si `type_conge == "RTT"` :
    - Lecture d’un champ `nb_heures_rtt` (entier >= 1).
    - Contrôle via `verifier_solde_rtt_suffisant`.
    - `nb_jours_ouvrables` peut rester à 0 (ou non significatif pour le solde).
  - Si `type_conge in ("CP", "Anciennete")` :
    - Calcul de `nb_jours_ouvrables` via `compter_jours_ouvrables`.
    - Contrôle via `verifier_solde_suffisant`.
  - Pour les autres types (Sans solde, Maladie…) :
    - Pas de contrôle de solde, mais affichage et export normaux.
- Côté RH et Responsable :
  - Même logique de séparation CP/RTT appliquée dans les écrans d’ajout / modification / validation de congés.

## Prochaines étapes suggérées

- Mettre en place les **scripts de migration SQLite** pour ajouter les nouvelles colonnes (RTT) sans casser les données existantes.
- Adapter progressivement :
  - Les vues de solde salarié et RH pour afficher clairement :
    - “Solde CP : X jours”.
    - “Solde RTT : Y heures”.
  - Les exports pour séparer CP/RTT et autres absences.
- Ajouter éventuellement :
  - Un mécanisme d’**archivage** des congés anciens.
  - Des tests unitaires sur :
    - les calculs de solde CP / RTT,
    - le workflow complet salarié → responsable → RH.

