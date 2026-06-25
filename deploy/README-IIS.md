# Déploiement Gestion Conges (Windows Server + IIS)

Ce guide décrit comment héberger l’application sur **Windows Server** avec **IIS**, en utilisant **HttpPlatformHandler** et le serveur WSGI **Waitress**.

## Prérequis

- **Windows Server** avec **IIS** installé
- **Python 3.10 ou 3.11** (64 bits recommandé) installé sur le serveur
- **HttpPlatformHandler** pour IIS ([téléchargement](https://www.iis.net/downloads/microsoft/httpplatformhandler))

## 1. Installer HttpPlatformHandler

1. Télécharger **HttpPlatformHandler** (x64) depuis le lien ci-dessus.
2. L’installer sur le serveur.
3. Redémarrer IIS si nécessaire : `iisreset` (en invite de commandes élevée).

## 2. Déployer l’application

1. Copier le projet sur le serveur (ex. `C:\inetpub\GestionConges`).
2. Créer un environnement virtuel Python et installer les dépendances :

   ```powershell
   cd C:\inetpub\GestionConges
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Créer le dossier des logs (le compte du pool IIS doit pouvoir y écrire) :

   ```powershell
   mkdir logs
   ```

4. Adapter **web.config** à votre chemin d’installation :
   - Ouvrir `web.config` à la racine du projet.
   - Remplacer **toutes** les occurrences du chemin (ex. `C:\Sites\Gestion-Conges`) par le chemin physique réel de votre site (ex. `D:\Apps\GestionConges`) : `processPath`, `workingDirectory`, `stdoutLogFile`.
   - **SECRET_KEY** : ne **pas** la mettre dans `web.config` (fichier versionné). La définir comme variable d'environnement **système** sur le serveur (cf. §5). Optionnellement, ajouter les variables SMTP/`MAIL_RH` dans `<environmentVariables>`.

## 3. Configurer le site dans IIS

1. Ouvrir **Gestionnaire des services Internet (IIS)**.
2. Créer un **site** (ou une **application** sous un site existant) :
   - **Chemin physique** : le dossier du projet (ex. `C:\inetpub\GestionConges`).
   - **Liaison** : HTTP, port 80 (ou le port souhaité), nom d’hôte si besoin.
3. Configurer le **pool d’applications** du site :
   - **Version du CLR .NET** : **Aucun code managé**.
   - **Identité** : un compte ayant les droits de lecture/écriture sur le dossier du site et sur le dossier `logs` (et sur le fichier SQLite `gestion_conges.db` après le premier lancement).

## 4. Vérifications

- Démarrer ou recycler le site dans IIS.
- Consulter les logs : `logs\stdout.log` en cas d’erreur de démarrage.
- Ouvrir l’URL du site dans un navigateur (ex. `http://votre-serveur/`).

## 5. Variables d’environnement

### SECRET_KEY — secret, hors du dépôt (obligatoire)

⚠️ **Ne jamais mettre `SECRET_KEY` dans `web.config`** : ce fichier est versionné dans
git. Un secret qui y figure est lisible par quiconque a accès au dépôt et permet de
**forger des sessions** (usurpation d'identité). La clé doit être une variable
d'environnement **système** du serveur, dont le processus Python (lancé par
HttpPlatformHandler) hérite automatiquement.

Mise en place (invite PowerShell **élevée**, sur le serveur) :

```powershell
# 1. Générer une clé forte
$key = & "C:\inetpub\GestionConges\venv\Scripts\python.exe" -c "import secrets; print(secrets.token_urlsafe(48))"

# 2. La poser comme variable SYSTÈME (persistante, héritée par IIS)
[Environment]::SetEnvironmentVariable("SECRET_KEY", $key, "Machine")

# 3. Redémarrer IIS pour que les services héritent de la nouvelle variable
iisreset
```

> **Rotation / clé compromise** : si une `SECRET_KEY` a déjà été versionnée dans git
> (historique inclus), elle doit être considérée comme **compromise**. Générer une
> nouvelle clé comme ci-dessus : toutes les sessions en cours seront invalidées
> (les utilisateurs devront se reconnecter), ce qui est le comportement attendu.
> L'ancienne clé reste dans l'historique git mais devient inutilisable.

### Autres variables (dans `<environmentVariables>` de `web.config`)

| Variable | Description |
|----------|-------------|
| `PREFERRED_URL_SCHEME` | `https` en production derrière IIS (cookies `Secure`, HSTS). |
| `PYTHONUNBUFFERED` | Laisser à `1` pour que les logs soient bien écrits. |
| `SKIP_DB_CREATE_ALL` | `1` en production : le schéma est géré par Alembic (`flask db upgrade`). |
| `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER` | SMTP pour les notifications (voir `config.py`). |
| `MAIL_RH` | Boîte RH entreprise : email à chaque demande + récap hebdo. |
| `MAIL_SUPPRESS_SEND` | `true` pour désactiver l’envoi d’e-mails (logs uniquement). |

Exemple pour ajouter le SMTP :

```xml
<environmentVariable name="MAIL_SERVER" value="smtp.example.com" />
<environmentVariable name="MAIL_PORT" value="587" />
<environmentVariable name="MAIL_USE_TLS" value="true" />
<environmentVariable name="MAIL_USERNAME" value="votre-compte" />
<environmentVariable name="MAIL_PASSWORD" value="votre-mot-de-passe" />
<environmentVariable name="MAIL_DEFAULT_SENDER" value="conges@votredomaine.local" />
```

## 6. Base de données et premier utilisateur

- La base SQLite **gestion_conges.db** est créée automatiquement au premier lancement dans le répertoire du projet. Le compte du pool IIS doit avoir les droits en **lecture/écriture** sur ce dossier.
- À **chaque mise à jour** de l'application, appliquer les migrations Alembic en attente avant de redémarrer le pool IIS :
  ```powershell
  $env:FLASK_APP="app.py:create_app"
  .\venv\Scripts\python.exe -m flask db upgrade
  ```
  Sur une base mise à niveau depuis l'ancien système de migrations (`scripts/migrations/*`), exécuter une seule fois `flask db stamp head` au lieu de `flask db upgrade` pour marquer la base comme à jour.
- Pour créer un premier utilisateur RH sur une base vide, exécuter (depuis le dossier du projet) :
  ```powershell
  .\venv\Scripts\python.exe scripts\create_admin.py
  ```
  Le script demande un mot de passe. Variables optionnelles : `ADMIN_IDENTIFIANT`, `ADMIN_NOM`, `ADMIN_PRENOM`.

## 7. Notifications (in-app, Web Push, email RH)

- **Notifications in-app** : toujours actives (liste dans le menu « Notifications »). Aucune configuration supplémentaire.
- **Conformité RGPD** : aucune adresse email salarié n'est collectée ; les notifications salarié (validation/refus) sont in-app et Web Push uniquement.
- **Email RH (entreprise)** : configurer `MAIL_RH` (variable d'environnement ou `web.config`) avec l'adresse de la boîte mail RH. Cette adresse reçoit un **récap hebdomadaire** des demandes de congé en attente (SMTP : `MAIL_SERVER`, `MAIL_PORT`, etc.). Aucun email n'est envoyé si aucune demande n'est en attente. Voir « Récap hebdomadaire RH » ci-dessous pour la planification.

### Récap hebdomadaire RH (planificateur de tâches Windows)

Le script `scripts/recap_hebdo.py` envoie un seul email à `MAIL_RH` listant toutes les demandes de congé en attente (validation responsable + validation RH). Aucun envoi si la liste est vide.

1. Ouvrir **Planificateur de tâches** (`taskschd.msc`).
2. Créer une tâche de base :
   - **Nom** : `ERPAC Gestion Congés - Récap hebdo RH`
   - **Déclencheur** : Chaque semaine, lundi 08:00.
   - **Action** : Démarrer un programme.
     - Programme : `C:\inetpub\GestionConges\venv\Scripts\python.exe`
     - Arguments : `scripts\recap_hebdo.py`
     - Démarrer dans : `C:\inetpub\GestionConges`
3. Dans les propriétés de la tâche, onglet **Général** → cocher « Exécuter même si l'utilisateur n'est pas connecté » et utiliser un compte de service ayant les droits sur le dossier du site.
4. Tester en lançant la tâche manuellement : un email récap doit arriver dans `MAIL_RH` (ou rien si aucune demande en attente).
- **Web Push (alertes hors du site)** : générer une paire de clés VAPID une fois sur le serveur :
  ```powershell
  .\venv\Scripts\python.exe gen_vapid_keys.py
  ```
  Les fichiers `vapid_private.pem` et `vapid_public.pem` sont créés à la racine du projet (déjà dans `.gitignore`). L'application les utilise automatiquement ; les utilisateurs peuvent cliquer sur « Activer les alertes » dans la barre de navigation.
- En **HTTP**, le serveur envoie bien les push, mais le navigateur peut ne pas afficher la notification système quand l'utilisateur n'est pas sur le site. Les notifications restent visibles dans l'app (liste des notifications). Voir `docs/WEB-PUSH-HTTPS.md` pour l'affichage des alertes en dehors du site (HTTPS requis).

## 8. Dépannage

- **Certificat HTTPS (conges.erpac.com)** : si les utilisateurs voient « Connexion non sécurisée » ou si l’antivirus bloque alors que le certificat est valide (\*.erpac.com, CA ERPAC-SRV18150RD1-CA), il faut que la **CA soit installée en racine de confiance** sur chaque poste (ou déployée via GPO). Voir **deploy/CERTIFICAT-HTTPS-INTRANET.md**.
- **503 / Service indisponible** : vérifier que HttpPlatformHandler est installé, que le chemin dans `web.config` pointe vers le bon `python.exe` du venv, et que le chemin physique du site dans IIS n’est pas utilisé par un autre programme.
- **Erreur au démarrage** : consulter `logs\stdout.log` et les journaux des événements Windows (Observateur d’événements).
- **Droits refusés** : s’assurer que l’identité du pool a les droits sur le dossier du site, sur `logs` et sur le fichier de base de données.
