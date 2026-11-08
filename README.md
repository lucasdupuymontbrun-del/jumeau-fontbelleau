# Jumeau énergétique — Domaine de Fontbelleau

Jumeau numérique énergétique des deux tours du Domaine de Fontbelleau (Lormont) et comparatif général de la tour A1 (conception DCE) et de la tour A2 (variante RE2020 de Veck Construction).

En ligne : https://lucasdupuymontbrun-del.github.io/jumeau-fontbelleau/

Démonstrateur réalisé pour le projet ESCT MP2-BC1-P3. Les consommations sont simulées (première année d'exploitation, octobre 2027 → septembre 2028) ; les logements, les ouvrages et les équipements viennent du DCE et de la maquette Revit `MQT-FONTBELLEAU-G4`.

- Jumeau énergétique (QR code du jumeau) : `index.html` — 129 logements en 3D de nuit, consommations, alertes, comparaison A1 / A2, coût global
- Comparatif général A1 / A2 : `comparatif/` — solutions lot par lot, quantités, coûts par ratios, exploitation et carbone ; classeur Excel et PDF dans `comparatif/docs/`
- Données : `data/energie/` (jumeau), `data/comparatif/` (comparatif), `model/` (maquette 3D, copie de celle du passeport)
- Générateurs : `tools/build_energie.py`, `tools/build_comparatif.py`
- QR code et étiquette : `qr/` (générés par `tools/qr.py`)
- Mise à jour : [`docs/MAINTENANCE.md`](docs/MAINTENANCE.md)

Les fiches des ouvrages (passeports numériques) sont sur le site du passeport, dépôt [`passeport-fontbelleau`](https://github.com/lucasdupuymontbrun-del/passeport-fontbelleau) : https://lucasdupuymontbrun-del.github.io/passeport-fontbelleau/

## Mise en ligne

GitHub : Settings > Pages > Deploy from a branch > `main` / racine. Le site est statique, sans compte ni base de données.

## Licences des composants

three.js et ses modules de post-traitement (MIT, `assets/vendor/`), polices Archivo et Big Shoulders Stencil (SIL Open Font License, `assets/fonts/` et `tools/fonts/`).
