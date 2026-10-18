# CloudDesk

API de suivi de demandes IT, développée progressivement pendant
ma préparation AZ-900, puis AZ-104.

## État actuel

- API FastAPI fonctionnelle en local.
- Route GET /health pour vérifier que l'application répond.
- Groupe de ressources Azure : rg-clouddesk-dev.
- Budget mensuel avec alertes au niveau de l'abonnement.

## Exécution locale

Prérequis : uv.

Installer les dépendances :
    uv sync --locked

Démarrer l'API :
    uv run uvicorn main:app --reload

Tester : http://localhost:8000/health
Documentation : http://localhost:8000/docs

## Choix techniques

- FastAPI : créer une API Python simple pour concentrer
  l'apprentissage sur Azure.
- uv : gérer l'environnement et les dépendances.
- uv.lock versionné : conserver les versions des dépendances.
- Groupe de ressources dédié : gérer ensemble les ressources
  de développement de CloudDesk.
- Budget au niveau de l'abonnement : surveiller les dépenses
  de tout le laboratoire. Les alertes ne bloquent pas la consommation.