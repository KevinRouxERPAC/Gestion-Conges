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
   - Dans la section `<environmentVariables>`, définir une **SECRET_KEY** forte pour la production (et optionnellement les variables SMTP si vous utilisez les e-mails).

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

## 5. Variables d’environnement (web.config)

Les variables suivantes peuvent être définies dans la section `<environmentVariables>` de `web.config` :

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Clé secrète Flask (obligatoire en production). |
| `PYTHONUNBUFFERED` | Laisser à `1` pour que les logs soient bien écrits. |
| `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER` | SMTP pour les notifications (voir `config.py`). |
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
- Pour créer un premier utilisateur RH sur une base vide, exécuter (depuis le dossier du projet) :
  ```powershell
  .\venv\Scripts\python.exe scripts\create_admin.py
  ```
  Le script demande un mot de passe. Variables optionnelles : `ADMIN_IDENTIFIANT`, `ADMIN_NOM`, `ADMIN_PRENOM`.

## 7. Notifications (in-app, Web Push, email RH)

- **Notifications in-app** : toujours actives (liste dans le menu « Notifications »). Aucune configuration supplémentaire.
- **Conformité RGPD** : aucune adresse email salarié n'est collectée ; les notifications salarié (validation/refus) sont in-app et Web Push uniquement.
- **Email RH (entreprise)** : configurer `MAIL_RH` (variable d'environnement ou `web.config`) avec l'adresse de la boîte mail RH. Cette adresse reçoit un email à chaque nouvelle demande de congé (SMTP : `MAIL_SERVER`, `MAIL_PORT`, etc.).
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
