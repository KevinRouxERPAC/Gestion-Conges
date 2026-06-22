# Plan de validation — Gestion des absences (ERPAC)

> Plan de recette fonctionnelle et UI/UX. À exécuter sur la base de démo
> (`run_verif.py`, port 5001) avec les comptes seedés.
>
> **Comptes de démo** (mot de passe : `demo1234`) :
> - `rh` — Alice RH (gestionnaire RH)
> - `resp` — Bob Resp (responsable, suppléant possible)
> - `sal` — Carla Salarie (rattachée à Bob)
>
> **Exercice actif** : 01/01/2026 → 31/12/2026 · **Date du jour (démo)** : 22/06/2026

## Légende des statuts

| Symbole | Signification |
|---------|---------------|
| ⬜ | À tester |
| ✅ | Conforme |
| ⚠️ | Conforme avec réserve (détailler) |
| ❌ | Non conforme (anomalie à corriger) |
| ⛔ | Bloqué / non testable |

## Grille de critères UI/UX (appliquée à chaque écran)

À chaque écran visité, on contrôle systématiquement :

- **U1 — Lisibilité** : hiérarchie visuelle claire, libellés en français, pas de texte tronqué.
- **U2 — Cohérence charte** : logo + vert ERPAC, typographie et espacements homogènes.
- **U3 — Feedback** : toasts/flash après chaque action, états de chargement, libellés de boutons explicites.
- **U4 — Navigation** : sidebar correcte selon le rôle, fil d'Ariane / retour, lien actif mis en évidence.
- **U5 — Formulaires** : labels associés, champs obligatoires signalés, messages d'erreur utiles, focus visible.
- **U6 — Accessibilité** : lien « aller au contenu », contrastes, navigation clavier, attributs ARIA des composants dynamiques.
- **U7 — Console** : aucune erreur JS / réseau (4xx-5xx) inattendue.

---

## 0. Préparation de l'environnement

| ID | Vérification | Attendu | Statut |
|----|--------------|---------|--------|
| ENV-01 | Base démo seedée (`instance/verif_demo.db`) | 3 comptes + exercice 2026 + allocations | ⬜ |
| ENV-02 | Serveur démarré (port 5001, `run_verif.py`) | Page `/login` accessible | ⬜ |
| ENV-03 | Aucune erreur au démarrage (logs serveur) | Logs propres | ⬜ |

---

## 1. Authentification & sécurité (transverse)

| ID | Scénario | Étapes | Attendu | Statut |
|----|----------|--------|---------|--------|
| AUTH-01 | Affichage login | Ouvrir `/` | Redirection `/login`, logo + carte centrée | ✅ |
| AUTH-02 | Login RH | `rh` / `demo1234` | Redirection `/rh/dashboard`, toast « Connexion réussie » | ✅ |
| AUTH-03 | Login responsable | `resp` / `demo1234` | Redirection `/responsable/dashboard` | ✅ |
| AUTH-04 | Login salarié | `sal` / `demo1234` | Redirection `/salarie/accueil` | ✅ |
| AUTH-05 | Mauvais mot de passe | `rh` / `xxxxxxxx` | Reste sur login, message « Identifiant ou mot de passe incorrect » | ✅ |
| AUTH-06 | Identifiant inexistant | `inconnu` / `demo1234` | Même message neutre (anti-énumération) | ✅ Message identique à AUTH-05 |
| AUTH-07 | Champs vides | Soumettre vide | Validation HTML5 / message d'erreur | ✅ `required` + `autofocus` sur identifiant |
| AUTH-08 | Afficher / masquer le mot de passe | Cliquer l'œil | Bascule visible/masqué | ✅ Bouton présent, masqué par défaut |
| AUTH-09 | Accès protégé sans session | Ouvrir `/rh/dashboard` déconnecté | Redirection login + message « Veuillez vous connecter » | ✅ Redirige `/login?next=/rh/dashboard` |
| AUTH-10 | Cloisonnement de rôle | En `sal`, ouvrir `/rh/dashboard` | Refus + redirection (pas de fuite) | ✅ Salarié renvoyé vers son accueil |
| AUTH-11 | Déconnexion | Menu utilisateur → Déconnexion | Retour login, toast « déconnecté » | ✅ `/logout` → login + flash |
| AUTH-12 | Changer mot de passe — succès | `/changer-mot-de-passe`, actuel + nouveau valide | Toast succès, reconnexion OK avec le nouveau | ✅ Changement + relogin OK (2 sens) |
| AUTH-13 | Changer MDP — actuel faux | Saisir mauvais mot de passe actuel | Erreur « Mot de passe actuel incorrect » | ✅ |
| AUTH-14 | Changer MDP — trop court | Nouveau < 8 caractères | Erreur politique (8 min) | ✅ « trop court » |
| AUTH-15 | Changer MDP — identique | Nouveau = ancien | Erreur « doit être différent » | ✅ Message exact présent |
| AUTH-16 | En-têtes de sécurité | Inspecter la réponse | CSP, X-Frame-Options, nosniff présents | ✅ CSP + XFO=DENY + nosniff + Referrer + Permissions |

> ⚠️ Après AUTH-12, **réinitialiser le mot de passe du compte testé** à `demo1234` (re-seed ou changement inverse) pour ne pas casser les scénarios suivants.

---

## 2. Espace Salarié (`sal` — Carla)

| ID | Scénario | Étapes | Attendu | Statut |
|----|----------|--------|---------|--------|
| SAL-01 | Tableau de bord — soldes | Ouvrir l'accueil | Cartes Solde CP, RTT restant, Total alloué, Total consommé cohérentes | ✅ CP 25/30, RTT 63h/70h, consommé 5j |
| SAL-02 | Barres de progression | Section « Progression de l'exercice » | CP et RTT : valeurs et largeurs cohérentes | ✅ |
| SAL-03 | Historique des congés | Tableau « Mes congés » | Périodes, quantités, types, statuts colorés | ✅ |
| SAL-04 | Demande CP (journées pleines) | 20→21/07, type CP | Statut « En attente responsable », solde projeté affiché | ✅ « 2 j en attente · projeté 23 » |
| SAL-05 | Demande RTT (demi-journée) | 22/07 matin, RTT 3,5h | Demi-journée RTT, heures saisies (multiple 0,25) | ✅ « 3 h 30 en attente », projeté 59 h 30 |
| SAL-06 | Demande — date fin < début | Fin antérieure au début | Refus / message d'erreur, pas de création | ✅ « date de fin doit être postérieure » |
| SAL-07 | Demande — type exceptionnel avec justificatif requis | Sélectionner ce type sans fichier | Blocage : justificatif obligatoire | ⛔→✅ Différé puis testé après RH-37 (voir EDGE/RH) |
| SAL-08 | Décompte jours ouvrables (live) | Saisir des dates | Nombre de jours ouvrables mis à jour (API) | ✅ 2j / 0 we / 0,5 demi / fin<début rejeté |
| SAL-09 | Annuler une demande en attente | Action « Annuler » | Statut « annulé », solde projeté réhabilité | ✅ |
| SAL-10 | Annulation interdite (validé) | Tenter d'annuler un congé validé | Action indisponible / refus | ✅ Refus serveur + bouton masqué |
| SAL-11 | Calendrier annuel | `/salarie/calendrier` | Affichage par mois, navigation années, légende | ✅ |
| SAL-12 | Calendrier — filtres par type | Cocher/décocher types | Filtrage des événements | ✅ Décochage CP → congé masqué |
| SAL-13 | Calendrier — vue « tout le monde » | Activer « tous » | Autres salariés visibles en « Absent » (type masqué, RGPD) | ✅ Mécanique OK ; masquage RGPD vérifié en code (pas d'autre congé démo) |
| SAL-14 | Mes heures (RTT hebdo) | `/salarie/heures` | Détail par semaine, total heures, RTT calculé | ✅ Détail vide (aucune saisie) |
| SAL-15 | Export Excel | Bouton Export Excel | Fichier `.xlsx` téléchargé, contenu correct | ✅ 200, xlsx, 5,4 Ko |
| SAL-16 | Export PDF | Bouton Export PDF | Fichier `.pdf` téléchargé, soldes inclus | ✅ 200, pdf, 2,7 Ko |

---

## 3. Espace Responsable (`resp` — Bob)

| ID | Scénario | Étapes | Attendu | Statut |
|----|----------|--------|---------|--------|
| RESP-01 | Dashboard — KPI | Ouvrir le dashboard | À valider, Mon solde CP, Mon RTT, Mon équipe | ✅ À valider 6, équipe 1 |
| RESP-02 | Demandes en attente (N1) | Carla a une demande | Ligne affichée avec période, type, jours | ✅ 6 demandes listées |
| RESP-03 | Détection de conflits équipe | Demandes chevauchantes | Colonne « Conflits équipe » renseignée | ⚠️ Colonne OK (« Aucun ») ; pas de 2e subordonné pour générer un conflit (logique vérifiée en code) |
| RESP-04 | Valider niveau 1 (unitaire) | Bouton Valider | Statut → en attente RH, toast « transmise aux RH » | ✅ |
| RESP-05 | Refuser niveau 1 (motif) | Bouton Refuser + motif | Statut refusé, notification salarié | ✅ « Demande refusée » |
| RESP-06 | Refus N1 — motif vide | Refuser sans motif | Blocage « motif obligatoire » | ✅ |
| RESP-07 | Validation par lots | Cocher plusieurs + Valider la sélection | Toutes transmises, compteur correct | ✅ « 2 validée(s) et transmise(s) » |
| RESP-08 | Refus par lots (motif commun) | Cocher plusieurs + Refuser | Page de saisie motif puis refus groupé | ✅ « 2 refusée(s) » |
| RESP-09 | Ajouter congé pour subordonné | Calendrier équipe → + Congé | Créé en attente RH, toast | ✅ « créé pour Carla et transmis aux RH » |
| RESP-10 | Calendrier d'équipe | Section calendrier | Congés des subordonnés colorés par type/statut | ✅ Calendrier + « Vos subordonnés » |
| RESP-11 | Délégation — créer | Désigner un suppléant (autre responsable), période | Délégation enregistrée (sortante) | ✅ Active, affichée (resp2 créé) |
| RESP-12 | Délégation — suppléant invalide | Choisir un non-responsable / soi-même | Refus avec message | ✅ Les 2 garde-fous OK |
| RESP-13 | Délégation — supprimer | Supprimer une délégation | Retirée de la liste | ✅ « Délégation supprimée » |
| RESP-14 | Périmètre suppléant | Le suppléant valide pour l'équipe déléguée | Subordonnés effectifs étendus pendant la période | ✅ resp2 voit + valide la demande de Carla |
| RESP-15 | Espace perso responsable | Mes congés / Mes heures / Calendrier | Mêmes fonctions que salarié | ✅ Routes salarié, toutes 200 |

---

## 4. Espace RH (`rh` — Alice)

### 4.1 Tableau de bord & validation

| ID | Scénario | Étapes | Attendu | Statut |
|----|----------|--------|---------|--------|
| RH-01 | Dashboard — KPIs | Ouvrir le dashboard | Total salariés, En congé, À valider, Soldes à risque | ✅ |
| RH-02 | Calendrier global | Section calendrier | Tous les congés validés de l'exercice | ✅ Calendrier + liste exercice actif |
| RH-03 | Demandes en attente RH (N2) | Après validation N1 | Demande listée avec conflits | ✅ 5 demandes listées |
| RH-04 | Valider (N2, unitaire) | Bouton Valider | Statut validé, **solde décrémenté**, notif salarié | ✅ Solde Carla 25→20 confirmé |
| RH-05 | Validation par lots | Cocher + Valider la sélection | Compteur correct | ✅ « 2 validée(s) » |
| RH-06 | Refuser (N2, motif) | Bouton Refuser + motif | Statut refusé, notif salarié | ✅ motif vide bloqué + refus OK |
| RH-07 | Refus par lots (motif commun) | Cocher + Refuser la sélection | Saisie motif → refus groupé | ✅ « 1 refusée(s) avec le même motif » |
| RH-08 | Avertissement solde négatif | Valider un congé > solde | Validation effectuée + warning solde négatif | ✅ « Solde CP négatif : -15 j », validé |
| RH-09 | Soldes à risque | Salarié avec CP élevés en fin d'exercice | Apparaît dans la carte « à risque » | ⚠️ Carte OK (0) ; non déclenchable (>90j de la fin) — logique vérifiée en code |

### 4.2 Gestion des salariés

| ID | Scénario | Étapes | Attendu | Statut |
|----|----------|--------|---------|--------|
| RH-10 | Liste & recherche | `/rh/salaries`, rechercher | Filtrage nom/prénom/identifiant | ✅ « carla » → 1 ligne (Alpine) |
| RH-11 | Créer un salarié | + Nouveau salarié | Création, rattachement responsable optionnel | ✅ |
| RH-12 | Créer — identifiant existant | Réutiliser un identifiant | Erreur « existe déjà » | ✅ |
| RH-13 | Créer — mot de passe trop court | < 8 caractères | Erreur politique | ✅ |
| RH-14 | Modifier un salarié | Éditer nom/rôle/responsable | Mise à jour, audit | ✅ |
| RH-15 | Garde-fou anti lock-out | Retirer le dernier accès RH | Refus « au moins un RH actif » | ✅ « ne pouvez pas retirer votre propre accès RH » |
| RH-16 | Statut actif/inactif | Désactiver un salarié | Bascule statut, sort des listes actives | ✅ |
| RH-17 | Auto-statut interdit | Modifier son propre statut | Refus | ✅ |
| RH-18 | Import CSV/Excel — dry-run | Importer en aperçu | Prévisualisation sans persistance | ✅ Aperçu 2 lignes, 0 créé |
| RH-19 | Import CSV/Excel — réel | Importer pour de bon | Créations/MAJ + rapport d'erreurs | ✅ « 2 créé(s) » |

### 4.3 Fiche salarié & congés

| ID | Scénario | Étapes | Attendu | Statut |
|----|----------|--------|---------|--------|
| RH-20 | Fiche salarié | Ouvrir une fiche | Soldes CP/RTT, exercice, historique | ✅ Solde décrémenté (20 rest. / 10 cons.) |
| RH-21 | Modifier l'allocation | CP alloués / ancienneté / report / RTT | Recalcul du solde, audit | ✅ |
| RH-22 | Ajouter un congé (validé direct) | + Ajouter un congé | Créé validé, notif salarié | ✅ |
| RH-23 | Modifier un congé | Éditer dates/type | MAJ + notif modification au salarié | ✅ |
| RH-24 | Supprimer un congé | Action supprimer | Retiré, audit, solde recalculé | ✅ |
| RH-25 | Justificatif — téléchargement | Congé avec justificatif | Fichier servi (RH ou salarié concerné) | ✅ 200 PDF (RH) |
| RH-26 | Justificatif — suppression | Supprimer le fichier | Retiré | ✅ « Justificatif supprimé » |
| RH-25b | **Ajout congé AVEC justificatif** | RH ajoute Maladie/EXC + PDF valide | Congé créé avec justificatif attaché | ✅ **Corrigé (BUG-01)** — congé créé + justificatif attaché ; test de non-régression vert |

### 4.4 Paramétrage & exercice

| ID | Scénario | Étapes | Attendu | Statut |
|----|----------|--------|---------|--------|
| RH-27 | Paramétrage exercice | Dates + jours par défaut | Enregistré | ✅ |
| RH-28 | Paramètres RTT | Seuil hebdo, h/jour absence, coef surplus, acquis/semaine | Enregistrés et pris en compte | ✅ |
| RH-29 | Générer les allocations | Bouton générer | Allocations CP+RTT pour tous les actifs | ✅ |
| RH-30 | Jours fériés — auto | Charger les fériés | Fériés de l'année ajoutés | ✅ « 11 jour(s) férié(s) ajouté(s) » |
| RH-31 | Jours fériés — ajout manuel | Ajouter une date | Férié personnalisé créé | ✅ |
| RH-32 | Jours fériés — suppression | Supprimer un férié | Retiré | ✅ |
| RH-33 | Clôture d'exercice — aperçu | Ouvrir la clôture | Prévisualisation du report par salarié | ✅ 6 salariés avec report CP/RTT |
| RH-34 | Clôture — report avec plafonds | Nouveau cycle + plafonds CP/RTT | Report appliqué, nouvel exercice, audit | ✅ Exécuté en fin de campagne (voir §RH-34) |
| RH-35 | Clôture — dates invalides | Fin ≤ début | Refus | ✅ « date de fin postérieure » |

### 4.5 Types exceptionnels

| ID | Scénario | Étapes | Attendu | Statut |
|----|----------|--------|---------|--------|
| RH-36 | Seed des types par défaut | Bouton « types par défaut » | Types créés (idempotent) | ✅ « 8 type(s) ajouté(s) » |
| RH-37 | Créer un type | Code, libellé, unité, plafond, justificatif | Type ajouté | ✅ FORMATION (justif. requis, plafond 5) |
| RH-38 | Modifier un type | Éditer libellé/unité/plafond | MAJ | ✅ |
| RH-39 | Activer / désactiver | Toggle | Statut basculé | ✅ |
| RH-40 | Plafond annuel respecté | Dépasser le plafond à la validation | Blocage « plafond dépassé » | ✅ 2e congé QUOTA bloqué (cumul > plafond) |

### 4.6 Heures hebdo & intéressement

| ID | Scénario | Étapes | Attendu | Statut |
|----|----------|--------|---------|--------|
| RH-41 | Saisie heures hebdo | Renseigner par salarié + semaine | Enregistré, navigation semaine | ✅ « Heures hebdomadaires enregistrées » |
| RH-42 | Recalcul RTT (mode hebdo) | Bouton enregistrer + recalculer | RTT recalculées en tenant compte des absences | ✅ « RTT recalculées pour 6 salarié(s) » |
| RH-43 | Intéressement — créer période | Libellé + dates + base/plancher | Période créée | ✅ |
| RH-44 | Intéressement — règles | Ajouter/modifier/supprimer règles | Pondération par type d'absence | ✅ « Règle ajoutée » |
| RH-45 | Intéressement — activer/supprimer | Toggle + suppression | États corrects | ✅ toggle + suppression OK |
| RH-46 | Intéressement — export | Export Excel d'une période | Fichier `.xlsx` cohérent | ✅ 200, xlsx, 6,5 Ko |

### 4.7 Audit, archives & exports

| ID | Scénario | Étapes | Attendu | Statut |
|----|----------|--------|---------|--------|
| RH-47 | Journal d'audit | `/rh/audit-log` | Actions tracées, filtres action/acteur, pagination | ✅ 29 entrées, filtre action → 10 |
| RH-48 | Archives — aperçu | Choisir date d'arrêté | Nb archivables / archivés affichés | ✅ |
| RH-49 | Archiver | Lancer l'archivage | Congés traités ≤ date archivés (hors en attente) | ✅ « 5 congé(s) archivé(s) » |
| RH-50 | Désarchiver | Bouton désarchiver | Congés réaffichés | ✅ « 5 congé(s) désarchivé(s) » |
| RH-51 | Export équipe Excel | Bouton export | `.xlsx` de toute l'équipe | ✅ 200, xlsx, 5,9 Ko |
| RH-52 | Export comptable CP/RTT | À une date donnée | `.xlsx` comptable | ✅ 200, xlsx, 6,3 Ko |

---

## 5. Notifications (transverse)

| ID | Scénario | Étapes | Attendu | Statut |
|----|----------|--------|---------|--------|
| NOTIF-01 | Badge compteur | Après une action notifiable | Compteur cloche incrémenté | ✅ count=15 ; polling 12 s |
| NOTIF-02 | Liste des notifications | Ouvrir la liste | Notifications triées, lien vers le congé | ✅ 16 items, badge « Nouveau », fond coloré |
| NOTIF-03 | Marquer comme lue | Cliquer une notification | Passe en lu, compteur décrémenté | ✅ Via lien `/voir` (ouverture = lue) |
| NOTIF-04 | Tout marquer lu | Bouton « tout lire » | Compteur à 0 | ✅ count → 0 |
| NOTIF-05 | Notif validation/refus | Workflow complet | Salarié notifié à chaque étape | ✅ 15 notifs générées par le workflow |
| NOTIF-06 | Web Push (config) | Endpoint `/notifications/vapid-public` | Clé renvoyée si configurée (sinon vide, non bloquant) | ✅ Endpoint OK, clé vide (pas de VAPID en démo) |

---

## 6. UI/UX transverse & responsive

| ID | Scénario | Étapes | Attendu | Statut |
|----|----------|--------|---------|--------|
| UX-01 | Sidebar repliable | Bouton « Réduire le menu » | Repli/dépli, état conservé | ✅ 256↔72px, persistance localStorage |
| UX-02 | Responsive mobile (375px) | Redimensionner | Mise en page adaptée, pas de débordement | ✅ Header hamburger, cartes empilées |
| UX-03 | Responsive tablette (768px) | Redimensionner | Grille adaptée | ✅ Sidebar + grille 2 colonnes |
| UX-04 | Toasts / flash | Après actions | Apparition + disparition propres | ✅ `role="alert"` dismissibles (« Fermer ») |
| UX-05 | Accessibilité de base | Lien « aller au contenu », labels, focus | Présents et fonctionnels | ✅ skip `#main-content`, `lang="fr"`, alt, labels |
| UX-06 | Cohérence charte | Toutes pages | Logo + vert ERPAC homogènes | ✅ |
| UX-07 | Console propre | Parcours complet | Aucune erreur JS / réseau inattendue | ✅ Aucune erreur |
| UX-08 | Formats FR | Nombres et heures | `1,5 j`, `5 h 15` (virgule décimale) | ✅ « 21 h 30 », « -15 j » — ⚠️ flash « 2.0 j » (OBS-01) |

---

## 7. Cas limites & robustesse

| ID | Scénario | Étapes | Attendu | Statut |
|----|----------|--------|---------|--------|
| EDGE-01 | Chevauchement de congés | Demander sur une période déjà posée | Détection / avertissement | ✅ « Chevauchement détecté avec le congé du 29/06… » |
| EDGE-02 | Congé sur jour férié | Période incluant un férié | Jour férié non décompté | ✅ 13–15/07 = 2j (14/07 férié exclu) vs 3j contrôle |
| EDGE-03 | Demi-journées début/fin | Combinaisons matin/après-midi | Décompte demi-journées correct | ✅ après-midi+matin = 1j ; 1 demi = 0,5j |
| EDGE-04 | 404 / ressource inexistante | Ouvrir un id inexistant | Page 404 propre | ✅ 404 (notif), 400 (dates invalides) |
| EDGE-05 | 403 justificatif d'autrui | Salarié A tente le justificatif de B | Accès refusé (403) | ✅ jimporte → 403 |
| EDGE-06 | Rate limit login | 11 tentatives/min | Blocage temporaire (429) | ✅ 429 dès la 10e tentative |

---

## Synthèse d'exécution

| Section | Total | ✅ | ⚠️ | ❌ | ⛔ |
|---------|-------|----|----|----|----|
| 1. Authentification | 16 | 16 | 0 | 0 | 0 |
| 2. Salarié | 16 | 16 | 0 | 0 | 0 |
| 3. Responsable | 15 | 14 | 1 | 0 | 0 |
| 4. RH | 53 | 52 | 1 | 0 | 0 |
| 5. Notifications | 6 | 6 | 0 | 0 | 0 |
| 6. UI/UX | 8 | 8 | 0 | 0 | 0 |
| 7. Cas limites | 6 | 6 | 0 | 0 | 0 |
| **Total** | **120** | **118** | **2** | **0** | **0** |

> **Verdict global : 100 % des cas conformes après corrections.** Les 2 anomalies détectées ont été corrigées : **BUG-01** (majeure — ajout RH d'un congé avec justificatif) et **OBS-01** (cosmétique — « 2.0 jour(s) » dans les messages flash). Suite de tests : **236 passés** (dont 1 nouveau test de non-régression). Les 2 ⚠️ (RESP-03 conflits, RH-09 soldes à risque) ne sont pas des défauts : logiques correctes mais non déclenchables avec le jeu de données / la date de démo.
>
> _Campagne exécutée le 22/06/2026 sur la base de démo. Anomalies corrigées et vérifiées. Base réinitialisée après la campagne._

### Anomalies relevées

| ID | Sévérité | Description | Statut |
|----|----------|-------------|--------|
| **BUG-01** | 🔴 Majeure | **Ajout/modif RH d'un congé avec justificatif échoue.** En ajoutant via le RH un congé `Maladie` ou exceptionnel à justificatif requis **avec** un justificatif PDF valide, le système répondait « Un justificatif est obligatoire » et **ne créait pas le congé** (rollback). Cause : `enregistrer_justificatif` ajoutait le `Justificatif` via `conge_id=` sans peupler la relation en mémoire ; la vérification immédiate `verifier_justificatif_obligatoire` appelée dans `_traiter_justificatif_conge` ([routes/rh.py:197](routes/rh.py:197)) lisait `conge.justificatif` encore en cache à `None`. | ✅ **Corrigé** — `Justificatif(conge=conge, …)` peuple le backref en mémoire ([services/justificatifs.py:121](services/justificatifs.py:121)). Test de non-régression ajouté sur la route réelle ([tests/test_justificatifs.py](tests/test_justificatifs.py)). |
| OBS-01 | 🟢 Cosmétique | Messages flash affichant un nombre de jours flottant : « 2.0 jour(s) », « Solde CP négatif : -15.0 jour(s) » au lieu de « 2 » / « -15 ». | ✅ **Corrigé** — helper `format_jours` ([services/format_heures.py](services/format_heures.py)) utilisé dans les messages ([routes/rh.py:262](routes/rh.py:262), [routes/rh.py:498](routes/rh.py:498), [services/creer_conge.py:185](services/creer_conge.py:185)) ; filtre Jinja `nb_jours` refactoré sur le même helper. |
