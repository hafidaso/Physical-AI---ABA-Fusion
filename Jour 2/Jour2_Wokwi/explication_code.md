# Explication du code : Système de Supervision Énergétique (Jour 2)

Dans ce projet de mini système de supervision énergétique avec l'ESP32, l'objectif n'est pas seulement de faire fonctionner le code, mais de comprendre la logique sous-jacente. L'explication qui suit justifie les choix techniques adoptés, en se concentrant sur les aspects essentiels du programme.

## 1. La logique globale (Le Workflow)
Pour simuler la supervision d'une alimentation, l'idée est simple : lire une tension, vérifier si elle est normale ou trop faible, et réagir en conséquence. 
Le code est organisé en suivant un workflow clair : `Sense` (mesurer) -> `Verify` (vérifier) -> `Decide` (décider) -> `Actuate` (agir) -> `Log` (enregistrer/afficher). Cette approche aide énormément à structurer le programme et à garder un fil conducteur.

## 2. L'organisation des variables et constantes
**Les `#define` pour les broches (Pins) :**
Plutôt que d'écrire les numéros des broches directement dans le code, l'utilisation des directives `#define` a été privilégiée. C'est une pratique beaucoup plus propre. Si le branchement d'un composant doit être modifié, le changement ne s'effectue qu'à un seul endroit au début du fichier.

**Le choix des types de variables (`int`, `float`, `bool`) :**
- Pour la lecture analogique du potentiomètre, un `int` est utilisé car l'ESP32 renvoie toujours une donnée brute sous forme de nombre entier entre 0 et 4095.
- Pour la **tension calculée** (`simulatedVoltage`), l'utilisation d'un `float` (nombre à virgule) est indispensable. Une tension pouvant être de 1.8V ou 2.5V, un entier aurait effacé les décimales et faussé la comparaison.
- Pour l'état du système (`systemOK`) et du bouton (`buttonPressed`), le choix s'est porté sur des variables booléennes (`bool`). Comme ce sont des états binaires (vrai/faux, appuyé/relâché), cela rend les conditions (`if`) beaucoup plus naturelles et lisibles.

## 3. Le choix de `INPUT_PULLUP` pour le bouton
Lors de la configuration dans le `setup()`, le bouton est déclaré avec `INPUT_PULLUP`. Cette technique permet d'activer la résistance de tirage (pull-up) interne de l'ESP32. L'avantage principal est de ne pas avoir à ajouter une résistance physique sur le circuit.
Avec cette configuration, la logique est inversée : lors d'un appui sur le bouton, le signal devient `LOW`. C'est exactement ce qui est vérifié dans le code : `buttonPressed = digitalRead(BUTTON_PIN) == LOW;`.

## 4. La conversion mathématique (L'étape Sense)
L'ESP32 ne lit pas directement des "Volts", il récupère une valeur entre 0 et 4095. Pour donner un sens physique à cette valeur, un produit en croix est appliqué :
`simulatedVoltage = analogValue * 3.3 / 4095.0;`
La multiplication se fait par 3.3 (la tension maximale de fonctionnement de l'ESP32) et la division par la résolution maximale (4095). Cette formule permet d'obtenir une valeur en Volts réelle, facilement comparable avec le seuil de sécurité fixé à 1.8V.

## 5. La prise de décision et l'action (Verify & Actuate)
C'est le cœur du système de supervision. La logique est séparée en deux scénarios clairs :
- **Si la tension est suffisante (>= 1.8V) :** Le système est normal. Le fonctionnement est autorisé en activant le relais (qui représente la charge). La LED verte s'allume, et il est essentiel de s'assurer de la désactivation du buzzer et de la LED rouge.
- **Si la tension baisse (Anomalie) :** Le système se met en mode protection. Le relais est immédiatement coupé, la LED rouge s'allume et le buzzer se déclenche pour alerter du problème.

Dans ces actions, il est important de toujours forcer l'état de chaque composant (par exemple : éteindre délibérément le buzzer en cas normal). Sans cela, le buzzer pourrait continuer de sonner même après le retour à la normale de la tension.

## 6. La gestion du Reset d'urgence (Le rôle clé du `return`)
Un bouton de réinitialisation est ajouté pour éteindre l'alarme et relancer la vérification.
L'utilisation du mot-clé `return;` juste après l'appui sur le bouton est primordiale. Cela permet d'interrompre instantanément l'exécution de la boucle `loop()` en cours. Le programme évite ainsi de redéclencher l'alarme immédiatement, et la boucle est forcée de recommencer depuis le début pour effectuer une nouvelle lecture propre.

## 7. Le rôle du Serial Monitor (L'étape Log)
L'utilisation récurrente de `Serial.println()` est indispensable. Le moniteur série sert d'outil principal de débogage. Il permet de voir en temps réel ce que l'ESP32 traite : la tension exacte calculée, l'état des variables internes, et de confirmer visuellement que la logique de décision fonctionne correctement, même avant de brancher les composants matériels (LEDs, relais).
