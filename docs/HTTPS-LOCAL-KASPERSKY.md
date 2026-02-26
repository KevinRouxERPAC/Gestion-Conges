# HTTPS en local et Kaspersky

Si Kaspersky (ou un autre antivirus) bloque l’accès au site en HTTPS en local avec un message du type « certificat non fiable » ou « connexion non sécurisée », vous pouvez appliquer l’une des solutions ci-dessous.

---

## Option 1 : Exclure le site dans Kaspersky (rapide)

Pour continuer à utiliser votre certificat actuel (ex. auto-signé) sans que Kaspersky bloque :

1. Ouvrir **Kaspersky** → **Paramètres** (ou **Réglages**).
2. Aller dans **Protection** → **Protection du navigateur** (ou **Vérification des connexions chiffrées** / **Scan SSL**).
3. Ajouter une **exception** pour l’URL de votre site, par exemple :
   - `https://localhost`
   - ou `https://votre-nom-de-serveur` (si vous accédez par le nom de la machine).

Selon la version de Kaspersky, l’option peut s’appeler :
- **Exclure des adresses** / **Sites exclus**,
- ou **Ne pas vérifier les connexions chiffrées pour** …

Après avoir ajouté l’URL, recharger la page du site.

---

## Option 2 : Utiliser un certificat fiable avec mkcert (recommandé pour le dev)

[mkcert](https://github.com/FiloSottile/mkcert) crée une **autorité de certification locale** et des certificats que Windows (et les navigateurs) considèrent comme fiables. Kaspersky peut toutefois continuer à inspecter le trafic ; si c’est le cas, combiner avec l’option 1 pour exclure l’URL.

### Étapes

1. **Installer mkcert** (ex. avec Chocolatey) :
   ```powershell
   choco install mkcert
   ```
   Ou télécharger depuis [https://github.com/FiloSottile/mkcert/releases](https://github.com/FiloSottile/mkcert/releases).

2. **Installer la CA locale** dans le magasin de confiance Windows :
   ```powershell
   mkcert -install
   ```

3. **Générer un certificat** pour votre accès local (adapter le nom si besoin) :
   ```powershell
   cd C:\Sites\Gestion-Conges
   mkcert -key-file deploy\ssl\localhost-key.pem -cert-file deploy\ssl\localhost.pem localhost 127.0.0.1 ::1
   ```
   Créer le dossier `deploy\ssl` si nécessaire.

4. **Exporter en .pfx** pour IIS (remplacer `VotreMotDePasse` par un mot de passe de votre choix) :
   ```powershell
   # Avec OpenSSL (ex. fourni avec Git pour Windows) :
   openssl pkcs12 -export -out deploy\ssl\localhost.pfx -inkey deploy\ssl\localhost-key.pem -in deploy\ssl\localhost.pem -passout pass:VotreMotDePasse
   ```

5. **Importer le certificat dans IIS** :
   - Ouvrir **Gestionnaire des services Internet (IIS)**.
   - Sélectionner le **serveur** (nom de la machine) → **Certificats serveur**.
   - **Importer** → choisir `deploy\ssl\localhost.pfx`, saisir le mot de passe.
   - Sur le **site** Gestion-Conges : **Liaisons** → **Ajouter** → Type **https**, port **443**, certificat SSL : celui que vous venez d’importer.

6. Si Kaspersky bloque encore, ajouter une exception pour `https://localhost` (option 1).

---

## Option 3 : Utiliser HTTP en local (sans certificat)

Pour le développement, vous pouvez désactiver HTTPS et accéder au site en HTTP. Aucun certificat, donc pas de blocage par Kaspersky pour ce motif.

1. Dans **web.config**, passer `PREFERRED_URL_SCHEME` à **http** :
   ```xml
   <environmentVariable name="PREFERRED_URL_SCHEME" value="http" />
   ```

2. Dans IIS, n’utiliser qu’une **liaison HTTP** (port 80 ou 5000), pas de liaison HTTPS.

3. Accéder au site via `http://localhost` (ou `http://votre-serveur`).

**Limite** : les notifications Web Push peuvent ne pas s’afficher en dehors de l’onglet du site (contexte non sécurisé). Elles restent visibles dans l’application (menu Notifications).

---

## Résumé

| Besoin                         | Solution recommandée                    |
|--------------------------------|----------------------------------------|
| Débloquer vite                 | Option 1 : exception Kaspersky         |
| HTTPS fiable en dev            | Option 2 : mkcert + liaison HTTPS IIS  |
| Pas de souci de certificat     | Option 3 : HTTP en local               |

Pour un environnement de **production** sur un vrai domaine, utilisez un certificat délivré par une autorité reconnue (Let’s Encrypt, certificat d’entreprise, etc.) et liez-le à la liaison HTTPS du site dans IIS.
