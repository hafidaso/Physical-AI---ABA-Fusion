# 📌 Jour 4 - Contrôle de Moteur CC avec Capteur DHT11 et Afficheur LCD I2C
## Système d'Acquisition et d'Actionnement Intégré sur Arduino Uno

Ce dossier contient le projet pratique du Jour 4 de l'atelier **Physical AI**, axé sur l'intégration d'un capteur de température/humidité (DHT11), d'un potentiomètre pour le contrôle de vitesse, d'un moteur à courant continu (CC) via un pont en H L298N, et d'un écran LCD I2C pour l'affichage en temps réel.

---

## ⚙️ Architecture Système & Fonctionnement

Le système est conçu autour d'une carte **Arduino Uno**. Il réalise les opérations suivantes :
1. **Contrôle de vitesse du moteur** : La tension analogique du potentiomètre (0-5V) est lue, convertie en signal PWM (0-255) puis envoyée au pilote de moteur L298N pour moduler la vitesse du moteur CC.
2. **Mesure environnementale** : Un capteur DHT11 mesure la température et l'humidité ambiantes toutes les 2 secondes sans bloquer l'exécution générale (via la fonction non-bloquante `millis()`).
3. **Affichage Local (LCD)** : Un écran LCD 1602 avec module I2C affiche la vitesse actuelle du moteur, la température et le taux d'humidité.
4. **Supervision Série** : Les données du potentiomètre, la vitesse calculée, et les mesures DHT11 sont envoyées sur le port série à 9600 bauds.

---

## 🔌 Câblage & Brochage (Pin Mapping)

Le tableau suivant récapitule les connexions physiques avec l'**Arduino Uno** :

| Composant | Broche Arduino Uno | Type de Signal | Description |
| :--- | :--- | :--- | :--- |
| **Potentiomètre** | **A2** | Entrée Analogique | Permet de régler la vitesse du moteur (0 à 1023) |
| **Capteur DHT11** | **A3** | Entrée Digitale | Acquisition des données de température et humidité |
| **LCD I2C 1602** | **SDA (ou A4)** | I2C (Données) | Ligne de données du bus I2C (adresse par défaut `0x27`) |
| **LCD I2C 1602** | **SCL (ou A5)** | I2C (Horloge) | Ligne d'horloge de synchronisation |
| **Pilote L298N - ENA**| **3** (PWM) | Sortie PWM | Commande de la vitesse du moteur CC |
| **Pilote L298N - IN1**| **A0** | Sortie Digitale | Sens de rotation : Fixé à `HIGH` |
| **Pilote L298N - IN2**| **A1** | Sortie Digitale | Sens de rotation : Fixé à `LOW` |

---

## 💻 Description du Code (`src/main.cpp`)

Le code applique les meilleures pratiques de programmation sur Arduino :
- **DHT11 Non-bloquant** : L'acquisition du DHT11 est cadencée à 2 secondes (`2000 ms`) avec une logique basée sur `millis()`, évitant ainsi l'utilisation de `delay()`, ce qui garantit une excellente réactivité pour la régulation de vitesse du moteur.
- **Régulation et Sécurité** : Les fonctions `map()` et `constrain()` convertissent précisément la valeur analogique brute (0-1023) en un rapport cyclique PWM (0-255) sécurisé.
- **Optimisation de l'affichage** : L'écran LCD est rafraîchi continuellement à chaque cycle (`delay(100)`), avec un formatage propre (utilisation d'espaces de remplissage) pour éviter le scintillement et l'accumulation de caractères fantômes.

---

## 📂 Fichiers et Documentation dans ce Dossier

* **[`src/main.cpp`](./src/main.cpp)** : Code source Arduino C++.
* **[`platformio.ini`](./platformio.ini)** : Configuration PlatformIO avec les bibliothèques `DHT sensor library` et `LiquidCrystal_I2C`.
* **[`Documentation_LCD1602_DHT11_Moteur_Arduino_Uno.pdf`](./Documentation_LCD1602_DHT11_Moteur_Arduino_Uno.pdf)** : Guide technique complet et schéma de câblage.
* **`20260521_162540.mp4`** : Vidéo de démonstration montrant le fonctionnement du matériel physique (moteur variant en vitesse avec le potentiomètre et LCD affichant les données du DHT11).

---

## 🛠️ Compilation & Téléversement

### Prérequis
* **Visual Studio Code** avec l'extension **PlatformIO IDE**.

### Instructions
1. Ouvrez le dossier `Motor Jour 4` dans VS Code.
2. PlatformIO téléchargera automatiquement les dépendances requises.
3. Connectez votre Arduino Uno à l'ordinateur en USB.
4. Compilez le projet en cliquant sur l'icône de coche (✓) dans la barre d'état.
5. Téléversez sur la carte en cliquant sur l'icône de flèche (→).
6. Ouvrez le Moniteur Série (icône de prise ou à 9600 bauds) pour observer la télémétrie.
