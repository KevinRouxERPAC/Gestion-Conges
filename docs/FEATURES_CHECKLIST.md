---
title: "Checklist fonctionnelle - Gestion des Congés"
---

## 1. Rôles et droits

- [x] **Salarié**: peut se connecter avec identifiant/mot de passe.
- [x] **Salarié**: peut consulter son historique de congés (liste + détails).
- [x] **Salarié**: voit son **solde CP (jours)** et son **solde RTT (heures)** sur l'écran d'accueil.
- [x] **Salarié**: peut consulter un **calendrier** de ses congés sur une année.
- [x] **Salarié**: peut voir (optionnellement) un calendrier incluant les congés des autres salariés.
- [x] **Salarié**: peut créer une **demande de congé** (CP, RTT, Sans solde, Maladie…).
- [x] **Salarié**: peut annuler une demande encore en attente (responsable ou RH).
- [x] **Salarié**: reçoit des notifications (in‑app / Web Push) lors des validations/refus de ses demandes.

- [x] **Responsable**: dispose d'un **tableau de bord responsable** distinct.
- [x] **Responsable**: voit la liste des demandes de son équipe en `en_attente_responsable`.
- [x] **Responsable**: peut **valider** une demande de son équipe (passe en `en_attente_rh` + notification RH).
- [x] **Responsable**: peut **refuser** une demande de son équipe avec un motif obligatoire (notification salarié).
- [x] **Responsable**: voit la liste de ses subordonnés (actifs/inactifs).
- [x] **Responsable**: peut accéder à un calendrier global pour organiser l'activité de son équipe.
- [x] **Responsable** (optionnel): peut créer un congé (CP/RTT/…) pour un membre de son équipe.

- [x] **RH**: peuvent créer / modifier / désactiver des utilisateurs (rôle, responsable hiérarchique, date d'embauche).
- [x] **RH**: accèdent à un **dashboard global** avec statistiques, liste des salariés, solde CP et indication RTT.
- [x] **RH**: disposent d'une fiche détaillée par salarié (soldes CP/RTT, historique des congés, actions CRUD).
- [x] **RH**: visualisent et traitent les demandes `en_attente_rh` (valider/refuser avec motif).

## 2. Types d'absences et règles de solde

- [x] **Types gérés**: `CP`, `Anciennete`, `RTT`, `Sans solde`, `Maladie` (et extensible).
- [x] **CP (jours)**: comptent dans le solde CP (jours ouvrables).
- [x] **Anciennete (jours)**: compte aussi dans le solde CP.
- [x] **RTT (heures)**: ne débite pas le solde CP, mais un **compteur RTT en heures** séparé.
- [x] **Sans solde**: n'impacte aucun solde mais est visible partout (liste, export, calendrier).
- [x] **Maladie**: n'impacte aucun solde mais est visible partout (liste, export, calendrier).
- [x] Tous les types d'absences apparaissent dans:
  - [x] Les listes de congés.
  - [x] Les exports Excel / PDF.
  - [x] Les calendriers (salarié, responsable, RH).

## 3. CP (jours) – logique de calcul

- [x] **Allocation CP annuelle** par salarié et exercice:
  - [x] `jours_alloues` (CP de base).
  - [x] `jours_anciennete` (bonus).
  - [x] `jours_report` (report d'exercice précédent).
- [x] **Consommation CP**:
  - [x] Somme de `nb_jours_ouvrables` pour les congés validés de type `CP` ou `Anciennete` dans l'exercice actif.
- [x] **Solde CP**:
  - [x] `cp_total_alloue = jours_alloues + jours_anciennete + jours_report`.
  - [x] `cp_total_consomme` correctement calculé.
  - [x] `cp_solde_restant = cp_total_alloue - cp_total_consomme`.
- [x] **Contrôles de solde CP**:
  - [x] À la demande/modification côté salarié.
  - [x] À l'ajout/modification côté RH.
  - [x] À la validation finale RH.

## 4. RTT (heures) – logique de calcul

- [x] **Allocation RTT annuelle** par salarié et exercice:
  - [x] `rtt_heures_allouees` (heures RTT de base).
  - [x] `rtt_heures_reportees` (heures reportées).
- [x] **Consommation RTT**:
  - [x] Les RTT sont saisis en **heures entières** via `nb_heures_rtt`.
  - [x] La somme de `nb_heures_rtt` est calculée pour les congés validés de type `RTT`.
- [x] **Solde RTT**:
  - [x] `rtt_total_alloue = rtt_heures_allouees + rtt_heures_reportees`.
  - [x] `rtt_total_consomme` correctement calculé.
  - [x] `rtt_solde_restant = rtt_total_alloue - rtt_total_consomme`.
- [x] **Contrôles de solde RTT**:
  - [x] À la demande/modification côté salarié.
  - [x] À l'ajout/modification côté RH.
  - [x] À la validation finale RH.

## 5. Workflows de validation & notifications

- [x] **Workflow salarié → responsable → RH**:
  - [x] Avec `responsable_id`: statut initial `en_attente_responsable`.
  - [x] Responsable valide → statut `en_attente_rh`.
  - [x] Responsable refuse → statut `refuse` + motif obligatoire.
  - [x] Sans responsable: statut initial `en_attente_rh`.
- [x] **Niveau RH**:
  - [x] RH voient les demandes en `en_attente_rh`.
  - [x] Validation → statut `valide` + notification salarié.
  - [x] Refus (motif obligatoire) → statut `refuse` + notification salarié.
- [x] **Notifications**:
  - [x] In‑app pour salarié/responsable/RH.
  - [x] Web Push (avec abonnement navigateur).
  - [x] Email vers la boîte RH (MAIL_RH) pour certaines notifications (sans données personnelles salariés).

## 6. Paramétrage annuel & génération des droits

- [x] **ParamétrageAnnuel**:
  - [x] Dates de début et fin d'exercice.
  - [x] `jours_conges_defaut` (jours CP par défaut).
  - [x] `rtt_heures_defaut` (heures RTT par défaut).
- [x] **Jours fériés**:
  - [x] Chargement automatique des jours fériés français.
  - [x] Gestion manuelle (ajout/suppression, auto_genere vs manuel).
- [x] **Génération des allocations**:
  - [x] Bouton RH "Générer les allocations CP/RTT".
  - [x] Crée ou met à jour les `AllocationConge` pour tous les salariés actifs (CP + RTT).

## 7. Calendriers et vues globales

- [x] **Calendrier salarié**:
  - [x] Vue annuelle de ses congés.
  - [x] Option pour voir tous les congés (organisation de l'équipe).
- [x] **Calendrier RH**:
  - [x] Vue globale sur l'exercice actif (FullCalendar).
  - [x] Légende des types de congés (CP/RTT/Maladie/Ancienneté/Autre).
  - [x] Liste détaillée des congés de l'exercice.
- [x] **Responsable**:
  - [x] Tableau de bord montrant les demandes de son équipe et les subordonnés.
  - [x] Calendrier FullCalendar de l'équipe avec légende.

## 8. Exports & reporting

- [x] **Export Excel salarié**:
  - [x] Colonnes: début, fin, jours ouvrables, **heures RTT**, type, statut.
- [x] **Export Excel équipe**:
  - [x] Colonnes: salarié, début, fin, jours, **heures RTT**, type, statut.
- [x] **Export PDF salarié**:
  - [x] Bloc de solde:
    - [x] CP alloués/consommés/restants (jours).
    - [x] RTT allouées/consommées/restantes (heures), si configurées.
  - [x] Tableau d'historique: période, jours, **heures RTT**, type, statut.

## 9. Tests automatisés

- [x] **57 tests passent** couvrant :
  - [x] Authentification et redirection par rôle (4 tests).
  - [x] Contrôle d'accès par rôle (4 tests).
  - [x] Calcul de jours ouvrables et jours fériés (6 tests).
  - [x] Détection de chevauchement (4 tests).
  - [x] Calcul de solde CP : allocation, consommation, types Sans solde/Maladie exclus, congé refusé exclu (7 tests).
  - [x] Calcul de solde RTT en heures : allocation, consommation, non-impact CP (3 tests).
  - [x] Vérification de solde CP/RTT suffisant avec exclusion en modification (5 tests).
  - [x] Génération des allocations (1 test).
  - [x] Workflow complet salarié → responsable → RH avec notifications (6 tests).
  - [x] Workflow sans responsable : demande directe RH (1 test).
  - [x] Annulation de demande par le salarié (2 tests).
  - [x] CRUD utilisateurs RH : création, modification, désactivation (3 tests).
  - [x] Ajout congé RH : CP, RTT, solde insuffisant (3 tests).
  - [x] Modification allocation CP + RTT (1 test).
  - [x] Validation RH vérifie le solde (1 test).
  - [x] Dashboard responsable avec calendrier (2 tests).
  - [x] Ajout congé par le responsable pour un subordonné : CP, RTT, contrôle équipe, solde insuffisant (4 tests).

## 10. Points à valider / compléter

- [ ] Souhaites‑tu un mécanisme d'**archivage** des congés anciens (changement de statut ou flag d'archive) ?
- [ ] Faut‑il des **rapports supplémentaires** (par service, par type d'absence, par période, etc.) ?
