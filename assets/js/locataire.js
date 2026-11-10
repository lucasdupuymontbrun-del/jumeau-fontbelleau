// Page locataire : consommation du logement sur un mois, comparée à des logements semblables,
// à partir des mêmes données que le jumeau (data/energie). Adresse : locataire/?l=A2.36 (option &m=2028-01).

const $ = (s, r = document) => r.querySelector(s);
const bind = (k) => $(`[data-bind="${k}"]`);
const NS = 'http://www.w3.org/2000/svg';
const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
const MOIS_C = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
const USAGES = [
  { u: 'chauffage', k: 'h', label: 'Chauffage', icon: 'i-flame', color: '#d95926' },
  { u: 'ecs', k: 'e', label: 'Eau chaude', icon: 'i-shower', color: '#3987e5' },
  { u: 'eau', k: 'w', label: 'Eau', icon: 'i-drop', color: '#199e70' },
  { u: 'elec', k: 'p', label: 'Électricité', icon: 'i-bolt', color: '#c98500' },
];
const LIGHT = {
  mieux: { c: '#22764a', label: 'Mieux que la moyenne' },
  ok: { c: '#34b27b', label: 'Normal' },
  plus: { c: '#e08a2e', label: 'Un peu plus' },
  trop: { c: '#d03b3b', label: 'Beaucoup plus' },
};
const CONSEIL = {
  chauffage: 'Réglez le thermostat sur 19 °C dans les pièces de vie et fermez les volets la nuit : chaque degré en moins réduit le chauffage d\'environ 7 % (ADEME). Pour aérer, ouvrez grand 5 à 10 minutes plutôt que de laisser une fenêtre entrouverte.',
  ecs: 'L\'eau chaude pèse lourd sur la facture d\'énergie : une douche plus courte et un mousseur sur les robinets la réduisent sans perte de confort.',
  eau: 'Une consommation d\'eau qui ne baisse jamais, même la nuit, peut venir d\'une fuite : vérifiez la chasse d\'eau et signalez tout écoulement au gardien.',
  elec: 'Les appareils en veille et le sèche-linge pèsent lourd : une multiprise à interrupteur coupe les veilles d\'un geste, et un séchage à l\'air libre ne coûte rien.',
  ok: 'Votre consommation est dans la norme. En hiver, aérez 5 à 10 minutes fenêtres grandes ouvertes plutôt que de laisser une fenêtre entrouverte : l\'air se renouvelle sans refroidir les murs.',
};

const S = { J: null, L: [], byId: new Map(), SE: null, days: [], months: [], l: null, m: 0, med: new Map() };

function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') n.className = v; else if (k === 'text') n.textContent = v;
    else if (k.startsWith('on')) n.addEventListener(k.slice(2), v);
    else if (k === 'style' && typeof v === 'object') { for (const [sk, sv] of Object.entries(v)) n.style.setProperty(sk, sv); }
    else n.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) n.append(c.nodeType ? c : document.createTextNode(String(c)));
  return n;
}
function sv(tag, attrs = {}, text) { const n = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) if (v != null) n.setAttribute(k, v); if (text != null) n.textContent = text; return n; }
const icon = (id) => { const s = sv('svg', { class: 'ico', 'aria-hidden': 'true' }); s.append(sv('use', { href: '#' + id })); return s; };
const nf = {};
function fmt(v, d = 0) { if (v == null || !isFinite(v)) return '—'; nf[d] = nf[d] || new Intl.NumberFormat('fr-FR', { minimumFractionDigits: d, maximumFractionDigits: d }); return nf[d].format(v).replace(/ /g, ' '); }
const etage = (n) => (n === 0 ? 'rez-de-chaussée' : n === 1 ? '1er étage' : `${n}e étage`);
const dayOf = (iso) => Math.round((new Date(iso + 'T12:00:00') - S.days[0]) / 86400000);

// somme d'une série sur [a, b] ; -1 = pas de donnée (compteur muet)
function sum(id, k, a, b) {
  const s = S.SE[id][k]; let t = 0, miss = 0;
  for (let i = a; i <= b; i++) { const v = s[i]; if (v < 0) miss++; else t += v; }
  return { t, miss };
}
const toUnit = (k, raw) => (k === 'w' ? raw / 1000 : raw / 10);       // m³ ou kWh
function euros(k, v) { const H = S.J.hypotheses; return k === 'w' ? v * H.prix_eau.valeur : k === 'p' ? v * H.prix_elec.valeur : v / 1000 * H.prix_chaleur.valeur; }

// écart à des logements semblables (même règle que le jumeau)
function ecart(l, U, a, b) {
  if (U.u === 'chauffage') { const r = sum(l.id, 'r', a, b).t; return r > 5 ? sum(l.id, 'h', a, b).t / r - 1 : null; }
  const perOcc = U.u !== 'elec';
  const rate = (x) => { const d = b - Math.max(a, dayOf(x.emmenagement)) + 1; return d > 0 ? sum(x.id, U.k, a, b).t / (perOcc ? x.occupants : 1) / d : 0; };
  const key = `${U.u}|${l.tour}|${perOcc ? '' : l.occupants}|${a}`;
  if (!S.med.has(key)) {
    const vals = S.L.filter((x) => x.tour === l.tour && dayOf(x.emmenagement) <= b && (perOcc || x.occupants === l.occupants)).map(rate).sort((p, q) => p - q);
    S.med.set(key, vals[Math.floor(vals.length / 2)]);
  }
  const med = S.med.get(key);
  return med > 0 ? rate(l) / med - 1 : null;
}
const lightOf = (e) => (e == null ? null : e > 0.30 ? 'trop' : e > 0.20 ? 'plus' : e < -0.10 ? 'mieux' : 'ok');

function monthStats(l, mi) {
  const [a, b] = S.months[mi];
  const em = dayOf(l.emmenagement);
  if (em > b) return { vide: true };
  return USAGES.map((U) => {
    const s = sum(l.id, U.k, Math.max(a, em), b);
    const v = toUnit(U.k, s.t);
    return { ...U, v, eur: euros(U.k, v), miss: s.miss, e: s.miss > (b - a + 1) / 2 ? null : ecart(l, U, a, b) };
  });
}

function renderHero() {
  const l = S.l, h = bind('hero'); h.textContent = '';
  h.append(el('p', { class: 'loc-eyebrow', text: `Tour ${l.tour} · ${etage(l.etage)} · façade ${l.orient}` }),
    el('h1', { class: 'mark loc-title', text: `Logement ${l.id}` }),
    el('p', { class: 'loc-sub', text: `${l.typo} · ${fmt(l.shab)} m² · ${l.occupants} occupant${l.occupants > 1 ? 's' : ''} · emménagement le ${new Date(l.emmenagement + 'T12:00:00').toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}` }));
}

function renderMonths() {
  const nav = bind('months'); nav.textContent = '';
  S.months.forEach(([a], i) => {
    const d = S.days[a];
    const b = el('button', { type: 'button', class: 'loc-m', 'aria-pressed': String(i === S.m), onclick: () => { S.m = i; history.replaceState(null, '', `?l=${S.l.id}&m=${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`); render(); } },
      el('span', { text: MOIS_C[d.getMonth()].replace('.', '') }), el('small', { text: d.getFullYear() }));
    nav.append(b);
  });
  nav.querySelector('[aria-pressed="true"]')?.scrollIntoView({ inline: 'center', block: 'nearest' });
}

function renderMonth() {
  const l = S.l, [a] = S.months[S.m], d = S.days[a];
  const nom = `${MOIS[d.getMonth()]} ${d.getFullYear()}`;
  bind('mois-titre').textContent = `En ${nom}`;
  const st = monthStats(l, S.m), host = bind('cards'); host.textContent = '';
  if (st.vide) {
    bind('total').textContent = 'Le logement n\'était pas encore habité ce mois-là.';
    bind('conseil').textContent = CONSEIL.ok;
    return st;
  }
  const tot = st.reduce((s, x) => s + x.eur, 0);
  bind('total').textContent = `≈ ${fmt(tot)} € d'énergie et d'eau ce mois-ci, dont ${fmt(st[0].eur)} € de chauffage.`;
  for (const x of st) {
    const g = lightOf(x.e);
    const val = x.k === 'w' ? `${fmt(x.v, 1)}` : fmt(x.v);
    const unit = x.k === 'w' ? 'm³' : 'kWh';
    let cmp;
    if (x.miss > 0 && g == null) cmp = el('p', { class: 'loc-cmp is-miss', text: `Compteur sans données pendant ${x.miss} jour${x.miss > 1 ? 's' : ''}` });
    else if (g) {
      const pct = Math.round(Math.abs(x.e) * 100);
      const txt = g === 'ok' ? 'Comme des logements semblables' : g === 'mieux' ? `${pct} % de moins que des logements semblables` : `${pct} % de plus que des logements semblables`;
      cmp = el('p', { class: 'loc-cmp', style: { '--c': LIGHT[g].c } }, el('i'), el('b', { text: LIGHT[g].label }), el('span', { text: txt }));
    }
    host.append(el('article', { class: 'loc-card', style: { '--u': x.color } },
      el('p', { class: 'loc-cl' }, icon(x.icon), x.label),
      el('p', { class: 'loc-cv' }, val, el('small', { text: ` ${unit}` })),
      el('p', { class: 'loc-ce', text: `≈ ${fmt(x.eur)} € TTC` }),
      cmp,
      x.miss > 0 && g != null ? el('p', { class: 'loc-cmp is-miss', text: `${x.miss} jour${x.miss > 1 ? 's' : ''} sans données` }) : null));
  }
  // conseil : l'usage le plus au-dessus des logements semblables
  const worst = st.filter((x) => x.e != null && x.e > 0.10).sort((p, q) => q.e - p.e)[0];
  bind('conseil').textContent = worst ? CONSEIL[worst.u] : CONSEIL.ok;
  return st;
}

function renderAlertes() {
  // alertes du logement en cours pendant le mois affiché
  const l = S.l, [ma, mb] = S.months[S.m];
  const list = S.J.alertes.filter((a) => a.cible === l.id && dayOf(a.debut) <= mb && (!a.fin || dayOf(a.fin) >= ma));
  const sec = bind('alertes'); sec.hidden = !list.length;
  const host = bind('alerte-list'); host.textContent = '';
  for (const a of list) {
    const d0 = new Date(a.debut + 'T12:00:00');
    host.append(el('article', { class: 'loc-alert' },
      el('p', { class: 'loc-al-t' }, icon('i-alert'), a.titre_simple || a.titre),
      el('p', { text: a.resume || '' }),
      el('p', { class: 'loc-al-d', text: `Détecté le ${d0.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}. Ce qui est prévu : ${a.faire || ''}` })));
  }
}

function renderChart() {
  const l = S.l, host = bind('chart'); host.textContent = '';
  const W = Math.max(300, host.clientWidth || 340), H = 170, top = 18, bottom = 24;
  const data = S.months.map((_, i) => { const st = monthStats(l, i); return st.vide ? 0 : st.reduce((s, x) => s + x.eur, 0); });
  const mx = Math.max(...data, 1), bw = W / data.length;
  const svg = sv('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Dépense d\'énergie et d\'eau par mois' });
  data.forEach((v, i) => {
    const h = (H - top - bottom) * v / mx, x = i * bw + bw * 0.18, w = bw * 0.64, y = H - bottom - h;
    const on = i === S.m;
    svg.append(sv('rect', { x, y, width: w, height: Math.max(1, h), rx: 3, fill: on ? '#1e2428' : '#b9c1c5' }));
    if (on) svg.append(sv('text', { x: x + w / 2, y: y - 5, 'text-anchor': 'middle', class: 'loc-cvl' }, `${fmt(v)} €`));
    svg.append(sv('text', { x: x + w / 2, y: H - 7, 'text-anchor': 'middle', class: 'loc-cx' }, MOIS_C[S.days[S.months[i][0]].getMonth()].replace('.', '').slice(0, 4)));
    const hit = sv('rect', { x: i * bw, y: 0, width: bw, height: H, fill: 'transparent', style: 'cursor:pointer' });
    hit.addEventListener('click', () => { S.m = i; render(); });
    svg.append(hit);
  });
  host.append(svg);
}

function render() {
  renderMonths();
  renderMonth();
  renderAlertes();
  renderChart();
}

function chooser() {
  // sans ?l= : choix du logement (démonstration)
  const h = bind('hero'); h.textContent = '';
  h.append(el('h1', { class: 'mark loc-title', text: 'Mon logement' }), el('p', { class: 'loc-sub', text: 'Démonstration : choisissez un logement. En exploitation, chaque locataire arrive directement sur le sien avec le QR code de son livret d\'accueil.' }));
  for (const t of ['A1', 'A2']) {
    const box = el('div', { class: 'loc-pick' }, el('h2', { text: `Tour ${t}` }));
    const grid = el('div', { class: 'loc-pick-grid' });
    for (const l of S.L.filter((x) => x.tour === t)) grid.append(el('a', { href: `?l=${l.id}`, text: l.id }));
    box.append(grid); h.append(box);
  }
  h.append(el('p', { class: 'loc-sub loc-qr' }, 'QR codes à imprimer, un par logement : ',
    el('a', { href: 'qr/QR_logements_A1.pdf', text: 'tour A1' }), ' · ', el('a', { href: 'qr/QR_logements_A2.pdf', text: 'tour A2' }), ' (PDF A4, 12 étiquettes par page).'));
  for (const k of ['months', 'cards', 'total', 'chart']) bind(k).textContent = '';
  document.querySelectorAll('.loc-sec').forEach((s) => { s.hidden = true; });
}

async function main() {
  const get = (p) => fetch(p, { cache: 'no-cache' }).then((r) => { if (!r.ok) throw new Error(p); return r.json(); });
  const [J, LG, SE] = await Promise.all([get('../data/energie/jumeau.json'), get('../data/energie/logements.json'), get('../data/energie/series.json')]);
  S.J = J; S.L = LG.logements; S.SE = SE;
  for (const l of S.L) S.byId.set(l.id, l);
  const d0 = new Date(J.periode.debut + 'T12:00:00');
  S.days = Array.from({ length: J.periode.jours }, (_, i) => new Date(d0.getTime() + i * 86400000));
  let s = 0;
  for (let d = 1; d <= S.days.length; d++) if (d === S.days.length || S.days[d].getMonth() !== S.days[s].getMonth()) { S.months.push([s, d - 1]); s = d; }
  const H = J.hypotheses;
  bind('prix').textContent = `Prix utilisés : chaleur ${fmt(H.prix_chaleur.valeur, 2)} € TTC/MWh, électricité ${fmt(H.prix_elec.valeur, 4)} € TTC/kWh, eau ${fmt(H.prix_eau.valeur, 2)} € TTC/m³. Abonnements non compris.`;
  const q = new URLSearchParams(location.search);
  S.l = S.byId.get((q.get('l') || '').toUpperCase());
  if (!S.l) { chooser(); return; }
  document.title = `Logement ${S.l.id} — Domaine de Fontbelleau`;
  const m = q.get('m');
  const want = m && /^\d{4}-\d{2}$/.test(m) ? S.months.findIndex(([a]) => S.days[a].getFullYear() === +m.slice(0, 4) && S.days[a].getMonth() === +m.slice(5) - 1) : -1;
  S.m = want >= 0 ? want : Math.max(0, S.months.findIndex(([a]) => S.days[a].getMonth() === 0));   // janvier par défaut
  renderHero();
  render();
  let w = window.innerWidth;
  window.addEventListener('resize', () => { if (Math.abs(window.innerWidth - w) > 8) { w = window.innerWidth; renderChart(); } });
}

main().catch((e) => { console.error(e); bind('hero').textContent = 'La page n\'a pas pu être chargée. Rechargez-la.'; });
