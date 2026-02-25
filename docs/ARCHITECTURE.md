# Architecture du projet Gestion des Congés

Documentation technique pour les développeurs : modèles, flux métier et conventions.

## Modèles de données

### User (`models/user.py`)

- **Champs** : id, nom, prenom, identifiant (unique), mot_de_passe_hash, role (`rh` | `salarie`), actif, date_embauche, email (colonne presente en BDD, non utilisee cote app pour conformite RGPD).
- **Relations** : conges (liste des Conge), allocations (AllocationConge).
- **Authentification** : Flask-Login (UserMixin), mots de passe hashés avec bcrypt.

### Conge (`models/conge.py`)

- **Champs** : user_id, date_debut, date_fin, nb_jours_ouvrables, type_conge (CP, RTT, Sans solde, Maladie, Anciennete), commentaire, cree_le, modifie_le.
- **Workflow** : statut (`valide` | `en_attente` | `refuse`), valide_par_id, valide_le, motif_refus.
- **Relation** : valide_par → User (RH qui a validé/refusé).

### ParametrageAnnuel / AllocationConge (`models/parametrage.py`)

- **ParametrageAnnuel** : debut_exercice, fin_exercice, jours_conges_defaut, actif. Une seule ligne actif=True à la fois.
- **AllocationConge** : user_id, parametrage_id, jours_alloues, jours_anciennete, jours_report. Contrainte unique (user_id, parametrage_id). Propriété `total_jours` = alloues + anciennete + report.

### JourFerie (`models/jour_ferie.py`)

- date_ferie, libelle, annee, auto_genere. Contrainte unique sur date_ferie.

### Notification / PushSubscription

- **Notification** : notifications in-app (user_id, type, titre, message, conge_id, lue).
- **PushSubscription** : abonnements Web Push (user_id, endpoint, p256dh, auth) pour envoyer des push hors du site.

## Services métier

- **calcul_jours** : `compter_jours_ouvrables(date_debut, date_fin)` (hors week-ends et jours fériés), `detecter_chevauchement(user_id, ...)`.
- **solde** : `get_parametrage_actif()`, `get_allocation(user_id)`, `calculer_jours_consommes()`, `calculer_solde()`, `verifier_solde_suffisant()`.
- **jours_feries** : chargement/génération des jours fériés français.
- **notifications** : `creer_notification()`, `notifier_conge_valide()`, `notifier_conge_refuse()` (in-app + webpush si abonne ; pas d'email salarie, RGPD). `notifier_rh_nouvelle_demande()` : in-app + Web Push aux RH + email vers MAIL_RH (boite entreprise) si configure.
- **webpush** : `envoyer_push_user(user_id, titre, message, url)` avec pywebpush et cles VAPID.
- **email** : envoi vers MAIL_RH uniquement (nouvelle demande de conge), pas d'email aux salaries.

## Blueprints et routes principales

- **auth** : `/login`, `/logout`.
- **rh** : `/rh/dashboard`, salariés (CRUD), congés (CRUD, validation/refus), paramétrage, export Excel/PDF.
- **salarie** : `/salarie/` (accueil), `/salarie/demander-conge`, export.
- **notifications** : `/notifications/` (liste), `/notifications/count`, `/notifications/vapid-public`, `/notifications/push-subscribe` (POST).

## Conventions

- Sessions : `session.permanent = True`, durée via `PERMANENT_SESSION_LIFETIME`.
- Proxy : `ProxyFix` (x_for=1, x_proto=1, x_host=1) pour IIS / reverse proxy.
- HSTS : désactivé si `PREFERRED_URL_SCHEME != "https"`.
- Service Worker : `static/sw.js` servi à la racine (`/sw.js`) pour la portée Web Push.
