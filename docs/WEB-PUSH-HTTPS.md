# Web Push et HTTPS

## Comportement actuel (site en HTTP)

- **Côté serveur** : l’envoi des notifications Web Push fonctionne (le serveur envoie bien le push à FCM/le navigateur).
- **Côté navigateur** : l’API Web Push et l’affichage des notifications sont limitées aux **contextes sécurisés** (HTTPS ou `localhost` selon les navigateurs). En HTTP (par ex. `http://mon-serveur/` ou `http://192.168.x.x:5000/`), le navigateur peut **ne pas afficher** la notification, même si le push a été reçu. L’utilisateur ne voit alors la notification qu’en se rendant sur le site (ou en actualisant) et en consultant la liste des notifications in-app.

## Pour que les alertes s’affichent sans être sur le site

Il faut que l’application soit servie en **HTTPS** (certificat valide ou auto-signé selon l’environnement). Dans ce cas :

- Le Service Worker peut recevoir le push.
- La notification système (toast) s’affiche même quand l’onglet est fermé ou que l’utilisateur n’est pas sur le site.

## Résumé

| Contexte              | Envoi serveur | Affichage notification (hors du site) |
|-----------------------|----------------|----------------------------------------|
| HTTP (hors localhost) | Oui            | Non (navigateur)                       |
| HTTPS                 | Oui            | Oui                                    |

Le projet reste configuré en HTTP uniquement par choix métier. Pour activer les notifications Web Push visibles hors du site, il faut mettre en place HTTPS (IIS, nginx, reverse proxy, etc.) pour l’application.
