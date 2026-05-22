# Workflow ABA Fusion

Ce dossier contient l'exportation du workflow utilisé dans **ABA Fusion** pour le projet.

## Fichier(s) inclus
- `Robot Smart- CSV-*.json` : Ce fichier JSON est une sauvegarde (export) du flux de travail automatisé (workflow) créé dans ABA Fusion.

## Fonctionnement du Workflow
Ce workflow s'occupe de la réception et du traitement de la télémétrie du robot :
1. **Webhook Trigger** : Il écoute les requêtes HTTP (POST) entrantes sur la route `/robot-telemetry` (requêtes envoyées par le script Python SCADA).
2. **Normalisation (JavaScript)** : Un nœud de traitement nettoie et formate les données reçues (conversion des booléens, vérification de l'humidité, horodatage, etc.).
3. **Validation** : Il vérifie que l'ID du dispositif n'est pas nul et que l'état reçu est valide (`NORMAL`, `WARNING`, `STOP`, ou `FAULT`).
4. **Intégration Google Sheets** : Si les données sont valides, elles sont ajoutées sous forme de nouvelle ligne dans un document Google Sheets (colonnes A à S).
5. **Réponses** : Le workflow renvoie une réponse HTTP 200 en cas de succès, ou une réponse 400 si les données sont invalides.

## Comment l'utiliser ?
Vous pouvez importer ce fichier JSON directement dans la plateforme **ABA Fusion** pour restaurer ou dupliquer votre workflow, y compris ses nœuds et ses connexions. Il vous suffira de vérifier et de re-connecter vos propres identifiants (Google Sheets, par exemple).
