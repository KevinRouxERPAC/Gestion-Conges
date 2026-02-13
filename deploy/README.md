# Déploiement Gestion Conges

- **Linux (nginx + Gunicorn)** : instructions ci-dessous.
- **Windows Server (IIS)** : voir [README-IIS.md](README-IIS.md).

---

# Déploiement Linux (nginx + Gunicorn)

Ce dossier contient les fichiers pour faire tourner l’application derrière nginx avec Gunicorn.

## Prérequis

- Python 3 (venv recommandé)
- nginx
- utilisateur `freebox` (ou adapter `User`/`Group` et chemins dans les fichiers)

## 1. Environnement Python

À la racine du projet :

```bash
cd /home/freebox/Gestion-Conges
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Variables d’environnement (production)

Créer le fichier d’environnement à partir de l’exemple et définir au minimum une `SECRET_KEY` forte :

```bash
cp deploy/gestion-conges.env.example deploy/gestion-conges.env
# Éditer deploy/gestion-conges.env et définir SECRET_KEY=...
```

Le fichier `deploy/gestion-conges.env` n’est pas versionné (voir `.gitignore`). S’il est absent, le service démarre quand même avec les valeurs par défaut de `config.py` (à éviter en production).

## 3. Service systemd (Gunicorn)

Installer le service et l’activer :

```bash
sudo cp /home/freebox/Gestion-Conges/deploy/gestion-conges.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable gestion-conges
sudo systemctl start gestion-conges
sudo systemctl status gestion-conges
```

Si vous déployez avec un autre utilisateur ou un autre chemin, modifier dans `gestion-conges.service` :

- `User` et `Group`
- `WorkingDirectory`
- `Environment="PATH=..."`
- `EnvironmentFile=...`
- `ExecStart=...`

## 4. Nginx (site secondaire)

L’application est configurée comme **site secondaire** : elle ne répond que sur le `server_name` défini (pas sur localhost ni comme site par défaut). Le site principal (page nginx ou autre) reste sur `localhost`.

Installer le vhost et activer le site :

```bash
sudo cp /home/freebox/Gestion-Conges/deploy/nginx-gestion-conges.conf /etc/nginx/sites-available/gestion-conges
sudo ln -s /etc/nginx/sites-available/gestion-conges /etc/nginx/sites-enabled/
# Adapter server_name dans le fichier (ex. sous-domaine : conges.mondomaine.fr)
sudo nginx -t && sudo systemctl reload nginx
```

**Accéder à l’application :**

- En production : ouvrir `http://<server_name>/` (ex. `http://conges.mondomaine.fr/`).
- En local (test) : ajouter dans `/etc/hosts` :  
  `127.0.0.1  gestion-conges.local`  
  puis ouvrir `http://gestion-conges.local/`.

## Commandes utiles

- Logs Gunicorn : `journalctl -u gestion-conges -f`
- Redémarrer l’app : `sudo systemctl restart gestion-conges`
- Recharger nginx : `sudo systemctl reload nginx`

## Base de données

La base SQLite `gestion_conges.db` est créée automatiquement dans le répertoire du projet au premier lancement. L’utilisateur du service (`freebox`) doit avoir les droits en lecture/écriture sur ce répertoire.

### Premier utilisateur (base vide)

Au premier déploiement, la base ne contient aucun utilisateur. Il faut créer un compte **RH** pour pouvoir se connecter et gérer les salariés / congés.

Sur la VM, à la racine du projet (avec le venv activé si besoin) :

```bash
cd /home/freebox/Gestion-Conges
venv/bin/python scripts/create_admin.py
```

Le script demande un mot de passe au clavier (au moins 6 caractères). Par défaut il crée l’utilisateur `admin` (nom : Admin, prénom : Gestion). Pour personnaliser :

```bash
ADMIN_IDENTIFIANT=rh ADMIN_NOM=Dupont ADMIN_PRENOM=Marie venv/bin/python scripts/create_admin.py
```

Ensuite, connecte-toi sur l’application avec cet identifiant et le mot de passe choisi. Depuis l’interface RH tu pourras créer les salariés, le paramétrage annuel (exercice, jours de congés) et les jours fériés si besoin.
