# Gestion des Conges (ERPAC)

Application web intranet de **gestion des conges** pour une equipe (salaries et gestionnaires RH). Gestion des soldes, demandes de conges, validation/refus par les RH, parametrage annuel (exercice, jours alloues, jours feries) et notifications (in-app et Web Push).

---

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | Python 3 + Flask |
| Base de donnees | SQLite (SQLAlchemy ORM) |
| Frontend | Jinja2, Tailwind CSS (CDN), Alpine.js |
| Authentification | Flask-Login, bcrypt |
| Production | Waitress (Windows/IIS) ou Gunicorn (Linux) |

Deploiement simple sur serveur intranet (pas de build frontend, pas de serveur BDD dedie).

---

## Prérequis

- Python 3.10+
- Optionnel : environnement virtuel (`venv`) recommande

---

## Installation et demarrage

### 1. Environnement

```bash
cd Gestion-Conges
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate   # Linux / macOS
pip install -r requirements.txt
```

### 2. Lancer l'application

**Developpement :**

```bash
python app.py
```

Application sur `http://localhost:5000` (multi-utilisateurs en dev).

**Production (ex. Windows IIS) :**

```bash
python run_wsgi.py
```

Port lu depuis `HTTP_PLATFORM_PORT` (IIS) ou `PORT`, sinon 5000.

### 3. Premier utilisateur (base vide)

Creer un compte **RH** pour se connecter :

```bash
.\venv\Scripts\python.exe scripts\create_admin.py
```

Le script demande un mot de passe (6 caracteres min). Par defaut : utilisateur `admin`. Pour personnaliser :

```bash
ADMIN_IDENTIFIANT=rh ADMIN_NOM=Dupont ADMIN_PRENOM=Marie python scripts/create_admin.py
```

---

## Configuration

Fichier `config.py` ; surcharge par **variables d'environnement** (ou `web.config` sous IIS).

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Cle secrete Flask (a remplacer en production) |
| `PREFERRED_URL_SCHEME` | `http` ou `https` |
| `MAIL_*` | SMTP pour e-mails (validation/refus de conges) |
| `MAIL_SUPPRESS_SEND` | `true` = ne pas envoyer les e-mails (logs uniquement) |
| `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY` | Web Push (ou fichier `vapid_private.pem` a la racine) |

Base SQLite : `gestion_conges.db` creee automatiquement au premier lancement.

---

## Structure du projet

- **app.py** : point d'entree Flask (`create_app`)
- **config.py** : configuration (DB, session, SMTP, VAPID)
- **run_wsgi.py** : lancement production (Waitress)
- **models/** : User, Conge, JourFerie, ParametrageAnnuel, AllocationConge, Notification, PushSubscription
- **routes/** : auth, rh, salarie, notifications
- **services/** : calcul_jours, jours_feries, solde, notifications, webpush, export
- **templates/** : Jinja2 (base, auth, rh, salarie, notifications)
- **static/** : CSS, JS (Alpine.js), sw.js (Service Worker Web Push)
- **scripts/** : create_admin.py, verifier_webpush.py
- **deploy/** : Linux (systemd, nginx), Windows (IIS)
- **docs/** : documentation complementaire (voir [docs/README.md](docs/README.md))

**CSS (Tailwind)** : en dev, si vous modifiez les styles, `npm run watch:css` ou `npm run build:css` (voir `package.json`).

---

## Fonctionnalites

### Authentification

- Connexion identifiant + mot de passe (bcrypt). Roles : `rh`, `salarie`. Session 30 min, redirection selon le role.

### Espace RH (`/rh/`)

- Tableau de bord (salaries, soldes, conges en cours, calendrier).
- Gestion salaries (CRUD, mot de passe).
- Conges : ajout, modification, suppression ; validation/refus des demandes ; calcul jours ouvrables, chevauchements, solde.
- Parametrage annuel : exercice, jours par defaut, allocations par salarie, jours feries (auto + manuel).
- Export Excel / PDF.

### Espace salarie (`/salarie/`)

- Accueil : solde (alloue / consomme / restant), liste des conges.
- Demande de conge (statut `en_attente` jusqu'a validation/refus RH).
- Export Excel / PDF.

### Notifications

- **In-app** : liste dans le menu Notifications (validation/refus, etc.), compteur, marquage lu.
- **Web Push** : clics « Activer les alertes » ; cles VAPID via `gen_vapid_keys.py`. En HTTPS : alertes hors du site ; en HTTP : push envoyes mais affichage systeme limite.

---

## Scripts utiles

| Script | Description |
|--------|-------------|
| `scripts/create_admin.py` | Cree un utilisateur RH (premier acces). |
| `gen_vapid_keys.py` | Genere vapid_private.pem et vapid_public.pem pour Web Push. |
| `scripts/verifier_webpush.py` | Verifie la config Web Push (cles, endpoint vapid-public). |

---

## Deploiement

- **Linux (nginx + Gunicorn)** : [deploy/README.md](deploy/README.md)
- **Windows Server (IIS)** : [deploy/README-IIS.md](deploy/README-IIS.md)

---

## Documentation complementaire

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) : architecture detaillee, modeles, flux et conventions pour les developpeurs.
