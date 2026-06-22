# Architecture du projet Gestion des absences (ERPAC)

Documentation technique pour les développeurs : modèles, services, flux métier et conventions.
Dernière mise à jour : 2026-06-16.

## Vue d'ensemble

- **Type** : monolithe web server-rendered (Flask + Jinja2).
- **Point d'entrée** : `app.py` → `create_app()` ; production `run_wsgi.py` (Waitress / IIS).
- **Couches** : `routes/` (contrôleurs HTTP) → `services/` (métier, sans HTTP) → `models/` (SQLAlchemy) + `templates/` (UI).
- **BDD** : SQLite (`gestion_conges.db`), mono-worker assumé (cap intranet — cf. [PLAN_IMPLEMENTATION.md](PLAN_IMPLEMENTATION.md) §R7).

## Modèles de données

### User (`models/user.py`)
- **Champs** : id, nom, prenom, identifiant (unique), mot_de_passe_hash (bcrypt), role (`rh` | `responsable` | `salarie`), actif, date_embauche, responsable_id (hiérarchie), email (colonne présente, non exploitée côté salarié — conformité RGPD).
- **Auth** : Flask-Login (UserMixin).

### Conge (`models/conge.py`)
- **Champs** : user_id, date_debut, date_fin, nb_jours_ouvrables (Float : demi-journées), demi_journee_debut / demi_journee_fin (bornes partielles), type_conge (CP, RTT, Sans solde, Maladie, Anciennete, EXC:…), **nb_heures_rtt** (`Numeric(6,2)` : heures RTT décimales, cf. R3), nb_heures_exceptionnelles, commentaire, cree_le, modifie_le, **archive** (FR53).
- **Workflow 2 niveaux** : statut `en_attente_responsable → en_attente_rh → valide | refuse`. Champs `valide_par_responsable_id/le`, `valide_par_id/le` (RH), `motif_refus`.

### ParametrageAnnuel / AllocationConge (`models/parametrage.py`)
- **ParametrageAnnuel** : debut_exercice, fin_exercice, jours_conges_defaut, actif (une seule ligne active). RTT hebdomadaire : `rtt_seuil_hebdo`, `rtt_heures_par_jour_absence`, `rtt_coef_surplus`, `rtt_acquis_par_semaine`.
- **AllocationConge** : jours_alloues, jours_anciennete, jours_report (CP, en jours), **rtt_heures_allouees / rtt_heures_reportees** (`Numeric(6,2)`, heures décimales). Contrainte unique (user_id, parametrage_id). Propriétés `total_jours`, `total_rtt_heures`.

### Autres
- **JourFerie** : date_ferie (unique), libelle, annee, auto_genere.
- **HeuresHebdo** (`models/heures_hebdo.py`) : heures travaillées par semaine (lundi), base du calcul RTT hebdomadaire.
- **Notification** (in-app) / **PushSubscription** (Web Push par appareil).
- **AuditLog**, **Delegation**, **CongeExceptionnelType**, **InteressementPeriode / InteressementRegle**.

## Services métier

- **consommation** (`services/consommation.py`) — **source de vérité unique (NFR9)** du décompte. `somme_consommation(...)` somme une colonne de `Conge` sur une fenêtre de dates / statuts / types. Les congés **à cheval** sur une borne d'exercice sont décomptés **au prorata** des jours ouvrables dans la fenêtre (cf. R1) ; les congés entièrement contenus passent par un agrégat SQL rapide.
- **solde** (`services/solde.py`) : `get_parametrage_actif`, `get_allocation`, `calculer_jours_cps_consommes`, `calculer_heures_rtt_consommes`, `calculer_solde`, `salaries_a_risque`, `cloturer_exercice_et_reporter`, `generer_allocations_pour_parametrage`. Le solde peut être **négatif** (avertissement, pas blocage) ; un déficit est reporté tel quel à la clôture.
- **calcul_jours** : `compter_jours_ouvrables[_avec_demi]`, détection de chevauchement.
- **creer_conge** : `construire_conge()` — validation + construction centralisée d'un congé (4 points d'entrée).
- **rtt_hebdo** : calcul RTT hebdomadaire (seuil réduit au prorata des absences + base `rtt_acquis_par_semaine`). RTT en heures **décimales** (plus d'arrondi entier, cf. R3).
- **conges_exceptionnels**, **delegation**, **jours_feries**, **interessement**, **audit**, **import_salaries**.
- **auth_utils** : bcrypt (`hash_password`/`check_password`), rôles valides, `valider_mot_de_passe` (≥ 8 caractères), `DUMMY_HASH` (anti-énumération par timing, cf. R4).
- **notifications** / **webpush** : in-app + Web Push (pas d'email salarié — RGPD ; email vers `MAIL_RH` entreprise uniquement).
- **export**, **export_comptable**, **export_interessement** : Excel/PDF (openpyxl / reportlab).

## Blueprints et routes

- **auth** : `/login` (rate-limité 10/min, 50/h), `/logout`, `/changer-mot-de-passe` (self-service, tous rôles).
- **rh** (`/rh`) : dashboard, CRUD salariés/congés, paramétrage, allocations, clôture d'exercice, heures hebdo, types exceptionnels, intéressement, audit, exports.
- **responsable** (`/responsable`) : dashboard N1, validation/refus (unitaire + lots), délégations.
- **salarie** (`/salarie`) : accueil, demande de congé, calendrier, heures, exports.
- **notifications** (`/notifications`) : liste, marquage lu, Web Push (subscribe, vapid-public).
- **api** (`/api`) : jours-feries, jours-ouvrables (JSON interne).

## Sécurité (conventions)

- **Sessions** : `session.permanent = True`, durée `PERMANENT_SESSION_LIFETIME` (30 min). Cookie durci : `HttpOnly`, `SameSite=Lax`, `Secure` si `PREFERRED_URL_SCHEME=https` (cf. R2).
- **En-têtes** : CSP, X-Frame-Options, Referrer-Policy, Permissions-Policy ; HSTS uniquement en HTTPS.
- **CSRF** : Flask-WTF global. **Rate-limit** : Flask-Limiter sur `/login` (storage mémoire ; Redis pour multi-worker).
- **Anti-énumération** : login avec identifiant inexistant exécute un `check_password` factice (`DUMMY_HASH`) pour égaliser le temps de réponse (cf. R4).
- **Proxy** : `ProxyFix` (x_for/x_proto/x_host = 1) pour IIS / reverse proxy.

## Migrations

Alembic via Flask-Migrate (dossier `migrations/`). `flask db upgrade` à chaque déploiement (sauvegarder la base avant). La migration `e3f1a2b4c5d6` fusionne les têtes divergentes et convertit les heures RTT en `Numeric(6,2)`.

## Filtres Jinja utiles
- `nb_jours` : formate les jours en français (`1,5`, `2`).
- `nb_heures` : formate les heures RTT décimales (`16,1`, `16`) — arrondi d'affichage uniquement.
