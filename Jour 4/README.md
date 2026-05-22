# 📌 Jour 4 : Contrôle d'Actionneurs et Interfaces Utilisateurs Physiques
## Intégration de Périphériques avec Arduino Uno

Ce dossier contient les travaux pratiques du **Jour 4** du programme **Physical AI**. Cette session est dédiée à la maîtrise des interfaces physiques sur microcontrôleur **Arduino Uno**, notamment l'acquisition de données capteurs, la gestion d'affichage (LCD et 7 segments), et le pilotage de puissance d'un moteur à courant continu (CC).

---

## 📁 Contenu du Dossier

### 1. [`Ex1 - Jour 4`](./Ex1%20-%20Jour%204/) (Afficheur 7 Segments & Logique Interactive)
Un projet PlatformIO mettant en œuvre un affichage interactif basé sur un afficheur 7 segments (logique active-basse), un bouton-poussoir et un potentiomètre.

**Fonctionnalités clés :**
- **Calcul dynamique** : Détermination du chiffre à afficher en combinant la valeur brute d'un potentiomètre et un décalage (`offset`) incrémenté par bouton-poussoir avec anti-rebond.
- **Décodage binaire** : Utilisation d'un tableau de correspondance binaire (`byte numbers[10][7]`) pour piloter les segments.
- **Logique conditionnelle** : Commutation automatique entre deux LEDs (bleue pour les chiffres pairs, blanche pour les impairs).

### 2. [`Motor Jour 4`](./Motor%20Jour%204/) (Pilotage de Vitesse de Moteur & Télémétrie)
Un projet PlatformIO complet intégrant la régulation de vitesse d'un moteur CC à l'aide d'un pilote en pont en H L298N, un capteur DHT11 et un écran LCD I2C 1602.

**Fonctionnalités clés :**
- **Contrôle PWM** : Commande en vitesse de 0 à 255 du moteur CC via le signal PWM de l'Arduino connecté à la broche ENA du L298N.
- **Acquisition Température/Humidité** : Mesures régulières et fiables via le capteur DHT11 toutes les 2 secondes sans bloquer la boucle principale (`millis()`).
- **Affichage I2C LCD** : Rendu clair et dynamique de la télémétrie système (vitesse du moteur, humidité, température) sur écran 1602.

---

## ⚙️ Compilation et Utilisation

1. Ouvrez l'un des deux dossiers de projets dans **VS Code** avec l'extension **PlatformIO IDE** installée.
2. PlatformIO configurera automatiquement l'environnement de compilation pour la carte **Arduino Uno**.
3. Connectez votre Arduino Uno à votre ordinateur.
4. Utilisez les raccourcis PlatformIO pour :
   - **Compiler** le code (bouton de coche `✓`).
   - **Téléverser** le programme sur la carte (bouton de flèche `→`).
   - **Ouvrir le moniteur série** pour visualiser les logs et la télémétrie en direct.
