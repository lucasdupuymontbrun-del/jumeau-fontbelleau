// Jumeau énergétique du Domaine de Fontbelleau : données, indicateurs, frise, détail, alertes, coût global.
import { createTwin } from './energie3d.js';

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const bind = (k) => $(`[data-bind="${k}"]`);
const SVGNS = 'http://www.w3.org/2000/svg';
function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') n.className = v; else if (k === 'text') n.textContent = v; else if (k === 'html') n.innerHTML = v;
    else if (k === 'style' && typeof v === 'object') { for (const [sk, sval] of Object.entries(v)) { if (sk.startsWith('--')) n.style.setProperty(sk, sval); else n.style[sk] = sval; } }
    else if (k.startsWith('on')) n.addEventListener(k.slice(2), v); else n.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) n.append(c.nodeType ? c : document.createTextNode(String(c)));
  return n;
}
function sv(tag, attrs = {}, ...kids) {
  const n = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) n.setAttribute(k, v);
  for (const c of kids.flat()) if (c != null) n.append(c.nodeType ? c : document.createTextNode(String(c)));
  return n;
}
const icon = (id, cls = 'ico') => { const s = sv('svg', { class: cls, 'aria-hidden': 'true' }); s.append(sv('use', { href: `#${id}` })); return s; };
const nf = (d = 0) => new Intl.NumberFormat('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d });
const fmt = (v, d = 0) => (v == null || !isFinite(v) ? '—' : nf(d).format(v));
const MOIS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
const MOIS_L = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
const reduceMotion = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const USAGE = {
  chauffage: { key: 'h', label: 'Chauffage', unit: 'kWh', icon: 'i-flame', css: '--s-chauffage', hex: '#d95926', ramp: ['#170904', '#3d1606', '#7a2c0c', '#c24a17', '#e8742c', '#f7a052'] },
  ecs: { key: 'e', label: 'Eau chaude', unit: 'kWh', icon: 'i-shower', css: '--s-ecs', hex: '#3987e5', ramp: ['#050c16', '#0d2343', '#164a8c', '#2a78d6', '#5598e7', '#86b6ef'] },
  eau: { key: 'w', label: 'Eau', unit: 'L', icon: 'i-drop', css: '--s-eau', hex: '#199e70', ramp: ['#03110c', '#072c1c', '#0d573d', '#168c63', '#28b583', '#6fd8af'] },
  elec: { key: 'p', label: 'Électricité', unit: 'kWh', icon: 'i-bolt', css: '--s-elec', hex: '#c98500', ramp: ['#120c02', '#332103', '#6b4600', '#ad7200', '#d99a12', '#f0c050'] },
};
const DIVERGE = ['#3987e5', '#2f5c93', '#3a3f45', '#93453f', '#e66767'];
const STATUS = { critique: { c: '#d03b3b', icon: 'i-octagon', label: 'Critique' }, serieuse: { c: '#ec835a', icon: 'i-alert', label: 'Importante' }, attention: { c: '#fab219', icon: 'i-info', label: 'À surveiller' } };
const LIGHTS = {
  ok: { c: '#34b27b', k: 0.6, label: 'Normal', note: 'comme des logements semblables' },
  plus: { c: '#f2a33a', k: 0.88, label: 'Un peu trop', note: '20 à 30 % de plus' },
  trop: { c: '#ef4d55', k: 1, label: 'Beaucoup trop', note: 'plus de 30 % de plus' },
  vide: { c: '#4a545c', k: 0.12, label: 'Pas encore habité', note: '' },
};
const ORIENT = { N: 'nord', NE: 'nord-est', E: 'est', SE: 'sud-est', S: 'sud', SO: 'sud-ouest', O: 'ouest', NO: 'nord-ouest' };
const etageLabel = (n) => (n === 1 ? '1er étage' : `${n}e étage`);
const PRIX_K = { h: 'prix_chaleur', e: 'prix_chaleur', w: 'prix_eau', p: 'prix_elec' };
const euros = (k, v) => (k === 'h' || k === 'e' ? v / 1000 * S.hyp.prix_chaleur : k === 'w' ? v / 1000 * S.hyp.prix_eau : v * S.hyp.prix_elec);
const PASSEPORT = 'https://lucasdupuymontbrun-del.github.io/passeport-fontbelleau/';
const fiche = (ref) => `${PASSEPORT}o/?r=${encodeURIComponent(ref)}#energie`;
const TYPE_ICON = { chauffage: 'i-flame', eau: 'i-drop', donnees: 'i-wifi-off', reseau: 'i-network', ventilation: 'i-fan' };
const FAMILLE = { menuiserie_ext: 'Menuiserie', ecaille: 'Écaille', garde_corps: 'Garde-corps', dalle: 'Dalle', voile: 'Voile', premur: 'Prémur', cloison: 'Cloison', porte_int: 'Porte', finition: 'Finition', fermeture: 'Fermeture', poutre: 'Poutre', poteau: 'Poteau' };

const S = {
  J: null, L: [], byId: new Map(), series: null, ouv: null, days: [], N: 0, ND: 0,
  usage: 'chauffage', color: 'statut', period: 'mois', day: 112, tab: 'etat', tower: 'ALL', floor: 0, sel: null, special: null,
  playing: false, twin: null, scale: {}, hyp: {}, index: null,
};

// ------------------------------------------------------------------ données
function prefix(arr) { const p = new Float64Array(arr.length + 1); for (let i = 0; i < arr.length; i++) p[i + 1] = p[i] + arr[i]; return p; }
function prepare(J, LG, SE, OU) {
  S.J = J; S.L = LG.logements; S.N = S.L.length; S.ND = J.periode.jours; S.ouv = OU;
  const d0 = new Date(J.periode.debut + 'T12:00:00');
  S.days = Array.from({ length: S.ND }, (_, i) => new Date(d0.getTime() + i * 86400000));
  S.L.forEach((l, i) => {
    S.byId.set(l.id, l); l.i = i;
    const raw = SE[l.id];
    l.miss = new Uint8Array(S.ND);
    const fill = (a, k) => {
      const out = new Float64Array(S.ND);
      for (let d = 0; d < S.ND; d++) {
        if (a[d] < 0) {
          l.miss[d] = 1;
          // estimation : référence × rapport habituel (chauffage), moyenne des 14 jours précédents (autres usages)
          if (k === 'h') {
            let s = 0, r = 0; for (let j = Math.max(0, d - 60); j < d; j++) if (a[j] >= 0) { s += a[j]; r += raw.r[j]; }
            out[d] = raw.r[d] * (r > 0 ? s / r : 1);
          } else { let s = 0, n = 0; for (let j = Math.max(0, d - 14); j < d; j++) if (a[j] >= 0) { s += a[j]; n++; } out[d] = n ? s / n : 0; }
        } else out[d] = a[d];
      }
      return out;
    };
    const scale = { h: 0.1, e: 0.1, w: 1, p: 0.1, r: 0.1 };
    l.d = {};
    for (const k of ['h', 'e', 'w', 'p', 'r']) {
      const f = fill(raw[k], k);
      for (let d = 0; d < S.ND; d++) f[d] *= scale[k];
      l.d[k] = f; l['P' + k] = prefix(f);
    }
  });
  // séries des tours
  for (const z of ['A1', 'A2']) {
    const T = J.tours[z].jour;
    T.elec_priv = Array.from({ length: S.ND }, (_, d) => S.L.filter(l => l.tour === z).reduce((s, l) => s + l.d.p[d], 0));
    T.sg = T.ventilation.map((v, d) => v + T.ascenseurs[d] + T.eclairage[d] + T.auxiliaires[d]);
    T.P = {};
    for (const k of Object.keys(T)) if (Array.isArray(T[k])) T.P[k] = prefix(T[k]);
  }
  for (const [k, h] of Object.entries(J.hypotheses)) S.hyp[k] = h.valeur;
  // ouvrage → indice de logement (vitrages)
  S.index = new Map();
  for (const [ref, rec] of Object.entries(OU.ouvrages)) if (rec.l && rec.l.length === 1) S.index.set(ref, S.byId.get(rec.l[0])?.i);
  // échelles d'intensité (95e centile) par usage et par période
  for (const [u, U] of Object.entries(USAGE)) {
    const k = U.key;
    const an = S.L.map(l => l['P' + k][S.ND] / l.shab).sort((a, b) => a - b);
    const mo = [], dy = [];
    for (const l of S.L) {
      for (const [a, b] of monthRanges()) mo.push((l['P' + k][b + 1] - l['P' + k][a]) / l.shab);
      for (let d = 6; d < S.ND; d += 3) dy.push((l['P' + k][d + 1] - l['P' + k][d - 6]) / 7 / l.shab);
    }
    mo.sort((a, b) => a - b); dy.sort((a, b) => a - b);
    const q = (arr, p) => arr[Math.min(arr.length - 1, Math.floor(p * arr.length))];
    S.scale[u] = { an: q(an, 0.96), mois: q(mo, 0.97), jour: q(dy, 0.975) };
  }
}
let _mr = null;
function monthRanges() {
  if (_mr) return _mr;
  _mr = []; let s = 0;
  for (let d = 1; d <= S.ND; d++) {
    if (d === S.ND || S.days[d].getMonth() !== S.days[s].getMonth()) { _mr.push([s, d - 1]); s = d; }
  }
  return _mr;
}
function monthOf(day) { return monthRanges().findIndex(([a, b]) => day >= a && day <= b); }
function range() {
  if (S.period === 'an') return [0, S.ND - 1];
  if (S.period === 'mois') return monthRanges()[monthOf(S.day)];
  return [Math.max(0, S.day - 6), S.day];
}
const sumL = (l, k, a, b) => l['P' + k][b + 1] - l['P' + k][a];
const sumT = (z, k, a, b) => S.J.tours[z].jour.P[k][b + 1] - S.J.tours[z].jour.P[k][a];
function fmtDay(d, long = false) { const x = S.days[d]; return long ? `${x.getDate()} ${MOIS_L[x.getMonth()]} ${x.getFullYear()}` : `${x.getDate()} ${MOIS[x.getMonth()]} ${x.getFullYear()}`; }
function dayIndex(iso) { return Math.round((new Date(iso + 'T12:00:00') - S.days[0]) / 86400000); }
function periodLabel() {
  if (S.period === 'an') return 'Toute l\'année';
  if (S.period === 'mois') { const [a] = range(); const x = S.days[a]; return `${MOIS_L[x.getMonth()]} ${x.getFullYear()}`; }
  return 'Moyenne des 7 derniers jours';
}
function monthName(day = S.day) { const x = S.days[day]; const m = MOIS_L[x.getMonth()]; return `${m[0].toUpperCase()}${m.slice(1)} ${x.getFullYear()}`; }

// ------------------------------------------------------------------ couleurs
function hex2rgb(h) { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
function rampAt(ramp, t) {
  t = Math.max(0, Math.min(1, t)) * (ramp.length - 1);
  const i = Math.min(ramp.length - 2, Math.floor(t)), f = t - i;
  const a = hex2rgb(ramp[i]), b = hex2rgb(ramp[i + 1]);
  return a.map((v, k) => Math.round(v + (b[k] - v) * f));
}
function valueOf(l, u = S.usage) {
  const [a, b] = range(); const k = USAGE[u].key;
  const v = sumL(l, k, a, b) / l.shab;
  return S.period === 'jour' ? v / (b - a + 1) : v;
}
function occupied(l) { const [, b] = range(); return dayIndex(l.emmenagement) <= b; }
function ecartOf(l, u = S.usage) {
  const [a, b] = range();
  if (u === 'chauffage') { const r = sumL(l, 'r', a, b); return r > 0.5 ? sumL(l, 'h', a, b) / r - 1 : 0; }
  // eau et eau chaude : par occupant et par jour de présence, comparées à la médiane de la tour ;
  // électricité : par jour de présence, comparée aux logements de la tour qui ont le même nombre d'occupants
  const k = USAGE[u].key, perOcc = u !== 'elec';
  const rate = (x) => { const d = b - Math.max(a, dayIndex(x.emmenagement)) + 1; return d > 0 ? sumL(x, k, a, b) / (perOcc ? x.occupants : 1) / d : 0; };
  const key = `${u}|${l.tour}|${perOcc ? '' : l.occupants}|${a}|${b}`;
  const cache = S._med || (S._med = new Map());
  if (!cache.has(key)) {
    const vals = S.L.filter(x => x.tour === l.tour && occupied(x) && (perOcc || x.occupants === l.occupants)).map(rate).sort((p, q) => p - q);
    cache.set(key, vals[Math.floor(vals.length / 2)]);
  }
  const med = cache.get(key);
  return med > 0 ? rate(l) / med - 1 : 0;
}
function lightOf(l, u = S.usage) {
  if (!occupied(l)) return 'vide';
  const e = ecartOf(l, u);
  return e > 0.30 ? 'trop' : e > 0.20 ? 'plus' : 'ok';
}
function visible(l) { return (S.tower === 'ALL' || l.tour === S.tower); }
function paint() {
  if (!S.twin) return;
  const arr = new Uint8Array(S.N * 4);
  const U = USAGE[S.usage];
  const vmax = S.scale[S.usage][S.period];
  for (const l of S.L) {
    let rgb, k;
    if (!visible(l)) { rgb = [0, 0, 0]; k = 0; }
    else if (S.color === 'statut') {
      const g = LIGHTS[lightOf(l)]; rgb = hex2rgb(g.c); k = g.k;
    } else if (S.color === 'intensite') {
      const t = Math.pow(Math.min(1.15, valueOf(l) / vmax), 0.9);
      rgb = rampAt(U.ramp, 0.12 + 0.88 * Math.min(1, t)); k = Math.min(1, t);
    } else {
      const e = ecartOf(l);
      const t = Math.max(-1, Math.min(1, e / 0.4));
      rgb = rampAt(DIVERGE, (t + 1) / 2); k = 0.25 + 0.75 * Math.abs(t);
    }
    if (S.floor && l.etage !== S.floor) { rgb = rgb.map(v => v * 0.22); k *= 0.25; }
    const o = l.i * 4;
    arr[o] = rgb[0]; arr[o + 1] = rgb[1]; arr[o + 2] = rgb[2]; arr[o + 3] = Math.round(k * 255);
  }
  S.twin.setColors(arr);
  renderLegend();
}
function renderLegend() {
  const U = USAGE[S.usage];
  const box = bind('legend'); box.textContent = '';
  if (S.color === 'statut') {
    const [a, b] = range();
    const vide = S.L.some(l => visible(l) && !occupied(l));
    box.classList.add('is-lights');
    box.append(el('span', { class: 'lr-title', text: `${U.label}, comparé à des logements semblables` }));
    const g4 = el('span', { class: 'lr-grid' });
    for (const g of ['ok', 'plus', 'trop', ...(vide ? ['vide'] : [])]) {
      const L = LIGHTS[g];
      g4.append(el('span', { class: 'lr-row' }, el('i', { style: { background: L.c, color: L.c } }), el('b', { text: L.label })));
    }
    box.append(g4);
    return;
  }
  box.classList.remove('is-lights');
  const unit = S.usage === 'eau' ? 'L/m²' : 'kWh/m²';
  const vmax = S.scale[S.usage][S.period];
  const d = vmax < 1 ? 2 : vmax < 10 ? 1 : 0;
  box.append(el('span', { class: 'lr-title', text: `${U.label}, ${unit}${S.period === 'jour' ? ' par jour' : ''}` }),
    el('span', { class: 'lr-bar', style: { background: `linear-gradient(90deg, ${U.ramp.slice(1).join(',')})` } }),
    el('span', { class: 'lr-ticks' }, el('span', { text: '0' }), el('span', { text: fmt(vmax / 2, d) }), el('span', { text: `≥ ${fmt(vmax, d)}` })));
}

// ------------------------------------------------------------------ indicateurs
function scopeTowers() { return S.tower === 'ALL' ? ['A1', 'A2'] : [S.tower]; }
function totals(towers, a, b) {
  const H = S.hyp;
  let reseau = 0, priv = 0, sg = 0, eau = 0, shab = 0, nlog = 0, mta = 0, pers = 0;
  for (const z of towers) {
    reseau += sumT(z, 'reseau', a, b); sg += sumT(z, 'sg', a, b); priv += sumT(z, 'elec_priv', a, b); mta += sumT(z, 'mta', a, b);
    const L = S.L.filter(l => l.tour === z);
    eau += L.reduce((s, l) => s + sumL(l, 'w', a, b), 0) / 1000;
    shab += S.J.tours[z].shab; nlog += L.length; pers += L.reduce((s, l) => s + l.occupants, 0);
  }
  const nd = b - a + 1;
  const elec = priv + sg;
  const cout = reseau / 1000 * H.prix_chaleur + elec * H.prix_elec + nlog * H.abo_elec * nd / 366 + eau * H.prix_eau;
  const co2 = reseau * H.co2_chaleur + elec * H.co2_elec;
  return { reseau, elec, priv, sg, eau, shab, nlog, cout, co2, mta, pers, nd };
}
function renderKpis() {
  const [a, b] = range();
  const t = totals(scopeTowers(), a, b);
  // feu tricolore : nombre de logements par couleur
  const L = S.L.filter(visible);
  const n = { ok: 0, plus: 0, trop: 0, vide: 0 };
  for (const l of L) n[lightOf(l)]++;
  const U = USAGE[S.usage];
  const quand = S.period === 'an' ? 'Sur l\'année' : S.period === 'mois' ? `En ${periodLabel()}` : `Autour du ${fmtDay(S.day)}`;
  const pb = n.plus + n.trop;
  const usageTxt = S.usage === 'chauffage' ? 'de chauffage' : S.usage === 'ecs' ? 'd\'eau chaude' : S.usage === 'eau' ? 'd\'eau' : 'd\'électricité';
  bind('state-line').textContent = pb === 0
    ? `${quand}, les ${n.ok} logements habités ont une consommation ${usageTxt} normale.`
    : `${quand} : ${n.ok} logement${n.ok > 1 ? 's' : ''} ${n.ok > 1 ? 'normaux' : 'normal'}, ${pb} consomme${pb > 1 ? 'nt' : ''} trop ${usageTxt}.`;
  const lights = bind('lights'); lights.textContent = '';
  for (const g of ['ok', 'plus', 'trop', ...(n.vide ? ['vide'] : [])]) {
    const G = LIGHTS[g];
    lights.append(el('div', { class: 'light', style: { '--lc': G.c } }, el('i'), el('span', { class: 'lt-l' }, el('b', { text: G.label }), G.note ? el('small', { text: G.note }) : null), el('span', { class: 'lt-n', text: String(n[g]) })));
  }
  const box = bind('kpis'); box.textContent = '';
  const tile = (l, v, u, s) => el('div', { class: 'kpi' }, el('span', { class: 'kpi-l', text: l }), el('span', { class: 'kpi-v' }, v, el('small', { text: u })), s ? el('span', { class: 'kpi-s', text: s }) : null);
  box.append(
    tile('Facture énergie et eau', t.cout > 10000 ? fmt(t.cout / 1000, 1) : fmt(t.cout), t.cout > 10000 ? 'k€' : '€', `≈ ${fmt(t.cout / t.nlog)} € par logement`),
    tile('Chaleur achetée', t.reseau > 20000 ? fmt(t.reseau / 1000, 1) : fmt(t.reseau), t.reseau > 20000 ? 'MWh' : 'kWh', `≈ ${fmt(t.reseau / 1000 * S.hyp.prix_chaleur)} € au réseau de chaleur`),
  );
  bind('date-mode').textContent = '';
}
function variantGain() {
  const J = S.J, H = S.hyp, last = S.ND - 1;
  const sh2 = J.tours.A2.shab, sh1 = J.tours.A1.shab;
  const heat = (z) => S.L.filter(l => l.tour === z).reduce((s, l) => s + sumL(l, 'h', 0, last), 0);
  const dHeat = (heat('A1') / sh1 - heat('A2') / sh2) * sh2;
  const solar = sumT('A2', 'solaire', 0, last);
  const dVent = (sumT('A2', 'ventilation', 0, last) / sh2 - sumT('A1', 'ventilation', 0, last) / sh1) * sh2;
  const heatKwh = (dHeat + solar) * (1 + J.calage.pertes_distribution.A2);
  return { eur: heatKwh / 1000 * H.prix_chaleur - dVent * H.prix_elec, co2: heatKwh * H.co2_chaleur - dVent * H.co2_elec, heatKwh, dVent };
}
function renderCmp() {
  const box = bind('cmp'); if (box.childElementCount && !S._cmpDirty) return; S._cmpDirty = false;
  box.textContent = '';
  const J = S.J, last = S.ND - 1;
  const per = (z, k) => S.L.filter(l => l.tour === z).reduce((s, l) => s + sumL(l, k, 0, last), 0) / J.tours[z].shab;
  const vent = (z) => sumT(z, 'ventilation', 0, last) / J.tours[z].shab;
  const rows = [
    { l: 'Chauffage', s: 'kWh par m² et par an', a: per('A1', 'h'), b: per('A2', 'h'), c: 'var(--s-chauffage)' },
    { l: 'Électricité des ventilateurs', s: 'kWh par m² et par an', a: vent('A1'), b: vent('A2'), c: 'var(--s-elec)' },
  ];
  const g = variantGain();
  box.append(el('p', { class: 'pane-lead', text: 'Sur l\'année, la tour A2 (variante du groupe) face à la tour A1 (conception du DCE).' }));
  for (const r of rows) {
    const mx = Math.max(r.a, r.b) || 1, ec = (r.b / r.a - 1) * 100, d = mx < 10 ? 1 : 0;
    box.append(el('div', { class: 'vs', style: { '--uc': r.c } },
      el('div', { class: 'vs-h' }, el('b', { text: r.l }), el('span', { class: 'vs-ec', text: `${ec > 0 ? '+' : '−'}${fmt(Math.abs(ec))} % en A2` })),
      el('div', { class: 'vs-row' }, el('span', { text: 'A1' }), el('div', { class: 'cmp-track' }, el('div', { class: 'cmp-fill is-hollow', style: { width: `${r.a / mx * 100}%` } })), el('span', { class: 'vs-v', text: fmt(r.a, d) })),
      el('div', { class: 'vs-row' }, el('span', { text: 'A2' }), el('div', { class: 'cmp-track' }, el('div', { class: 'cmp-fill', style: { width: `${r.b / mx * 100}%` } })), el('span', { class: 'vs-v', text: fmt(r.b, d) })),
      el('small', { text: r.s })));
  }
  box.append(el('div', { class: 'vs-money' },
    el('div', {}, el('span', { class: 'kpi-l', text: 'Économie d\'énergie de la variante' }), el('span', { class: 'kpi-v' }, `≈ ${fmt(g.eur)}`, el('small', { text: '€ par an' }))),
    el('div', {}, el('span', { class: 'kpi-l', text: 'CO₂ évité' }), el('span', { class: 'kpi-v' }, fmt(g.co2 / 1000, 1), el('small', { text: 't par an' })))),
    el('p', { class: 'vs-why', text: 'Pourquoi : la tour A2 est isolée par l\'extérieur, ventilée en hybride (le moteur n\'aide que si le tirage naturel ne suffit pas) et préchauffe son eau au soleil. Elle compte plus d\'occupants par logement : son eau et son eau chaude ne se comparent pas.' }),
    el('p', { class: 'vs-why', text: 'Avec une chaleur de réseau peu chère et peu carbonée, le gain reste modeste en euros : la variante se justifie surtout par la RE2020 et le confort.' }),
    el('ul', { class: 'more-links' }, el('li', {}, el('a', { href: '#cout-global', text: 'Coût de l\'énergie sur 50 ans' })), el('li', {}, el('a', { href: 'comparatif/', text: 'Comparatif complet : travaux, quantités, carbone' }))));
}

// ------------------------------------------------------------------ alertes
function alertState(a, day = S.day) {
  const s = dayIndex(a.debut), f = a.fin ? dayIndex(a.fin) : Infinity;
  if (S.period === 'an' && !S.playing) return f < S.ND ? 'close' : 'open';
  if (day < s) return 'future';
  if (day >= f) return 'close';
  return 'open';
}
function alertTarget(a) {
  if (S.byId.has(a.cible)) return { kind: 'logement', id: a.cible };
  if (a.cible.startsWith('SS-')) return { kind: 'ss', tour: a.cible.slice(3) };
  return { kind: 'vhy', revit: a.revit, colonne: a.colonne, ref: a.cible, tour: 'A2' };
}
function renderAlerts() {
  const ol = bind('alerts'); ol.textContent = '';
  const A = S.J.alertes;
  const open = A.filter(a => alertState(a) === 'open').length;
  const nb = bind('alert-n'); nb.textContent = open ? String(open) : ''; nb.hidden = !open;
  const order = { open: 0, close: 1, future: 2 };
  const list = [...A].sort((p, q) => order[alertState(p)] - order[alertState(q)] || p.debut.localeCompare(q.debut));
  for (const a of list) {
    const st = alertState(a); const g = STATUS[a.gravite] || STATUS.attention;
    const when = st === 'future' ? `à partir du ${fmtDay(dayIndex(a.debut))}` : st === 'open' ? `depuis le ${fmtDay(dayIndex(a.debut))}` : `réglé le ${fmtDay(dayIndex(a.fin))}`;
    const badge = st === 'open' ? 'En cours' : st === 'close' ? 'Réglé' : 'Plus tard';
    ol.append(el('li', {}, el('article', { class: `al al-${st}`, style: { '--pc': g.c } },
      el('header', {}, icon(TYPE_ICON[a.type] || g.icon), el('h3', { text: a.titre_simple || a.titre })),
      el('p', { class: 'al-m' }, el('span', { class: 'al-st', text: badge }), ` ${when}${a.cout_eur ? ` · coût ≈ ${fmt(a.cout_eur)} €` : ''}`),
      el('p', { class: 'al-r', text: a.resume || a.cause }),
      el('p', { class: 'al-f' }, el('b', { text: 'À faire : ' }), a.faire || a.action),
      el('button', { class: 'chip', type: 'button', onclick: () => openAlert(a) }, icon('i-target'), 'Voir sur la maquette'))));
  }
}
function openAlert(a, panel = true) {
  stop();
  const t = alertTarget(a);
  setUsage(a.type === 'eau' ? 'eau' : 'chauffage');
  setMonth(monthOf(Math.min(S.ND - 1, dayIndex(a.debut) + 2)));
  if (!panel) {
    if (t.kind === 'logement') { setFloor(0, false); S.twin.markElement(null); S.twin.select(t.id, true); }
    else if (t.kind === 'ss') { S.twin.select(null); S.twin.markElement(null); S.twin.focusPoint(S.twin.towerBase(t.tour).setY(8), 70); }
    else { S.twin.select(null); const p = S.twin.markElement(t.revit); S.twin.focusPoint(p || S.twin.roofOf('A2'), 48); }
    return;
  }
  if (t.kind === 'logement') { setFloor(0, false); selectLogement(t.id, true); }
  else if (t.kind === 'ss') { S.twin.select(null); S.twin.markElement(null); S.twin.focusPoint(S.twin.towerBase(t.tour).setY(8), 70); showSpecial({ kind: 'ss', tour: t.tour, alerte: a }); }
  else { S.twin.select(null); const p = S.twin.markElement(t.revit); S.twin.focusPoint(p || S.twin.roofOf('A2'), 48); showSpecial({ kind: 'vhy', colonne: t.colonne, alerte: a }); }
}

// repères 3D
const pinEls = new Map();
function buildPins() {
  const host = $('[data-v="pins"]'); host.textContent = '';
  for (const a of S.J.alertes) {
    const g = STATUS[a.gravite] || STATUS.attention;
    const short = S.byId.has(a.cible) ? a.cible : a.cible.startsWith('SS-') ? `Sous-station ${a.cible.slice(3)}` : `Extracteur ${a.colonne}`;
    const p = el('button', { class: 'pin', type: 'button', style: { '--pc': g.c }, title: a.titre, onclick: () => openAlert(a) },
      el('span', { class: 'pin-head' }, icon(TYPE_ICON[a.type] || g.icon), short), el('span', { class: 'pin-stem' }), el('span', { class: 'pin-dot' }));
    host.append(p);
    pinEls.set(a.id, { el: p, a });
  }
}
function pinPoint(a) {
  const t = alertTarget(a);
  if (t.kind === 'logement') return S.twin.logementPoint(t.id);
  if (t.kind === 'ss') return S.twin.towerBase(t.tour);
  return S.twin.roofOf('A2');
}
const labelEls = new Map();
function updateLabels(project) {
  const host = $('[data-v="pins"]');
  const on = S.twin.state.plan && S.floor;
  const want = on ? S.L.filter(l => l.etage === S.floor && visible(l)) : [];
  const keep = new Set(want.map(l => l.id));
  for (const [id, n] of labelEls) if (!keep.has(id)) { n.remove(); labelEls.delete(id); }
  const U = USAGE[S.usage];
  for (const l of want) {
    let n = labelEls.get(l.id);
    if (!n) { n = el('button', { class: 'plabel', type: 'button', onclick: () => selectLogement(l.id, false) }, el('b'), el('span')); host.append(n); labelEls.set(l.id, n); }
    const sc = project(l._center);
    if (!sc || sc.hidden) { n.style.display = 'none'; continue; }
    n.style.display = ''; n.style.left = `${sc.x}px`; n.style.top = `${sc.y}px`;
    const v = S.color === 'intensite' ? valueOf(l) : ecartOf(l) * 100;
    n.children[0].textContent = l.id;
    n.children[1].textContent = S.color === 'intensite' ? `${fmt(v, v < 10 ? 2 : 0)}` : `${v > 0 ? '+' : ''}${fmt(v)} %`;
    n.classList.toggle('is-sel', S.sel === l.id);
  }
}
function updatePins(project) {
  if (!S.twin) return;
  updateLabels(project);
  for (const { el: p, a } of pinEls.values()) {
    const st = alertState(a);
    const t = alertTarget(a);
    let show = st !== 'future';
    if (t.kind === 'logement') { const l = S.byId.get(t.id); if (!visible(l) || (S.floor && l.etage !== S.floor)) show = false; }
    else if (S.tower !== 'ALL' && t.tour !== S.tower) show = false;
    if (S.sel === a.cible) show = false;
    const v = a._p || (a._p = pinPoint(a));
    const sc = show && v ? project(v) : null;
    if (!sc || sc.hidden) { p.style.display = 'none'; continue; }
    p.style.display = '';
    p.classList.toggle('is-closed', st === 'close');
    p.style.left = `${sc.x}px`; p.style.top = `${sc.y}px`;
  }
}

// ------------------------------------------------------------------ mois
function setMonth(i) {
  const [a, b] = monthRanges()[Math.max(0, Math.min(monthRanges().length - 1, i))];
  S.period = 'mois';
  setDay(Math.min(b, a + 14));
  renderTimeline();
}
function renderTimeline() {
  const host = bind('months'); if (!host) return; host.textContent = '';
  const zs = scopeTowers();
  const M = monthRanges();
  const vals = M.map(([a, b]) => zs.reduce((s, z) => s + sumT(z, 'mta', a, b), 0));
  const mx = Math.max(...vals) || 1;
  const cur = S.period === 'an' ? -1 : monthOf(S.day);
  M.forEach(([a, b], i) => {
    const x = S.days[a]; const m = x.getMonth();
    const al = S.J.alertes.filter(q => { const d = dayIndex(q.debut); return d >= a && d <= b; });
    const btn = el('button', { type: 'button', class: 'mo' + (i === cur ? ' is-on' : '') + (S.playing && i === cur ? ' is-live' : ''), 'aria-pressed': String(i === cur),
      'aria-label': `${MOIS_L[m]} ${x.getFullYear()}${al.length ? `, ${al.length} problème${al.length > 1 ? 's' : ''} détecté${al.length > 1 ? 's' : ''}` : ''}`,
      onclick: () => { stop(); setMonth(i); } },
      el('span', { class: 'mo-bar' }, el('i', { style: { height: `${Math.max(6, vals[i] / mx * 100)}%` } })),
      el('span', { class: 'mo-l', text: MOIS[m].replace('.', '') }),
      el('span', { class: 'mo-y', text: m === 0 || i === 0 ? String(x.getFullYear()) : '' }),
      el('span', { class: 'mo-dots' }, ...al.map(q => el('i', { style: { background: (STATUS[q.gravite] || STATUS.attention).c } }))));
    host.append(btn);
  });
  host.append(el('button', { type: 'button', class: 'mo mo-an' + (S.period === 'an' ? ' is-on' : ''), 'aria-pressed': String(S.period === 'an'),
    onclick: () => { stop(); setPeriod('an'); } }, el('span', { class: 'mo-l', text: 'Toute l\'année' })));
}
function moveCursor() {
  const host = bind('months'); if (!host) return;
  const cur = S.period === 'an' ? -1 : monthOf(S.day);
  [...host.querySelectorAll('.mo:not(.mo-an)')].forEach((b, i) => { b.classList.toggle('is-on', i === cur); b.classList.toggle('is-live', S.playing && i === cur); b.setAttribute('aria-pressed', String(i === cur)); });
  const an = host.querySelector('.mo-an'); if (an) { an.classList.toggle('is-on', S.period === 'an'); an.setAttribute('aria-pressed', String(S.period === 'an')); }
}
function wireTimeline() {}

// ------------------------------------------------------------------ lecture de l'année
let raf = 0, last = 0, acc = 0;
function toggle() { if (S.playing) stop(); else play(); }
function play() {
  if (S.day >= S.ND - 1) S.day = 0;
  S.playing = true; if (S.period !== 'jour') setPeriod('jour', false);
  const b = $('[data-act="play"]'); b.classList.add('is-playing'); b.firstChild.firstChild.setAttribute('href', '#i-pause'); b.setAttribute('aria-label', 'Mettre en pause');
  last = performance.now(); acc = S.day; setDay(S.day);
  const step = (now) => {
    if (!S.playing) return;
    acc += Math.max(0, now - last) / 1000 * 28; last = now;
    const d = Math.max(0, Math.min(S.ND - 1, Math.floor(acc)));
    if (d !== S.day) setDay(d);
    if (d >= S.ND - 1) { stop(); setPeriod('an'); return; }
    raf = requestAnimationFrame(step);
  };
  raf = requestAnimationFrame(step);
}
function stop() {
  if (!S.playing) return;
  S.playing = false; cancelAnimationFrame(raf);
  const b = $('[data-act="play"]'); b.classList.remove('is-playing'); b.firstChild.firstChild.setAttribute('href', '#i-play'); b.setAttribute('aria-label', "Faire défiler l'année jour par jour");
  if (S.period === 'jour') setPeriod('mois'); else renderAlerts();
}

// ------------------------------------------------------------------ état et mises à jour
function setDay(d) {
  S.day = d;
  const T = S.J.meteo.temperature;
  if (S.period === 'an' && !S.playing) { bind('date-day').textContent = 'Oct. 2027 – sept. 2028'; bind('date-temp').textContent = 'Toute l\'année'; }
  else if (S.period === 'mois' && !S.playing) {
    const [a, b] = range(); let s = 0; for (let i = a; i <= b; i++) s += T[i];
    bind('date-day').textContent = monthName(d); bind('date-temp').textContent = `${fmt(s / (b - a + 1), 1)} °C en moyenne dehors`;
  } else { bind('date-day').textContent = fmtDay(d); bind('date-temp').textContent = `${fmt(T[d], 1)} °C dehors`; }
  paint(); renderKpis(); renderCmp(); moveCursor();
  if (!S.playing || d % 4 === 0) renderAlerts();
  if (S.sel && !S.playing) renderDetail();
}
function setPeriod(p, refresh = true) {
  S.period = p;
  if (refresh) { setDay(S.day); moveCursor(); }
}
function setUsage(u) {
  S.usage = u;
  $$('[data-usage]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.usage === u)));
  paint(); renderKpis(); if (S.sel) renderDetail();
}
function setTab(name, focus = false) {
  $$('[data-tab]').forEach(b => { const on = b.dataset.tab === name; b.setAttribute('aria-selected', String(on)); b.tabIndex = on ? 0 : -1; if (on && focus) b.focus(); });
  $$('[data-pane]').forEach(p => { p.hidden = p.dataset.pane !== name; });
  S.tab = name;
}
function setFloor(n, fly = true) {
  S.floor = n;
  $$('[data-floor]').forEach(b => b.setAttribute('aria-pressed', String(+b.dataset.floor === n)));
  S.twin.setFloor(n, fly);
  paint();
}
function setTower(z) {
  S.tower = z;
  $$('[data-tower]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.tower === z)));
  S.twin.setTower(z); paint(); renderKpis(); renderTimeline();
}

// ------------------------------------------------------------------ détail d'un logement
function selectLogement(id, fly = false) {
  S.sel = id; S.special = null;
  S.twin.markElement(null);
  S.twin.select(id, fly);
  const url = new URL(location); if (id) url.searchParams.set('l', id); else url.searchParams.delete('l'); history.replaceState(null, '', url);
  if (!id) { closeDetail(); return; }
  $('#detail').hidden = false; document.body.classList.add('has-detail');
  renderDetail(); renderTimeline();
}
function updateInsets() {
  if (!S.twin) return;
  const wide = window.innerWidth > 900;
  const L = wide ? ($('.panel-left').getBoundingClientRect().right + 8) : 0;
  const R = wide ? (S.sel || S.special ? $('#detail').getBoundingClientRect().width + 26 : 70) : 0;
  S.twin.setInsets(L, R);
}
function closeDetail() {
  S.sel = null; S.special = null; S.twin?.select(null); S.twin?.markElement(null);
  $('#detail').hidden = true; document.body.classList.remove('has-detail');
  const url = new URL(location); url.searchParams.delete('l'); history.replaceState(null, '', url);
  renderTimeline(); updateInsets();
}
function showSpecial(sp) {
  S.sel = null; S.special = sp; S.twin.select(null);
  $('#detail').hidden = false; document.body.classList.add('has-detail');
  renderDetail(); renderTimeline(); updateInsets();
}
function monthlyBars(l) {
  const M = monthRanges();
  const vals = M.map(([a, b]) => ({ h: sumL(l, 'h', a, b), e: sumL(l, 'e', a, b), r: sumL(l, 'r', a, b), m: S.days[a].getMonth(), a, b }));
  const W = 340, H = 150, top = 8, base = H - 20, bw = W / 12;
  const mx = Math.max(...vals.map(v => Math.max(v.h + v.e, v.r + v.e))) * 1.08 || 1;
  const y = (v) => base - (v / mx) * (base - top);
  const svg = sv('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': `Consommation mensuelle du logement ${l.id}` });
  for (const g of [0.5, 1]) svg.append(sv('line', { x1: 0, x2: W, y1: y(mx / 1.08 * g), y2: y(mx / 1.08 * g), stroke: 'rgba(176,196,214,.10)' }));
  const wrap = el('div', { class: 'chart-wrap' });
  const tip = el('div', { class: 'chart-tip', hidden: true });
  vals.forEach((v, i) => {
    const x0 = i * bw + 4, w = bw - 8;
    const g = sv('g', { tabindex: 0 });
    const hH = base - y(v.h), hE = base - y(v.e);
    if (v.h > 0) g.append(sv('rect', { x: x0, y: y(v.h), width: w, height: Math.max(0, hH), fill: '#d95926', rx: 0 }));
    if (v.e > 0) g.append(sv('rect', { x: x0, y: y(v.h + v.e) , width: w, height: Math.max(0, hE - 2), fill: '#3987e5', rx: 3 }));
    // référence recalée du chauffage : trait
    if (v.r > 1) g.append(sv('line', { x1: x0 - 2, x2: x0 + w + 2, y1: y(v.r), y2: y(v.r), stroke: '#eef1f2', 'stroke-width': 2, 'stroke-dasharray': '3 2' }));
    g.append(sv('rect', { x: i * bw, y: 0, width: bw, height: H, fill: 'transparent' }));
    svg.append(g);
    svg.append(sv('text', { x: i * bw + bw / 2, y: H - 5, 'text-anchor': 'middle', 'font-size': 10, fill: '#85919a' }, MOIS[v.m].replace('.', '')));
    const show = () => { tip.hidden = false; tip.style.left = `${((i + 0.5) / 12) * 100}%`; tip.style.top = `${(y(v.h + v.e) / H) * 100}%`;
      tip.innerHTML = `<b>${MOIS_L[v.m]}</b><br><span class="sw" style="background:#d95926"></span>Chauffage ${fmt(v.h)} kWh<br><span class="sw" style="background:#3987e5"></span>Eau chaude ${fmt(v.e)} kWh<br>Logements semblables ${fmt(v.r)} kWh`; };
    g.addEventListener('pointerenter', show); g.addEventListener('focus', show);
    g.addEventListener('pointerleave', () => { tip.hidden = true; }); g.addEventListener('blur', () => { tip.hidden = true; });
  });
  wrap.append(svg, tip);
  return el('div', {}, wrap, el('div', { class: 'key' },
    el('span', {}, el('i', { style: { background: '#d95926' } }), 'Chauffage'), el('span', {}, el('i', { style: { background: '#3987e5' } }), 'Eau chaude'),
    el('span', {}, el('i', { class: 'line', style: { background: '#eef1f2' } }), 'Logements semblables (chauffage)')));
}
function alertCard(a) {
  const g = STATUS[a.gravite] || STATUS.attention;
  const d = dayIndex(a.debut);
  const per = a.fin ? `du ${fmtDay(d)} au ${fmtDay(dayIndex(a.fin))}` : `depuis le ${fmtDay(d)}`;
  const rule = S.J.regles.find(r => r.id === a.regle);
  return el('div', { class: 'alert-card', style: { '--pc': g.c } },
    el('h4', {}, icon(TYPE_ICON[a.type] || g.icon), a.titre_simple || a.titre),
    el('p', {}, el('b', { text: `${g.label} · ` }), per),
    el('p', { text: a.resume || a.cause }),
    el('p', {}, el('b', { text: 'À faire : ' }), a.faire || a.action),
    a.cout_eur ? el('p', {}, el('b', { text: 'Coût estimé : ' }), `${fmt(a.cout_eur)} € TTC`) : null,
    el('details', { class: 'more more-al' }, el('summary', { text: 'Détail technique' }),
      el('p', {}, el('b', { text: 'Cause probable : ' }), a.cause),
      el('p', {}, el('b', { text: 'Action : ' }), a.action),
      rule ? el('p', {}, el('b', { text: `Règle ${rule.id} : ` }), rule.texte) : null),
    el('div', { class: 'tagline' }, el('span', { class: 'tag tag-fic', text: 'Anomalie simulée' }), el('span', { class: 'tag', text: 'Détection automatique' })));
}
function renderDetail() {
  const box = bind('detail'); box.textContent = '';
  if (S.special) return renderSpecial(box);
  const l = S.byId.get(S.sel); if (!l) return;
  const [a, b] = range();
  const U = USAGE[S.usage]; const k = U.key;
  const e = ecartOf(l); const g = lightOf(l); const G = LIGHTS[g];
  const tours = { A1: 'Tour A1 · COGEDIM', A2: 'Tour A2 · CDC Habitat' };
  const em = new Date(l.emmenagement + 'T12:00:00');
  const H = S.hyp;
  const an = (kk) => sumL(l, kk, 0, S.ND - 1);
  const per = (kk) => sumL(l, kk, a, b);
  const facture = (f) => euros('h', f('h')) + euros('e', f('e')) + euros('w', f('w')) + euros('p', f('p'));
  const coutAn = facture(an) + H.abo_elec;
  const coutPer = facture(per) + H.abo_elec * (b - a + 1) / S.ND;
  const co2An = (an('h') + an('e')) * H.co2_chaleur + an('p') * H.co2_elec;
  const alerts = S.J.alertes.filter(x => x.cible === l.id);
  const miss = l.miss.reduce((s, x) => s + x, 0);
  const quand = S.period === 'an' ? 'Sur l\'année' : S.period === 'mois' ? `En ${periodLabel()}` : `Cette semaine-là (jusqu'au ${fmtDay(S.day)})`;
  const qte = per(k);
  const qteTxt = k === 'w' ? `${fmt(qte / 1000, 1)} m³ d'eau` : `${fmt(qte)} kWh ${S.usage === 'chauffage' ? 'de chauffage' : S.usage === 'ecs' ? 'd\'eau chaude' : 'd\'électricité'}`;
  const comp = S.usage === 'chauffage' ? 'des logements semblables (même taille, même étage, même orientation, même météo)' : S.usage === 'elec' ? `les logements de la tour qui comptent aussi ${l.occupants} occupant${l.occupants > 1 ? 's' : ''}` : 'la moyenne de la tour, par occupant';
  const phrase = g === 'vide'
    ? `${quand}, le logement n'est pas encore habité (emménagement le ${em.getDate()} ${MOIS_L[em.getMonth()]} ${em.getFullYear()}).`
    : `${quand}, ce logement a consommé ${qteTxt}, soit ≈ ${fmt(euros(k, qte))} €. C'est ${Math.abs(e) < 0.05 ? 'autant que' : `${fmt(Math.abs(e) * 100)} % de ${e > 0 ? 'plus' : 'moins'} que`} ${comp}.`;
  const orient = ORIENT[l.orient] || l.orient;
  box.append(...[
    el('p', { class: 'dt-eyebrow', text: `${tours[l.tour]} · ${etageLabel(l.etage)} · façade ${orient}` }),
    el('h2', { class: 'dt-title', text: `Logement ${l.id}` }),
    el('p', { class: 'dt-sub', text: `${l.typo} · ${fmt(l.shab, 0)} m² · ${l.occupants} occupant${l.occupants > 1 ? 's' : ''}` }),
    el('p', { class: 'dt-light', style: { '--lc': G.c } }, el('i'), el('b', { text: G.label }), g !== 'vide' && Math.abs(e) >= 0.05 ? el('span', { text: `${e > 0 ? '+' : '−'}${fmt(Math.abs(e) * 100)} %` }) : null),
    el('p', { class: 'dt-phrase', text: phrase }),
    alerts.length ? el('div', { class: 'dt-section' }, el('h3', { text: 'Problème détecté' }), ...alerts.map(alertCard)) : null,
    el('div', { class: 'dt-grid' },
      S.period === 'an' ? null : el('div', { class: 'mini' }, el('span', { class: 'ml', text: S.period === 'mois' ? 'Facture du mois' : 'Facture de la semaine' }), el('div', { class: 'mv', text: `${fmt(coutPer)} €` }), el('div', { class: 'ms', text: 'Énergie et eau, abonnement compris' })),
      el('div', { class: 'mini' }, el('span', { class: 'ml', text: 'Facture de l\'année' }), el('div', { class: 'mv', text: `${fmt(coutAn)} €` }), el('div', { class: 'ms', text: `${fmt(coutAn / 12)} € par mois en moyenne` }))),
    el('div', { class: 'dt-section' }, el('h3', { text: 'Mois par mois' }), monthlyBars(l)),
    el('a', { class: 'dt-loc', href: `locataire/?l=${l.id}&m=${S.days[S.day].getFullYear()}-${String(S.days[S.day].getMonth() + 1).padStart(2, '0')}`, target: '_blank', rel: 'noopener' },
      el('b', { text: 'Ce que voit le locataire' }), el('span', { text: 'Sa page « Mon logement », ouverte avec le QR code de son livret d\'accueil' })),
    el('details', { class: 'more more-dt' }, el('summary', { text: 'Pour aller plus loin' }),
      el('div', { class: 'dt-section' }, el('h3', { text: 'Sur l\'année' }),
        el('div', { class: 'dt-grid' },
          ...['chauffage', 'ecs', 'eau', 'elec'].map(u => {
            const K = USAGE[u]; const s = an(K.key);
            const val = u === 'eau' ? `${fmt(s / 1000, 1)} m³` : `${fmt(s)} kWh`;
            const sub = u === 'eau' ? `${fmt(s / l.occupants / S.ND)} L par personne et par jour` : `${fmt(s / l.shab, 1)} kWh/m² · ${fmt(euros(K.key, s))} €`;
            return el('div', { class: 'mini', style: { '--uc': `var(${K.css})` } }, el('span', { class: 'ml' }, icon(K.icon), K.label), el('div', { class: 'mv', text: val }), el('div', { class: 'ms', text: sub }));
          }),
          el('div', { class: 'mini' }, el('span', { class: 'ml', text: 'Émissions' }), el('div', { class: 'mv', text: `${fmt(co2An)} kg CO₂e` }), el('div', { class: 'ms', text: `${fmt(co2An / l.shab, 1)} kg/m²` })),
          el('div', { class: 'mini' }, el('span', { class: 'ml', text: 'Emménagement' }), el('div', { class: 'mv', text: `${em.getDate()} ${MOIS[em.getMonth()]} ${em.getFullYear()}` }), el('div', { class: 'ms', text: l.ext ? `${fmt(l.ext, 1)} m² extérieurs` : '' })))),
      el('div', { class: 'dt-section' }, el('h3', { text: 'Comptage' }),
        el('dl', { class: 'facts' },
          el('dt', { text: 'Compteur' }), el('dd', { text: 'Module thermique Uponor Combi Port : chauffage, eau chaude et eau froide comptés séparément (CCTP 502 §5.5.1)' }),
          el('dt', { text: 'Relevé' }), el('dd', { text: miss ? `Chaque jour, par radio ; ${miss} jours sans donnée, estimés` : 'Chaque jour, par radio' }),
          el('dt', { text: 'Ventilation' }), el('dd', { text: l.tour === 'A1' ? 'VMC simple flux hygroréglable B' : 'Ventilation hybride hygroréglable B (variante A2)' }),
          el('dt', { text: 'Plan' }), el('dd', { text: `${l.plan} (tableau des surfaces ind. A)` })),
        el('div', { class: 'tagline' }, el('span', { class: 'tag tag-real', text: 'Typologie, surface, position : DCE et maquette' }), el('span', { class: 'tag tag-fic', text: 'Consommations simulées' }))),
      equipementsBlock(l),
      ouvragesBlock(l)),
  ].filter(Boolean));
}
// équipements prévus au CCTP (non modélisés), dénombrés d'après les plans CVC des logements types
const TYPO_EQ = { T2: { pp: 2, eau: 1, bouches: 3 }, T3A: { pp: 3, eau: 1, bouches: 3 }, T3B: { pp: 3, eau: 1, bouches: 4 }, T4: { pp: 4, eau: 2, bouches: 5 } };
function equipementsBlock(l) {
  const t = TYPO_EQ[l.typo];
  if (!t) return null;
  const a1 = l.tour === 'A1';
  const items = [
    ['1', 'module thermique d\'appartement Uponor Combi Port'],
    ['1', 'thermostat d\'ambiance programmable'],
    [String(a1 ? t.pp + t.eau : t.pp), 'radiateur(s) acier HM Classic Easy M'],
    a1 ? null : [String(t.eau), 'sèche-serviettes eau chaude Atlantic Corsaire'],
    [String(t.pp), 'entrée(s) d\'air hygroréglable(s) EH 5/45'],
    [String(t.bouches), a1 ? 'bouche(s) d\'extraction hygroréglable(s)' : 'bouche(s) d\'extraction hygroréglable(s) basse pression'],
    ['1', a1 ? 'compteur d\'énergie chauffage + ECS (en option au CCTP)' : 'compteur d\'énergie chauffage + ECS (en base)'],
  ].filter(Boolean);
  const ul = el('ul', { class: 'eq-list' });
  for (const [n, txt] of items) ul.append(el('li', {}, el('b', { text: n }), el('span', { text: txt })));
  return el('div', { class: 'dt-section' }, el('h3', { text: 'Équipements du logement' }), ul,
    el('p', { class: 'dt-note' }, a1 ? 'Prévus au CCTP 502-503-504, non modélisés : comptés d\'après les plans CVC des logements types. ' : 'CCTP 502-503-504 et variante A2 ; dénombrement d\'après les plans CVC des logements types. ',
      el('a', { href: 'comparatif/#quantites', text: 'Voir le comparatif A1 / A2' })));
}
function ouvragesBlock(l) {
  if (!l.ouvrages.length) return null;
  const idx = S.J._idx;
  const rows = l.ouvrages.map(r => ({ ref: r, rec: S.ouv.ouvrages[r] })).filter(x => x.rec);
  const prio = { menuiserie_A1: 0, menuiserie_A2: 0, facade_A1: 1, facade_A2: 1, ite_A2: 1, balcon: 2, separatif: 3 };
  rows.sort((a, b) => (prio[a.rec.p] ?? 5) - (prio[b.rec.p] ?? 5) || a.ref.localeCompare(b.ref));
  const ul = el('ul', { class: 'links' });
  const shown = rows.slice(0, 7);
  for (const { ref, rec } of shown) {
    const p = S.ouv.profils[rec.p];
    ul.append(el('li', {}, el('a', { href: fiche(ref) }, el('b', { text: ref.replace(/^(A[12])-/, '$1 ').replace(/([A-Za-z]+)(\d)/, '$1 $2') }), el('span', { text: p ? p.titre.split(' — ')[0] : '' }))));
  }
  return el('div', { class: 'dt-section' }, el('h3', { text: `Ouvrages du logement (${rows.length})` }), ul,
    el('p', { class: 'dt-note', text: 'Chaque passeport d\'ouvrage porte maintenant un volet « Énergie » : composition, U ou R, source et fiabilité.' }));
}
function lineChart(series, opts) {
  // series : [{ v: [...], color, dash, label }] même unité (un seul axe)
  const W = 340, H = 140, top = 8, base = H - 18;
  const all = series.flatMap(s => s.v);
  const mn = opts.min ?? 0, mx = (opts.max ?? Math.max(...all)) * 1.05;
  const x = (i) => (i / (S.ND - 1)) * W, y = (v) => base - ((v - mn) / (mx - mn)) * (base - top);
  const svg = sv('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': opts.label });
  for (const [a, b] of monthRanges()) { if (S.days[a].getMonth() % 3 === 0) svg.append(sv('text', { x: x(a), y: H - 3, 'font-size': 10, fill: '#85919a' }, MOIS[S.days[a].getMonth()])); }
  if (opts.band) svg.append(sv('rect', { x: x(opts.band[0]), y: top, width: x(opts.band[1]) - x(opts.band[0]), height: base - top, fill: 'rgba(255,61,139,.10)' }));
  for (const g of opts.grid || []) { svg.append(sv('line', { x1: 0, x2: W, y1: y(g), y2: y(g), stroke: 'rgba(176,196,214,.12)' })); svg.append(sv('text', { x: W, y: y(g) - 3, 'text-anchor': 'end', 'font-size': 10, fill: '#85919a' }, opts.gridLabel ? opts.gridLabel(g) : fmt(g))); }
  for (const s of series) {
    let d = ''; s.v.forEach((v, i) => { d += (i ? 'L' : 'M') + x(i).toFixed(1) + ',' + y(v).toFixed(1); });
    svg.append(sv('path', { d, fill: 'none', stroke: s.color, 'stroke-width': 2, 'stroke-dasharray': s.dash || null, 'stroke-linejoin': 'round' }));
  }
  return el('div', {}, el('div', { class: 'chart-wrap' }, svg), el('div', { class: 'key' }, ...series.map(s => el('span', {}, el('i', { class: 'line', style: { background: s.color } }), s.label))));
}
function smooth(a, n = 7) { return a.map((_, i) => { let s = 0, k = 0; for (let j = Math.max(0, i - n + 1); j <= i; j++) { s += a[j]; k++; } return s / k; }); }
function renderSpecial(box) {
  const sp = S.special;
  if (sp.kind === 'ss') {
    const T = S.J.tours[sp.tour].jour;
    const mta = T.mta, loss = T.pertes;
    const share = smooth(loss).map((v, i) => 100 * v / (v + smooth(mta)[i]));
    const a = sp.alerte;
    box.append(...[el('p', { class: 'dt-eyebrow', text: `${S.J.tours[sp.tour].nom} · parking R-1` }), el('h2', { class: 'dt-title', text: `Sous-station ${sp.tour}` }),
      el('p', { class: 'dt-sub', text: 'Échangeur raccordé au réseau de chaleur des Hauts de Garonne. Son compteur, comparé à la somme des modules thermiques, mesure les pertes de distribution.' }),
      el('div', { class: 'dt-section' }, el('h3', { text: 'Pertes de distribution, kWh par jour (moyenne 7 jours)' }),
        lineChart([{ v: smooth(loss), color: '#e66767', label: 'Pertes mesurées' }, { v: smooth(T.pertes_modele), color: '#b8c1c7', dash: '4 3', label: 'Modèle appris sur le 1er trimestre' }],
          { label: 'Pertes de distribution journalières, mesurées et attendues', grid: niceGrid(Math.max(...smooth(loss))), band: a ? [dayIndex(a.debut), a.fin ? dayIndex(a.fin) : S.ND - 1] : null })),
      el('div', { class: 'dt-section' }, el('h3', { text: 'Part de la chaleur perdue avant les logements' }),
        lineChart([{ v: share.map(x => Math.min(50, x)), color: '#c9a46a', label: 'Pertes / chaleur livrée, %' }], { label: 'Part des pertes', min: 0, max: 50, grid: [10, 20, 30, 40], gridLabel: (g) => `${g} %`, band: a ? [dayIndex(a.debut), a.fin ? dayIndex(a.fin) : S.ND - 1] : null })),
      a ? el('div', { class: 'dt-section' }, el('h3', { text: 'Alerte' }), alertCard(a)) : null,
      a ? el('p', { class: 'dt-note', text: `Excès de pertes sur l'épisode : ${fmt(a.exces_kwh)} kWh, soit ${fmt(a.cout_eur)} € TTC au prix du réseau.` }) : null].filter(Boolean));
  } else {
    const X = S.J.tours.A2.extracteurs;
    const x = X.find(e => e.colonne === sp.colonne) || X[0];
    const a = sp.alerte;
    // attendu : médiane des autres extracteurs, ramenée au débit de celui-ci
    const others = X.filter(e => e !== x);
    const exp = x.kwh.map((_, i) => { const v = others.map(e => e.kwh[i] / e.debit).sort((p, q) => p - q); return v[Math.floor(v.length / 2)] * x.debit; });
    const band = a ? [dayIndex(a.debut), a.fin ? dayIndex(a.fin) : S.ND - 1] : null;
    const tot = x.kwh.reduce((s, v) => s + v, 0), ass = x.assistance.reduce((s, v) => s + v, 0) / x.assistance.length;
    box.append(...[el('p', { class: 'dt-eyebrow', text: 'Tour A2 · toiture · variante RE2020' }), el('h2', { class: 'dt-title', text: `Extracteur hybride, colonne ${x.colonne}` }),
      el('p', { class: 'dt-sub', text: `${x.designation}. La colonne est ventilée par tirage naturel ; le moteur n'assiste que lorsque le tirage ne suffit pas (temps doux, été, vent faible).` }),
      el('div', { class: 'dt-section' }, el('h3', { text: 'Électricité de l\'extracteur, kWh par jour (moyenne 7 jours)' }),
        lineChart([{ v: smooth(x.kwh), color: '#3987e5', label: 'Mesurée' }, { v: smooth(exp), color: '#b8c1c7', dash: '4 3', label: 'Attendue (autres extracteurs, même débit)' }],
          { label: 'Consommation journalière de l\'extracteur, mesurée et attendue', grid: niceGrid(Math.max(...smooth(x.kwh))), band })),
      el('div', { class: 'dt-section' }, el('h3', { text: 'Part du temps en assistance mécanique' }),
        lineChart([{ v: smooth(x.assistance).map(v => v * 100), color: '#c9a46a', label: 'Assistance, % du temps' }], { label: 'Part du temps en assistance', min: 0, max: 100, grid: [25, 50, 75], gridLabel: (g) => `${g} %`, band })),
      el('p', { class: 'dt-note', text: `Sur l'année : ${fmt(tot)} kWh, assistance ${fmt(ass * 100)} % du temps en moyenne.` }),
      a ? el('div', { class: 'dt-section' }, el('h3', { text: 'Alerte' }), alertCard(a)) : null,
      a ? el('p', { class: 'dt-note', text: `Électricité en trop pendant la panne : ${fmt(a.exces_kwh)} kWh, soit ${fmt(a.cout_eur)} € TTC.` }) : null,
      el('div', { class: 'dt-section' }, el('h3', { text: 'Ouvrage dans la maquette' }), el('ul', { class: 'links' }, el('li', {}, el('a', { href: fiche(x.ref) }, el('b', { text: x.ref.replace(/^A2-/, 'A2 ') }), el('span', { text: 'Passeport de l\'équipement' })))))].filter(Boolean));
  }
}
function niceGrid(mx) { const p = Math.pow(10, Math.floor(Math.log10(mx))); const s = mx / p > 5 ? 2 * p : mx / p > 2 ? p : p / 2; const out = []; for (let v = s; v < mx; v += s) out.push(v); return out; }

// ------------------------------------------------------------------ récit : comparaison et coût global
function renderStory() {
  const J = S.J;
  // barres par usage (A1 creux, A2 plein, étiquettes directes)
  const host = bind('cmp-bars'); host.textContent = '';
  const per = (z, k) => S.L.filter(l => l.tour === z).reduce((s, l) => s + sumL(l, k, 0, S.ND - 1), 0) / J.tours[z].shab;
  const rows = [
    { u: 'chauffage', l: 'Chauffage', a: per('A1', 'h'), b: per('A2', 'h'), unit: 'kWh/m²' },
    { u: 'ecs', l: 'Eau chaude', a: per('A1', 'e'), b: per('A2', 'e'), unit: 'kWh/m²' },
    { u: 'ecs', l: 'Chaleur achetée au réseau', a: sumT('A1', 'reseau', 0, S.ND - 1) / J.tours.A1.shab, b: sumT('A2', 'reseau', 0, S.ND - 1) / J.tours.A2.shab, unit: 'kWh/m²', c: '#c9a46a' },
    { u: 'elec', l: 'Ventilation (électricité)', a: sumT('A1', 'ventilation', 0, S.ND - 1) / J.tours.A1.shab, b: sumT('A2', 'ventilation', 0, S.ND - 1) / J.tours.A2.shab, unit: 'kWh/m²' },
    { u: 'eau', l: 'Eau', a: per('A1', 'w'), b: per('A2', 'w'), unit: 'L/m²' },
  ];
  const W = Math.max(320, Math.round(host.clientWidth || 520)), rowH = 46, H = rows.length * rowH + 10, lab = Math.min(190, W * 0.36);
  const svg = sv('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Consommation par m² des tours A1 et A2' });
  rows.forEach((r, i) => {
    const c = r.c || USAGE[r.u].hex;
    const mx = Math.max(r.a, r.b) * 1.15;
    const sx = (v) => (v / mx) * (W - lab - 84);
    const y0 = i * rowH + 6;
    svg.append(sv('text', { x: 0, y: y0 + 17, 'font-size': 13, fill: '#eef1f2', 'font-weight': 600 }, r.l));
    svg.append(sv('text', { x: 0, y: y0 + 33, 'font-size': 11.5, fill: '#85919a' }, `${r.b < r.a ? '−' : '+'}${fmt(Math.abs(r.b / r.a - 1) * 100)} % en A2`));
    svg.append(sv('rect', { x: lab, y: y0 + 4, width: Math.max(2, sx(r.a)), height: 14, rx: 4, fill: 'none', stroke: c, 'stroke-width': 1.5 }));
    svg.append(sv('text', { x: lab + sx(r.a) + 8, y: y0 + 15, 'font-size': 12, fill: '#b8c1c7' }, `A1 · ${fmt(r.a, r.a < 20 ? 1 : 0)}`));
    svg.append(sv('rect', { x: lab, y: y0 + 22, width: Math.max(2, sx(r.b)), height: 14, rx: 4, fill: c }));
    svg.append(sv('text', { x: lab + sx(r.b) + 8, y: y0 + 33, 'font-size': 12, fill: '#eef1f2', 'font-weight': 600 }, `A2 · ${fmt(r.b, r.b < 20 ? 1 : 0)}`));
  });
  host.append(el('div', { class: 'chart-wrap' }, svg), el('div', { class: 'key' }, el('span', {}, el('i', { class: 'hollow', style: { '--c': '#b8c1c7' } }), 'Tour A1 (DCE, contour)'), el('span', {}, el('i', { style: { background: '#b8c1c7' } }), 'Tour A2 (variante, plein)'),
    el('span', { text: 'Écart d\'eau et d\'eau chaude : effet du nombre d\'occupants, pas de la variante.' })));

  // réseau mois par mois : barres groupées
  const mh = bind('cmp-months'); mh.textContent = '';
  const M = monthRanges();
  const data = M.map(([a, b]) => ({ m: S.days[a].getMonth(), A1: sumT('A1', 'reseau', a, b) / 1000, A2: sumT('A2', 'reseau', a, b) / 1000, sol: sumT('A2', 'solaire', a, b) / 1000 }));
  const W2 = Math.max(320, Math.round(mh.clientWidth || 640)), H2 = 220, top = 10, base = H2 - 24, gw = W2 / 12;
  const mx = Math.max(...data.map(d => Math.max(d.A1, d.A2 + d.sol))) * 1.1;
  const y = (v) => base - (v / mx) * (base - top);
  const s2 = sv('svg', { viewBox: `0 0 ${W2} ${H2}`, role: 'img', 'aria-label': 'Chaleur achetée au réseau par mois, tours A1 et A2' });
  for (const g of niceGrid(mx)) { s2.append(sv('line', { x1: 0, x2: W2, y1: y(g), y2: y(g), stroke: 'rgba(176,196,214,.10)' })); s2.append(sv('text', { x: 0, y: y(g) - 3, 'font-size': 10, fill: '#85919a' }, `${fmt(g)} MWh`)); }
  const wrap = el('div', { class: 'chart-wrap' }); const tip = el('div', { class: 'chart-tip', hidden: true });
  data.forEach((d, i) => {
    const x0 = i * gw + gw * 0.14, bw = gw * 0.34;
    const g = sv('g', { tabindex: 0 });
    g.append(sv('rect', { x: x0, y: y(d.A1), width: bw, height: base - y(d.A1), fill: 'none', stroke: '#c9a46a', 'stroke-width': 1.5, rx: 3 }));
    g.append(sv('rect', { x: x0 + bw + 2, y: y(d.A2), width: bw, height: base - y(d.A2), fill: '#c9a46a', rx: 3 }));
    if (d.sol > 0.05) g.append(sv('rect', { x: x0 + bw + 2, y: y(d.A2 + d.sol), width: bw, height: Math.max(0, base - y(d.sol) - 2), fill: '#fab219', opacity: 0.0 }));
    if (d.sol > 0.05) g.append(sv('rect', { x: x0 + bw + 2, y: y(d.A2 + d.sol), width: bw, height: Math.max(1, y(d.A2) - y(d.A2 + d.sol) - 2), fill: 'url(#hatch-sol)', stroke: '#c98500', 'stroke-width': 1, rx: 3 }));
    g.append(sv('rect', { x: i * gw, y: 0, width: gw, height: H2, fill: 'transparent' }));
    s2.append(g);
    s2.append(sv('text', { x: i * gw + gw / 2, y: H2 - 6, 'text-anchor': 'middle', 'font-size': 11, fill: '#85919a' }, MOIS[d.m]));
    const show = () => { tip.hidden = false; tip.style.left = `${((i + 0.5) / 12) * 100}%`; tip.style.top = `${(y(Math.max(d.A1, d.A2 + d.sol)) / H2) * 100}%`;
      tip.innerHTML = `<b>${MOIS_L[d.m]}</b><br>A1 ${fmt(d.A1, 1)} MWh · A2 ${fmt(d.A2, 1)} MWh<br>Solaire A2 ${fmt(d.sol, 1)} MWh`; };
    g.addEventListener('pointerenter', show); g.addEventListener('focus', show); g.addEventListener('pointerleave', () => { tip.hidden = true; }); g.addEventListener('blur', () => { tip.hidden = true; });
  });
  const defs = sv('defs'); const pat = sv('pattern', { id: 'hatch-sol', width: 6, height: 6, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' });
  pat.append(sv('rect', { width: 6, height: 6, fill: 'rgba(201,133,0,.15)' }), sv('line', { x1: 0, y1: 0, x2: 0, y2: 6, stroke: '#c98500', 'stroke-width': 2 })); defs.append(pat); s2.prepend(defs);
  wrap.append(s2, tip);
  mh.append(wrap, el('div', { class: 'key' }, el('span', {}, el('i', { class: 'hollow', style: { '--c': '#c9a46a' } }), 'Tour A1'), el('span', {}, el('i', { style: { background: '#c9a46a' } }), 'Tour A2'),
    el('span', {}, el('i', { style: { background: 'repeating-linear-gradient(45deg,#c98500 0 2px,rgba(201,133,0,.15) 2px 5px)' } }), 'Chaleur fournie par le soleil en A2')));

  renderCoutGlobal();
  // règles, sources, colophon
  const rl = bind('rules'); rl.textContent = '';
  for (const r of J.regles) rl.append(el('li', {}, el('b', {}, el('span', { class: 'rid', text: r.id }), r.label), r.texte));
  const src = bind('real-src'); src.textContent = '';
  const ul = el('ul', { class: 'norms' });
  for (const h of Object.values(J.hypotheses)) if (h.fiab === 'verifie') ul.append(el('li', {}, el('b', { text: `${h.label} : ${fmt(h.valeur, h.valeur < 1 ? 4 : 2)} ${h.unite}. ` }), h.src));
  src.append(ul);
  bind('cep').textContent = `Cep ${fmt(J.reference.cep_etude, 1)} kWhep/m².an pour ${fmt(J.reference.cep_max, 1)} autorisés, Bbio ${fmt(J.reference.bbio, 1)}`;
  bind('gen-date').textContent = new Date(J.genere + 'T12:00:00').toLocaleDateString('fr-FR');
}

function renderCoutGlobal() {
  const form = bind('cg-form');
  if (!form.childElementCount) {
    const H = S.J.hypotheses;
    const field = (k, step, label, hint, isHyp) => el('label', { class: isHyp ? 'is-hyp' : '' }, el('span', {}, label, el('small', { text: hint })),
      el('input', { type: 'number', step, value: S.hyp[k], 'data-k': k, inputmode: 'decimal', oninput: (e) => { const v = parseFloat(e.target.value); if (isFinite(v)) { S.hyp[k] = v; S._cmpDirty = true; renderCoutGlobal(); renderKpis(); renderCmp(); } } }));
    form.append(el('h3', { text: 'Prix (sources publiques)' }),
      field('prix_chaleur', 0.01, 'Chaleur du réseau, € TTC/MWh', 'Hauts de Garonne, prix moyen 2023'),
      field('prix_elec', 0.0001, 'Électricité, € TTC/kWh', 'Tarif réglementé Base 6 kVA'),
      field('prix_eau', 0.01, 'Eau, € TTC/m³', 'Bordeaux Métropole, 2024'),
      el('h3', { text: 'Hypothèses' }),
      field('evol_energie', 0.1, 'Évolution de l\'énergie, %/an', 'À ajuster', true),
      field('evol_eau', 0.1, 'Évolution de l\'eau, %/an', 'À ajuster', true),
      field('co2_elec', 0.001, 'CO₂ de l\'électricité, kg/kWh', 'Ordre de grandeur, à vérifier', true),
      el('h3', { text: 'Variante A2' }),
      el('label', {}, el('span', {}, 'Surcoût de la variante, € HT', el('small', {}, 'Estimé par ratios dans le ', el('a', { href: 'comparatif/#couts', text: 'comparatif A1 / A2' }))),
        el('input', { type: 'number', step: 1000, placeholder: 'ex. 450 000', 'data-k': 'surcout', value: S.surcout || null, oninput: (e) => { S.surcout = parseFloat(e.target.value) || 0; renderCoutGlobal(); } })));
  }
  const H = S.hyp, YEARS = 50, J = S.J;
  const last = S.ND - 1;
  const yearCost = (z) => {
    const L = S.L.filter(l => l.tour === z);
    const heat = sumT(z, 'reseau', 0, last) / 1000 * H.prix_chaleur;
    const elec = (sumT(z, 'elec_priv', 0, last) + sumT(z, 'sg', 0, last)) * H.prix_elec + L.length * H.abo_elec;
    const water = L.reduce((s, l) => s + sumL(l, 'w', 0, last), 0) / 1000 * H.prix_eau;
    return { energy: heat + elec, water };
  };
  // économie attribuable à la variante (ramenée à la surface de A2) : chauffage, solaire, ventilation
  const sh2 = J.tours.A2.shab, sh1 = J.tours.A1.shab;
  const heat = (z) => S.L.filter(l => l.tour === z).reduce((s, l) => s + sumL(l, 'h', 0, last), 0);
  const dHeat = (heat('A1') / sh1 - heat('A2') / sh2) * sh2;           // kWh
  const solar = sumT('A2', 'solaire', 0, last);                          // kWh
  const dVent = (sumT('A2', 'ventilation', 0, last) / sh2 - sumT('A1', 'ventilation', 0, last) / sh1) * sh2; // kWh élec en plus
  const gainHeatKwh = (dHeat + solar) * (1 + J.calage.pertes_distribution.A2);
  const gainEur = gainHeatKwh / 1000 * H.prix_chaleur - dVent * H.prix_elec;
  const gainCo2 = gainHeatKwh * H.co2_chaleur - dVent * H.co2_elec;
  const c1 = yearCost('A1'), c2 = yearCost('A2');
  const ge = H.evol_energie / 100, gw = H.evol_eau / 100;
  const cum1 = [0], cum2 = [S.surcout || 0], save = [0];
  for (let y = 0; y < YEARS; y++) {
    cum1.push(cum1[y] + (c1.energy * Math.pow(1 + ge, y)) / sh1 * sh2);
    cum2.push(cum2[y] + c2.energy * Math.pow(1 + ge, y));
    save.push(save[y] + gainEur * Math.pow(1 + ge, y));
  }
  let payback = null;
  if (S.surcout > 0) { for (let y = 1; y <= YEARS; y++) if (save[y] >= S.surcout) { payback = y - 1 + (S.surcout - save[y - 1]) / (save[y] - save[y - 1]); break; } }
  // graphique
  const host = bind('cg-chart'); host.textContent = '';
  const W = Math.max(320, Math.round(host.clientWidth || 640)), Hh = 260, top = 10, base = Hh - 24, left = 46;
  const mx = Math.max(cum1[YEARS], cum2[YEARS]) * 1.05;
  const x = (y) => left + (y / YEARS) * (W - left - 70), yy = (v) => base - (v / mx) * (base - top);
  const svg = sv('svg', { viewBox: `0 0 ${W} ${Hh}`, role: 'img', 'aria-label': 'Dépenses cumulées d\'énergie sur 50 ans, tours A1 et A2' });
  for (const g of niceGrid(mx)) { svg.append(sv('line', { x1: left, x2: W - 70, y1: yy(g), y2: yy(g), stroke: 'rgba(176,196,214,.10)' })); svg.append(sv('text', { x: left - 6, y: yy(g) + 4, 'text-anchor': 'end', 'font-size': 10, fill: '#85919a' }, `${fmt(g / 1e6, 1)} M€`)); }
  for (const y of [0, 10, 20, 30, 40, 50]) svg.append(sv('text', { x: x(y), y: Hh - 6, 'text-anchor': 'middle', 'font-size': 10.5, fill: '#85919a' }, y ? `${y} ans` : 'Livraison'));
  const line = (arr, color, dash) => { let d = ''; arr.forEach((v, i) => { d += (i ? 'L' : 'M') + x(i).toFixed(1) + ',' + yy(v).toFixed(1); }); svg.append(sv('path', { d, fill: 'none', stroke: color, 'stroke-width': 2, 'stroke-dasharray': dash })); };
  line(cum1, '#b8c1c7', '5 4'); line(cum2, '#c9a46a');
  svg.append(sv('text', { x: x(YEARS) + 6, y: yy(cum1[YEARS]) + 4, 'font-size': 12, fill: '#b8c1c7' }, 'Base DCE'));
  svg.append(sv('text', { x: x(YEARS) + 6, y: yy(cum2[YEARS]) + 4, 'font-size': 12, fill: '#c9a46a', 'font-weight': 700 }, 'Variante'));
  if (payback != null) { svg.append(sv('line', { x1: x(payback), x2: x(payback), y1: top, y2: base, stroke: '#ff3d8b', 'stroke-dasharray': '3 3' })); svg.append(sv('text', { x: x(payback) + 5, y: top + 12, 'font-size': 11.5, fill: '#ff3d8b' }, `retour en ${fmt(payback, 1)} ans`)); }
  host.append(el('div', { class: 'chart-wrap' }, svg), el('div', { class: 'key' }, el('span', {}, el('i', { class: 'line', style: { background: '#b8c1c7' } }), 'Tour A1 (base DCE), ramenée à la surface de A2'), el('span', {}, el('i', { class: 'line', style: { background: '#c9a46a' } }), 'Tour A2 (variante), surcoût compris')));
  bind('cg-sub').textContent = 'Chaleur et électricité, € TTC, prix évolutifs. Tour A1 ramenée à la surface de A2 pour comparer à périmètre égal.';
  const out = bind('cg-out'); out.textContent = '';
  const k = (l, v, u, s) => el('div', { class: 'kpi' }, el('span', { class: 'kpi-l', text: l }), el('span', { class: 'kpi-v' }, v, el('small', { text: u })), s ? el('span', { class: 'kpi-s', text: s }) : null);
  out.append(
    k('Économie de la variante, année 1', fmt(gainEur), '€ TTC', `${fmt(gainHeatKwh / 1000, 1)} MWh de chaleur évités, ventilation déduite`),
    k('Économie cumulée sur 50 ans', fmt(save[YEARS] / 1000), 'k€', `Émissions évitées : ${fmt(gainCo2 * YEARS / 1000, 0)} t CO₂e`),
    k('Temps de retour', payback != null ? fmt(payback, 1) : '—', payback != null ? 'ans' : '', S.surcout > 0 ? (payback == null ? 'Non atteint en 50 ans' : `Pour ${fmt(S.surcout)} € de surcoût`) : 'Saisissez le surcoût de la variante'),
  );
}

// ------------------------------------------------------------------ présentation en 5 étapes
function tourSteps() {
  const J = S.J, A = (id) => J.alertes.find(a => a.id === id);
  const T = J.meteo.temperature;
  const jan = monthRanges().findIndex(([a]) => S.days[a].getMonth() === 0);
  const [ja, jb] = monthRanges()[jan];
  let tmin = Infinity; for (let i = ja; i <= jb + 10 && i < S.ND; i++) tmin = Math.min(tmin, T[i]);
  const last = S.ND - 1;
  const per = (z, k) => S.L.filter(l => l.tour === z).reduce((s, l) => s + sumL(l, k, 0, last), 0) / J.tours[z].shab;
  const vent = (z) => sumT(z, 'ventilation', 0, last) / J.tours[z].shab;
  const dH = (1 - per('A2', 'h') / per('A1', 'h')) * 100, rV = vent('A1') / vent('A2');
  const g = variantGain();
  const a145 = A('CH-A1.45'), a173 = A('EA-A1.73'), avhy = J.alertes.find(a => a.type === 'ventilation');
  const x145 = (a145?.titre.match(/×([\d,]+)/) || [])[1] || '2,6';
  return [
    { t: 'Une année dans les deux tours',
      p: 'Chaque fenêtre éclairée est un logement. Chaque jour, le jumeau lit les compteurs déjà prévus au marché (chauffage, eau chaude, eau, électricité) et colore le logement : vert s\'il consomme comme des logements semblables, orange ou rouge s\'il consomme plus.',
      go: () => { closeDetail(); setTab('etat'); setUsage('chauffage'); setColor('statut'); setTower('ALL'); setFloor(0, false); S.twin.markElement(null); S.twin.reset(); S.day = 0; play(); } },
    a145 && { t: 'La vague de froid de janvier',
      p: `Fin janvier, il fait jusqu'à ${fmt(tmin, 1)} °C. Presque tous les logements restent verts : ils chauffent davantage, mais comme leurs voisins. Le logement A1.45, lui, chauffe ${x145} fois plus : une fenêtre restée ouverte. Le jumeau le signale dès le ${fmtDay(dayIndex(a145.debut))}.`,
      go: () => { setTab('alertes'); openAlert(a145, wide()); } },
    a173 && { t: 'Une fuite d\'eau détectée',
      p: `En mars, le compteur d'eau du logement A1.73 indique presque le double d'habitude, même la nuit. Le jumeau prévient au bout de 5 jours : ${fmt(a173.volume_l / 1000, 1)} m³ perdus, soit ${fmt(a173.cout_eur)} €. Sans lui, on l'aurait découvert sur la facture, des mois plus tard.`,
      go: () => { setTab('alertes'); openAlert(a173, wide()); } },
    avhy && { t: 'Une panne que personne ne voit',
      p: `Sur la tour A2, l'extracteur de ventilation de la colonne ${avhy.colonne} ne repasse plus en tirage naturel. L'air est bien renouvelé, personne ne se plaint… mais il consomme ${String(avhy.ratio).replace('.', ',')} fois plus que les huit autres et sur-ventile la colonne en plein hiver. Le jumeau le repère en comparant les extracteurs entre eux.`,
      go: () => { setTab('alertes'); openAlert(avhy, wide()); } },
    { t: 'Tour A1 ou tour A2 ?',
      p: `Sur l'année, la tour A2 (variante du groupe) chauffe ${fmt(dH)} % de moins par m² que la tour A1 (DCE), et ses ventilateurs consomment ${fmt(rV, 1)} fois moins. Avec une chaleur de réseau peu chère et peu carbonée, l'économie reste modeste : ≈ ${fmt(g.eur)} € par an. La variante se justifie surtout par la RE2020 et le confort.`,
      go: () => { stop(); closeDetail(); S.twin.markElement(null); setUsage('chauffage'); setPeriod('an'); setTab('cmp'); setTower('ALL'); S.twin.reset(); } },
  ].filter(Boolean);
}
const wide = () => window.innerWidth > 900;
function tourShow(i) {
  const steps = S.tourSteps; if (!steps) return;
  S.tourI = Math.max(0, Math.min(steps.length - 1, i));
  const st = steps[S.tourI];
  bind('tour-n').textContent = `Étape ${S.tourI + 1} sur ${steps.length}`;
  bind('tour-t').textContent = st.t; bind('tour-p').textContent = st.p;
  const dots = bind('tour-dots'); dots.textContent = '';
  steps.forEach((_, k) => dots.append(el('i', { class: k === S.tourI ? 'is-on' : '' })));
  $('[data-act="tour-prev"]').disabled = S.tourI === 0;
  $('[data-act="tour-next"]').textContent = S.tourI === steps.length - 1 ? 'Terminer' : 'Suivant';
  stop();
  st.go();
}
function tourStart() {
  S.tourSteps = tourSteps();
  bind('tour').hidden = false; document.body.classList.add('in-tour');
  if (!wide()) $('#jumeau').scrollIntoView({ behavior: reduceMotion() ? 'auto' : 'smooth', block: 'start' });
  tourShow(0);
}
function tourEnd() {
  stop();
  bind('tour').hidden = true; document.body.classList.remove('in-tour');
  S.tourSteps = null;
}
function setColor(c) {
  S.color = c;
  $$('[data-color]').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.color === c)));
  paint(); renderKpis(); if (S.sel) renderDetail();
}

// ------------------------------------------------------------------ démarrage
async function main() {
  const get = (p) => fetch(p, { cache: 'no-cache' }).then(r => { if (!r.ok) throw new Error(p); return r.json(); });
  const [J, LG, SE, OU] = await Promise.all([get('data/energie/jumeau.json'), get('data/energie/logements.json'), get('data/energie/series.json'), get('data/energie/ouvrages.json')]);
  prepare(J, LG, SE, OU);
  // surcoût de la variante : repris du comparatif général (estimation par ratios), modifiable
  fetch('data/comparatif/comparatif.json', { cache: 'no-cache' }).then(r => r.ok ? r.json() : null).then(C => {
    if (!C || S.surcout) return;
    S.surcout = C.defauts.delta;
    const inp = document.querySelector('[data-k="surcout"]');
    if (inp) { inp.value = S.surcout; renderCoutGlobal(); }
  }).catch(() => {});
  bind('period-label').textContent = `${MOIS[S.days[0].getMonth()]} ${S.days[0].getFullYear()} → ${MOIS[S.days[S.ND - 1].getMonth()]} ${S.days[S.ND - 1].getFullYear()}`;
  renderStory();
  let rsT = 0; let lastW = window.innerWidth;
  window.addEventListener('resize', () => { if (Math.abs(window.innerWidth - lastW) < 40) return; lastW = window.innerWidth; clearTimeout(rsT); rsT = setTimeout(renderStory, 250); });
  buildPins();
  wireTimeline();

  const params = new URLSearchParams(location.search);
  const centers = { A1: J.tours.A1.centre, A2: J.tours.A2.centre };
  const ciel = ['nuit', 'bleue', 'jour'].includes(params.get('ciel')) ? params.get('ciel') : 'bleue';
  document.body.dataset.ciel = ciel;
  S.twin = await createTwin($('#stage'), {
    base: 'model/', ciel, logements: S.L, centers, floor0: LG.geometrie.plancher_r1, elementLog: S.index,
    onPick: (id) => { stop(); if (id) selectLogement(id, false); else if (!S.special) closeDetail(); },
    onHover: (id, x, y) => {
      const tip = $('[data-v="tip"]');
      if (!id) { tip.hidden = true; return; }
      const l = S.byId.get(id); const U = USAGE[S.usage];
      const e = ecartOf(l), G = LIGHTS[lightOf(l)];
      const [a, b] = range(); const q = sumL(l, U.key, a, b);
      tip.innerHTML = `<b>Logement ${l.id} · ${l.typo}</b><span><i class="tip-dot" style="background:${G.c}"></i>${G.label}${lightOf(l) === 'vide' ? '' : ` · ${e > 0 ? '+' : '−'}${fmt(Math.abs(e) * 100)} %`}</span><span>${U.label} : ${U.key === 'w' ? `${fmt(q / 1000, 1)} m³` : `${fmt(q)} kWh`} · ≈ ${fmt(euros(U.key, q))} €</span>`;
      tip.style.left = `${x}px`; tip.style.top = `${y}px`; tip.hidden = false;
    },
    onFrame: updatePins,
  });

  updateInsets();
  window.addEventListener('resize', updateInsets);
  const hint = $('[data-v="hint"]');
  if (hint) { const gone = () => hint.classList.add('is-gone'); $('#stage').addEventListener('pointerdown', gone, { once: true }); setTimeout(gone, 7000); }
  // contrôles
  $$('[data-usage]').forEach(b => b.addEventListener('click', () => setUsage(b.dataset.usage)));
  $$('[data-color]').forEach(b => b.addEventListener('click', () => setColor(b.dataset.color)));
  const tabs = $$('[data-tab]');
  tabs.forEach((b, i) => {
    b.addEventListener('click', () => setTab(b.dataset.tab));
    b.addEventListener('keydown', (e) => { const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0; if (d) { e.preventDefault(); setTab(tabs[(i + d + tabs.length) % tabs.length].dataset.tab, true); } });
  });
  $('[data-act="tour"]').addEventListener('click', tourStart);
  $('[data-act="tour-close"]').addEventListener('click', tourEnd);
  $('[data-act="tour-prev"]').addEventListener('click', () => tourShow(S.tourI - 1));
  $('[data-act="tour-next"]').addEventListener('click', () => { if (S.tourI >= S.tourSteps.length - 1) tourEnd(); else tourShow(S.tourI + 1); });
  $$('[data-floor]').forEach(b => b.addEventListener('click', () => setFloor(+b.dataset.floor)));
  $$('[data-tower]').forEach(b => b.addEventListener('click', () => setTower(b.dataset.tower)));
  $('[data-act="play"]').addEventListener('click', toggle);
  $('[data-act="reset"]').addEventListener('click', () => { const pb = $('[data-act="plan"]'); pb.setAttribute('aria-pressed', 'false'); setFloor(0); S.twin.reset(); });
  $('[data-act="fullscreen"]').addEventListener('click', () => S.twin.fullscreen());
  $('[data-act="plan"]').addEventListener('click', (e) => {
    const on = e.currentTarget.getAttribute('aria-pressed') !== 'true';
    e.currentTarget.setAttribute('aria-pressed', String(on));
    if (on && !S.floor) { S.floor = 5; $$('[data-floor]').forEach(b => b.setAttribute('aria-pressed', String(+b.dataset.floor === 5))); S.twin.state.floor = 5; }
    S.twin.state.plan = on; S.twin.setFloor(S.floor); paint();
  });
  $('[data-close-detail]').addEventListener('click', closeDetail);
  const dq = $('#dlg-qr');
  $('#btn-qr').addEventListener('click', () => { stop(); dq.showModal(); });
  dq.querySelector('[data-close]').addEventListener('click', () => dq.close());
  dq.addEventListener('click', (e) => { if (e.target === dq) dq.close(); });
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Escape') return;
    if (S.tourSteps) tourEnd(); else if (!$('#detail').hidden) closeDetail();
  });

  // état initial
  const d = params.get('d'); if (d) { const i = dayIndex(d); if (i >= 0 && i < S.ND) S.day = i; }
  const u = params.get('u'); if (u && USAGE[u]) S.usage = u;
  setPeriod(S.period, false); setUsage(S.usage); setColor(S.color); setDay(S.day); renderTimeline(); renderAlerts();
  const l = params.get('l');
  if (l && S.byId.has(l)) {
    const lg = S.byId.get(l);
    setTimeout(() => { selectLogement(l, true); }, 900);
    if (lg) S.tower = 'ALL';
  }
  if (params.has('presentation')) setTimeout(tourStart, 1200);
  document.documentElement.classList.add('ready');
}
main().catch((e) => {
  console.error(e);
  const st = $('[data-v="status"]'); if (st) { st.hidden = false; st.textContent = 'Le jumeau n\'a pas pu se charger. Rechargez la page.'; }
});
