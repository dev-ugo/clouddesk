# Déploiement de CloudDesk sur Azure App Service

Ce guide documente le premier déploiement manuel de l'API. Les commandes Bash sont destinées à WSL/Ubuntu et se lancent depuis la racine du dépôt. Le résultat fonctionnel a été confirmé le **18 octobre 2026**, par une réponse de `/health` dans Azure.

## 1. Préparer l'environnement Azure

Pour reproduire l'hébergement, disposer d'un abonnement actif et des droits nécessaires pour créer et configurer ses ressources.

### Groupe de ressources

Dans le portail Azure, créer ou sélectionner `rg-clouddesk-dev` et ajouter les tags :

| Tag | Valeur |
| --- | --- |
| `project` | `clouddesk` |
| `environment` | `dev` |

L'emplacement du groupe concerne ses métadonnées. Les ressources du groupe peuvent avoir un emplacement différent. Les tags du groupe ne sont pas automatiquement hérités par les ressources ; les ajouter à celles-ci si nécessaire.

### Région autorisée

Le premier essai dans la région initialement choisie a été refusé par une stratégie de l'abonnement. La liste consultée pendant la séance était :

```json
["belgiumcentral","germanywestcentral","denmarkeast","austriaeast","francecentral"]
```

Le déploiement a ensuite été réalisé dans **France Central**. Pour un autre abonnement, consulter sa propre liste : **Azure Policy / Stratégie → Affectations → politique de régions autorisées → Paramètres**.

### Application et plan

Dans **App Services → Créer → Application web**, utiliser :

| Paramètre | Valeur |
| --- | --- |
| Groupe de ressources | `rg-clouddesk-dev` |
| Nom | `app-clouddesk-dev`, ou un nom disponible pour une reproduction |
| Publication | Code |
| Pile | Python |
| Version | Version compatible avec `requires-python` et cohérente avec la version locale |
| Système | Linux |
| Région | France Central, sous réserve d'autorisation et de disponibilité |
| Nouveau plan | `asp-clouddesk-dev-frc` |
| Niveau | Free F1 |

Vérifier F1 dans le récapitulatif avant création. La disponibilité d'un niveau dépend notamment de la région et de l'abonnement. Le déploiement continu et Application Insights n'ont pas été ajoutés à ce jalon.

L'application et son plan utilisent la même région. L'adresse publique exacte se trouve dans **Vue d'ensemble → Domaine par défaut** ; elle peut contenir un suffixe généré.

### Budget du laboratoire

Configuration demandée pendant la séance :

| Paramètre | Valeur |
| --- | --- |
| Nom | `budget-lab-azure` |
| Étendue | Abonnement personnel |
| Filtre | Aucun |
| Réinitialisation | Mensuelle |
| Montant | 5 dans la devise affichée par Azure |
| Début / expiration prévus | 1er octobre 2026 / 1er octobre 2027 |
| Alertes | Coût réel à 50 %, 80 % et 100 %, vers l'adresse personnelle |

Les valeurs et la devise exactes sont à consulter dans le budget créé. Ce montant est un seuil choisi pour le laboratoire, pas une estimation du coût de l'API. Les notifications utilisent des données mises à jour avec un délai ; elles ne bloquent pas les dépenses.

## 2. Préparer le projet Python

Le code à déployer se trouve dans `main.py`. Les dépendances `fastapi` et `uvicorn` sont déclarées dans `pyproject.toml`, avec leurs versions résolues dans `uv.lock`.

Pour cette structure simple, conserver la configuration suivante :

```toml
[tool.uv]
package = false
```

Si `[tool.uv]` existe déjà, ajouter la clé dans cette section. Ce réglage demande à uv de gérer les dépendances sans construire et installer CloudDesk lui-même comme paquet Python.

Après une modification de configuration :

```bash
uv lock
uv sync --locked
```

La commande `uv lock` actualise le lockfile si nécessaire ; `uv sync --locked` vérifie sa cohérence avant de synchroniser l'environnement.

## 3. Se connecter et relever les versions

Installer [Azure CLI pour Linux](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-linux?pivots=apt) si nécessaire, puis :

```bash
az login --use-device-code
az account show --query name --output tsv
```

Vérifier que le nom affiché correspond au bon abonnement. Si nécessaire, le sélectionner explicitement avec `az account set --subscription "NOM_OU_ID"`.

Définir les raccourcis utilisés dans les commandes suivantes :

```bash
CLOUDDESK_RG="rg-clouddesk-dev"
CLOUDDESK_APP="app-clouddesk-dev"
```

Adapter le nom de l'application à celui réellement créé. Ces variables Bash appartiennent au terminal courant. `$CLOUDDESK_APP` récupère la valeur enregistrée ; `--name "$CLOUDDESK_APP"` fournit donc ce nom à Azure CLI. Elles ne sont pas des paramètres enregistrés dans l'application Azure.

Consulter les versions et la pile configurée :

```bash
uv --version
uv run python --version
az version
az webapp config show \
  --resource-group "$CLOUDDESK_RG" \
  --name "$CLOUDDESK_APP" \
  --query "{runtime:linuxFxVersion,startup:appCommandLine}" \
  --output json
```

L'exacte version utilisée le 18 octobre n'a pas été consignée ; ces commandes indiquent l'état au moment où elles sont exécutées.

## 4. Configurer la préparation et le démarrage

Activer la préparation du code lors du déploiement :

```bash
az webapp config appsettings set \
  --resource-group "$CLOUDDESK_RG" \
  --name "$CLOUDDESK_APP" \
  --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true \
  --output none
```

Le moteur de build Oryx prend en charge `pyproject.toml` avec `uv.lock` pour utiliser uv. Les deux fichiers doivent être inclus à la racine de l'archive.

Définir la commande de démarrage :

```bash
az webapp config set \
  --resource-group "$CLOUDDESK_RG" \
  --name "$CLOUDDESK_APP" \
  --startup-file "python -m uvicorn main:app --host 0.0.0.0 --port 8000" \
  --output none
```

| Élément | Signification |
| --- | --- |
| `python -m uvicorn` | Lance le serveur Uvicorn dans l'environnement Python de l'application. |
| `main:app` | Charge l'objet `app` du fichier `main.py`. |
| `--host 0.0.0.0` | Écoute sur les interfaces réseau du conteneur pour recevoir les requêtes acheminées par la plateforme. |
| `--port 8000` | Utilise le port d'écoute de notre serveur dans le conteneur. |

`--reload` est réservé à l'exécution locale de développement. Azure gère l'entrée HTTPS publique ; cette commande concerne le processus à l'intérieur de l'environnement hébergé.

## 5. Construire l'archive et la déployer

```bash
uv run python -m zipfile -c /tmp/clouddesk.zip \
  main.py pyproject.toml uv.lock README.md
```

L'archive contient le code et les fichiers nécessaires à la préparation. L'environnement local `.venv`, Git et les éventuels fichiers `.env` restent en dehors. Les fichiers doivent être directement à la racine du ZIP, sans dossier parent `clouddesk/`.

```bash
az webapp deploy \
  --resource-group "$CLOUDDESK_RG" \
  --name "$CLOUDDESK_APP" \
  --src-path /tmp/clouddesk.zip \
  --type zip
```

La commande cible la Web App existante. Répéter cette étape après une modification du code, en recréant d'abord le ZIP. Si le code utilise plus tard d'autres fichiers, adapter son contenu.

## 6. Vérifier l'application

Récupérer le domaine réellement attribué à la Web App :

```bash
CLOUDDESK_HOST=$(az webapp show \
  --resource-group "$CLOUDDESK_RG" \
  --name "$CLOUDDESK_APP" \
  --query defaultHostName \
  --output tsv)

curl --fail-with-body --include "https://$CLOUDDESK_HOST/health"
```

Résultat attendu : une réponse **HTTP 200** contenant :

```json
{"status":"ok","application":"clouddesk"}
```

La documentation interactive est accessible sur le même domaine avec `/docs`. L'URL racine `/` peut répondre 404, car aucune route `/` n'a été définie dans cette version.

Cette validation confirme la réponse de notre API au moment du test. Elle ne constitue pas encore une surveillance continue ni une vérification de la disponibilité future.

## 7. Incidents rencontrés et enseignements

### Région refusée

**Observation :** Azure a refusé `app-clouddesk-dev` avec un message indiquant que l'abonnement ne pouvait déployer que dans certaines régions.

**Action et résultat :** consultation des régions autorisées, puis création de l'hébergement dans France Central.

**Enseignement :** une stratégie Azure peut bloquer une création qui ne respecte pas ses règles. Le groupe de ressources peut conserver son emplacement de métadonnées tout en regroupant des ressources hébergées ailleurs.

### Construction du paquet Python impossible

**Erreur observée :**

```text
Expected a Python module at: src/clouddesk/__init__.py
```

**Cause identifiée :** la configuration de packaging attendait un paquet sous `src/clouddesk/`, alors que l'archive envoyée contenait une application `main.py` à la racine.

**Correction appliquée :** ajout de `package = false` dans `[tool.uv]`, actualisation du lockfile, puis reconstruction et redéploiement du ZIP. L'avertissement de version du backend de build n'était pas l'erreur fatale affichée.

**Enseignement :** les fichiers livrés et la configuration du projet doivent décrire la même structure.

### Attente « Starting the site… »

**Observation :** Azure CLI affichait encore ces messages après environ 143 secondes, alors que `/health` renvoyait déjà la réponse attendue.

**Conclusion établie :** l'API répondait. La cause de l'attente du suivi CLI n'a pas été déterminée pendant la séance ; aucune correction supplémentaire du démarrage n'a été validée.

**Action :** vérification de la route HTTP et interruption possible de l'attente locale avec `Ctrl+C`, une fois la réponse confirmée. Interrompre cette attente n'arrête pas la Web App.

## 8. Consulter les journaux en cas d'échec

Dans un second terminal, redéfinir les deux variables Bash, puis :

```bash
az webapp log config \
  --resource-group "$CLOUDDESK_RG" \
  --name "$CLOUDDESK_APP" \
  --docker-container-logging filesystem \
  --output none

az webapp log tail \
  --resource-group "$CLOUDDESK_RG" \
  --name "$CLOUDDESK_APP"
```

La commande `log tail` suit les journaux en continu ; `Ctrl+C` ferme cette consultation. Le portail propose également **Surveillance → Flux de journaux**. Examiner les erreurs réelles avant de modifier une dépendance ou la commande de démarrage.

## 9. Versionner la documentation

Depuis la racine du dépôt, après intégration de ces deux fichiers :

```bash
git diff -- README.md docs/deploiement.md pyproject.toml uv.lock
git add README.md docs/deploiement.md pyproject.toml uv.lock
git commit -m "Document first Azure deployment and technical choices"
```

## Références officielles

- [Groupes de ressources](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/manage-resource-groups-portal)
- [Tags et héritage](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/tag-resources)
- [Création et gestion des budgets](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets)
- [Déployer une API Python dans App Service](https://learn.microsoft.com/en-us/azure/app-service/quickstart-python)
- [Configuration Python, Oryx et démarrage](https://learn.microsoft.com/en-us/azure/app-service/configure-language-python)
- [Configuration du packaging uv](https://docs.astral.sh/uv/concepts/projects/config/)
- [Commande az webapp deploy](https://learn.microsoft.com/en-us/cli/azure/webapp#az-webapp-deploy)
- [Journaux App Service](https://learn.microsoft.com/en-us/cli/azure/webapp/log)

[Retour au README](../README.md)
