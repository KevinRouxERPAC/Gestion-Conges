# Certificat HTTPS en intranet (conges.erpac.com)

Le site utilise un certificat *.erpac.com emis par une autorite interne ERPAC-SRV18150RD1-CA. Les problemes (avertissement Non securise, blocage Kaspersky) viennent du fait que les postes clients ne font pas confiance a cette CA.

## 1. S'assurer qu'il n'y aura pas de probleme

**Sur le reseau (recommandé)**  
Deployer la CA racine sur tous les postes : via GPO (Stratégie de groupe) qui installe le certificat de la CA dans Autorites de certification racines de confiance. Une fois la CA installee, navigateurs et logiciels accepteront le certificat sans avertissement.

**Sur chaque poste (si pas de GPO)**  
1. Obtenir le fichier certificat de la CA (.cer) aupres de l'admin.  
2. Double-clic sur le fichier - Installer le certificat - Ordinateur local - Placer dans Autorites de certification racines de confiance.  
3. Si Kaspersky bloque encore : ajouter une exception pour https://conges.erpac.com (voir HTTPS-LOCAL-KASPERSKY.md).

## 2. Verifier qu'un poste fait confiance au certificat

- Navigateur : ouvrir https://conges.erpac.com - cadenas - afficher le certificat. La chaine doit remonter a ERPAC-SRV18150RD1-CA avec statut Valide.  
- Windows : certmgr.msc ou certlm.msc - Autorites de certification racines de confiance - verifier la presence de ERPAC-SRV18150RD1-CA.  
- Script : python scripts/check_https_cert.py https://conges.erpac.com (affiche le certificat serveur).

## 3. Resume

| Action | Effet |
|--------|--------|
| CA installee en racine de confiance sur tous les postes | Plus d'avertissement navigateur, pas de blocage antivirus pour ce certificat. |
| GPO qui deploye cette CA | Meme resultat pour tout le parc Windows domaine. |
| Exception Kaspersky pour https://conges.erpac.com | Contourne le blocage sur un poste. |

Le certificat serveur est correct ; l'essentiel est que chaque poste client fasse confiance a la CA qui l'a emis.

## 4. Installation rapide sur son PC (script ou commande)

**Prerequis** : obtenir le fichier .cer de la CA (ERPAC-SRV18150RD1-CA) aupres de l'admin, puis le placer dans le projet (ex. deploy\erpac-ca.cer).

**Script (depuis la racine du projet)** :
```powershell
.\deploy\installer-ca-erpac.ps1
```
Si le .cer est ailleurs : `.\deploy\installer-ca-erpac.ps1 C:\chemin\vers\ERPAC-CA.cer`

**Commande directe (remplacer le chemin par le votre)** :
```powershell
certutil -user -addstore Root "C:\Sites\Gestion-Conges\deploy\erpac-ca.cer"
```
Ou pour installer pour tous les utilisateurs (necessite admin) :
```powershell
certutil -addstore Root "C:\Sites\Gestion-Conges\deploy\erpac-ca.cer"
```
