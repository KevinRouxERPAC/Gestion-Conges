# Scripts de migration BDD — LEGACY

> ⚠️ Ce dossier contient les anciens scripts de migration (un par évolution de schéma).
> **Ils ne sont plus exécutés automatiquement** au démarrage de l'application.
>
> Toutes les migrations futures passent désormais par **Alembic via Flask-Migrate**,
> dossier `migrations/` à la racine du projet.

## Pourquoi ?

Avant Alembic, chaque évolution de schéma était un script `migrate_*.py` rejoué à chaque
démarrage avec try/except. Cette approche ne tenait pas la route à mesure que le projet
grossissait : pas de tracking des migrations appliquées, ordre fragile, erreurs masquées
en `warning`.

## Commandes Alembic (depuis la racine du projet)

```bash
# Voir l'état courant de la BDD
SECRET_KEY=... FLASK_APP=app.py:create_app flask db current

# Générer une migration depuis les changements de modèles
SECRET_KEY=... FLASK_APP=app.py:create_app flask db migrate -m "ajout colonne X"

# Appliquer les migrations en attente
SECRET_KEY=... FLASK_APP=app.py:create_app flask db upgrade

# Reculer d'une migration
SECRET_KEY=... FLASK_APP=app.py:create_app flask db downgrade
```

Sur Windows PowerShell : remplacer `SECRET_KEY=... FLASK_APP=...` par
`$env:SECRET_KEY="..."; $env:FLASK_APP="app.py:create_app"; flask db ...`.

## Migration initiale

La première révision Alembic (`migrations/versions/*_initial_schema.py`) contient
le schéma complet au moment de l'introduction d'Alembic. Sur les bases déjà
existantes (déjà migrées par les anciens scripts), exécuter une seule fois :

```bash
flask db stamp head
```

…pour marquer la base comme « déjà à la révision initiale » sans rejouer les `CREATE TABLE`.

## Anciens scripts (à conserver pour mémoire)

| Script | Évolution |
|--------|-----------|
| `migrate_conges_statut.py` | Ajout statut/valide_par_id/valide_le/motif_refus sur conges |
| `migrate_user_email.py` | Ajout colonne email sur users |
| `migrate_validation_2_niveaux.py` | Validation responsable + RH (responsable_id, valide_par_responsable_*) |
| `migrate_rtt_columns.py` | Colonnes RTT (nb_heures_rtt, rtt_heures_allouees, etc.) |
| `migrate_conges_exceptionnels.py` | Type CongeExceptionnelType + nb_heures_exceptionnelles |
| `migrate_heures_payees.py` | Saisie mensuelle des heures |
| `migrate_rtt_calc_heures.py` | Mode de calcul RTT (fixe/heures) |
| `migrate_interessement.py` | Périodes et règles d'intéressement |

Ces scripts ne sont **pas** appelés automatiquement. Ils restent utilisables manuellement
si une base très ancienne doit être rattrapée hors Alembic, mais ce cas devrait être
exceptionnel — préférer un `flask db stamp head` puis l'ajout des colonnes manquantes
via des révisions Alembic dédiées.
