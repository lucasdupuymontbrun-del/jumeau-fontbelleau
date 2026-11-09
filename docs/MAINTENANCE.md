# Jumeau énergétique et comparatif A1 / A2 — guide de mise à jour

## 1. Ce que contient le site

| Partie | Où | D'où ça vient |
|---|---|---|
| Page du jumeau | `index.html`, `assets/js/energie.js`, `assets/js/energie3d.js`, `assets/css/energie.css` | Interface |
| 129 logements (typologie, SHAB, position) | `data/energie/logements.json` | Voiles séparatifs radiaux de la maquette + tableau des surfaces ind. A. Numérotation : A2 d'après les portes « A2 PO R5-Lx », A1 d'après le logement témoin A1.31 |
| Séries journalières (chauffage, eau chaude, eau, électricité) | `data/energie/series.json` | **Fictif** : scénario simulé, calé sur des hypothèses (chauffage A1 36 kWh/m², A2 −12 % avec l'ITE) |
| Sous-stations, ventilation, extracteurs, solaire, alertes, hypothèses de prix | `data/energie/jumeau.json` | Prix et CO₂ : sources publiques citées dans le fichier ; anomalies injectées, détection par règles (R1 à R5) |
| Volet « Énergie » des ouvrages | `data/energie/ouvrages.json` | CCTP 301, 309, 402, 417, 502, étude thermique citée, variante A2 de la maquette. Copié aussi dans le passeport, qui l'affiche dans chaque fiche |
| Maquette 3D | `model/` | Copie de `model/` du passeport (même export Revit) |
| Comparatif | `comparatif/index.html`, `data/comparatif/comparatif.json`, `comparatif/docs/` | `tools/build_comparatif.py` |
| QR code du jumeau | `qr/Jumeau-Energetique.*`, `qr/Etiquette_Jumeau-Energetique.pdf` | `tools/qr.py` ; à refaire seulement si l'adresse du site change |

## 1 bis. Prise en main

La page est organisée en trois questions (onglets du panneau de gauche) : « Tout va bien ? » (logements en vert, orange ou rouge), « Problèmes » (alertes en langage simple, avec ce qu'il faut faire) et « A1 ou A2 ? » (comparaison sur l'année). Un mois se choisit sous la maquette ; le bouton lecture fait défiler l'année jour par jour. Les réglages avancés (compteur affiché, couleur selon la quantité consommée, vue en plan) sont dans « Pour aller plus loin ».

Couleurs : vert jusqu'à +20 % par rapport à des logements semblables, orange de +20 à +30 %, rouge au-delà (même seuil que la règle d'alerte R1). Chauffage : référence recalée (météo, taille, étage, orientation) ; eau et eau chaude : par occupant, comparées à la tour ; électricité : comparée aux logements de la tour qui ont le même nombre d'occupants.

Présentation pour l'oral : bouton « Présentation » en haut à droite, ou adresse `…/jumeau-fontbelleau/?presentation` pour la lancer à l'ouverture. Les textes des étapes sont calculés à partir des données (`tourSteps()` dans `assets/js/energie.js`) ; les textes simples des alertes (`titre_simple`, `resume`, `faire`) sont dans `ALERT_TEXT` de `tools/build_energie.py`.

## 2. Mettre à jour après une modification de la maquette

Les deux générateurs lisent le site du passeport (registre des ouvrages `data/index.json`, fiches `data/o/`, maquette 3D `model/`). Ils cherchent le dépôt `passeport-fontbelleau` à côté de celui-ci ; sinon, donner son chemin en argument ou dans la variable `FONTBELLEAU_PASSEPORT`.

1. Régénérer d'abord le passeport (son guide, § 6 : exports Revit puis `tools/build_passeports.py`).
2. Ici :

```bash
python tools/build_energie.py          # aucune dépendance
pip install openpyxl reportlab
python tools/build_comparatif.py
```

`build_energie.py` écrit `data/energie/` et `model/` de ce site, ainsi que `data/energie/ouvrages.json` et `logements.json` du passeport (volet « Énergie » des fiches) : publier les deux dépôts.

3. Le classeur Excel sort avec ses formules : l'ouvrir et l'enregistrer dans Excel, ou le recalculer avec LibreOffice, pour qu'il affiche les valeurs avant de le diffuser.

## 3. Ventilation de la tour A2 : ventilation hybride hygroréglable B

Choix du groupe du 06/11/2026, à la place de la double flux. Dans la maquette : 9 extracteurs hybrides stato-mécaniques en tête de colonne (famille « VAR A2 - Extracteur hybride stato-mécanique », paramètres « Colonne VMC » et « Débit DCE (m³/h) »), colonnes aux emplacements du DCE, 3 caissons de toiture supprimés.

Le jumeau lit les extracteurs dans le registre du passeport (`A2-VHY-EXT-A` à `I`) et simule pour chacun :

- un débit moyen égal à 55 % du débit DCE de la colonne (modulation hygroréglable) ;
- une assistance mécanique 18 % du temps par grand froid, jusqu'à 95 % par temps chaud (+5 points par °C au-dessus de 8 °C) ;
- 0,10 Wh/m³ en assistance (seuil « basse consommation » de la fiche CEE BAR-TH-155) et 0,12 kWh/j de régulation par extracteur.

Ces valeurs sont en tête de `tools/build_energie.py` (`VHY_MODUL`, `VHY_WH_M3`, `VHY_VEILLE`, `assistance()`). Le scénario contient une panne : l'extracteur de la colonne B reste en assistance forcée du 8 janvier au 1er mars 2028, détectée par la règle R5 (consommation ramenée au débit supérieure à 2,5 fois la médiane des huit autres pendant 7 jours).

## 4. Passer aux vraies données

Remplacer la fonction `simulate()` de `tools/build_energie.py` par la lecture des exports de télé-relève (un fichier par compteur, un relevé par jour) en gardant le même format de sortie ; les règles de détection s'appliquent telles quelles.

Hypothèses à confirmer par l'étude énergétique : gains de la variante A2, fonctionnement de la ventilation hybride, rendement solaire (30 %), évolution des prix. Elles sont modifiables dans la page (bloc « Coût global ») et dans l'en-tête du générateur.

## 5. Comparatif

- **Quantités** : maquette (surfaces, volumes, nombres d'éléments), géométrie (façade, rupteurs, balcons), CCTP pour les équipements non modélisés de la tour A1 (« CCTP, non modélisé »), dénombrement par typologie d'après les plans CVC des logements types (`TYPO` dans le script).
- **Coûts** : budget objectif du dossier (`BUDGET_2020`) actualisé par l'index BT01 (`BT01`), écarts de la variante dans `couts()` (quantité × prix unitaire, source ou « hypothèse »). Les prix unitaires se modifient aussi sur la page et dans le classeur (cellules jaunes).
- **Exploitation et carbone** : repris de `data/energie/jumeau.json` (année 1 simulée), entretien dans `exploitation()`.
- Le jumeau reprend le surcoût total du comparatif comme valeur par défaut du « coût global ».

## 6. Adresses

- Ce site : https://lucasdupuymontbrun-del.github.io/jumeau-fontbelleau/ (comparatif : `comparatif/`)
- Passeports des ouvrages : https://lucasdupuymontbrun-del.github.io/passeport-fontbelleau/
- Les anciennes adresses `passeport-fontbelleau/energie/` et `passeport-fontbelleau/comparatif/` redirigent ici, paramètres compris.
