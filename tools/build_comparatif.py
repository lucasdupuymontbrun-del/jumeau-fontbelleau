#!/usr/bin/env python3
"""Comparatif général des tours A1 (conception DCE) et A2 (variante RE2020 du groupe).

Rassemble, pour chaque tour :
  - les solutions lot par lot (CCTP du DCE, maquette, variante modélisée) ;
  - les quantités : maquette pour ce qui est modélisé, CCTP « non modélisé » pour les équipements
    (chauffage, ventilation, ECS) que la maquette ne contient pas, typologies pour le dénombrement ;
  - les coûts de travaux : budget objectif du dossier (2020) actualisé BT01, écarts de la variante par ratios ;
  - l'exploitation et le carbone : année 1 simulée du jumeau énergétique (données fictives).

Sorties :
  data/comparatif/comparatif.json   (lu par la page comparatif/)
  comparatif/docs/Comparatif_A1_A2_Fontbelleau.xlsx  (formules, hypothèses modifiables)
  comparatif/docs/Comparatif_A1_A2_Fontbelleau.pdf   (synthèse imprimable)

Usage : python3 tools/build_comparatif.py [chemin du dépôt passeport-fontbelleau, par défaut à côté de celui-ci]
"""
import collections
import datetime
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from build_energie import load_model, tower_center  # noqa: E402

TODAY = datetime.date.today().isoformat()
OUT_JSON = os.path.join(ROOT, 'data', 'comparatif', 'comparatif.json')
PASSEPORT = os.environ.get('FONTBELLEAU_PASSEPORT') or (sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(ROOT), 'passeport-fontbelleau'))
OUT_DIR = os.path.join(ROOT, 'comparatif', 'docs')
BASE_NAME = 'Comparatif_A1_A2_Fontbelleau'

# ------------------------------------------------------------------ sources
SOURCES = {
    'maquette': {'titre': 'Maquette MQT-FONTBELLEAU-G4 (export Revit, passeports numériques)', 'ref': 'Surfaces, volumes, dimensions et nombres d\'éléments'},
    'cctp301': {'titre': 'CCTP lot 301 Gros œuvre, ind. B', 'ref': '§6.7.10 rupteurs de ponts thermiques'},
    'cctp309': {'titre': 'CCTP lot 309 Isolation flocage, ind. 0', 'ref': 'Flocage PH RDC et PH R-1'},
    'cctp402': {'titre': 'CCTP lot 402 Étanchéité, ind. B', 'ref': '§3.2.2 isolant PU 120, R ≥ 5,40'},
    'cctp417': {'titre': 'CCTP lot 417 Menuiseries extérieures PVC, ind. A', 'ref': 'Double vitrage 4/16/4 ITR ; Uw renvoyé à l\'étude thermique'},
    'cctp502': {'titre': 'CCTP lots 502-503-504 CVC plomberie, ind. B (mars 2021)', 'ref': '§3.2.2 surpresseurs, §3.4 ECS, §4.4 ventilation, §5.3 sous-station, §5.5 MTA, §5.6 émission'},
    'cvc_cellules': {'titre': 'Plans CVC 03.02.01.04.06 — logements types, ind. B (fév. 2021)', 'ref': 'Pièces, émetteurs, bouches et entrées d\'air par typologie'},
    'surfaces': {'titre': 'Tableau des surfaces et typologies (repris dans le jumeau énergétique)', 'ref': 'A1 : 70 logements, A2 : 59 logements'},
    'budget': {'titre': 'BUDGET.xlsx, onglet 2020.04.23 (dossier PE)', 'ref': 'Objectif par lot ; la colonne « tour A1 » vaut 50 % de chaque poste'},
    'etude': {'titre': 'Étude thermique RT 2012 (Home Inclusiv), citée par la présentation synthétique du DCE', 'ref': 'Pièce non jointe au dossier'},
    'var': {'titre': 'Variante RE2020 du groupe, modélisée dans la maquette (tour A2)', 'ref': 'Hors pièces du marché'},
    'choix_vhy': {'titre': 'Choix du groupe du 06/11/2026 : ventilation hybride hygroréglable B', 'ref': 'Remplace la double flux. Colonnes aux emplacements du DCE, 3 caissons de toiture supprimés, un extracteur hybride par sortie (maquette mise à jour)'},
    'vhy_maquette': {'titre': 'Maquette MQT-FONTBELLEAU-G4, système « VMC hybride hygro B A2 - Extraction »', 'ref': '9 extracteurs (paramètres « Colonne VMC » et « Débit DCE »), 13 colonnes d\'étage, 105 traversées de dalle et 9 en toiture relevées'},
    'vhy_cee': {'titre': 'Fiche CEE BAR-TH-155, ventilation hybride hygroréglable (ADEME)', 'ref': 'Type B : bouches et entrées d\'air hygroréglables, sous Avis Technique ; extracteur « basse consommation » si puissance spécifique ≤ 0,1 Wh/m³', 'url': 'https://calculateur-cee.ademe.fr/pdf/display/300/BAR-TH-155'},
    'vhy_guide': {'titre': 'Guide de la ventilation naturelle et hybride « VNHy », habitat collectif et individuel (ADEME, DHUP, USH, 2010)', 'ref': 'Conception, dimensionnement, mise en œuvre et maintenance', 'url': 'https://www.envirobat-oc.fr/IMG/pdf/guide_de_la_ventilation_naturelle_et_hybride_vnhy_avems.pdf'},
    'jumeau': {'titre': 'Jumeau énergétique Fontbelleau — année 1 simulée (oct. 2027 – sept. 2028)', 'ref': 'Données fictives, hypothèses documentées sur la page Méthode', 'url': 'https://lucasdupuymontbrun-del.github.io/jumeau-fontbelleau/#methode'},
    'bt01': {'titre': 'Index BT01 tous corps d\'état (Insee), relevé ANIL', 'ref': 'Avril 2020 : 111,5 ; août 2026 : 139,4', 'url': 'https://www.anil.org/outils/indices-et-plafonds/indice-bt-01'},
    'ite_prix': {'titre': 'Construires.fr — coût d\'une ITE en 2026', 'ref': 'PSE graphité sous enduit : 100 à 150 €/m² TTC posé, + 15 à 25 % de frais annexes (échafaudage)', 'url': 'https://www.construires.fr/isolation-thermique-exterieure/'},
    'solaire_prix': {'titre': 'TECSOL, colloque solaire thermique collectif (2013)', 'ref': 'Eau chaude solaire collective < 50 m² : ≈ 1 200 €/m² (travaux + ingénierie)', 'url': 'https://media.xpair.com/pdf/energies-renouvelables/solaire-thermique-collectif-TECSOL.pdf'},
    'tv_prix': {'titre': 'Meuse Grand Sud, fiche pluvial « toiture végétalisée » (valeur 2019)', 'ref': 'Végétalisation extensive hors porteur et étanchéité : 40 à 70 € HT/m²', 'url': 'https://www.meusegrandsud.fr/fileadmin/user_upload/mediatheque/agglo/Eaux_Pluviales/PLUVIAL_toiture_vegetalisee_FT.pdf'},
    'prix_chaleur': {'titre': 'Réseau des Hauts de Garonne (3324C), dossier de classement, Bordeaux Métropole (déc. 2024)', 'ref': 'Prix moyen 2023 : 96,72 € TTC/MWh'},
    'prix_elec': {'titre': 'Tarif réglementé de l\'électricité, option Base 6 kVA (août 2026)', 'ref': '0,2001 € TTC/kWh'},
    'co2_chaleur': {'titre': 'Arrêté du 11 avril 2025 (contenus CO₂ des réseaux, année 2023)', 'ref': 'Réseau 3324C : 0,034 kgCO₂e/kWh (ACV). Mise à jour par arrêté du 30 mars 2026 : à reprendre'},
}

SOURCES.update({
    'miqcp': {'titre': 'MIQCP, guide de négociation des rémunérations de maîtrise d\'œuvre (actualisation 2019)', 'ref': 'Honoraires exprimés en pourcentage du montant HT des travaux, selon la complexité de l\'opération', 'url': 'https://www.marche-public.fr/contrats-publics/MIQCP-guide-negociation-2019.htm'},
    'cee_bar155': {'titre': 'Fiche CEE BAR-TH-155, ventilation hybride hygroréglable', 'ref': 'Secteur d\'application : appartements existants. Durée de vie conventionnelle : 17 ans', 'url': 'https://calculateur-cee.ademe.fr/pdf/display/300/BAR-TH-155'},
    'cee_bar127': {'titre': 'Fiche CEE BAR-TH-127, VMC simple flux hygroréglable', 'ref': 'Durée de vie conventionnelle : 17 ans', 'url': 'https://calculateur-cee.ademe.fr/pdf/display/299/BAR-TH-127'},
    'ademe_solaire': {'titre': 'ADEME, guide « Adopter le solaire thermique »', 'ref': 'Capteurs plans 20 à 30 ans, ballon 15 à 20 ans, circulateur, sondes et régulation environ 10 ans', 'url': 'https://librairie.ademe.fr/ged/7736/guide-adopter-solaire-thermique.pdf'},
    'fonds_chaleur': {'titre': 'ADEME, Fonds Chaleur : installation de production d\'eau chaude solaire thermique (2026)', 'ref': 'Logements collectifs éligibles ; dépôt de nouvelles demandes suspendu, aide close le 4 novembre 2026', 'url': 'https://agirpourlatransition.ademe.fr/entreprises/aides-financieres/catalogue/2026/installation-de-production-deau-chaude-solaire-thermique'},
    'fonds_chaleur_cond': {'titre': 'ADEME, conditions d\'éligibilité et de financement, solaire thermique eau chaude sanitaire (2024)', 'ref': 'Aide forfaitaire à partir de 25 m² de capteurs en métropole', 'url': 'https://agir.ademe.fr/sites/default/files/Conditions%20%C3%A9ligibilit%C3%A9%20et%20financement%20-%20Solaire%20thermique%20eau%20chaude%20sanitaire%20-%202024.pdf'},
    'tfpb': {'titre': 'CGI art. 1384 A ; décret n° 2023-560 du 3 juillet 2023 (synthèse Cerqual Qualitel Certification)', 'ref': 'Logement locatif social neuf : exonération de 25 ans si la décision de financement est prise avant le 31/12/2026, 30 ans si les critères de performance sont aussi remplis (permis 2025-2027 : Ic construction ≤ 580 et Ic énergie ≤ 260 kgCO₂e/m², certification NF Habitat)', 'url': 'https://qualitel.org/professionnels/uploads/Complement_Exo_TFPB_MAJ_RE2020_Juin_2023_QC4_VDEF.pdf'},
    'tfpb_montant': {'titre': 'Fipeco, note sur les taxes foncières', 'ref': 'Taxe foncière moyenne des logements : environ 12,5 € par m² de surface, avec de forts écarts entre communes', 'url': 'https://fipeco.fr/pdf/Taxes%20fonci%C3%A8res.pdf'},
    'tva_lls': {'titre': 'TVA des logements locatifs sociaux neufs (CGI art. 278 sexies), amendements au PLF 2026', 'ref': '5,5 % en PLAI ou en PLUS dans le cadre du NPNRU ; 10 % pour les autres PLUS et les PLS. Retour à 5,5 % pour tous : amendements rejetés', 'url': 'https://www.assemblee-nationale.fr/dyn/17/amendements/1906A/AN/1907.pdf'},
    'demolition': {'titre': 'La Maison Saint-Gobain, budget des travaux de démolition', 'ref': 'Évacuation des gravats seule : 30 à 70 €/m³', 'url': 'https://www.lamaisonsaintgobain.fr/guides-travaux/questions-travaux/quel-budget-prevoir-pour-les-travaux-de-demolition'},
})

FIAB = {
    'maquette': 'Maquette',
    'cctp': 'CCTP',
    'cctp_nm': 'CCTP, non modélisé',
    'variante': 'Variante (maquette)',
    'calcul': 'Calcul',
    'estime': 'Estimé',
    'cite': 'Prix publié',
    'hypothese': 'Hypothèse',
    'budget': 'Budget du dossier',
    'simule': 'Simulé (jumeau)',
    'decision': 'Choix du groupe',
}

# ------------------------------------------------------------------ typologies (plans CVC cellules types)
# pièces : principales (séjour + chambres), pièces d'eau (salle de bains / salle d'eau), bouches d'extraction
TYPO = {
    'T2':  {'pp': 2, 'eau': 1, 'bouches': 3, 'pieces': 'séjour, 1 chambre, salle d\'eau, WC, cuisine'},
    'T3A': {'pp': 3, 'eau': 1, 'bouches': 3, 'pieces': 'séjour, 2 chambres, salle de bains, WC, cuisine'},
    'T3B': {'pp': 3, 'eau': 1, 'bouches': 4, 'pieces': 'séjour, 2 chambres, salle de bains, WC, cuisine, buanderie'},
    'T4':  {'pp': 4, 'eau': 2, 'bouches': 5, 'pieces': 'séjour, 3 chambres, salle de bains, salle d\'eau, WC, cuisine, buanderie'},
}

# ------------------------------------------------------------------ coûts : paramètres et ratios (modifiables)
BT01 = {'base': 111.5, 'base_mois': 'avril 2020', 'actuel': 139.4, 'actuel_mois': 'août 2026'}

BUDGET_2020 = [  # (code, intitulé, objectif deux tours en € HT 2020) — BUDGET.xlsx
    ('801', 'VRD (300B)', 360039), ('807', 'Espaces verts (300C)', 109274), ('301', 'Gros œuvre', 6000000),
    ('309', 'Isolation flocage', 89771), ('402', 'Étanchéité', 339805), ('417', 'Menuiseries extérieures PVC', 306699),
    ('416', 'Menuiseries extérieures alu', 95484), ('422', 'Occultations', 97900), ('502', 'Plomberie, CVC (502-503-504)', 1270567),
    ('510', 'Électricité', 724000), ('522', 'Ascenseurs', 133016), ('602', 'Cloisons, doublages', 476339),
    ('603', 'Menuiserie intérieure', 290829), ('609', 'Carrelage', 422700), ('610', 'Sols souples', 171143),
    ('616', 'Peinture', 460927), ('616F', 'Peinture — façades', 137152), ('620', 'Métallerie', 1605385),
    ('621', 'Porte de garage', 19421), ('ITE', 'Façade ITE (lot créé par la variante)', 0),
]


def r1(x):
    return round(x, 1)


def num(s):
    return float(s.replace(' ', '').replace('\xa0', '').replace(' ', '').replace(',', '.'))


# ------------------------------------------------------------------ lecture des ouvrages
def load_rows():
    idx = json.load(open(os.path.join(PASSEPORT, 'data', 'index.json'), encoding='utf-8'))
    rows = []
    for o in idx['ouvrages']:
        ref, reference, des, zone, etage, fam, statut, revit = o[:8]   # colonnes suivantes : dates 4D (passeport)
        j = json.load(open(os.path.join(PASSEPORT, 'data', 'o', ref + '.json'), encoding='utf-8'))
        idd = {it['cle']: it for it in j['identite'] if isinstance(it, dict)}
        sv = (idd.get('surface_volume') or {}).get('valeur') or ''
        S = V = None
        m = re.search(r'([\d\s ,]+)\s*m²', sv)
        if m:
            S = num(m.group(1))
        m = re.search(r'([\d\s ,]+)\s*m³', sv)
        if m:
            V = num(m.group(1))
        rows.append({'ref': ref, 'zone': zone, 'etage': etage, 'fam': fam, 'des': des, 'S': S or 0.0, 'V': V or 0.0})
    return rows


def fondations_par_tour(els):
    """Affecte chaque élément de fondation à une tour (rayon 15 m autour du centre) ou au parking."""
    c = {z: tower_center(els, z) for z in ('A1', 'A2')}
    out = {}
    for e in els:
        if e['meta'].get('zone') != 'FOND':
            continue
        P = e['pts']
        mx = sum(p[0] for p in P) / len(P)
        my = sum(p[1] for p in P) / len(P)
        t = 'PARK'
        for z in ('A1', 'A2'):
            if math.hypot(mx - c[z][0], my - c[z][1]) < 15:
                t = z
        out[e['ref']] = t
    return out


def balcons_fronts(els):
    """Longueur de liaison balcon / plancher par tour et par étage (arc au bord de dalle)."""
    res = {}
    for z in ('A1', 'A2'):
        c = tower_center(els, z)
        per = collections.Counter()
        for e in els:
            m = e['meta']
            if m.get('zone') != z or m.get('famille') != 'dalle' or 'balcon' not in m.get('designation', '').lower():
                continue
            P = e['pts']
            r = [math.hypot(p[0] - c[0], p[1] - c[1]) for p in P]
            a = [math.degrees(math.atan2(p[1] - c[1], p[0] - c[0])) for p in P]
            da = [((x - a[0] + 180) % 360) - 180 for x in a]
            per[m.get('etage')] += math.radians(max(da) - min(da)) * min(r)
        res[z] = per
    return res


# ------------------------------------------------------------------ quantités
def quantites(rows, fond, fronts, logs):
    def agg(z, pred):
        n = s = v = 0
        for r in rows:
            if r['zone'] == z and pred(r):
                n += 1
                s += r['S']
                v += r['V']
        return n, s, v

    def both(pred):
        return {z: agg(z, pred) for z in ('A1', 'A2')}

    typ = {z: collections.Counter() for z in ('A1', 'A2')}
    for l in logs:
        typ[l['tour']][l['typo']] += 1

    def per_typo(z, key):
        return sum(n * TYPO[t][key] for t, n in typ[z].items())

    def rad(z):
        return sum(n * (TYPO[t]['pp'] + TYPO[t]['eau']) for t, n in typ[z].items())

    def eau(z):
        return sum(n * TYPO[t]['eau'] for t, n in typ[z].items())

    Q = []

    def add(groupe, item, unite, a1, a2, f1, f2, note='', src=None, dec=0):
        Q.append({'groupe': groupe, 'item': item, 'unite': unite, 'A1': None if a1 is None else round(a1, dec),
                  'A2': None if a2 is None else round(a2, dec), 'f1': f1, 'f2': f2, 'note': note, 'src': src or []})

    # ---- structure (maquette)
    G = 'Structure'
    voile = both(lambda r: r['fam'] == 'voile')
    prem = both(lambda r: r['fam'] == 'premur')
    dal = both(lambda r: r['fam'] == 'dalle' and 'balcon' not in r['des'].lower())
    bal = both(lambda r: r['fam'] == 'dalle' and 'balcon' in r['des'].lower())
    pot = both(lambda r: r['fam'] == 'poteau')
    pou = both(lambda r: r['fam'] == 'poutre')
    esc = both(lambda r: r['fam'] == 'escalier')
    add(G, 'Voiles et poutres-voiles béton armé', 'm³', voile['A1'][2], voile['A2'][2], 'maquette', 'maquette', f"{voile['A1'][0]} / {voile['A2'][0]} éléments", ['maquette'], 1)
    add(G, 'Prémurs (noyau, gaines)', 'm³', prem['A1'][2], prem['A2'][2], 'maquette', 'maquette', '', ['maquette'], 1)
    add(G, 'Dalles hautes (RDC à R+9)', 'm²', dal['A1'][1], dal['A2'][1], 'maquette', 'maquette', 'Planchers identiques : 22 cm courant, 25 cm au PH RDC', ['maquette'], 0)
    add(G, 'Dalles hautes — béton', 'm³', dal['A1'][2], dal['A2'][2], 'maquette', 'maquette', '', ['maquette'], 1)
    add(G, 'Dalles de balcon', 'u', bal['A1'][0], bal['A2'][0], 'maquette', 'maquette', f"{bal['A1'][1]:.0f} m² / {bal['A2'][1]:.0f} m²", ['maquette'])
    add(G, 'Poteaux béton armé', 'm³', pot['A1'][2], pot['A2'][2], 'maquette', 'maquette', f"{pot['A1'][0]} / {pot['A2'][0]} poteaux", ['maquette'], 1)
    add(G, 'Poutres et linteaux', 'm³', pou['A1'][2], pou['A2'][2], 'maquette', 'maquette', f"{pou['A1'][0]} / {pou['A2'][0]} éléments", ['maquette'], 1)
    add(G, 'Escaliers coulés en place', 'u', esc['A1'][0], esc['A2'][0], 'maquette', 'maquette', '', ['maquette'])

    # ---- fondations (maquette, réparties par position)
    G = 'Fondations sous tour'
    fq = {z: collections.defaultdict(lambda: [0, 0.0]) for z in ('A1', 'A2')}
    bc = {'A1': 0.0, 'A2': 0.0}
    for r in rows:
        if r['zone'] != 'FOND':
            continue
        t = fond.get(r['ref'])
        if t not in ('A1', 'A2'):
            continue
        des = r['des']
        k = 'Pieux' if des.startswith('Pieu') else 'Casques' if des.startswith('Casque') else 'Longrines' if des.startswith('Longrine') else 'Voiles enterrés'
        fq[t][k][0] += 1
        fq[t][k][1] += r['V']
        if 'bas carbone' in des:
            bc[t] += r['V']
    for k in ('Pieux', 'Casques', 'Longrines', 'Voiles enterrés'):
        add(G, k, 'm³', fq['A1'][k][1], fq['A2'][k][1], 'maquette', 'maquette', f"{fq['A1'][k][0]} / {fq['A2'][k][0]} éléments", ['maquette'], 1)
    add(G, 'dont béton bas carbone', 'm³', 0, bc['A2'], 'cctp', 'variante', 'Pieux, casques et longrines de la tour A2', ['var'], 1)

    # ---- enveloppe
    G = 'Enveloppe'
    ite = both(lambda r: r['fam'] == 'ite')
    mens = {}
    for z in ('A1', 'A2'):
        c = collections.Counter()
        for r in rows:
            if r['zone'] == z and r['fam'] == 'menuiserie_ext':
                d = r['des']
                k = 'fe' if '125x125' in d else 'pf180' if '180x215' in d else 'pf310' if '310x215' in d else 'mr' if 'rideau' in d.lower() else 'porte'
                c[k] += 1
        mens[z] = c
    baies = {z: mens[z]['fe'] * 1.25 * 1.25 + mens[z]['pf180'] * 1.80 * 2.15 + mens[z]['pf310'] * 3.10 * 2.15 for z in ('A1', 'A2')}
    # façade brute R+1 → acrotère : géométrie des 9 travées d'ITE modélisées sur A2 (9,10 m × 25,87 m), tours identiques
    brute = 9 * 9.10 * 25.87
    opaque = {z: brute - baies[z] for z in ('A1', 'A2')}
    add(G, 'Façade R+1 → acrotère, brute', 'm²', brute, brute, 'calcul', 'calcul', '9 travées de 9,10 m × 25,87 m (géométrie des tours identique)', ['maquette'])
    add(G, 'Fenêtres PVC 125 × 125', 'u', mens['A1']['fe'], mens['A2']['fe'], 'maquette', 'variante', 'A2 : coffre de volet roulant isolé et étanche', ['maquette', 'var'])
    add(G, 'Portes-fenêtres 180 × 215 + fixe', 'u', mens['A1']['pf180'], mens['A2']['pf180'], 'maquette', 'maquette', '', ['maquette'])
    add(G, 'Portes-fenêtres 310 × 215 + fixe', 'u', mens['A1']['pf310'], mens['A2']['pf310'], 'maquette', 'maquette', '', ['maquette'])
    add(G, 'Surface de baies (cotes nominales)', 'm²', baies['A1'], baies['A2'], 'calcul', 'calcul', 'Nombre × dimensions nominales', ['maquette'])
    add(G, 'Façade opaque des logements', 'm²', opaque['A1'], ite['A2'][1], 'calcul', 'maquette', f"A2 : surface des 9 éléments d'ITE (calcul : {opaque['A2']:.0f} m²)", ['maquette'])
    add(G, 'Doublage intérieur PSE graphité 13+100', 'm²', opaque['A1'], 0, 'calcul', 'variante', 'Remplacé par l\'ITE sur A2', ['etude', 'var'])
    add(G, 'ITE PSE graphité 140 mm sous enduit mince', 'm²', 0, ite['A2'][1], 'cctp', 'variante', 'Knauf XTherm ITEx Sun+, λ 0,031', ['var'])
    roof = [r for r in rows if r['zone'] == 'A1' and r['fam'] == 'dalle' and r['etage'] == 'R+9' and r['S'] > 100]
    tv = [r for r in rows if r['zone'] == 'A2' and r['fam'] == 'toiture']
    add(G, 'Toiture-terrasse PU 120 + gravillons', 'm²', roof[0]['S'] if roof else None, 0, 'calcul', 'variante', 'A1 : surface du plancher haut R+9', ['cctp402', 'maquette'])
    add(G, 'Toiture végétalisée extensive sur PU 120', 'm²', 0, tv[0]['S'] if tv else None, 'cctp', 'variante', 'Substrat 8 cm, sédums', ['var'])
    # rupteurs : nez de plancher R+2 à R+9 (8 planchers), hors balcons
    per = 2 * math.pi * 12.97
    rupt = {}
    for z in ('A1', 'A2'):
        fr = sum(v for k, v in fronts[z].items() if k != 'RDC')
        rupt[z] = 8 * per - fr
    add(G, 'Rupteurs de pont thermique (nez de plancher)', 'ml', rupt['A1'], rupt['A2'], 'calcul', 'calcul', 'Périmètre de dalle 81,5 m × 8 planchers, liaisons de balcon déduites (CCTP 301 : sauf balcons)', ['cctp301', 'maquette'])
    fr_all = {z: sum(v for k, v in fronts[z].items() if k != 'RDC') for z in ('A1', 'A2')}
    add(G, 'Liaisons balcon / plancher sans rupteur', 'ml', fr_all['A1'], fr_all['A2'], 'calcul', 'calcul', 'Ponts thermiques non traités', ['cctp301', 'maquette'])
    eca = both(lambda r: r['fam'] == 'ecaille')
    gc = both(lambda r: r['fam'] == 'garde_corps')
    add(G, 'Écailles de façade (tôle et verre)', 'u', eca['A1'][0], eca['A2'][0], 'maquette', 'maquette', '', ['maquette'])
    add(G, 'Garde-corps vitrés', 'u', gc['A1'][0], gc['A2'][0], 'maquette', 'maquette', '', ['maquette'])

    # ---- logements
    G = 'Logements'
    shab = {z: sum(l['shab'] for l in logs if l['tour'] == z) for z in ('A1', 'A2')}
    add(G, 'Logements', 'u', sum(typ['A1'].values()), sum(typ['A2'].values()), 'cctp', 'cctp', ', '.join(f"{t} {typ['A1'][t]}/{typ['A2'][t]}" for t in ('T2', 'T3A', 'T3B', 'T4')), ['surfaces'])
    add(G, 'Surface habitable', 'm²', shab['A1'], shab['A2'], 'cctp', 'cctp', '', ['surfaces'])
    add(G, 'Pièces principales', 'u', per_typo('A1', 'pp'), per_typo('A2', 'pp'), 'estime', 'estime', 'Séjours + chambres, par typologie', ['cvc_cellules'])

    # ---- chauffage et ECS (A1 : CCTP non modélisé ; A2 : CCTP + variante)
    G = 'Chauffage et eau chaude'
    n1, n2 = sum(typ['A1'].values()), sum(typ['A2'].values())
    add(G, 'Sous-station secondaire (ballon tampon ≥ 1 000 L, 2 groupes de 2 pompes doubles, vase, pot de décantation, compteurs de calories)', 'u', 1, 1, 'cctp_nm', 'cctp_nm', 'Raccordée à la sous-station primaire RCU du parking, commune aux deux tours', ['cctp502'])
    add(G, 'Surpresseur eau froide KSB Hya-Solo DV, 9,58 m³/h', 'u', 1, 1, 'cctp_nm', 'cctp_nm', '', ['cctp502'])
    add(G, 'Modules thermiques d\'appartement Uponor Combi Port', 'u', n1, n2, 'cctp_nm', 'cctp_nm', '1 par logement : ECS instantanée, comptage, distribution du chauffage', ['cctp502'])
    add(G, 'Thermostats d\'ambiance programmables', 'u', n1, n2, 'cctp_nm', 'cctp_nm', 'Vanne deux voies sur le retour chauffage', ['cctp502'])
    add(G, 'Radiateurs acier HM Classic Easy M', 'u', rad('A1'), rad('A2') - eau('A2'), 'estime', 'estime', '1 par pièce principale + 1 par pièce d\'eau (A1 : panneau aussi en salle d\'eau)', ['cctp502', 'cvc_cellules'])
    add(G, 'Sèche-serviettes eau chaude Atlantic Corsaire', 'u', 0, eau('A2'), 'cctp', 'estime', 'Prestation CDC uniquement', ['cctp502', 'cvc_cellules'])
    add(G, 'Compteurs d\'énergie chauffage + ECS télé-relevés', 'u', n1, n2, 'cctp_nm', 'cctp_nm', 'A1 (COGEDIM) : en option au CCTP ; A2 (CDC) : en base', ['cctp502'])
    add(G, 'Compteurs d\'eau froide télé-relevés', 'u', n1, n2, 'cctp_nm', 'cctp_nm', 'En gaine palière', ['cctp502'])
    sol = [r for r in rows if r['zone'] == 'A2' and r['fam'] == 'cvc' and 'Capteur' in r['des']]
    add(G, 'Capteurs solaires thermiques 2,5 m² (inclinés 30°)', 'u', 0, len(sol), 'cctp', 'variante', f"{len(sol) * 2.5:.0f} m² en toiture", ['var'])
    add(G, 'Ballon solaire 1 500 L + station solaire', 'u', 0, 1, 'cctp', 'estime', 'Ballon modélisé ; station (pompe, échangeur, régulation) estimée', ['var'])

    # ---- ventilation
    G = 'Ventilation'
    vhy = [r for r in rows if r['zone'] == 'A2' and r['ref'].startswith('A2-VHY-EXT-')]
    deb_vhy = sum(int(re.search(r'\(([\d ]+) m³/h\)', r['des']).group(1).replace(' ', '')) for r in vhy)
    add(G, 'Caissons d\'extraction VMC hygro B Atlantic Airvent PA', 'u', 3, 0, 'cctp_nm', 'variante', 'A1 : 4 390 + 4 280 + 4 065 m³/h. Base DCE de A2 : 4 095 + 3 315 + 3 280 m³/h, remplacés par les extracteurs hybrides', ['cctp502'])
    add(G, 'Extracteurs hybrides stato-mécaniques en tête de colonne', 'u', 0, len(vhy), 'cctp', 'variante', 'Ø400 à Ø560, débouché 1,40 m au-dessus de la toiture finie ; 13 colonnes d\'étage regroupées en 9 sorties', ['vhy_maquette', 'choix_vhy'])
    add(G, 'Débit d\'extraction installé', 'm³/h', 4390 + 4280 + 4065, deb_vhy, 'cctp_nm', 'variante', 'A2 : somme des débits DCE des colonnes, repris sur les extracteurs de la maquette', ['cctp502', 'vhy_maquette'])
    add(G, 'Entrées d\'air hygroréglables acoustiques EH 5/45', 'u', per_typo('A1', 'pp'), per_typo('A2', 'pp'), 'estime', 'estime', '1 par pièce principale (tableau CCTP §4.4.5), dans les deux tours', ['cctp502', 'cvc_cellules'])
    add(G, 'Bouches d\'extraction (cuisine, bains, WC, buanderie)', 'u', per_typo('A1', 'bouches'), per_typo('A2', 'bouches'), 'estime', 'estime', 'Hygroréglables BH / BHC / BAWC en A1 ; hygroréglables basse pression du système hybride en A2', ['cctp502', 'cvc_cellules'])
    add(G, 'Extracteur de gaine, local ménage', 'u', 0, 1, 'cctp', 'cctp_nm', 'Tour A2 uniquement (CCTP §4.4.3)', ['cctp502'])
    return Q, {'opaque_A1': opaque['A1'], 'ite_A2': ite['A2'][1], 'tv_A2': tv[0]['S'] if tv else 0, 'roof_A1': roof[0]['S'] if roof else 0,
               'bc_A2': bc['A2'], 'fe_A2': mens['A2']['fe'], 'sol_m2': len(sol) * 2.5, 'n1': n1, 'n2': n2, 'shab': shab,
               'typ': {z: dict(typ[z]) for z in typ}, 'rupt_A2': rupt['A2'], 'fronts_A2': fr_all['A2'],
               'vhy_n': len(vhy), 'vhy_ml': round(13 * (70.20 - 43.47)), 'vhy_bouches': per_typo('A2', 'bouches'), 'vhy_tremies': 105 + 9}


# ------------------------------------------------------------------ solutions lot par lot
def lots(k):
    L = [
        ('301', 'Gros œuvre', [
            ('Structure', 'Voiles BA 20 cm, dalles 22 cm, noyau en prémurs', 'Identique', 'identique', ['maquette']),
            ('Fondations', 'Pieux, casques et longrines en béton courant', f"Béton bas carbone sur pieux, casques et longrines ({k['bc_A2']:.0f} m³)", 'modifie', ['maquette', 'var']),
            ('Ponts thermiques', 'Rupteurs Schöck Rutherma en nez de plancher, R+2 à R+9, sauf balcons', 'Identique au DCE (redondants avec l\'ITE : à arbitrer)', 'identique', ['cctp301']),
        ]),
        ('309', 'Isolation flocage', [
            ('Planchers sur locaux non chauffés', 'PH RDC 24 cm, R 6,3 ; PH R-1 14 cm, R 3,7', 'Identique', 'identique', ['cctp309']),
        ]),
        ('ITE', 'Façade ITE (pas de lot au DCE)', [
            ('Isolation des murs par l\'extérieur', '—', f"PSE graphité 140 mm, λ 0,031, sous enduit mince ({k['ite_A2']:.0f} m²). U ≈ 0,21 W/m².K", 'ajoute', ['var']),
        ]),
        ('602', 'Cloisons, doublages (CCTP absent)', [
            ('Isolation des murs par l\'intérieur', f"Doublage collé PSE graphité 13+100 ({k['opaque_A1']:.0f} m²). Paroi U 0,27 W/m².K", 'Supprimé en façade : voiles préparés pour peinture', 'supprime', ['etude', 'var']),
        ]),
        ('402', 'Étanchéité', [
            ('Toiture-terrasse', 'PU 120 mm (Efigreen Duo), R ≥ 5,40, protection gravillons 4 cm', 'PU 120 mm, R 5,45, végétalisation extensive 8 cm (sédums)', 'modifie', ['cctp402', 'var']),
        ]),
        ('417', 'Menuiseries extérieures PVC', [
            ('Fenêtres', 'PVC double vitrage 4/16/4 ITR, coffre de volet roulant, entrée d\'air hygroréglable', 'Même menuiserie, coffre isolé et étanche, entrée d\'air hygroréglable conservée', 'modifie', ['cctp417', 'var']),
            ('Performance', 'Uw non disponible (renvoyé à l\'étude thermique absente)', 'Uw non disponible', 'identique', ['cctp417']),
        ]),
        ('502', 'Chauffage, eau chaude', [
            ('Production', 'Sous-station RCU, ballon tampon, MTA Uponor Combi Port par logement', 'Identique', 'identique', ['cctp502']),
            ('Émission', 'Radiateurs acier HM Classic Easy M + robinets thermostatiques', 'Radiateurs + sèche-serviettes eau chaude en salle de bains (prestation CDC)', 'modifie', ['cctp502']),
            ('Comptage individuel', 'Compteurs d\'énergie chauffage et ECS en option', 'En base', 'modifie', ['cctp502']),
            ('Eau chaude solaire', '—', f"{k['sol_m2']:.0f} m² de capteurs plans, ballon solaire 1 500 L (préchauffage)", 'ajoute', ['var']),
        ]),
        ('503', 'Ventilation', [
            ('Système', 'VMC simple flux hygroréglable B, 3 caissons Airvent PA en toiture (12 735 m³/h)', 'Ventilation hybride hygroréglable B : tirage naturel, 9 extracteurs stato-mécaniques en tête de colonne pour l\'assister (10 690 m³/h au DCE)', 'modifie', ['cctp502', 'choix_vhy', 'vhy_guide']),
            ('Conduits', 'Colonnes raccordées aux caissons par des réseaux horizontaux en toiture', 'Colonnes élargies (Ø355 à Ø560), rectilignes jusqu\'à la toiture, sans réseau horizontal', 'modifie', ['vhy_maquette']),
            ('Amenées d\'air', 'Entrées d\'air EH 5/45 dans les menuiseries', 'Identique : entrées d\'air hygroréglables EH 5/45', 'identique', ['cctp502', 'vhy_maquette']),
        ]),
        ('504', 'Plomberie, sanitaires', [
            ('Équipements', 'Prestation COGEDIM : évier à poser, meuble vasque', 'Prestation CDC : kitchenette complète, pare-douche', 'programme', ['cctp502']),
        ]),
        ('620', 'Métallerie (CCTP absent)', [
            ('Façade', 'Écailles tôle et verre, garde-corps vitrés verts', 'Identique', 'identique', ['maquette']),
        ]),
    ]
    out = []
    for code, nom, lignes in L:
        out.append({'lot': code, 'nom': nom, 'lignes': [{'theme': t, 'A1': a, 'A2': b, 'ecart': e, 'src': s} for t, a, b, e, s in lignes]})
    return out


# ------------------------------------------------------------------ coûts
def couts(k):
    coef = BT01['actuel'] / BT01['base']
    postes = [
        # id, lot, poste, qte, unité, PU € HT, fiab, src, note, (min, max)
        ('bc', '301', 'Béton bas carbone sur fondations', k['bc_A2'], 'm³', 12, 'hypothese', [], 'Surcoût par m³ à confirmer avec le fournisseur (FDES BETie)', (5, 25)),
        ('ite', 'ITE', 'ITE PSE graphité 140 mm sous enduit, échafaudage compris', k['ite_A2'], 'm²', 125, 'cite', ['ite_prix'], '100 à 150 €/m² TTC publiés (maison) ; ramené HT et majoré pour l\'échafaudage d\'une tour de 28 m', (100, 160)),
        ('dbl', '602', 'Doublage PSE 13+100 supprimé en façade', k['ite_A2'], 'm²', -38, 'hypothese', [], 'Fourniture et pose d\'un doublage collé', (-45, -30)),
        ('prep', '602', 'Préparation des voiles pour peinture directe', k['ite_A2'], 'm²', 8, 'hypothese', [], 'Ragréage et enduit de surfaçage', (5, 15)),
        ('las', '616F', 'Lasure de façade remplacée par l\'enduit de l\'ITE', k['ite_A2'], 'm²', -18, 'hypothese', [], 'CCTP 616 absent : affectation de la lasure à confirmer', (-25, 0)),
        ('tv', '402', 'Végétalisation extensive', k['tv_A2'], 'm²', 55, 'cite', ['tv_prix'], '40 à 70 € HT/m² hors étanchéité (valeur 2019)', (40, 70)),
        ('grav', '402', 'Protection gravillons supprimée', k['tv_A2'], 'm²', -8, 'hypothese', [], '', (-12, -5)),
        ('vr', '417', 'Coffres de volet roulant isolés et étanches', k['fe_A2'], 'u', 60, 'hypothese', [], 'Surcoût par fenêtre', (30, 100)),
        ('vhy', '502', 'Extracteurs hybrides basse consommation, régulation comprise', k['vhy_n'], 'u', 2500, 'hypothese', ['vhy_maquette'], 'Prix non publié : à consulter auprès des fabricants de systèmes sous Avis Technique', (1500, 4000)),
        ('caisson', '502', 'Caissons d\'extraction hygro B et réseaux de toiture supprimés', 3, 'u', -5000, 'hypothese', ['cctp502'], 'Caisson Airvent PA et sa part de réseau horizontal en toiture', (-7000, -3500)),
        ('cond', '502', 'Conduits verticaux élargis (Ø355 à Ø560)', k['vhy_ml'], 'ml', 45, 'hypothese', ['vhy_maquette'], 'Surcoût par rapport aux sections du DCE ; 13 colonnes de 43,47 à 70,20 NGF', (25, 70)),
        ('bouche', '502', 'Bouches hygro B basse pression', k['vhy_bouches'], 'u', 15, 'hypothese', ['cvc_cellules'], 'Surcoût par bouche par rapport aux bouches hygro B standard', (5, 30)),
        ('gaine', '602', 'Gaines techniques et trémies agrandies', k['vhy_tremies'], 'u', 80, 'hypothese', ['vhy_maquette'], 'Reprise des cloisons de gaine et trémies plus grandes, par traversée de dalle', (40, 150)),
        ('sol', '502', 'Eau chaude solaire : capteurs, ballon 1 500 L, station', k['sol_m2'], 'm²', 1200, 'cite', ['solaire_prix'], 'Installations collectives de moins de 50 m²', (900, 1500)),
    ]
    P = [{'id': i, 'lot': lot, 'poste': p, 'qte': round(q, 1), 'unite': u, 'pu': pu, 'fiab': f, 'src': s, 'note': n, 'min': mn, 'max': mx}
         for i, lot, p, q, u, pu, f, s, n, (mn, mx) in postes]
    pistes = [
        {'poste': 'Supprimer les rupteurs de nez de plancher, redondants avec l\'ITE', 'qte': round(k['rupt_A2']), 'unite': 'ml', 'pu': -60, 'fiab': 'hypothese',
         'note': 'À valider par le BET thermique (ponts thermiques résiduels, règles RE2020)'},
        {'poste': 'Traiter les liaisons de balcon par rupteurs (type Isokorb)', 'qte': round(k['fronts_A2']), 'unite': 'ml', 'pu': 250, 'fiab': 'hypothese',
         'note': 'L\'ITE laisse les balcons en pont thermique ; ordre de grandeur'},
        {'poste': 'Rehausser les 9 sorties de ventilation (tirage du R+9), si le bureau d\'études le demande', 'qte': 9, 'unite': 'u', 'pu': 400, 'fiab': 'hypothese',
         'note': 'Conduit et costière plus hauts ; à vérifier avec la notice de l\'Avis Technique'},
        {'poste': 'Lever l\'option compteurs d\'énergie de la tour A1 (instrumentation du jumeau)', 'qte': k['n1'], 'unite': 'logement', 'pu': 250, 'fiab': 'hypothese',
         'note': 'Concerne A1 : sans comptage individuel, pas de suivi par logement'},
    ]
    budget = [{'lot': c, 'nom': n, 'objectif_2020': o, 'A1_2020': o / 2} for c, n, o in BUDGET_2020]
    return {'bt01': dict(BT01, coef=round(coef, 4)), 'budget': budget, 'postes': P, 'pistes': pistes,
            'note': 'Montants en € HT. Budget objectif du 23/04/2020 actualisé par l\'index BT01 ; écarts de la variante en valeur 2026 par ratios.'}


# ------------------------------------------------------------------ exploitation et carbone
def exploitation(k):
    J = json.load(open(os.path.join(ROOT, 'data', 'energie', 'jumeau.json'), encoding='utf-8'))
    LG = json.load(open(os.path.join(ROOT, 'data', 'energie', 'logements.json'), encoding='utf-8'))['logements']
    H = {kk: v['valeur'] for kk, v in J['hypotheses'].items()}
    T = {}
    for z in ('A1', 'A2'):
        d = J['tours'][z]['jour']
        ls = [l for l in LG if l['tour'] == z]
        T[z] = {
            'shab': J['tours'][z]['shab'], 'logements': len(ls), 'occupants': sum(l['occupants'] for l in ls),
            'chauffage': round(sum(l['an']['chauffage'] for l in ls)), 'ecs': round(sum(l['an']['ecs'] for l in ls)),
            'reseau': round(sum(d['reseau'])), 'solaire': round(sum(d['solaire'])), 'pertes': round(sum(d['pertes'])),
            'pertes_modele': round(sum(d['pertes_modele'])), 'ventilation': round(sum(d['ventilation'])),
            'ascenseurs': round(sum(d['ascenseurs'])), 'eclairage': round(sum(d['eclairage'])), 'auxiliaires': round(sum(d['auxiliaires'])),
            'eau': round(sum(l['an']['eau'] for l in ls), 1), 'elec_priv': round(sum(l['an']['elec'] for l in ls)),
        }
    # gain attribuable à la variante, même méthode que le jumeau (ramené à la surface de A2)
    s1, s2 = T['A1']['shab'], T['A2']['shab']
    pert = J['calage']['pertes_distribution']['A2']
    dheat = (T['A1']['chauffage'] / s1 - T['A2']['chauffage'] / s2) * s2
    dvent = (T['A2']['ventilation'] / s2 - T['A1']['ventilation'] / s1) * s2
    # le gain de chauffage vient de l'ITE (la ventilation hybride garde les débits de la VMC hygro B) ;
    # la ventilation hybride agit sur l'électricité des ventilateurs
    gains = [
        {'id': 'ite', 'poste': 'ITE (enveloppe)', 'chaleur': round(dheat * (1 + pert)), 'elec': 0},
        {'id': 'vhy', 'poste': 'Ventilation hybride (électricité des ventilateurs)', 'chaleur': 0, 'elec': -round(dvent)},
        {'id': 'sol', 'poste': 'Eau chaude solaire', 'chaleur': round(T['A2']['solaire'] * (1 + pert)), 'elec': 0},
        {'id': 'tv', 'poste': 'Toiture végétalisée', 'chaleur': 0, 'elec': 0, 'note': 'Confort d\'été et gestion des eaux pluviales ; pas de gain de chauffage chiffré'},
        {'id': 'bc', 'poste': 'Béton bas carbone', 'chaleur': 0, 'elec': 0, 'note': 'Agit sur le carbone de construction'},
    ]
    maint = [
        {'id': 'vent', 'poste': 'Ventilation : visites, courroies, régulation', 'A1': 900, 'A2': 1000, 'fiab': 'hypothese',
         'note': 'A1 : 3 caissons simple flux (300 €/an chacun). A2 : 9 extracteurs hybrides, contrôle annuel des moteurs et de la régulation (≈ 110 €/an chacun). Nettoyage des bouches identique dans les deux tours'},
        {'id': 'sol', 'poste': 'Eau chaude solaire : contrat d\'entretien', 'A1': 0, 'A2': 540, 'fiab': 'hypothese', 'note': '1,5 % de l\'investissement par an'},
        {'id': 'toit', 'poste': 'Toiture : entretien', 'A1': round(k['roof_A1'] * 0.5), 'A2': round(k['tv_A2'] * 1.5), 'fiab': 'hypothese',
         'note': 'Gravillons 0,5 €/m².an ; végétalisation extensive 1,5 €/m².an (1 passage)'},
    ]
    construction = [
        {'poste': 'Béton bas carbone (fondations A2)', 'valeur': round(-k['bc_A2'] * 219 * 0.30 / 1000, 1), 'unite': 'tCO₂e', 'fiab': 'hypothese',
         'note': f"{k['bc_A2']:.0f} m³ × 219 kgCO₂e/m³ (béton de référence C25/30) × −30 % ; à remplacer par la FDES du fournisseur"},
        {'poste': 'ITE PSE 140 mm et enduit, moins le doublage intérieur', 'valeur': None, 'unite': 'tCO₂e', 'fiab': 'hypothese', 'note': 'À chiffrer avec les FDES INIES (bilan proche de zéro attendu : un isolant remplace l\'autre)'},
        {'poste': 'Extracteurs hybrides et conduits élargis, moins les 3 caissons et leurs réseaux', 'valeur': None, 'unite': 'tCO₂e', 'fiab': 'hypothese', 'note': 'À chiffrer (PEP ecopassport) : bilan proche de zéro attendu'},
        {'poste': 'Capteurs solaires et ballon', 'valeur': None, 'unite': 'tCO₂e', 'fiab': 'hypothese', 'note': 'À chiffrer (PEP ecopassport) : impact en hausse'},
        {'poste': 'Végétalisation de toiture', 'valeur': None, 'unite': 'tCO₂e', 'fiab': 'hypothese', 'note': 'À chiffrer : impact faible'},
    ]
    prix = {kk: H[kk] for kk in ('prix_chaleur', 'prix_elec', 'prix_eau', 'co2_chaleur', 'co2_elec', 'ep_elec', 'evol_energie')}
    return {'tours': T, 'prix': prix, 'pertes_A2': pert, 'gains': gains, 'maintenance': maint, 'construction': construction,
            'duree': 30, 'evol_maintenance': 2.0,
            'note': 'Année 1 simulée par le jumeau énergétique (données fictives). La tour A1 inclut une anomalie de sous-station détectée en hiver (by-pass, ≈ 6 MWh).'}


def defaults(C, E):
    """Totaux par défaut (pour le JSON, le PDF et le contrôle du classeur)."""
    coef = BT01['actuel'] / BT01['base']
    delta = sum(p['qte'] * p['pu'] for p in C['postes'])
    a1 = sum(b['A1_2020'] for b in C['budget']) * coef
    p = E['prix']
    g_eur = {g['id']: g['chaleur'] / 1000 * p['prix_chaleur'] + g['elec'] * p['prix_elec'] for g in E['gains']}
    g_co2 = {g['id']: g['chaleur'] * p['co2_chaleur'] + g['elec'] * p['co2_elec'] for g in E['gains']}
    dm = sum(m['A2'] - m['A1'] for m in E['maintenance'])
    return {'A1_2026': round(a1), 'delta': round(delta), 'A2_2026': round(a1 + delta), 'delta_pct': round(delta / a1 * 100, 2),
            'delta_logement': round(delta / E['tours']['A2']['logements']), 'delta_m2': round(delta / E['tours']['A2']['shab'], 1),
            'gain_energie': round(sum(g_eur.values())), 'gain_co2': round(sum(g_co2.values())), 'delta_maintenance': round(dm),
            'gain_net': round(sum(g_eur.values()) - dm), 'gains_eur': {kk: round(v) for kk, v in g_eur.items()},
            'gains_co2': {kk: round(v) for kk, v in g_co2.items()}}


TFPB_M2 = 12.5          # € par m² habitable et par an (moyenne nationale, Fipeco)


def cycle(C, E):
    """Coût global sur 50 ans : conception, remplacements, fin de vie et aides (écart de la variante, tour A2)."""
    P = {p['id']: p for p in C['postes']}
    shab2 = E['tours']['A2']['shab']
    rempl = [
        {'id': 'vent', 'poste': 'Ventilation : 9 extracteurs hybrides (A2) au lieu de 3 caissons (A1)',
         'A1': round(-P['caisson']['pu'] * P['caisson']['qte']), 'A2': round(P['vhy']['pu'] * P['vhy']['qte']), 'duree': 17, 'fiab': 'hypothese', 'src': ['cee_bar155', 'cee_bar127'],
         'note': 'Durée de vie conventionnelle de 17 ans dans les deux fiches CEE : remplacement aux années 17 et 34. Prix des postes du comparatif'},
        {'id': 'sol_reg', 'poste': 'Eau chaude solaire : circulateur, sondes et régulation', 'A1': 0, 'A2': 3000, 'duree': 10, 'fiab': 'hypothese', 'src': ['ademe_solaire'],
         'note': 'Environ 10 ans (ADEME). Montant : environ 8 % de l\'installation'},
        {'id': 'sol_ballon', 'poste': 'Eau chaude solaire : ballon de 1 500 L', 'A1': 0, 'A2': 6000, 'duree': 20, 'fiab': 'hypothese', 'src': ['ademe_solaire'],
         'note': '15 à 20 ans (ADEME). Montant : environ 17 % de l\'installation'},
        {'id': 'sol_capt', 'poste': 'Eau chaude solaire : 30 m² de capteurs plans', 'A1': 0, 'A2': 12000, 'duree': 25, 'fiab': 'hypothese', 'src': ['ademe_solaire'],
         'note': '20 à 30 ans (ADEME), 25 ans retenus. Montant : environ 33 % de l\'installation'},
    ]
    ite, tv = P['ite']['qte'], P['tv']['qte']
    fin = [
        {'id': 'ite', 'poste': 'Dépose et tri de l\'ITE (PSE graphité et enduit)', 'qte': ite, 'unite': 'm²', 'pu': 15, 'fiab': 'hypothese', 'src': [],
         'note': 'Dépose sélective de l\'isolant et de l\'enduit avant la démolition'},
        {'id': 'dbl', 'poste': 'Doublage intérieur à déposer en moins', 'qte': ite, 'unite': 'm²', 'pu': -8, 'fiab': 'hypothese', 'src': [],
         'note': 'Le doublage collé de la conception DCE se dépose au curage'},
        {'id': 'tv', 'poste': 'Évacuation du substrat de la toiture végétalisée (8 cm)', 'qte': round(tv * 0.08, 1), 'unite': 'm³', 'pu': 50, 'fiab': 'cite', 'src': ['demolition'],
         'note': 'Terre et sédums évacués comme des matériaux inertes'},
    ]
    tfpb_an = round(shab2 * TFPB_M2)
    aides = [
        {'id': 'tfpb', 'titre': 'Exonération de taxe foncière prolongée de 25 à 30 ans', 'statut': 'Conditionnelle', 'montant_an': tfpb_an, 'annees': [26, 30], 'fiab': 'hypothese',
         'src': ['tfpb', 'tfpb_montant'],
         'conditions': 'La tour A2 est un logement locatif social neuf (CDC Habitat). Son exonération de taxe foncière dure 25 ans si la décision de financement est prise avant le 31/12/2026. '
                       'Elle passe à 30 ans si la construction respecte aussi les seuils RE2020 de 2028 (permis déposé en 2025-2027 : Ic construction ≤ 580 et Ic énergie ≤ 260 kgCO₂e/m²), attestés par une certification NF Habitat. '
                       'Rien ne garantit que la variante atteigne ces seuils : il faut le calcul RE2020 de la tour A2.',
         'note': f'Taxe évitée pendant les années 26 à 30 : {shab2:,.0f} m² × {TFPB_M2:.1f} €/m² (moyenne nationale) ≈ {tfpb_an:,} € par an, valeur 2026'.replace(',', ' ').replace('.', ',')},
        {'id': 'fonds_chaleur', 'titre': 'Fonds Chaleur de l\'ADEME (eau chaude solaire)', 'statut': 'Suspendue', 'montant': 0, 'src': ['fonds_chaleur', 'fonds_chaleur_cond'],
         'conditions': 'Les installations de logement collectif de 25 m² de capteurs ou plus sont éligibles en métropole : les 30 m² de la tour A2 le seraient. Le dépôt de nouvelles demandes est suspendu depuis le 4 novembre 2026 ; à surveiller pour 2027.'},
        {'id': 'cee', 'titre': 'Certificats d\'économies d\'énergie (fiche BAR-TH-155)', 'statut': 'Non applicable', 'montant': 0, 'src': ['cee_bar155'],
         'conditions': 'La fiche vise les appartements existants : une construction neuve n\'y ouvre pas droit.'},
        {'id': 'tva', 'titre': 'TVA réduite du logement social', 'statut': 'Fiscalité', 'montant': None, 'src': ['tva_lls'],
         'conditions': '10 % pour un logement financé en PLUS hors renouvellement urbain, 5,5 % en PLAI ou en PLUS dans le cadre du NPNRU. Les amendements qui rétablissaient 5,5 % pour tous ont été rejetés. Le taux s\'applique ici aux dépenses du bailleur.'},
    ]
    return {
        'annees': 50,
        'params': {'tva': 10.0, 'evol_couts': 2.0, 'actualisation': 0.0, 'honoraires': 10.0, 'tfpb': False},
        'conception': {'etudes': 12000, 'fiab': 'hypothese', 'src': ['miqcp'],
                       'note': 'Honoraires de maîtrise d\'œuvre en pourcentage du surcoût de travaux (méthode MIQCP), plus 12 000 € HT d\'études propres à la variante : dimensionnement de la ventilation hybride par le calcul, étude de faisabilité solaire, calcul RE2020 et ACV'},
        'remplacements': rempl, 'fin_de_vie': fin, 'aides': aides, 'tfpb_m2': TFPB_M2,
        'note': 'Écart de la tour A2 (variante) par rapport à la conception du DCE, sur 50 ans. Énergie : gain du jumeau (tour A1 ramenée à la surface de A2), au prix TTC payé par les locataires. '
                'Dépenses du bailleur (études, travaux, entretien, remplacements, fin de vie) majorées de la TVA du logement social. Montants courants avec évolution des prix ; actualisation réglable (0 % par défaut).',
    }


def cycle_totals(Cy, D, E, over=None):
    p = dict(Cy['params'])
    p.update(over or {})
    Y = Cy['annees']
    tva, gc, ge, r, hon = p['tva'] / 100, p['evol_couts'] / 100, E['prix']['evol_energie'] / 100, p['actualisation'] / 100, p['honoraires'] / 100
    cats = {c: [0.0] * (Y + 1) for c in ('conception', 'travaux', 'energie', 'entretien', 'remplacements', 'fin', 'aides')}
    cats['conception'][0] = (hon * D['delta'] + Cy['conception']['etudes']) * (1 + tva)
    cats['travaux'][0] = D['delta'] * (1 + tva)
    for t in range(1, Y + 1):
        cats['energie'][t] = -D['gain_energie'] * (1 + ge) ** (t - 1)
        cats['entretien'][t] = D['delta_maintenance'] * (1 + gc) ** (t - 1) * (1 + tva)
    for rp in Cy['remplacements']:
        t = rp['duree']
        while t < Y:
            cats['remplacements'][t] += (rp['A2'] - rp['A1']) * (1 + gc) ** t * (1 + tva)
            t += rp['duree']
    cats['fin'][Y] = sum(f['qte'] * f['pu'] for f in Cy['fin_de_vie']) * (1 + gc) ** Y * (1 + tva)
    tf = next(a for a in Cy['aides'] if a['id'] == 'tfpb')
    if p['tfpb']:
        for t in range(tf['annees'][0], tf['annees'][1] + 1):
            cats['aides'][t] -= tf['montant_an'] * (1 + gc) ** (t - 1)
    act = [(1 + r) ** -t for t in range(Y + 1)]
    tot = {c: round(sum(v[t] * act[t] for t in range(Y + 1))) for c, v in cats.items()}
    cum, run = [], 0.0
    for t in range(Y + 1):
        run += sum(v[t] for v in cats.values()) * act[t]
        cum.append(round(run))
    retour = next((t for t in range(1, Y + 1) if cum[t] <= 0), None)
    tfpb_pot = round(sum(tf['montant_an'] * (1 + gc) ** (t - 1) * act[t] for t in range(tf['annees'][0], tf['annees'][1] + 1)))
    return {'params': p, 'totaux': tot, 'total': cum[-1], 'retour': retour, 'cumul': cum,
            'locataires': tot['energie'], 'bailleur': cum[-1] - tot['energie'], 'tfpb_potentiel': tfpb_pot}


def attention(k, D):
    return [
        {'niveau': 'fort', 'titre': 'Gain d\'exploitation faible avec un réseau de chaleur bon marché et bas carbone',
         'texte': (f"La variante économise ≈ {D['gain_energie']:,} € TTC d'énergie par an pour un surcoût de travaux estimé à {D['delta']:,} € HT. Avec l'entretien supplémentaire (≈ {D['delta_maintenance']:,} €/an, hypothèses), le bilan annuel est de {D['gain_net']:+,} €, ".replace(',', ' ')
                   + ('proche de zéro : les travaux ne sont pas remboursés par l\'usage.' if abs(D['gain_net']) < 500 else ('négatif.' if D['gain_net'] < 0 else 'positif mais sans commune mesure avec le surcoût.'))
                   + " Elle se justifie par la RE2020, le confort et la qualité de l'air, pas par le coût d'usage.")},
        {'niveau': 'fort', 'titre': 'Ventilation hybride : gain réel, mais à valider par le bureau d\'études',
         'texte': f"La ventilation hybride divise par 4 environ l'électricité de ventilation ({str(round(k['vent_A1'], 1)).replace('.', ',')} contre {str(round(k['vent_A2'], 1)).replace('.', ',')} kWh/m².an dans le jumeau) sans toucher aux débits ni au chauffage. Ce gain repose sur des hypothèses : assistance 18 % du temps par grand froid jusqu'à 95 % par temps chaud, extracteurs basse consommation (≤ 0,1 Wh/m³). Le système doit être sous Avis Technique (extracteurs, bouches et entrées d'air d'un même fabricant), admettre 9 étages par colonne et faire l'objet d'un dimensionnement des conduits par le calcul."},
        {'niveau': 'moyen', 'titre': 'Gaines techniques à agrandir',
         'texte': 'À l\'étage courant, les colonnes élargies recoupent 50 fois les parois de gaine, 19 fois des cloisons et 5 fois des cloisons séparatives : les gaines sont à agrandir (le DCE prévoyait déjà de les optimiser). 105 trémies d\'étage et 9 en toiture à réserver ; dévoiement sous la toiture pour les colonnes B, F et H, dont la sortie est décalée de 0,4 à 0,7 m.'},
        {'niveau': 'moyen', 'titre': 'Rupteurs et balcons avec l\'ITE',
         'texte': f"L'ITE rend les rupteurs de nez de plancher du CCTP 301 redondants (≈ {k['rupt_A2']:.0f} ml) mais laisse ≈ {k['fronts_A2']:.0f} ml de liaisons de balcon en pont thermique. À arbitrer avec le BET thermique avant de figer la variante."},
        {'niveau': 'moyen', 'titre': 'Comptage individuel en option sur la tour A1',
         'texte': 'Le CCTP met les compteurs d\'énergie chauffage et ECS de la tour COGEDIM en option. Sans eux, le jumeau énergétique ne peut pas suivre A1 logement par logement.'},
        {'niveau': 'moyen', 'titre': 'Toiture végétalisée et sorties de ventilation',
         'texte': 'Les 3 caissons et leurs réseaux disparaissent de la toiture : il reste 9 sorties à 1,40 m au-dessus de la toiture finie (NF DTU 24.1), chacune entourée d\'une zone stérile de 40 cm, et un cheminement d\'entretien jusqu\'aux extracteurs, avec les capteurs solaires.'},
        {'niveau': 'info', 'titre': 'Surface habitable gagnée',
         'texte': 'Supprimer le doublage intérieur libère ≈ 11 cm le long des façades, soit de l\'ordre de 80 m² de surface habitable sur la tour A2. Non intégré au chiffrage.'},
        {'niveau': 'info', 'titre': 'Budget du dossier réparti à 50/50',
         'texte': 'La colonne « tour A1 » du budget vaut exactement la moitié de chaque poste, VRD et parking compris, et date d\'avril 2020. Les montants par tour sont donc des ordres de grandeur.'},
    ]


# ------------------------------------------------------------------ classeur Excel (formules)
def build_xlsx(data, path):
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    F = 'Arial'
    f_title = Font(name=F, size=14, bold=True)
    f_h = Font(name=F, size=10, bold=True, color='FFFFFF')
    f_b = Font(name=F, size=10)
    f_bb = Font(name=F, size=10, bold=True)
    f_in = Font(name=F, size=10, color='0000FF')
    f_link = Font(name=F, size=10, color='008000')
    f_note = Font(name=F, size=9, italic=True, color='56616A')
    fill_h = PatternFill('solid', fgColor='1E2428')
    fill_in = PatternFill('solid', fgColor='FFFF00')
    fill_g = PatternFill('solid', fgColor='EEF0EE')
    thin = Side(style='thin', color='CFD4D2')
    bd = Border(bottom=thin)
    wrap = Alignment(wrap_text=True, vertical='top')
    EUR = '#,##0 "€";(#,##0 "€");"-"'
    NUM = '#,##0;(#,##0);"-"'
    NUM1 = '#,##0.0;(#,##0.0);"-"'

    wb = Workbook()

    def sheet(title, widths):
        ws = wb.create_sheet(title)
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.sheet_view.showGridLines = False
        return ws

    def header(ws, row, labels):
        for i, t in enumerate(labels, 1):
            c = ws.cell(row=row, column=i, value=t)
            c.font = f_h
            c.fill = fill_h
            c.alignment = Alignment(wrap_text=True, vertical='center')
        ws.row_dimensions[row].height = 28

    def put(ws, row, col, v, font=f_b, fmt=None, fill=None, al=None):
        c = ws.cell(row=row, column=col, value=v)
        c.font = font
        if fmt:
            c.number_format = fmt
        if fill:
            c.fill = fill
        c.alignment = al or Alignment(vertical='top', wrap_text=isinstance(v, str) and len(v) > 40)
        c.border = bd
        return c

    # ---- Lisez-moi
    ws = wb.active
    ws.title = 'Lisez-moi'
    ws.column_dimensions['A'].width = 26
    ws.column_dimensions['B'].width = 100
    ws.sheet_view.showGridLines = False
    ws['A1'] = 'Comparatif tours A1 / A2 — Domaine de Fontbelleau'
    ws['A1'].font = f_title
    rows = [
        ('Objet', 'Comparer la tour A1 (conception DCE, RT 2012) et la tour A2 (variante RE2020 du groupe) : solutions lot par lot, quantités, coûts de travaux, exploitation et carbone.'),
        ('Généré le', data['genere']),
        ('Statut', 'Document d\'étude. Coûts estimés par ratios ; exploitation issue de l\'année 1 simulée du jumeau énergétique (données fictives).'),
        ('Cellules à modifier', 'Texte bleu sur fond jaune : prix unitaires, index, prix de l\'énergie, entretien. Les totaux se recalculent.'),
        ('Couleurs', 'Bleu : saisie. Noir : formule. Vert : renvoi vers une autre feuille.'),
        ('Origine des données', 'Maquette : mesuré dans la maquette. CCTP : pièce du marché. CCTP, non modélisé : équipement prévu au CCTP mais absent de la maquette, compté quand même. Variante : modélisé par le groupe (tour A2). Calcul : dérivé de la maquette. Estimé : dénombré par typologie. Prix publié : ratio sourcé. Hypothèse : valeur de travail à confirmer.'),
        ('Règle de comptage', 'Tour A1 : les équipements de chauffage, ventilation et ECS du CCTP sont comptés même s\'ils ne sont pas modélisés. Tour A2 : ce sont les éléments de la variante.'),
        ('Feuilles', 'Synthèse · Lots · Quantités · Coûts · Exploitation · Sources'),
        ('Page web', 'https://lucasdupuymontbrun-del.github.io/passeport-fontbelleau/comparatif/'),
    ]
    for i, (a, b) in enumerate(rows, 3):
        ws.cell(row=i, column=1, value=a).font = f_bb
        c = ws.cell(row=i, column=2, value=b)
        c.font = f_b
        c.alignment = wrap
    ws.cell(row=14, column=1, value='Exemple de saisie').font = f_bb
    c = ws.cell(row=14, column=2, value=125)
    c.font = f_in
    c.fill = fill_in
    ws.cell(row=15, column=2, value='← prix unitaire d\'un poste (feuille Coûts, colonne F), en € HT').font = f_note

    # ---- Quantités
    ws = sheet('Quantités', [24, 52, 9, 13, 13, 13, 20, 20, 60])
    ws['A1'] = 'Quantités par tour'
    ws['A1'].font = f_title
    header(ws, 3, ['Groupe', 'Ouvrage / équipement', 'Unité', 'Tour A1', 'Tour A2', 'Écart A2 − A1', 'Origine A1', 'Origine A2', 'Note'])
    r = 4
    for q in data['quantites']:
        put(ws, r, 1, q['groupe'])
        put(ws, r, 2, q['item'], al=wrap)
        put(ws, r, 3, q['unite'])
        dec = NUM1 if q['unite'] in ('m³',) else NUM
        put(ws, r, 4, q['A1'], fmt=dec)
        put(ws, r, 5, q['A2'], fmt=dec)
        put(ws, r, 6, f'=IF(AND(ISNUMBER(D{r}),ISNUMBER(E{r})),E{r}-D{r},"")', fmt=dec)
        put(ws, r, 7, FIAB[q['f1']])
        put(ws, r, 8, FIAB[q['f2']])
        put(ws, r, 9, q['note'], font=f_note, al=wrap)
        r += 1
    ws.freeze_panes = 'C4'

    # ---- Lots
    ws = sheet('Lots', [10, 30, 26, 52, 52, 14])
    ws['A1'] = 'Solutions lot par lot'
    ws['A1'].font = f_title
    header(ws, 3, ['Lot', 'Intitulé', 'Sujet', 'Tour A1 — DCE', 'Tour A2 — variante', 'Écart'])
    lab = {'identique': 'Identique', 'modifie': 'Modifié', 'ajoute': 'Ajouté', 'supprime': 'Supprimé', 'programme': 'Programme'}
    r = 4
    for L in data['lots']:
        for ln in L['lignes']:
            put(ws, r, 1, L['lot'])
            put(ws, r, 2, L['nom'], al=wrap)
            put(ws, r, 3, ln['theme'], al=wrap)
            put(ws, r, 4, ln['A1'], al=wrap)
            put(ws, r, 5, ln['A2'], al=wrap)
            put(ws, r, 6, lab[ln['ecart']], font=f_bb)
            r += 1
    ws.freeze_panes = 'A4'

    # ---- Coûts
    C = data['couts']
    ws = sheet('Coûts', [10, 52, 12, 10, 12, 14, 16, 16, 60])
    ws['A1'] = 'Coûts de travaux (€ HT)'
    ws['A1'].font = f_title
    put(ws, 3, 1, 'Index', font=f_bb)
    put(ws, 4, 2, f"BT01 de base ({C['bt01']['base_mois']}, date du budget)")
    put(ws, 4, 6, C['bt01']['base'], font=f_in, fill=fill_in, fmt='0.0')
    put(ws, 5, 2, f"BT01 actuel ({C['bt01']['actuel_mois']})")
    put(ws, 5, 6, C['bt01']['actuel'], font=f_in, fill=fill_in, fmt='0.0')
    ws['F5'].comment = Comment('Source : Insee, index BT01 base 2010, relevé ANIL (anil.org/outils/indices-et-plafonds/indice-bt-01)', 'Comparatif')
    put(ws, 6, 2, 'Coefficient d\'actualisation')
    put(ws, 6, 6, '=F5/F4', fmt='0.000')
    # écarts de la variante
    put(ws, 8, 1, 'Écarts de la variante A2 (valeur 2026, ratios)', font=f_bb)
    header(ws, 9, ['Lot', 'Poste', 'Quantité', 'Unité', 'Origine', 'PU € HT', 'Montant € HT', 'Fourchette PU', 'Justification'])
    r = 10
    first = r
    for p in C['postes']:
        put(ws, r, 1, p['lot'])
        put(ws, r, 2, p['poste'], al=wrap)
        put(ws, r, 3, p['qte'], fmt=NUM1, font=f_in, fill=fill_in)
        put(ws, r, 4, p['unite'])
        put(ws, r, 5, FIAB[p['fiab']])
        put(ws, r, 6, p['pu'], fmt=EUR, font=f_in, fill=fill_in)
        put(ws, r, 7, f'=C{r}*F{r}', fmt=EUR)
        put(ws, r, 8, f"{p['min']} à {p['max']} €")
        src = '; '.join(SOURCES[s]['titre'] for s in p['src'])
        put(ws, r, 9, (p['note'] + (' — ' + src if src else '')).strip(' —'), font=f_note, al=wrap)
        r += 1
    last = r - 1
    put(ws, r, 2, 'Total des écarts de la variante', font=f_bb)
    put(ws, r, 7, f'=SUM(G{first}:G{last})', fmt=EUR, font=f_bb)
    tot_delta = f'G{r}'
    r += 2
    # budget par lot
    put(ws, r, 1, 'Budget par lot et par tour', font=f_bb)
    r += 1
    header(ws, r, ['Lot', 'Intitulé', 'Objectif 2020 (2 tours)', '', 'Tour A1 2020', 'Tour A1 2026', 'Écart variante', 'Tour A2 2026', 'Note'])
    r += 1
    b0 = r
    for b in C['budget']:
        put(ws, r, 1, b['lot'])
        put(ws, r, 2, b['nom'])
        put(ws, r, 3, b['objectif_2020'], fmt=EUR, font=f_in)
        put(ws, r, 5, f'=C{r}/2', fmt=EUR)
        put(ws, r, 6, f'=E{r}*$F$6', fmt=EUR)
        put(ws, r, 7, f'=SUMIF($A${first}:$A${last},A{r},$G${first}:$G${last})', fmt=EUR)
        put(ws, r, 8, f'=F{r}+G{r}', fmt=EUR)
        if b['lot'] == 'ITE':
            put(ws, r, 9, 'Lot absent du budget : créé par la variante', font=f_note)
        r += 1
    b1 = r - 1
    put(ws, r, 2, 'Total', font=f_bb)
    for col in 'CEFGH':
        put(ws, r, ord(col) - 64, f'=SUM({col}{b0}:{col}{b1})', fmt=EUR, font=f_bb)
    btot = r
    r += 1
    put(ws, r, 2, 'Écart A2 / A1')
    put(ws, r, 8, f'=IF(F{btot}=0,0,H{btot}/F{btot}-1)', fmt='0.0%')
    r += 1
    put(ws, r, 2, 'Contrôle : total des écarts = colonne Écart variante')
    put(ws, r, 8, f'=IF(ABS(G{btot}-{tot_delta})<1,"OK","À vérifier")')
    r += 2
    put(ws, r, 1, 'Pistes à étudier (non incluses dans le total)', font=f_bb)
    r += 1
    header(ws, r, ['', 'Poste', 'Quantité', 'Unité', 'Origine', 'PU € HT', 'Montant € HT', '', 'Note'])
    r += 1
    for p in C['pistes']:
        put(ws, r, 2, p['poste'], al=wrap)
        put(ws, r, 3, p['qte'], fmt=NUM, font=f_in, fill=fill_in)
        put(ws, r, 4, p['unite'])
        put(ws, r, 5, FIAB[p['fiab']])
        put(ws, r, 6, p['pu'], fmt=EUR, font=f_in, fill=fill_in)
        put(ws, r, 7, f'=C{r}*F{r}', fmt=EUR)
        put(ws, r, 9, p['note'], font=f_note, al=wrap)
        r += 1
    r += 1
    put(ws, r, 2, C['note'], font=f_note, al=wrap)
    ws.freeze_panes = 'A3'
    COUT = {'delta': f"'Coûts'!{tot_delta}", 'A1': f"'Coûts'!F{btot}", 'A2': f"'Coûts'!H{btot}"}

    # ---- Exploitation
    E = data['exploitation']
    ws = sheet('Exploitation', [46, 16, 16, 16, 16, 50])
    ws['A1'] = 'Exploitation et carbone — année 1 simulée'
    ws['A1'].font = f_title
    put(ws, 3, 1, 'Prix et facteurs', font=f_bb)
    prix_rows = [('Chaleur du réseau, € TTC/MWh', 'prix_chaleur', '0.00', SOURCES['prix_chaleur']['titre']),
                 ('Électricité, € TTC/kWh', 'prix_elec', '0.0000', SOURCES['prix_elec']['titre']),
                 ('CO₂ de la chaleur, kgCO₂e/kWh', 'co2_chaleur', '0.000', SOURCES['co2_chaleur']['titre']),
                 ('CO₂ de l\'électricité, kgCO₂e/kWh', 'co2_elec', '0.000', 'Hypothèse : ordre de grandeur, à vérifier'),
                 ('Évolution du prix de l\'énergie, %/an', 'evol_energie', '0.0', 'Hypothèse'),
                 ('Évolution du coût d\'entretien, %/an', None, '0.0', 'Hypothèse')]
    R = {}
    r = 4
    for lab_, key, fmt, src in prix_rows:
        put(ws, r, 1, lab_)
        v = E['prix'][key] if key else E['evol_maintenance']
        if key in ('evol_energie',) or key is None:
            v = v / 100
            fmt = '0.0%'
        put(ws, r, 2, v, font=f_in, fill=fill_in, fmt=fmt)
        put(ws, r, 6, src, font=f_note, al=wrap)
        R[key or 'evol_maint'] = f'$B${r}'
        r += 1
    put(ws, r, 1, 'Pertes de distribution A2 (part de la chaleur livrée)')
    put(ws, r, 2, E['pertes_A2'], font=f_in, fill=fill_in, fmt='0%')
    R['pertes'] = f'$B${r}'
    r += 2
    put(ws, r, 1, 'Consommations par tour (kWh/an sauf mention)', font=f_bb)
    r += 1
    header(ws, r, ['Poste', 'Tour A1', 'Tour A2', 'A1 /m²', 'A2 /m²', 'Note'])
    r += 1
    labels = [('shab', 'Surface habitable, m²'), ('logements', 'Logements'), ('occupants', 'Occupants (hypothèse du jumeau)'),
              ('chauffage', 'Chauffage livré aux logements'), ('ecs', 'Eau chaude livrée aux logements'), ('solaire', 'Production solaire'),
              ('pertes', 'Pertes de distribution mesurées'), ('reseau', 'Chaleur achetée au réseau'), ('ventilation', 'Électricité de ventilation'),
              ('ascenseurs', 'Électricité des ascenseurs'), ('eclairage', 'Éclairage des communs'), ('auxiliaires', 'Auxiliaires (pompes, régulation)'),
              ('eau', 'Eau froide + chaude, m³'), ('elec_priv', 'Électricité privative des logements')]
    t0 = r
    rowof = {}
    for key, lab_ in labels:
        put(ws, r, 1, lab_)
        put(ws, r, 2, E['tours']['A1'][key], font=f_in, fmt=NUM)
        put(ws, r, 3, E['tours']['A2'][key], font=f_in, fmt=NUM)
        if key not in ('shab', 'logements', 'occupants'):
            put(ws, r, 4, f'=B{r}/B${t0}', fmt=NUM1)
            put(ws, r, 5, f'=C{r}/C${t0}', fmt=NUM1)
        rowof[key] = r
        r += 1
    put(ws, rowof['pertes'], 6, 'A1 : inclut l\'anomalie de by-pass de la sous-station (≈ 6 MWh)', font=f_note)
    put(ws, r, 1, 'Coût de la chaleur, € TTC', font=f_bb)
    put(ws, r, 2, f"=B{rowof['reseau']}/1000*{R['prix_chaleur']}", fmt=EUR)
    put(ws, r, 3, f"=C{rowof['reseau']}/1000*{R['prix_chaleur']}", fmt=EUR)
    put(ws, r, 4, f'=B{r}/B${t0}', fmt='0.00')
    put(ws, r, 5, f'=C{r}/C${t0}', fmt='0.00')
    rc = r
    r += 1
    put(ws, r, 1, 'Coût de l\'électricité des communs, € TTC', font=f_bb)
    e1 = f"(B{rowof['ventilation']}+B{rowof['ascenseurs']}+B{rowof['eclairage']}+B{rowof['auxiliaires']})"
    e2 = f"(C{rowof['ventilation']}+C{rowof['ascenseurs']}+C{rowof['eclairage']}+C{rowof['auxiliaires']})"
    put(ws, r, 2, f"={e1}*{R['prix_elec']}", fmt=EUR)
    put(ws, r, 3, f"={e2}*{R['prix_elec']}", fmt=EUR)
    put(ws, r, 4, f'=B{r}/B${t0}', fmt='0.00')
    put(ws, r, 5, f'=C{r}/C${t0}', fmt='0.00')
    r += 1
    put(ws, r, 1, 'CO₂ chaleur + communs, kgCO₂e', font=f_bb)
    put(ws, r, 2, f"=B{rowof['reseau']}*{R['co2_chaleur']}+{e1}*{R['co2_elec']}", fmt=NUM)
    put(ws, r, 3, f"=C{rowof['reseau']}*{R['co2_chaleur']}+{e2}*{R['co2_elec']}", fmt=NUM)
    put(ws, r, 4, f'=B{r}/B${t0}', fmt='0.00')
    put(ws, r, 5, f'=C{r}/C${t0}', fmt='0.00')
    r += 2
    # gains attribuables
    put(ws, r, 1, 'Gain annuel attribuable à chaque élément de la variante', font=f_bb)
    r += 1
    header(ws, r, ['Élément', 'Chaleur évitée, kWh', 'Électricité, kWh', 'Gain € TTC/an', 'Gain kgCO₂e/an', 'Note'])
    r += 1
    g0 = r
    for g in E['gains']:
        put(ws, r, 1, g['poste'])
        put(ws, r, 2, g['chaleur'], font=f_in, fmt=NUM)
        put(ws, r, 3, g['elec'], font=f_in, fmt=NUM)
        put(ws, r, 4, f"=B{r}/1000*{R['prix_chaleur']}+C{r}*{R['prix_elec']}", fmt=EUR)
        put(ws, r, 5, f"=B{r}*{R['co2_chaleur']}+C{r}*{R['co2_elec']}", fmt=NUM)
        put(ws, r, 6, g.get('note', 'Méthode du jumeau : écart de chauffage par m² ramené à la surface de A2, + pertes de distribution'), font=f_note, al=wrap)
        r += 1
    g1 = r - 1
    put(ws, r, 1, 'Total', font=f_bb)
    for col in 'BCDE':
        put(ws, r, ord(col) - 64, f'=SUM({col}{g0}:{col}{g1})', fmt=EUR if col == 'D' else NUM, font=f_bb)
    gtot = r
    r += 2
    put(ws, r, 1, 'Entretien annuel (€ HT/an)', font=f_bb)
    r += 1
    header(ws, r, ['Poste', 'Tour A1', 'Tour A2', 'Écart', '', 'Note'])
    r += 1
    m0 = r
    for m in E['maintenance']:
        put(ws, r, 1, m['poste'])
        put(ws, r, 2, m['A1'], font=f_in, fill=fill_in, fmt=EUR)
        put(ws, r, 3, m['A2'], font=f_in, fill=fill_in, fmt=EUR)
        put(ws, r, 4, f'=C{r}-B{r}', fmt=EUR)
        put(ws, r, 6, m['note'], font=f_note, al=wrap)
        r += 1
    m1 = r - 1
    put(ws, r, 1, 'Total', font=f_bb)
    for col in 'BCD':
        put(ws, r, ord(col) - 64, f'=SUM({col}{m0}:{col}{m1})', fmt=EUR, font=f_bb)
    mtot = r
    r += 2
    put(ws, r, 1, 'Bilan annuel de la variante (énergie − entretien)', font=f_bb)
    put(ws, r, 4, f'=D{gtot}-D{mtot}', fmt=EUR, font=f_bb)
    rbil = r
    r += 2
    # coût global
    put(ws, r, 1, f"Cumul sur {E['duree']} ans (prix évolutifs)", font=f_bb)
    r += 1
    header(ws, r, ['Année', 'Gain énergie cumulé', 'Entretien cumulé', 'Bilan cumulé', 'Surcoût travaux', 'Bilan cumulé − surcoût'])
    r += 1
    y0 = r
    for y in range(1, E['duree'] + 1):
        put(ws, r, 1, y)
        prev = f'B{r - 1}' if y > 1 else '0'
        prevc = f'C{r - 1}' if y > 1 else '0'
        put(ws, r, 2, f"={prev}+$D${gtot}*(1+{R['evol_energie']})^(A{r}-1)", fmt=EUR)
        put(ws, r, 3, f"={prevc}+$D${mtot}*(1+{R['evol_maint']})^(A{r}-1)", fmt=EUR)
        put(ws, r, 4, f'=B{r}-C{r}', fmt=EUR)
        put(ws, r, 5, f"={COUT['delta']}", fmt=EUR, font=f_link)
        put(ws, r, 6, f'=D{r}-E{r}', fmt=EUR)
        r += 1
    y1 = r - 1
    EXP = {'gain': f"'Exploitation'!D{gtot}", 'co2': f"'Exploitation'!E{gtot}", 'maint': f"'Exploitation'!D{mtot}", 'bilan': f"'Exploitation'!D{rbil}",
           'c1': f"'Exploitation'!B{rc}", 'c2': f"'Exploitation'!C{rc}", 'cum': f"'Exploitation'!F{y1}", 'y0': y0, 'y1': y1}
    r += 1
    put(ws, r, 1, E['note'], font=f_note, al=wrap)
    ws.freeze_panes = 'A3'

    # ---- Coût global sur 50 ans
    Cy = data['cycle']
    Y = Cy['annees']
    ws = sheet('Coût global 50 ans', [44, 15, 15, 15, 15, 15, 15, 15, 15, 12, 15, 15])
    ws['A1'] = f'Coût global sur {Y} ans — écart de la variante (tour A2)'
    ws['A1'].font = f_title
    put(ws, 2, 1, Cy['note'], font=f_note, al=wrap)
    ws.merge_cells('A2:L2')
    ws.row_dimensions[2].height = 42
    put(ws, 4, 1, 'Paramètres', font=f_bb)
    pr = Cy['params']
    prm = [('Honoraires de maîtrise d\'œuvre, % du surcoût de travaux', pr['honoraires'] / 100, '0.0%', 'Méthode MIQCP : pourcentage du montant HT des travaux'),
           ('Études propres à la variante, € HT', Cy['conception']['etudes'], EUR, Cy['conception']['note']),
           ('TVA du logement social sur les dépenses du bailleur', pr['tva'] / 100, '0.0%', '10 % (PLUS hors NPNRU) ou 5,5 % (PLAI, PLUS en NPNRU)'),
           ('Évolution des coûts d\'entretien et de travaux, %/an', pr['evol_couts'] / 100, '0.0%', 'Hypothèse'),
           ('Taux d\'actualisation, %/an', pr['actualisation'] / 100, '0.0%', '0 % : euros courants'),
           ('Compter la taxe foncière prolongée (1 = oui, 0 = non)', 1 if pr['tfpb'] else 0, '0', 'Conditionnelle : seuils RE2020 2028 et certification'),
           ('Taxe foncière évitée par an (années 26 à 30), € 2026', next(a for a in Cy['aides'] if a['id'] == 'tfpb')['montant_an'], EUR, f"{data['tours']['A2']['shab']} m² × {Cy['tfpb_m2']} €/m² (moyenne nationale, Fipeco)")]
    PR = {}
    r = 5
    for i, (lab_, v, fm, note) in enumerate(prm):
        put(ws, r, 1, lab_)
        put(ws, r, 2, v, font=f_in, fill=fill_in, fmt=fm)
        put(ws, r, 3, note, font=f_note)
        PR[i] = f'$B${r}'
        r += 1
    HON, ETU, TVA, GC, ACT, TF, TFA = (PR[i] for i in range(7))
    put(ws, r, 1, 'Évolution du prix de l\'énergie, %/an')
    put(ws, r, 2, f"='Exploitation'!{R['evol_energie']}", font=f_link, fmt='0.0%')
    GE = f'$B${r}'
    r += 1
    put(ws, r, 1, 'Surcoût de travaux de la variante, € HT')
    put(ws, r, 2, f"={COUT['delta']}", font=f_link, fmt=EUR)
    DEL = f'$B${r}'
    r += 1
    put(ws, r, 1, 'Énergie économisée la première année, € TTC')
    put(ws, r, 2, f"={EXP['gain']}", font=f_link, fmt=EUR)
    GAIN = f'$B${r}'
    r += 1
    put(ws, r, 1, 'Entretien supplémentaire, € HT/an')
    put(ws, r, 2, f"={EXP['maint']}", font=f_link, fmt=EUR)
    MNT = f'$B${r}'
    r += 2
    put(ws, r, 1, 'Remplacements', font=f_bb)
    r += 1
    header(ws, r, ['Remplacement', 'Durée de vie, ans', 'Tour A1, € HT', 'Tour A2, € HT', 'Écart', 'Note'])
    r += 1
    RP = []
    for rp in Cy['remplacements']:
        put(ws, r, 1, rp['poste'])
        put(ws, r, 2, rp['duree'], font=f_in, fill=fill_in, fmt='0')
        put(ws, r, 3, rp['A1'], font=f_in, fill=fill_in, fmt=EUR)
        put(ws, r, 4, rp['A2'], font=f_in, fill=fill_in, fmt=EUR)
        put(ws, r, 5, f'=D{r}-C{r}', fmt=EUR)
        put(ws, r, 6, rp['note'] + ' — ' + '; '.join(SOURCES[x]['titre'] for x in rp['src']), font=f_note)
        RP.append(r)
        r += 1
    r += 1
    put(ws, r, 1, f'Fin de vie (année {Y})', font=f_bb)
    r += 1
    header(ws, r, ['Poste', 'Quantité', 'Unité', 'PU € HT', 'Montant 2026', 'Note'])
    r += 1
    f0 = r
    for f in Cy['fin_de_vie']:
        put(ws, r, 1, f['poste'])
        put(ws, r, 2, f['qte'], font=f_in, fmt=NUM1)
        put(ws, r, 3, f['unite'])
        put(ws, r, 4, f['pu'], font=f_in, fill=fill_in, fmt=EUR)
        put(ws, r, 5, f'=B{r}*D{r}', fmt=EUR)
        put(ws, r, 6, f['note'], font=f_note)
        r += 1
    put(ws, r, 1, 'Total', font=f_bb)
    put(ws, r, 5, f'=SUM(E{f0}:E{r - 1})', fmt=EUR, font=f_bb)
    FIN = f'$E${r}'
    r += 2
    put(ws, r, 1, 'Année par année', font=f_bb)
    r += 1
    header(ws, r, ['Année', 'Études', 'Travaux', 'Énergie', 'Entretien', 'Remplacements', 'Fin de vie', 'Aides', 'Total', 'Facteur', 'Total actualisé', 'Cumul'])
    r += 1
    y0 = r
    for t in range(Y + 1):
        a = f'$A{r}'
        put(ws, r, 1, t)
        put(ws, r, 2, f'=IF({a}=0,({HON}*{DEL}+{ETU})*(1+{TVA}),0)', fmt=EUR)
        put(ws, r, 3, f'=IF({a}=0,{DEL}*(1+{TVA}),0)', fmt=EUR)
        put(ws, r, 4, f'=IF({a}>=1,-{GAIN}*(1+{GE})^({a}-1),0)', fmt=EUR)
        put(ws, r, 5, f'=IF({a}>=1,{MNT}*(1+{GC})^({a}-1)*(1+{TVA}),0)', fmt=EUR)
        terms = '+'.join(f'IF(AND({a}>0,{a}<{Y},MOD({a},$B${x})=0),$E${x},0)' for x in RP)
        put(ws, r, 6, f'=({terms})*(1+{GC})^{a}*(1+{TVA})', fmt=EUR)
        put(ws, r, 7, f'=IF({a}={Y},{FIN}*(1+{GC})^{a}*(1+{TVA}),0)', fmt=EUR)
        put(ws, r, 8, f'=IF(AND({TF}=1,{a}>=26,{a}<=30),-{TFA}*(1+{GC})^({a}-1),0)', fmt=EUR)
        put(ws, r, 9, f'=SUM(B{r}:H{r})', fmt=EUR)
        put(ws, r, 10, f'=1/(1+{ACT})^{a}', fmt='0.000')
        put(ws, r, 11, f'=I{r}*J{r}', fmt=EUR)
        put(ws, r, 12, f'=K{r}' if t == 0 else f'=L{r - 1}+K{r}', fmt=EUR)
        r += 1
    y1 = r - 1
    put(ws, r, 1, f'Total sur {Y} ans (actualisé)', font=f_bb)
    for col in 'BCDEFGHI':
        put(ws, r, ord(col) - 64, f'=SUMPRODUCT({col}{y0}:{col}{y1},$J${y0}:$J${y1})', fmt=EUR, font=f_bb)
    CG = {'total': f"'Coût global 50 ans'!I{r}", 'loc': f"'Coût global 50 ans'!D{r}",
          'tfpb': f"'Coût global 50 ans'!B{r + 1}"}
    r += 1
    put(ws, r, 1, 'Taxe foncière évitée si l\'exonération est prolongée (années 26 à 30)', font=f_bb)
    put(ws, r, 2, f'=SUMPRODUCT(({"$A$" + str(y0)}:$A${y1}>=26)*($A${y0}:$A${y1}<=30)*{TFA}*(1+{GC})^($A${y0}:$A${y1}-1)*$J${y0}:$J${y1})', fmt=EUR, font=f_bb)
    r += 2
    put(ws, r, 1, 'Aides financières et fiscales', font=f_bb)
    r += 1
    header(ws, r, ['Aide', 'Statut', 'Conditions', '', '', 'Sources'])
    r += 1
    for a_ in Cy['aides']:
        put(ws, r, 1, a_['titre'], al=wrap)
        put(ws, r, 2, a_['statut'])
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=5)
        c = ws.cell(row=r, column=3, value=a_['conditions'])
        c.font = f_b
        c.alignment = wrap
        put(ws, r, 6, '; '.join(SOURCES[x]['titre'] for x in a_['src']), font=f_note, al=wrap)
        ws.row_dimensions[r].height = 15 * max(2, math.ceil(len(a_['conditions']) / 60))
        r += 1
    ws.freeze_panes = 'A4'

    # ---- Synthèse (première feuille utile)
    ws = sheet('Synthèse', [52, 18, 18, 54])
    wb.move_sheet('Synthèse', offset=-(len(wb.sheetnames) - 2))
    ws['A1'] = 'Synthèse — tours A1 et A2'
    ws['A1'].font = f_title
    header(ws, 3, ['Indicateur', 'Valeur', 'Unité', 'Lecture'])
    lines = [
        ('Coût de travaux tour A1 (budget actualisé)', f"={COUT['A1']}", '€ HT', 'Budget objectif 2020 × BT01'),
        ('Coût de travaux tour A2 avec la variante', f"={COUT['A2']}", '€ HT', ''),
        ('Surcoût de la variante', f"={COUT['delta']}", '€ HT', 'Somme des postes de la feuille Coûts'),
        ('Surcoût par logement A2', f"={COUT['delta']}/{E['tours']['A2']['logements']}", '€ HT', ''),
        ('Surcoût par m² habitable A2', f"={COUT['delta']}/{E['tours']['A2']['shab']}", '€ HT/m²', ''),
        ('Gain d\'énergie annuel de la variante', f"={EXP['gain']}", '€ TTC/an', 'Méthode du jumeau'),
        ('Entretien supplémentaire', f"={EXP['maint']}", '€ HT/an', 'Hypothèses'),
        ('Bilan annuel (énergie − entretien)', f"={EXP['bilan']}", '€/an', 'Énergie économisée moins entretien supplémentaire'),
        ('CO₂ évité en exploitation', f"={EXP['co2']}/1000", 'tCO₂e/an', 'Chaleur du réseau à 0,034 kgCO₂e/kWh'),
        (f"Bilan cumulé sur {E['duree']} ans, surcoût déduit", f"={EXP['cum']}", '€', ''),
        (f"Coût global net sur {data['cycle']['annees']} ans", f"={CG['total']}", '€', 'Feuille Coût global : études, travaux, énergie, entretien, remplacements, fin de vie, aides (selon la case taxe foncière)'),
        ('dont énergie économisée par les locataires', f"={CG['loc']}", '€', ''),
        ('Taxe foncière évitée si l\'exonération est prolongée', f"={CG['tfpb']}", '€', 'Conditionnelle : seuils RE2020 2028 et certification'),
    ]
    for i, (a, f, u, n) in enumerate(lines, 4):
        put(ws, i, 1, a)
        put(ws, i, 2, f, fmt='#,##0.0' if 'tCO' in u else EUR if '€' in u else NUM, font=f_link)
        put(ws, i, 3, u)
        put(ws, i, 4, n, font=f_note, al=wrap)
    r = 4 + len(lines) + 1
    put(ws, r, 1, 'Points d\'attention', font=f_bb)
    r += 1
    for a in data['attention']:
        put(ws, r, 1, a['titre'], font=f_bb, al=wrap)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        c = ws.cell(row=r, column=2, value=a['texte'])
        c.font = f_b
        c.alignment = wrap
        ws.row_dimensions[r].height = 15 * max(2, math.ceil(len(a['texte']) / 95))
        r += 1

    # ---- Sources
    ws = sheet('Sources', [16, 70, 70, 60])
    ws['A1'] = 'Sources et hypothèses'
    ws['A1'].font = f_title
    header(ws, 3, ['Clé', 'Source', 'Référence', 'Lien'])
    r = 4
    for key, s in data['sources'].items():
        put(ws, r, 1, key)
        put(ws, r, 2, s['titre'], al=wrap)
        put(ws, r, 3, s['ref'], al=wrap)
        put(ws, r, 4, s.get('url', ''), font=f_note)
        r += 1
    wb.save(path)
    return EXP


# ------------------------------------------------------------------ PDF de synthèse
def build_pdf(data, D, path):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

    fonts = os.path.join(HERE, 'fonts')
    pdfmetrics.registerFont(TTFont('Archivo', os.path.join(fonts, 'Archivo-Regular.ttf')))
    pdfmetrics.registerFont(TTFont('Archivo-Bold', os.path.join(fonts, 'Archivo-Bold.ttf')))
    pdfmetrics.registerFont(TTFont('Stencil', os.path.join(fonts, 'BigShouldersStencilDisplay-ExtraBold.ttf')))
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily('Archivo', normal='Archivo', bold='Archivo-Bold', italic='Archivo', boldItalic='Archivo-Bold')

    G = colors.HexColor('#1e2428')
    AR = colors.HexColor('#56616a')
    TR = colors.HexColor('#cfd4d2')
    PK = colors.HexColor('#d1126f')
    BG = colors.HexColor('#f2f3f1')
    st = {
        'h1': ParagraphStyle('h1', fontName='Stencil', fontSize=26, leading=28, textColor=G, spaceAfter=4),
        'h2': ParagraphStyle('h2', fontName='Archivo-Bold', fontSize=13, leading=16, textColor=G, spaceBefore=10, spaceAfter=6),
        'p': ParagraphStyle('p', fontName='Archivo', fontSize=9, leading=12.5, textColor=G),
        'small': ParagraphStyle('s', fontName='Archivo', fontSize=7.5, leading=10, textColor=AR),
        'cell': ParagraphStyle('c', fontName='Archivo', fontSize=7.8, leading=10, textColor=G, alignment=TA_LEFT),
        'cellb': ParagraphStyle('cb', fontName='Archivo-Bold', fontSize=7.8, leading=10, textColor=G),
        'num': ParagraphStyle('n', fontName='Archivo', fontSize=7.8, leading=10, textColor=G, alignment=2),
        'kpi': ParagraphStyle('k', fontName='Archivo-Bold', fontSize=15, leading=18, textColor=G),
        'kpil': ParagraphStyle('kl', fontName='Archivo', fontSize=7.5, leading=9.5, textColor=AR),
    }

    def clean(t):
        t = str(t).replace('≈ ', 'env. ').replace('≈', 'env. ').replace('≥ ', 'mini ').replace('λ ', 'lambda ').replace(' → ', ' à ').replace('→', 'à')
        return t.replace('CO₂', 'CO<sub>2</sub>')

    def P(t, s='cell'):
        return Paragraph(clean(t), st[s])

    def fmt(v, d=0):
        if v is None or v == '':
            return '—'
        s = f'{v:,.{d}f}'.replace(',', ' ').replace('.', ',')
        return s

    def table(rows, widths, head=True, zebra=True):
        t = Table(rows, colWidths=widths, repeatRows=1 if head else 0)
        sty = [('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEBELOW', (0, 0), (-1, -1), 0.4, TR),
               ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3), ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4)]
        if head:
            sty += [('BACKGROUND', (0, 0), (-1, 0), G), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white)]
        t.setStyle(TableStyle(sty))
        return t

    def H(t):
        return Paragraph(clean(t), ParagraphStyle('th', fontName='Archivo-Bold', fontSize=7.8, leading=10, textColor=colors.white))

    def footer(canv, doc):
        canv.saveState()
        canv.setFont('Archivo', 7)
        canv.setFillColor(AR)
        canv.drawString(14 * mm, 8 * mm, f"Domaine de Fontbelleau — Comparatif tours A1 / A2 — document d'étude, coûts estimés par ratios, exploitation simulée (données fictives) — {data['genere']}")
        canv.drawRightString(doc.pagesize[0] - 14 * mm, 8 * mm, f'{doc.page}')
        canv.restoreState()

    doc = SimpleDocTemplate(path, pagesize=landscape(A4), leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=14 * mm,
                            title='Comparatif tours A1 / A2 — Domaine de Fontbelleau', author='Veck Construction — groupe MP2-BC1-P3')
    W = doc.width
    S = []
    S.append(P('Domaine de Fontbelleau · Lormont', 'small'))
    S.append(P('Comparatif des tours A1 et A2', 'h1'))
    S.append(P("Tour A1 : conception du DCE (RT 2012, COGEDIM, 70 logements). Tour A2 : variante RE2020 étudiée par le groupe et modélisée dans la maquette (CDC Habitat, 59 logements). "
               "Quantités issues de la maquette ; équipements de chauffage, ventilation et ECS du CCTP comptés même s'ils ne sont pas modélisés. Coûts estimés par ratios, exploitation issue de l'année 1 simulée du jumeau énergétique.", 'p'))
    S.append(Spacer(1, 8))
    E = data['exploitation']
    k = [(f"{fmt(D['delta'])} €", 'Surcoût de la variante (HT)', f"+{fmt(D['delta_pct'], 1)} % du coût de la tour"),
         (f"{fmt(D['delta_logement'])} €", 'Par logement de la tour A2 (HT)', f"{fmt(D['delta_m2'])} € HT/m² habitable"),
         (f"{fmt(D['gain_energie'])} €/an", 'Énergie économisée (TTC)', f"{fmt(D['gain_co2'] / 1000, 1)} tCO₂e évitées par an"),
         (f"{fmt(D['gain_net'])} €/an", 'Bilan énergie − entretien', 'Entretien : hypothèses à confirmer')]
    cells = [[[P(a, 'kpi'), P(b, 'kpil'), P(c, 'small')] for a, b, c in k]]
    t = Table(cells, colWidths=[W / 4] * 4)
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), BG), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEAFTER', (0, 0), (-2, -1), 3, colors.white),
                           ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8), ('LEFTPADDING', (0, 0), (-1, -1), 8)]))
    S.append(t)
    S.append(Spacer(1, 6))
    S.append(P('Points d\'attention', 'h2'))
    rows = [[H('Constat'), H('Explication')]] + [[P(a['titre'], 'cellb'), P(a['texte'])] for a in data['attention']]
    S.append(table(rows, [W * 0.28, W * 0.72]))
    S.append(PageBreak())

    S.append(P('Solutions lot par lot', 'h2'))
    lab = {'identique': 'Identique', 'modifie': 'Modifié', 'ajoute': 'Ajouté', 'supprime': 'Supprimé', 'programme': 'Programme'}
    rows = [[H('Lot'), H('Sujet'), H('Tour A1 — DCE'), H('Tour A2 — variante'), H('Écart')]]
    for L in data['lots']:
        for i, ln in enumerate(L['lignes']):
            rows.append([P(f"{L['lot']} · {L['nom']}" if i == 0 else '', 'cellb'), P(ln['theme']), P(ln['A1']), P(ln['A2']), P(lab[ln['ecart']], 'cellb')])
    S.append(table(rows, [W * 0.17, W * 0.15, W * 0.3, W * 0.3, W * 0.08]))
    S.append(PageBreak())

    S.append(P('Quantités', 'h2'))
    rows = [[H('Groupe'), H('Ouvrage / équipement'), H('Unité'), H('A1'), H('A2'), H('Origine A1'), H('Origine A2'), H('Note')]]
    prev = None
    for q in data['quantites']:
        d = 1 if q['unite'] == 'm³' else 0
        rows.append([P(q['groupe'] if q['groupe'] != prev else '', 'cellb'), P(q['item']), P(q['unite']), P(fmt(q['A1'], d), 'num'), P(fmt(q['A2'], d), 'num'),
                     P(FIAB[q['f1']]), P(FIAB[q['f2']]), P(q['note'], 'small')])
        prev = q['groupe']
    S.append(table(rows, [W * 0.11, W * 0.27, W * 0.05, W * 0.07, W * 0.07, W * 0.1, W * 0.1, W * 0.23]))
    S.append(PageBreak())

    C = data['couts']
    S.append(P('Coûts de travaux', 'h2'))
    S.append(P(f"Budget objectif du dossier (23/04/2020, colonne « tour A1 » = 50 % de chaque lot) actualisé par l'index BT01 ({C['bt01']['base']} en {C['bt01']['base_mois']}, {C['bt01']['actuel']} en {C['bt01']['actuel_mois']} : × {fmt(C['bt01']['coef'], 3)}). "
               "Écarts de la variante chiffrés par ratios, en € HT valeur 2026. Les prix unitaires se modifient dans le classeur Excel et sur la page web.", 'p'))
    S.append(Spacer(1, 4))
    rows = [[H('Lot'), H('Poste'), H('Quantité'), H('PU € HT'), H('Montant € HT'), H('Origine'), H('Justification')]]
    for p in C['postes']:
        src = '; '.join(SOURCES[s]['titre'] for s in p['src'])
        rows.append([P(p['lot']), P(p['poste']), P(f"{fmt(p['qte'], 1 if p['unite'] == 'm³' else 0)} {p['unite']}", 'num'), P(fmt(p['pu']), 'num'),
                     P(fmt(p['qte'] * p['pu']), 'num'), P(FIAB[p['fiab']]), P((p['note'] + (' — ' + src if src else '')).strip(' —'), 'small')])
    rows.append([P(''), P('Total des écarts', 'cellb'), P(''), P(''), P(fmt(D['delta']), 'num'), P(''), P('')])
    S.append(table(rows, [W * 0.05, W * 0.27, W * 0.1, W * 0.07, W * 0.09, W * 0.09, W * 0.33]))
    S.append(Spacer(1, 6))
    coef = BT01['actuel'] / BT01['base']
    dl = collections.Counter()
    for p in C['postes']:
        dl[p['lot']] += p['qte'] * p['pu']
    rows = [[H('Lot'), H('Intitulé'), H('Tour A1 2020'), H('Tour A1 2026'), H('Écart variante'), H('Tour A2 2026')]]
    for b in C['budget']:
        a = b['A1_2020'] * coef
        rows.append([P(b['lot']), P(b['nom']), P(fmt(b['A1_2020']), 'num'), P(fmt(a), 'num'), P(fmt(dl[b['lot']]) if dl[b['lot']] else '—', 'num'), P(fmt(a + dl[b['lot']]), 'num')])
    tot = sum(b['A1_2020'] for b in C['budget'])
    rows.append([P(''), P('Total', 'cellb'), P(fmt(tot), 'num'), P(fmt(tot * coef), 'num'), P(fmt(D['delta']), 'num'), P(fmt(tot * coef + D['delta']), 'num')])
    S.append(KeepTogether([P('Budget par lot et par tour (€ HT)', 'h2'), table(rows, [W * 0.07, W * 0.33, W * 0.15, W * 0.15, W * 0.15, W * 0.15])]))
    S.append(Spacer(1, 6))
    rows = [[H('Piste à étudier (non incluse)'), H('Quantité'), H('PU € HT'), H('Montant € HT'), H('Note')]]
    for p in C['pistes']:
        rows.append([P(p['poste']), P(f"{fmt(p['qte'])} {p['unite']}", 'num'), P(fmt(p['pu']), 'num'), P(fmt(p['qte'] * p['pu']), 'num'), P(p['note'], 'small')])
    S.append(KeepTogether([table(rows, [W * 0.35, W * 0.1, W * 0.08, W * 0.1, W * 0.37])]))
    S.append(PageBreak())

    S.append(P('Exploitation et carbone (année 1 simulée)', 'h2'))
    T = E['tours']
    pr = E['prix']

    def per(z, key):
        return T[z][key] / T[z]['shab']
    rows = [[H('Poste'), H('A1 kWh/an'), H('A2 kWh/an'), H('A1 kWh/m²'), H('A2 kWh/m²')]]
    for key, lab_ in [('chauffage', 'Chauffage livré'), ('ecs', 'Eau chaude livrée'), ('solaire', 'Production solaire'), ('pertes', 'Pertes de distribution'),
                      ('reseau', 'Chaleur achetée au réseau'), ('ventilation', 'Électricité de ventilation'), ('ascenseurs', 'Ascenseurs'), ('eclairage', 'Éclairage des communs'), ('auxiliaires', 'Auxiliaires')]:
        rows.append([P(lab_), P(fmt(T['A1'][key]), 'num'), P(fmt(T['A2'][key]), 'num'), P(fmt(per('A1', key), 1), 'num'), P(fmt(per('A2', key), 1), 'num')])
    S.append(table(rows, [W * 0.32, W * 0.17, W * 0.17, W * 0.17, W * 0.17]))
    S.append(Spacer(1, 6))
    rows = [[H('Élément de la variante'), H('Chaleur évitée kWh/an'), H('Électricité kWh/an'), H('Gain € TTC/an'), H('Gain kgCO₂e/an'), H('Note')]]
    for g in E['gains']:
        rows.append([P(g['poste']), P(fmt(g['chaleur']), 'num'), P(fmt(g['elec']), 'num'), P(fmt(D['gains_eur'][g['id']]), 'num'), P(fmt(D['gains_co2'][g['id']]), 'num'), P(g.get('note', ''), 'small')])
    rows.append([P('Total', 'cellb'), P(''), P(''), P(fmt(D['gain_energie']), 'num'), P(fmt(D['gain_co2']), 'num'), P('')])
    S.append(KeepTogether([P('Gain annuel par élément', 'h2'), table(rows, [W * 0.25, W * 0.13, W * 0.12, W * 0.1, W * 0.1, W * 0.3])]))
    S.append(Spacer(1, 6))
    rows = [[H('Entretien (hypothèses)'), H('A1 € HT/an'), H('A2 € HT/an'), H('Note')]]
    for m in E['maintenance']:
        rows.append([P(m['poste']), P(fmt(m['A1']), 'num'), P(fmt(m['A2']), 'num'), P(m['note'], 'small')])
    S.append(KeepTogether([table(rows, [W * 0.3, W * 0.1, W * 0.1, W * 0.5])]))
    S.append(Spacer(1, 6))
    rows = [[H('Carbone de construction (indicatif)'), H('Valeur'), H('Note')]]
    for c in E['construction']:
        rows.append([P(c['poste']), P(f"{fmt(c['valeur'], 1)} tCO₂e" if c['valeur'] is not None else 'à chiffrer', 'num'), P(c['note'], 'small')])
    S.append(KeepTogether([table(rows, [W * 0.35, W * 0.12, W * 0.53])]))
    S.append(Spacer(1, 6))
    S.append(P(f"Prix : chaleur {fmt(pr['prix_chaleur'], 2)} € TTC/MWh, électricité {fmt(pr['prix_elec'], 4)} € TTC/kWh. CO₂ : chaleur {fmt(pr['co2_chaleur'], 3)}, électricité {fmt(pr['co2_elec'], 3)} kgCO₂e/kWh. {E['note']}", 'small'))
    S.append(PageBreak())

    Cy = data['cycle']
    cg, cgt = D['cycle'], D['cycle_tfpb']
    S.append(P(f"Coût global sur {Cy['annees']} ans", 'h2'))
    S.append(P(Cy['note'], 'p'))
    S.append(Spacer(1, 6))
    k = [(f"{'+' if cg['total'] > 0 else '−'}{fmt(abs(cg['total']))} €", 'Coût global net de la variante, sans aide', 'Pas remboursée en 50 ans' if cg['retour'] is None else f"Remboursée en {cg['retour']} ans"),
         (f"{fmt(cg['totaux']['conception'] + cg['totaux']['travaux'])} €", 'Études et travaux (bailleur, TVA comprise)', f"TVA {fmt(Cy['params']['tva'], 1)} %"),
         (f"{fmt(-cg['totaux']['energie'])} €", 'Énergie économisée sur 50 ans', 'Par les locataires (charges)'),
         (f"{'+' if cgt['total'] > 0 else '−'}{fmt(abs(cgt['total']))} €", 'Avec la taxe foncière prolongée', f"{fmt(cgt['tfpb_potentiel'])} € évités, si conditions remplies")]
    cells = [[[P(a, 'kpi'), P(b, 'kpil'), P(c, 'small')] for a, b, c in k]]
    t = Table(cells, colWidths=[W / 4] * 4)
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), BG), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LINEAFTER', (0, 0), (-2, -1), 3, colors.white),
                           ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8), ('LEFTPADDING', (0, 0), (-1, -1), 8)]))
    S.append(t)
    S.append(Spacer(1, 6))
    T_ = cg['totaux']
    steps = sorted({t_ for rp in Cy['remplacements'] for t_ in range(rp['duree'], Cy['annees'], rp['duree'])})
    rows = [[H('Poste'), H('Quand'), H('Qui paie'), H('Sur 50 ans')],
            [P('Études (honoraires sur le surcoût et études propres à la variante)'), P('Avant les travaux'), P('Bailleur'), P(fmt(T_['conception']), 'num')],
            [P('Travaux (surcoût de la variante)'), P('Construction'), P('Bailleur'), P(fmt(T_['travaux']), 'num')],
            [P('Énergie économisée'), P('Chaque année'), P('Locataires'), P(fmt(T_['energie']), 'num')],
            [P('Entretien supplémentaire'), P('Chaque année'), P('Bailleur (en partie dans les charges)'), P(fmt(T_['entretien']), 'num')],
            [P('Remplacements'), P('Années ' + ', '.join(map(str, steps))), P('Bailleur'), P(fmt(T_['remplacements']), 'num')],
            [P('Fin de vie'), P(f"Année {Cy['annees']}"), P('Bailleur'), P(fmt(T_['fin']), 'num')],
            [P('Aides acquises'), P('—'), P('—'), P(fmt(T_['aides']), 'num')],
            [P('Coût global net', 'cellb'), P(''), P(f"Bailleur {fmt(cg['bailleur'])} · locataires {fmt(cg['locataires'])}"), P(fmt(cg['total']), 'num')]]
    S.append(KeepTogether([table(rows, [W * 0.45, W * 0.2, W * 0.2, W * 0.15])]))
    S.append(Spacer(1, 6))
    rows = [[H('Aide'), H('Statut'), H('Conditions'), H('Montant')]]
    for a_ in Cy['aides']:
        m = f"{fmt(cgt['tfpb_potentiel'])} € (années 26 à 30)" if a_['id'] == 'tfpb' else ('0 €' if a_.get('montant') == 0 else '—')
        src = '; '.join(SOURCES[x]['titre'] for x in a_['src'])
        rows.append([P(a_['titre'], 'cellb'), P(a_['statut']), P(a_['conditions'] + ' — ' + src, 'small'), P(m, 'num')])
    S.append(KeepTogether([P('Aides financières et fiscales', 'h2'), table(rows, [W * 0.2, W * 0.1, W * 0.55, W * 0.15])]))
    S.append(Spacer(1, 6))
    rows = [[H('Remplacement'), H('Durée de vie'), H('A1 € HT'), H('A2 € HT'), H('Note')]]
    for rp in Cy['remplacements']:
        rows.append([P(rp['poste']), P(f"{rp['duree']} ans", 'num'), P(fmt(rp['A1']), 'num'), P(fmt(rp['A2']), 'num'), P(rp['note'] + ' — ' + '; '.join(SOURCES[x]['titre'] for x in rp['src']), 'small')])
    for f in Cy['fin_de_vie']:
        rows.append([P('Fin de vie : ' + f['poste']), P(f"année {Cy['annees']}", 'num'), P(''), P(fmt(f['qte'] * f['pu']), 'num'), P(f"{fmt(f['qte'], 1 if f['unite'] == 'm³' else 0)} {f['unite']} × {fmt(f['pu'])} € HT. {f['note']}", 'small')])
    S.append(KeepTogether([P('Remplacements et fin de vie', 'h2'), table(rows, [W * 0.3, W * 0.1, W * 0.1, W * 0.1, W * 0.4])]))
    S.append(PageBreak())

    S.append(P('Sources et hypothèses', 'h2'))
    S.append(P("Règle de comptage : pour la tour A1, les équipements de chauffage, ventilation et ECS prévus au CCTP sont comptés même s'ils ne sont pas modélisés (« CCTP, non modélisé ») ; pour la tour A2, ce sont les éléments de la variante. "
               "Les dénombrements par pièce (radiateurs, bouches, entrées d'air) suivent les plans CVC des logements types appliqués aux typologies.", 'small'))
    S.append(Spacer(1, 4))
    rows = [[H('Source'), H('Référence'), H('Lien')]]
    for key, s in data['sources'].items():
        rows.append([P(s['titre']), P(s['ref'], 'small'), P(s.get('url', ''), 'small')])
    S.append(table(rows, [W * 0.38, W * 0.37, W * 0.25]))
    doc.build(S, onFirstPage=footer, onLaterPages=footer)


# ------------------------------------------------------------------ main
def main():
    els = load_model()
    rows = load_rows()
    fond = fondations_par_tour(els)
    fronts = balcons_fronts(els)
    logs = json.load(open(os.path.join(ROOT, 'data', 'energie', 'logements.json'), encoding='utf-8'))['logements']
    Q, k = quantites(rows, fond, fronts, logs)
    C = couts(k)
    E = exploitation(k)
    for z in ('A1', 'A2'):
        k['vent_' + z] = E['tours'][z]['ventilation'] / E['tours'][z]['shab']
    D = defaults(C, E)
    Cy = cycle(C, E)
    D['cycle'] = cycle_totals(Cy, D, E)
    D['cycle_tfpb'] = cycle_totals(Cy, D, E, {'tfpb': True})
    data = {
        'schema': 1, 'genere': TODAY,
        'tours': {'A1': {'nom': 'Tour A1 — COGEDIM', 'conception': 'DCE — RT 2012', 'logements': k['n1'], 'shab': round(k['shab']['A1'], 1), 'typologies': k['typ']['A1']},
                  'A2': {'nom': 'Tour A2 — CDC Habitat', 'conception': 'Variante RE2020 du groupe', 'logements': k['n2'], 'shab': round(k['shab']['A2'], 1), 'typologies': k['typ']['A2']}},
        'typologies': TYPO, 'fiab': FIAB, 'sources': SOURCES,
        'lots': lots(k), 'quantites': Q, 'couts': C, 'exploitation': E, 'cycle': Cy, 'defauts': D, 'attention': attention(k, D),
        'documents': [
            {'titre': 'Classeur Excel', 'detail': 'Quantités, coûts et exploitation avec formules ; hypothèses modifiables', 'fichier': f'docs/{BASE_NAME}.xlsx'},
            {'titre': 'Synthèse PDF', 'detail': 'Format A4 paysage, à joindre au rapport', 'fichier': f'docs/{BASE_NAME}.pdf'},
        ],
    }
    cg, cgt = D['cycle'], D['cycle_tfpb']
    eur = lambda v: f'{abs(v):,.0f}'.replace(',', '\u202f') + ' €'
    data['attention'].insert(1, {'niveau': 'fort', 'titre': 'Sur 50 ans, l\'énergie ne rembourse pas la variante ; la taxe foncière pourrait le faire',
        'texte': f"En coût global sur 50 ans (études, travaux, énergie, entretien, remplacements et fin de vie), la variante coûte {eur(cg['total'])} de {'plus' if cg['total'] > 0 else 'moins'} que la conception du DCE : "
                 f"les locataires économisent {eur(-cg['locataires'])} d'énergie, le bailleur dépense {eur(cg['bailleur'])} de plus. "
                 f"Les CEE ne s'appliquent pas en construction neuve et le Fonds Chaleur solaire est fermé depuis le 4 novembre 2026. "
                 f"Seule l'exonération de taxe foncière prolongée de 25 à 30 ans (si la tour A2 atteint les seuils RE2020 de 2028 et obtient une certification) change le bilan : "
                 f"{eur(cgt['tfpb_potentiel'])} de taxe évitée, et la variante {'coûte encore ' + eur(cgt['total']) + ' de plus' if cgt['total'] > 0 else 'rapporte ' + eur(cgt['total'])} sur 50 ans."})
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(',', ':'))
    build_xlsx(data, os.path.join(OUT_DIR, BASE_NAME + '.xlsx'))
    build_pdf(data, D, os.path.join(OUT_DIR, BASE_NAME + '.pdf'))
    print(json.dumps(D, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
