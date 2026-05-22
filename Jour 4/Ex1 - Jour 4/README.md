# 📌 Jour 4 - Exercice 1 : Afficheur 7 Segments, Potentiomètre, Bouton et LEDs
## Contrôle Interactif et Logique Conditionnelle sur Arduino Uno

Ce dossier contient le projet pratique de l'Exercice 1 du Jour 4 de l'atelier **Physical AI**. Ce projet met en œuvre un afficheur à 7 segments (cathode commune/anode commune avec logique active-basse), un bouton-poussoir pour le décalage (offset), un potentiomètre pour la sélection de chiffres, et deux LEDs (bleue et blanche) pour indiquer la parité du chiffre affiché.

---

## ⚙️ Architecture Système & Fonctionnement

Le système repose sur la logique interactive suivante :
1. **Sélection du chiffre (Potentiomètre)** : La tension du potentiomètre est lue sur la broche analogique **A4** (0-1023) et mappée vers un chiffre de base compris entre **0 et 9**.
2. **Décalage dynamique (Bouton)** : À chaque pression sur le bouton branché sur la broche **4** (utilisant la résistance de tirage interne `INPUT_PULLUP`), un `offset` est incrémenté de +1.
3. **Calcul de l'affichage** : Le chiffre final affiché est déterminé par la formule :  
   $$\text{Chiffre} = (\text{Mappage Potentiomètre} + \text{offset}) \pmod{10}$$
4. **Affichage 7 segments (Logique active-basse)** : Les segments de l'afficheur (pins a à g) sont pilotés selon une table de vérité prédéfinie. L'allumage d'un segment se fait par un état logique **LOW** (0).
5. **Indicateur de Parité (LEDs)** :
   - Si le chiffre affiché est **pair** (0, 2, 4, 6, 8) : la **LED Bleue** s'allume et la LED Blanche s'éteint.
   - Si le chiffre affiché est **impair** (1, 3, 5, 7, 9) : la **LED Blanche** s'allume et la LED Bleue s'éteint.

---

## 🔌 Câblage & Brochage (Pin Mapping)

Le tableau suivant récapitule les connexions physiques avec l'**Arduino Uno** :

| Composant | Broche Arduino Uno | Type de Signal | Description |
| :--- | :--- | :--- | :--- |
| **Bouton Poussoir** | **4** | Entrée Digitale (Pull-Up) | Permet d'ajouter un offset à la valeur affichée |
| **Potentiomètre** | **A4** | Entrée Analogique | Sélectionne la base du chiffre à afficher (0-9) |
| **LED Bleue** | **2** | Sortie Digitale | Allumée si le chiffre affiché est pair |
| **LED Blanche (Light)** | **3** | Sortie Digitale | Allumée si le chiffre affiché est impair |
| **Segment A** | **11** | Sortie Digitale | Segment supérieur |
| **Segment B** | **10** | Sortie Digitale | Segment supérieur droit |
| **Segment C** | **7** | Sortie Digitale | Segment inférieur droit |
| **Segment D** | **9** | Sortie Digitale | Segment inférieur |
| **Segment E** | **8** | Sortie Digitale | Segment inférieur gauche |
| **Segment F** | **13** | Sortie Digitale | Segment supérieur gauche |
| **Segment G** | **12** | Sortie Digitale | Segment central |

---

## 🧠 Logique de l'Afficheur 7 Segments

La table de décodage binaire des chiffres de 0 à 9 dans le tableau `numbers[10][7]` est configurée en **logique active-basse (LOW = segment allumé)**.
Exemple pour le chiffre **0** :
- Segments **a, b, c, d, e, f** = `LOW` (Allumés)
- Segment **g** = `HIGH` (Éteint)
- Représentation dans le code : `{LOW, LOW, LOW, LOW, LOW, LOW, HIGH}`

---

## 🛠️ Compilation & Téléversement

### Prérequis
* **Visual Studio Code** avec l'extension **PlatformIO IDE** installée.

### Instructions
1. Ouvrez le dossier `Ex1 - Jour 4` dans VS Code.
2. Connectez la carte Arduino Uno via le câble USB.
3. Lancez la compilation en cliquant sur l'icône de validation (✓).
4. Téléversez le micrologiciel sur la carte avec l'icône de flèche (→).
5. Tournez le potentiomètre pour faire varier le chiffre affiché et observez le bouton modifier l'offset en temps réel.
