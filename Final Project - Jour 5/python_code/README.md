# Tableau de Bord SCADA et Pont ABA Fusion

Ce dossier contient le script Python (`smart_robot_scada_fusion.py`) qui sert d'interface de supervision (SCADA) et de pont de données vers ABA Fusion.

## Fonctionnalités
- **Supervision en temps réel** : Interface graphique développée avec Pygame permettant de visualiser la position (simulée), l'état des capteurs (IR, MPU6050, vitesse), ainsi que l'état des relais et la connectivité.
- **Communication MQTT** : Se connecte au broker HiveMQ pour recevoir la télémétrie envoyée par l'ESP32 et lui envoyer des commandes d'urgence (`STOP`, `RELEASE_STOP`).
- **Pont de données (Webhook)** : Récupère les données MQTT et les transmet en tâche de fond vers un Webhook ABA Fusion pour enregistrement (ex: Google Sheets).

## Installation des dépendances
Pour installer les librairies requises (telles que `pygame`, `paho-mqtt`, `requests`), exécutez la commande suivante :

```bash
pip install -r requirements_smart_robot_scada.txt
```

## Exécution
Pour des raisons de sécurité, les identifiants MQTT ne sont pas codés en dur. Avant de lancer le tableau de bord, vous devez définir vos identifiants via des variables d'environnement :

```bash
export ROBOT_MQTT_USER="votre_nom_d_utilisateur"
export ROBOT_MQTT_PASS="votre_mot_de_passe"
```

Puis, lancez l'application :

```bash
python smart_robot_scada_fusion.py
```

### Raccourcis Clavier
Sur l'interface, vous pouvez utiliser les touches suivantes :
- `S` : Déclencher un arrêt d'urgence distant.
- `R` : Relâcher l'arrêt d'urgence distant.
- `T` : Demander le statut immédiat au robot.
