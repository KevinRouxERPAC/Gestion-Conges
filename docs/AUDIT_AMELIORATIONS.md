# Audit & Améliorations — Gestion des Congés ERPAC

> Document généré le 24/03/2026. Recense toutes les améliorations identifiées lors de l'audit complet du site, leur statut et les détails de correction.

---

## Légende des statuts

| Icône | Statut |
|-------|--------|
| FAIT | Corrigé et testé (60/60 tests OK) |
| A FAIRE | Reste à implémenter |

---

## CRITIQUE

| # | Sujet | Statut | Détail |
|---|-------|--------|--------|
| 1 | SECRET_KEY exposée dans `web.config` | FAIT | Remplacée par un placeholder. Commentaire d'instruction ajouté. **Action manuelle requise** : régénérer la clé en production (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) |

---

## PRIORITE HAUTE — Sécurité

| # | Sujet | Statut | Détail |
|---|-------|--------|--------|
| 2 | Whitelist des rôles utilisateur | FAIT | Constante `ROLES_AUTORISES` ajoutée dans `rh.py`. Validation dans `creer_salarie` et `modifier_salarie` |
| 3 | Durcissement cookies de session | FAIT | `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE="Lax"`, `SESSION_COOKIE_SECURE` (auto si HTTPS) ajoutés dans `config.py` |
| 4 | Validation incomplète dans `modifier_conge` | FAIT | Ajout de la vérification `types_standards` identique à `ajouter_conge` |
| 5 | Plafonds congés exceptionnels non revérifiés à la validation RH | FAIT | Bloc `else` ajouté dans `valider_conge` appelant `verifier_plafond` pour les types `EXC:` |
| 6 | Open redirect via `Referer` | FAIT | Fonction `_safe_redirect_url` ajoutée dans `notifications.py`, vérifie que le host du referrer correspond |
| 7 | Pas de rate limiting sur `/login` | FAIT | Rate limiter en mémoire : 5 tentatives max / 15 min par IP. Reset après login réussi |

---

## PRIORITE HAUTE — Architecture & Robustesse

| # | Sujet | Statut | Détail |
|---|-------|--------|--------|
| 8 | Pas de gestionnaire d'erreurs global | FAIT | Handlers 404/403/500 ajoutés dans `app.py`. Template `erreur.html` créé (cohérent avec le design du site). Rollback DB sur 500 |
| 9 | Migrations silencieuses au démarrage | FAIT | Niveau de log passé de `warning` à `error` avec `exc_info=True`. `logging.basicConfig` configuré au démarrage |
| 10 | Erreur masquée dans le calcul RTT | FAIT | `except Exception: rtt_calc = None` remplacé par logging `error` avec traceback. Fallback gracieux conservé |
| 11 | Import `bcrypt` inutilisé | FAIT | `import bcrypt` supprimé de `auth.py` et `rh.py`. `hash_password` inutilisé supprimé de `auth.py` |

---

## PRIORITE MOYENNE — Performance

| # | Sujet | Statut | Détail |
|---|-------|--------|--------|
| 12 | Pattern N+1 sur le dashboard RH | FAIT | Fonction `calculer_soldes_batch` créée (3 requêtes au lieu de ~5N). Congés en cours agrégés en 1 requête. Idem pour les inactifs |
| 13 | Pas de pagination | FAIT | Limite de 50 congés par défaut sur accueil salarié et fiche RH, avec lien "Afficher tout" (`?tous=1`) |
| 14 | SQLite en production | FAIT | URI configurable via `DATABASE_URL` (env var). SQLite par défaut. `.env.example` mis à jour |
| 15 | Polling notifications sans Page Visibility | FAIT | `visibilitychange` listener ajouté : polling suspendu quand onglet masqué, repris immédiatement au retour |
| 16 | Pas de cache-busting sur les assets | FAIT | `@app.url_defaults` ajoute `?v=<mtime>` automatiquement à tous les `url_for('static', ...)` |

---

## PRIORITE MOYENNE — UI/UX

| # | Sujet | Statut | Détail |
|---|-------|--------|--------|
| 17 | Légende calendrier salarié masquée | FAIT | `class="hidden"` retiré des labels "Ancienneté" et "Autre" dans `calendrier.html` |
| 18 | Badge notifications mobile non synchronisé | FAIT | Corrigé au point 15 : fonction `updateBadges` met à jour `#nav-notif-badge` et `#nav-notif-badge-mobile` |
| 19 | Dialogues natifs `confirm()` / `alert()` | FAIT | Fallbacks natifs retirés dans `static/js/app.js` : confirmations/alertes passent par la modale accessible (fallback neutre sans API native) |
| 20 | Deux systèmes de boutons (Tailwind + `.erpac-btn`) | A FAIRE | Harmoniser vers un seul système de boutons |
| 21 | Seuil responsive incohérent (900px vs Tailwind) | FAIT | Media query `.erpac-toolbar` alignée sur `md` Tailwind (`max-width: 767px`) dans `static/css/custom.css` |

---

## PRIORITE MOYENNE — Accessibilité (WCAG)

| # | Sujet | Statut | Détail |
|---|-------|--------|--------|
| 22 | Menu mobile : `aria-expanded` / `aria-controls` manquants | FAIT | Bouton hamburger enrichi avec `aria-controls="mobile-menu"` et binding `:aria-expanded` dans `base.html` |
| 23 | Pas de `aria-current="page"` sur la nav | FAIT | Ajout de `aria-current="page"` conditionnel sur les liens de navigation desktop et mobile selon `request.endpoint` |
| 24 | Pas de règle CSS `[x-cloak]` | FAIT | Règle `[x-cloak] { display: none !important; }` ajoutée dans `static/css/custom.css` |
| 25 | Barres de progression sans ARIA | FAIT | Ajout de `role="progressbar"`, `aria-valuemin/max/now` sur les barres CP/RTT dans `templates/salarie/accueil.html` et `templates/responsable/dashboard.html` |
| 26 | Tableaux sans `scope="col"` ni `<caption>` | FAIT | Ajout systématique de `scope="col"` et `<caption class="sr-only">` sur les tableaux applicatifs (salarié, responsable, RH, paramétrage, intéressement, heures) |
| 27 | Touche Espace non gérée sur `role="button"` | FAIT | Gestion `Enter` + `Espace` avec `preventDefault()` sur les lignes cliquables de `rh/dashboard.html` et `rh/salaries.html` |
| 28 | Flash messages : bouton fermer sans `aria-label` | FAIT | Bouton de fermeture des flashs complété avec `aria-label="Fermer le message"` |
| 29 | Login : `autocomplete` manquant | FAIT | `autocomplete="username"` et `autocomplete="current-password"` ajoutés dans `templates/auth/login.html` |
| 30 | Footer `aria-hidden="true"` | FAIT | Attribut `aria-hidden` retiré du footer global dans `base.html` |
| 31 | `outline: none` global sans alternative systématique | FAIT | Remplacé par un style `:focus-visible` explicite (outline + offset) pour `input/select/textarea` |
| 32 | Pas de `aria-describedby` / `aria-invalid` sur les champs en erreur | FAIT | Gestion globale côté front dans `static/js/app.js` : champs invalides annotés avec `aria-invalid="true"` et message relié via `aria-describedby` |

---

## PRIORITE BASSE — Qualité de code & Bonnes pratiques

| # | Sujet | Statut | Détail |
|---|-------|--------|--------|
| 33 | Scripts inline abondants (bloque CSP) | FAIT | Scripts inline extraits vers `static/js/` (`conge-form.js`, `rh-heures.js`, `rh-dashboard.js`, `responsable-dashboard.js`, `salarie-calendrier.js`) ; seuls scripts externes + JSON data scripts restent |
| 34 | Pas de minification de `app.js` | FAIT | `static/js/app.min.js` généré via `terser`, script npm `build:js` ajouté et template de base basculé sur la version minifiée |
| 35 | Route `rh.py` trop volumineuse | FAIT | Extractions métier vers `services/rh_dashboard.py` et `services/rh_admin_actions.py` (dashboard RH, actions intéressement, actions types exceptionnels) |
| 36 | Double `db.session.commit()` après notifications | FAIT | Transactions fusionnées avec un seul commit après notifications dans `routes/salarie.py`, `routes/responsable.py` et `routes/rh.py` (`flush()` utilisé pour obtenir `conge.id` avant notification) |
| 37 | `innerHTML` dans `app.js` (toast) | FAIT | Toast notifications reconstruit via API DOM (`createElement`, `textContent`, `appendChild`) dans `static/js/app.js` |
| 38 | Tableaux responsives incomplets | FAIT | Ajout de wrappers `overflow-x-auto` sur les tableaux principaux (salarié, responsable, RH, paramétrage, intéressement, historiques) |
| 39 | `flex-nowrap` sur l'en-tête accueil salarié | FAIT | En-tête actions de `templates/salarie/accueil.html` passé en `flex-wrap` mobile avec `sm:flex-nowrap` |
| 40 | Contraste à vérifier (WCAG) | A FAIRE | Valider les combinaisons de couleurs avec un outil WCAG |
| 41 | Pas de `.env.example` complet à la racine | FAIT | Fichier `.env.example` ajouté à la racine avec toutes les variables applicatives documentées (DB, mail, web push, WSGI, admin script) |
| 42 | Pas de tests e2e | FAIT | Base Playwright ajoutée (`playwright.config.js`, script npm `test:e2e`, test smoke `tests/e2e/auth-smoke.spec.js`) |

---

## Récapitulatif

| Statut | Nombre |
|--------|--------|
| FAIT | 40 |
| A FAIRE | 2 |
| **Total** | **42** |

---

## Fichiers modifiés (corrections appliquées)

- `web.config` — SECRET_KEY placeholder
- `config.py` — cookies session, DATABASE_URL configurable
- `app.py` — error handlers, logging, cache-busting, migrations
- `routes/rh.py` — whitelist rôles, validation type_conge, plafonds EXC, batch soldes, pagination
- `routes/auth.py` — rate limiting, nettoyage imports
- `routes/salarie.py` — logging RTT, pagination
- `routes/notifications.py` — safe redirect
- `routes/responsable.py` — commit unique après notifications
- `routes/rh.py` — commit unique après notifications RH
- `services/solde.py` — `calculer_soldes_batch`
- `services/rh_dashboard.py` — extraction logique métier dashboard RH
- `services/rh_admin_actions.py` — extraction actions RH (intéressement, types exceptionnels)
- `static/js/app.js` — Page Visibility, badges synchronisés, fallback sans dialogues natifs
- `static/js/app.min.js` — bundle minifié chargé en production
- `static/js/conge-form.js` — logique formulaire congés (RTT/EXC heures)
- `static/js/rh-heures.js` — validation grille hebdo extraite du template
- `static/js/rh-dashboard.js` — calendrier RH extrait du template
- `static/js/responsable-dashboard.js` — calendrier responsable extrait du template
- `static/js/salarie-calendrier.js` — calendrier salarié extrait du template
- `static/css/custom.css` — règle `[x-cloak]`, focus visible
- `templates/erreur.html` — nouveau template d'erreur
- `templates/base.html` — nav ARIA, `aria-current`, footer, flash close label
- `templates/auth/login.html` — autocomplete username/password
- `templates/salarie/calendrier.html` — légende visible
- `templates/salarie/accueil.html` — lien "voir tout"
- `templates/responsable/dashboard.html` — progress bars ARIA
- `templates/rh/salaries.html` — support clavier Enter/Espace
- `templates/rh/salarie_detail.html` — lien "voir tout"
- `templates/rh/dashboard.html` — tables accessibles, navigation clavier
- `templates/rh/heures.html` — table accessible
- `templates/rh/parametrage.html` — table jours fériés accessible
- `templates/rh/interessement.html` — table périodes accessible
- `templates/rh/interessement_regles.html` — table règles accessible
- `templates/rh/types_exceptionnels.html` — table accessible
- `templates/salarie/heures.html` — table accessible
- `static/js/app.js` — `aria-invalid` / `aria-describedby` dynamiques sur erreurs de formulaire
- `templates/salarie/demander_conge.html` — script inline extrait
- `templates/responsable/ajouter_conge.html` — script inline extrait
- `templates/rh/ajouter_conge.html` — script inline extrait
- `templates/rh/modifier_conge.html` — script inline extrait
- `templates/rh/heures.html` — script inline extrait
- `templates/rh/dashboard.html` — script inline extrait
- `templates/responsable/dashboard.html` — script inline extrait
- `templates/salarie/calendrier.html` — script inline extrait
- `.env.example` — variables d'environnement complètes en racine
- `playwright.config.js` — configuration E2E Playwright
- `tests/e2e/auth-smoke.spec.js` — premier test smoke E2E
- `package.json` — scripts `test:e2e` / `test:e2e:headed` / `build:js`
- `templates/base.html` — chargement de `app.min.js`
- `deploy/gestion-conges.env.example` — variable DATABASE_URL documentée
