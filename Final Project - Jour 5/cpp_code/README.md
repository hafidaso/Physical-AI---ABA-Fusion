# Contrôleur de Sécurité Robotique Intelligent

Ce dossier contient le code C++ (`main.cpp`) pour le contrôleur de sécurité intelligent du robot, conçu pour fonctionner sur un ESP32 (avec le Maker Point Beginner Kit).

## Architecture et Fonctionnalités
- **Lecture des capteurs** : Infrarouge (détection d'obstacle), Potentiomètre (simulation de vitesse), MPU6050 (détection de choc), Bouton d'arrêt d'urgence.
- **Logique de sécurité locale** : Évalue en continu l'état du robot (NORMAL, WARNING, STOP/DANGER, FAULT) et contrôle les actionneurs (Relais, LEDs, Buzzer) de manière autonome, même sans connexion réseau.
- **Jumeau Numérique (Digital Twin)** : Connexion WiFi et MQTT vers HiveMQ Cloud.
- **Télémétrie** : Envoi régulier des données capteurs et de l'état (format JSON).
- **Commandes distantes** : Écoute d'un topic MQTT pour recevoir des commandes distantes (ex: `STOP` ou `RELEASE_STOP`).

## Matériel Requis
- Carte de développement ESP32
- Maker Point Beginner Kit
- Capteurs : IR, MPU6050, BME280, Potentiomètre
- Actionneurs : Relais x2, Afficheur 7 segments (TM1637), LEDs, Buzzer

## Configuration
Avant de compiler et de flasher, assurez-vous de configurer les variables suivantes au début du fichier `main.cpp` :
- `ssid` et `password` : Identifiants de votre réseau WiFi.
- `mqttUser` et `mqttPass` : Identifiants de votre cluster HiveMQ.

*Note : Veillez à ne pas publier vos mots de passe publiquement !*
