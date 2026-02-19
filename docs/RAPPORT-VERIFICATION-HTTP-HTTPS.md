# Rapport de vérification – Application en HTTP uniquement

**Date :** 19 février 2026  
**Politique :** Le projet est configuré pour **HTTP uniquement**. Aucune redirection vers HTTPS, aucun HSTS.

---

## 1. Résumé

**Configuration appliquée :**
- `config.py` : `PREFERRED_URL_SCHEME = "http"` (URLs générées en http).
- `app.py` : `PREFERRED_URL_SCHEME` forcé à `"http"` + hook `after_request` qui supprime tout en-tête `Strict-Transport-Security` (pas de HSTS).
- `web.config` (IIS) : pas de section `<rewrite>`, commentaire indiquant d’utiliser le site en HTTP uniquement.
- `deploy/nginx-gestion-conges.conf` : `listen 80` uniquement, commentaire « HTTP uniquement, pas de HTTPS ».

**Conclusion :** L’application ne renvoie que sur HTTP. Si le navigateur affiche du HTTPS, la cause est **hors projet** (IIS, HSTS enregistré dans le navigateur).

---

## 2. Fichiers vérifiés

### 2.1 `web.config` (IIS)

- **Contenu :** Uniquement `system.webServer` avec `handlers` (HttpPlatformHandler) et `httpPlatform` (processPath, arguments, variables d’environnement).
- **Absent :** Pas de section `<rewrite>`, pas de règle « Redirect HTTP to HTTPS », pas de liaison HTTPS imposée par ce fichier.
- **Verdict :** Aucune redirection HTTPS côté configuration IIS dans le dépôt.

---

### 2.2 Application Flask (`app.py`, `config.py`)

- **app.py :**
  - Un seul `redirect()` : `redirect(url_for("auth.login"))` pour la route `/`. Aucun `_scheme='https'` ni URL absolue en `https://`.
  - Aucun `after_request` ni middleware ajoutant des en-têtes (HSTS, etc.).
- **config.py :**
  - Pas de `PREFERRED_URL_SCHEME = 'https'`.
  - Pas de configuration liée à SSL/HTTPS pour l’application web (uniquement MAIL_USE_TLS/MAIL_USE_SSL pour le SMTP).
- **Verdict :** L’application Flask ne force pas HTTPS.

---

### 2.3 Routes (`routes/auth.py`, `routes/rh.py`, `routes/salarie.py`)

- Tous les `redirect()` utilisent `url_for(...)` sans `_scheme` ni `_external=True` vers une URL en `https://`.
- Redirections uniquement internes (login, dashboard, accueil, etc.).
- **Verdict :** Aucune redirection explicite vers HTTPS.

---

### 2.4 Templates (`templates/base.html`)

- Liens : `url_for('rh.dashboard')`, `url_for('auth.logout')`, etc. — tous relatifs au schéma de la requête.
- Une seule URL externe en `https://` : CDN Alpine.js (`https://cdn.jsdelivr.net/...`), sans impact sur le schéma du site.
- Pas de `<meta http-equiv="refresh" content="0; url=https://...">` ni de JavaScript forçant `location.href = 'https://...'`.
- **Verdict :** Aucun forçage HTTPS dans les templates.

---

### 2.5 JavaScript (`static/js/app.js`)

- Logique limitée (validation de dates, etc.). Aucune redirection ni modification de `location` vers HTTPS.
- **Verdict :** Aucun forçage HTTPS côté client.

---

### 2.6 Déploiement

- **run_wsgi.py :** Lance Waitress sur `127.0.0.1:port`. Aucune configuration HTTPS.
- **deploy/nginx-gestion-conges.conf :** `listen 80` uniquement ; pas de `listen 443`, pas de `return 301 https://`. `X-Forwarded-Proto $scheme` transmet le schéma reçu (http si le client est en http).
- **deploy/gestion-conges.service :** Gunicorn en écoute sur `127.0.0.1:5000`. Aucune mention HTTPS.
- **Verdict :** Les configs de déploiement du dépôt ne forcent pas HTTPS.

---

## 3. Où peut venir la redirection HTTPS ?

Si le navigateur affiche quand même le site en HTTPS, les causes possibles sont **hors dépôt** :

| Cause | Où vérifier |
|-------|-------------|
| **Règle IIS « Réécriture d’URL »** | Gestionnaire IIS → Site → Réécriture d’URL. Supprimer toute règle du type « Redirect HTTP to HTTPS ». |
| **Liaison HTTPS seule ou prioritaire** | Liaisons du site IIS : si seule la liaison 443 existe, ou si une règle redirige 80 → 443. |
| **HSTS (navigateur)** | Le site a peut-être été visité en HTTPS auparavant ; le navigateur a enregistré HSTS pour ce domaine. Effacer la politique HSTS pour le domaine (ex. `chrome://net-internals/#hsts` → Delete domain). |
| **Autre `web.config` ou configuration IIS** | Un `web.config` dans un répertoire parent ou une configuration au niveau du serveur/du site dans IIS (non versionnée ici). |

---

## 4. Synthèse

| Élément | Forçage HTTPS dans le dépôt ? |
|--------|--------------------------------|
| web.config | Non |
| app.py / config.py | Non |
| Routes (auth, rh, salarie) | Non |
| Templates (base.html, etc.) | Non |
| static/js/app.js | Non |
| deploy (nginx, service) | Non |

**Aucune redirection vers HTTPS ni configuration imposant HTTPS n’a été trouvée dans le projet.**  
Pour retrouver un accès en HTTP, il faut agir sur la configuration IIS (règles de réécriture, liaisons) et/ou sur le navigateur (HSTS).
