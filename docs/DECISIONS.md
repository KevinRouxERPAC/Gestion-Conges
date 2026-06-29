# Décisions techniques et produit

Décisions durables qui ne ressortent pas directement du code. À maintenir à jour.
Dernière mise à jour : 2026-06-26.

## Architecture

### Cap intranet (SQLite + mono-worker)

L'application reste un outil **intranet** : SQLite + worker unique sont des contraintes officielles
et documentées, pas un défaut. La bascule vers PostgreSQL + Redis est anticipée dans le code
(commentaires) mais n'est pas planifiée tant qu'aucun besoin multi-site ou de concurrence d'écriture
n'est formalisé.

### RTT en décimal (`Numeric(6,2)`)

Les heures RTT sont stockées en `Numeric(6,2)` (ex. `16.10` h) dans `models/conge.py` et
`models/parametrage.py`. L'arrondi n'a lieu **qu'à l'affichage** via le filtre Jinja `nb_heures`.
Pas de minutes entières en base (Option B rejetée — `Numeric` plus lisible pour la comptabilité).

## Règles métier

### Clôture d'exercice — report de solde négatif

Un solde CP ou RTT **négatif** (déficit) est reporté tel quel vers le nouvel exercice ; il n'est
pas écrêté à 0. Le plafond de report ne s'applique qu'aux reports **positifs**.

### Ancienneté à la clôture

Quand `cloturer_exercice_et_reporter` crée une nouvelle allocation (cas habituel : le paramétrage
vient d'être créé), elle part avec `jours_anciennete=0`. **Le RH doit ré-éditer manuellement les
allocations** pour réaffecter les jours d'ancienneté. Ce comportement est incohérent avec
`generer_allocations_pour_parametrage` qui préserve l'ancienneté existante.
→ À trancher et aligner (cf. `docs/deep-dive-cloture-exercice.md` §R3).

### RGPD — aucun email salarié

Les notifications salariés (validation / refus) sont **exclusivement** in-app et Web Push. Aucun
email n'est envoyé aux salariés. La variable `User.email` est collectée à l'import mais n'est pas
exploitée côté salarié. Seule la boîte RH entreprise (`MAIL_RH`) reçoit des emails (adresse
d'entreprise, pas de données personnelles employé).

## Sécurité

### `SECRET_KEY` hors dépôt

La `SECRET_KEY` de production **ne doit jamais figurer dans `web.config`** (fichier versionné).
Elle doit être posée comme variable d'environnement **système** du serveur. Si elle a déjà été
versionnée, la considérer comme compromise et la régénérer (voir `deploy/README-IIS.md` §5).

### `SKIP_DB_CREATE_ALL=1` en production

`db.create_all()` est désactivé en production via cette variable. Le schéma est exclusivement géré
par Alembic (`flask db upgrade`). Actif uniquement pour les tests et le premier démarrage local.
