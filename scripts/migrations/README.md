# Scripts de migration BDD

Scripts one-shot pour faire evoluer le schema SQLite (colonnes, valeurs).

- **migrate_conges_statut.py** : statut, valide_par_id, valide_le, motif_refus sur conges
- **migrate_user_email.py** : colonne email sur users
- **migrate_validation_2_niveaux.py** : responsable_id (users), valide_par_responsable_* (conges), statuts en_attente_*

Executes automatiquement au demarrage de l'app (app.py). Pour lancer manuellement (depuis la racine du projet) :

    python scripts/migrations/migrate_conges_statut.py
    python scripts/migrations/migrate_user_email.py
    python scripts/migrations/migrate_validation_2_niveaux.py