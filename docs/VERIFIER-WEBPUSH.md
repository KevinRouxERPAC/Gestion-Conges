# Verifier les notifications Web Push

Ce guide permet de verifier que les notifications Web Push sont correctement configurees et fonctionnent.

## 1. Verifier la configuration cote serveur

Executer le script de verification (a la racine du projet) :

```bash
# Windows (avec venv active)
.\venv\Scripts\python.exe scripts\verifier_webpush.py

# Linux / macOS
python scripts/verifier_webpush.py
```

Resultat attendu :

- `VAPID vapid_private.pem: OK` — le fichier de cle privee est present
- `Cle chargee: OK` — la cle est chargee par l'application
- `Endpoint vapid-public: OK` — l'API renvoie bien la cle publique VAPID

Si un element est `MANQUANT` ou `NON` :

1. **Generer les cles VAPID** (si `vapid_private.pem` est manquant) :
   ```bash
   python gen_vapid_keys.py
   ```
2. **Verifier les dependances** : `pywebpush` et `py_vapid` (ou `vapid`) doivent etre installes (`pip install -r requirements.txt`).

---

## 2. Activer les alertes dans le navigateur

1. Se connecter a l'application (en tant que **salarie** pour recevoir les notifications de validation/refus).
2. Dans la barre de navigation, cliquer sur **« Activer les alertes »**.
3. Accepter la demande d'autorisation du navigateur pour les notifications.
4. Le bouton doit disparaitre ou afficher « Alertes activees ».

Si le bouton n'apparait pas ou affiche « Alertes non configurees », la cle VAPID n'est pas disponible (revoir l'etape 1).  
Si « Notifications bloquees » s'affiche, autoriser les notifications pour le site dans les parametres du navigateur.

---

## 3. Declencher une notification (test de bout en bout)

Les Web Push sont envoyes lorsqu'une **notification in-app** est creee, en particulier lors de la **validation** ou du **refus** d'une demande de conge par un RH.

**Procedure de test :**

1. **Compte salarie** : se connecter, activer les alertes (etape 2), puis **demander un conge** (date debut / date fin, enregistrer).
2. **Compte RH** : se connecter, aller sur le tableau de bord, dans « Demandes en attente » **valider** ou **refuser** la demande du salarie.
3. **Cote salarie** :
   - Une **notification in-app** doit apparaitre dans le menu Notifications.
   - Une **notification systeme (Web Push)** doit s'afficher (fenetre popup du navigateur / OS), meme si l'onglet de l'application n'est pas actif (sous **HTTPS**). En HTTP, le push est envoye mais l'affichage systeme peut etre limite.

Pour tester sans second compte : utiliser deux navigateurs (ou une fenetre privee) : un pour le salarie, un pour le RH.

---

## 4. Verifications complementaires

- **Service Worker** : l'app enregistre `/sw.js`. Verifier dans les DevTools (F12) -> Application -> Service Workers que le worker est actif.
- **Abonnement en base** : apres « Activer les alertes », une entree existe dans la table `push_subscription` pour l'utilisateur (si vous avez acces a la BDD).
- **HTTPS** : pour recevoir les notifications **hors du site** (fenetre reduite ou onglet ferme), le site doit etre servi en HTTPS. En HTTP, les push peuvent etre envoyes mais l'affichage natif depend du navigateur.

---

## Resume des points de defaillance

| Symptome | Cause probable |
|----------|-----------------|
| `verifier_webpush.py` : MANQUANT / NON | Cles VAPID absentes ou non chargees -> executer `gen_vapid_keys.py` |
| « Alertes non configurees » au clic | Endpoint `/notifications/vapid-public` ne renvoie pas de cle |
| « Notifications bloquees » | Utilisateur a refuse les notifications -> reautoriser dans le navigateur |
| Pas de push apres validation/refus | Salarie n'a pas clique sur « Activer les alertes », ou `pywebpush` manquant / erreur cote serveur (voir logs) |
| Push recu mais pas affiche | En HTTP, affichage systeme limite ; passer en HTTPS pour un comportement complet |
