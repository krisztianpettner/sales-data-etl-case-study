#!/usr/bin/env python3
"""
Generate the sales dashboard — one self-contained HTML file (dashboard.html).

Reads data/dashboard_data.json (contract v2, produced by export_json.py) and embeds it
as `const DATA = {...}`. Everything is rendered client-side from DATA; this module never
touches the database. Chart.js is inlined from etl/chart.umd.min.js.

Design (2026-10-12 redesign, agreed with the user):
  * one scrollable "story" page, 5 sections: Hol tartunk → Mi jön → Mit hoztunk →
    Kiknek dolgozunk → Adat és módszertan; year + product-line slicers scope everything.
  * every KPI carries context (same calendar window last year, delta, sparkline);
    one-sentence findings are generated from the data, never hand-written.
  * the order register (realized, accrual value) sits next to the funnel WON.
  * colors: TG1 blue / TG2 orange (validated pair), outcome states from the fixed status
    palette, light + dark theme from the same tokens, every chart has a table twin.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import PROJECT_ROOT, DATA_DIR  # noqa: E402

CHARTJS_PATH = Path(__file__).resolve().parent / "chart.umd.min.js"


def generate():
    """Read JSON, return the dashboard HTML as a string."""
    data = json.loads((DATA_DIR / "dashboard_data.json").read_text(encoding="utf-8"))
    cjs = CHARTJS_PATH.read_text(encoding="utf-8") if CHARTJS_PATH.exists() else "/* Chart.js not found */"
    html = TEMPLATE.replace("__CHARTJS__", cjs)
    html = html.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    html = html.replace("__GENERATED__", datetime.now().strftime("%Y-%m-%d %H:%M"))
    return html


TEMPLATE = r"""<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MEGBÍZÓ — Értékesítési áttekintés</title>
<style>
:root{
  color-scheme:light;
  --bg:#f9f9f7; --surface:#fcfcfb; --surface-2:#f3f2ee; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,.10); --shadow:0 1px 2px rgba(11,11,11,.06);
  --tg1:#2a78d6; --tg1-soft:#86b6ef; --tg2:#eb6834; --tg2-soft:#f6b08e; --all:#1baf7a; --all-soft:#8fd9ba;
  --won:#0ca30c; --lost:#d03b3b; --post:#fab219; --open:#898781; --cnr:#c3c2b7; --prep:#5598e7;
  --up:#006300; --down:#b42318; --warn-bg:rgba(250,178,25,.12); --info-bg:rgba(42,120,214,.08);
  --chip:#eeede8; --chip-active:#0b0b0b; --chip-active-ink:#fcfcfb;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    color-scheme:dark;
    --bg:#0d0d0d; --surface:#1a1a19; --surface-2:#232321; --ink:#f0efec; --ink2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10); --shadow:none;
    --tg1:#3987e5; --tg1-soft:#9ec5f4; --tg2:#d95926; --tg2-soft:#f0a07e; --all:#199e70; --all-soft:#7fd1ac;
    --won:#0ca30c; --lost:#e66767; --post:#fab219; --open:#898781; --cnr:#4a4a47; --prep:#6da7ec;
    --up:#0ca30c; --down:#e66767; --warn-bg:rgba(250,178,25,.14); --info-bg:rgba(57,135,229,.12);
    --chip:#2a2a28; --chip-active:#f0efec; --chip-active-ink:#0d0d0d;
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --bg:#0d0d0d; --surface:#1a1a19; --surface-2:#232321; --ink:#f0efec; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10); --shadow:none;
  --tg1:#3987e5; --tg1-soft:#9ec5f4; --tg2:#d95926; --tg2-soft:#f0a07e; --all:#199e70; --all-soft:#7fd1ac;
  --won:#0ca30c; --lost:#e66767; --post:#fab219; --open:#898781; --cnr:#4a4a47; --prep:#6da7ec;
  --up:#0ca30c; --down:#e66767; --warn-bg:rgba(250,178,25,.14); --info-bg:rgba(57,135,229,.12);
  --chip:#2a2a28; --chip-active:#f0efec; --chip-active-ink:#0d0d0d;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:var(--bg);color:var(--ink);line-height:1.45;font-size:15px}
a{color:inherit}
.wrap{max-width:1360px;margin:0 auto;padding:0 24px}
@media(max-width:640px){.wrap{padding:0 16px}}

/* header */
.hdr{position:sticky;top:0;z-index:50;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(10px);border-bottom:1px solid var(--border)}
.hdr .wrap{display:flex;flex-wrap:wrap;align-items:center;gap:10px 18px;padding-top:10px;padding-bottom:10px}
.brand{display:flex;flex-direction:column;margin-right:auto}
.brand h1{font-size:1.05rem;font-weight:700;letter-spacing:.01em}
.brand .asof{font-size:.74rem;color:var(--muted)}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{border:0;background:var(--chip);color:var(--ink2);font:inherit;font-size:.8rem;font-weight:600;padding:6px 13px;border-radius:999px;cursor:pointer;transition:background .15s,color .15s}
.chip:hover{color:var(--ink)}
.chip.active{background:var(--chip-active);color:var(--chip-active-ink)}
.chip.sc-tg1.active{background:var(--tg1);color:#fff}
.chip.sc-tg2.active{background:var(--tg2);color:#fff}
.chip .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:1px}
.theme{border:1px solid var(--border);background:transparent;color:var(--ink2);border-radius:999px;width:34px;height:34px;cursor:pointer;font-size:1rem}

/* sections */
section{padding:30px 0 6px}
.sec-h{display:flex;align-items:baseline;gap:12px;margin-bottom:6px}
.sec-h .n{font-size:.78rem;font-weight:700;color:var(--muted);letter-spacing:.08em}
.sec-h h2{font-size:1.35rem;font-weight:700}
.lead{color:var(--ink2);font-size:.92rem;margin-bottom:16px;max-width:900px}
.grid{display:grid;gap:14px;margin-bottom:14px}
.g2{grid-template-columns:1fr 1fr}.g3{grid-template-columns:repeat(3,1fr)}.g6{grid-template-columns:repeat(6,1fr)}
.g21{grid-template-columns:2fr 1fr}.g12{grid-template-columns:1fr 2fr}
@media(max-width:1100px){.g6{grid-template-columns:repeat(3,1fr)}.g3{grid-template-columns:1fr 1fr}}
@media(max-width:760px){.g2,.g3,.g21,.g12{grid-template-columns:1fr}.g6{grid-template-columns:1fr 1fr}}
.card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:16px 18px;box-shadow:var(--shadow);min-width:0}
.card h3{font-size:.9rem;font-weight:650;margin-bottom:2px;display:flex;align-items:center;gap:8px}
.card .sub{font-size:.76rem;color:var(--muted);margin-bottom:10px}
.card .tools{margin-left:auto;display:flex;gap:6px}
.tbtn{border:1px solid var(--border);background:transparent;color:var(--muted);font:inherit;font-size:.7rem;padding:3px 9px;border-radius:999px;cursor:pointer}
.tbtn.on,.tbtn:hover{color:var(--ink);border-color:var(--axis)}
.plot{position:relative;height:260px}
.plot.tall{height:320px}.plot.short{height:200px}
.plot canvas{width:100%!important;height:100%!important}
.tbl-view{display:none}
.card.show-table .plot{display:none}.card.show-table .tbl-view{display:block}

/* insights */
.insights{display:grid;grid-template-columns:repeat(2,1fr);gap:10px;margin-top:14px}
@media(max-width:760px){.insights{grid-template-columns:1fr}}
.ins{background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--all);border-radius:12px;padding:10px 14px;font-size:.9rem}
.ins.tg1{border-left-color:var(--tg1)}.ins.tg2{border-left-color:var(--tg2)}
.ins b{font-weight:700}

/* KPI tiles */
.kpi{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:14px 16px 10px;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:4px;min-width:0}
.kpi .lbl{font-size:.74rem;color:var(--ink2);font-weight:600}
.kpi .val{font-size:1.7rem;font-weight:700;letter-spacing:-.01em;line-height:1.1}
.kpi .val small{font-size:.9rem;font-weight:600;color:var(--ink2)}
.kpi .delta{font-size:.76rem;font-weight:650;display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.kpi .delta .ref{color:var(--muted);font-weight:500}
.d-up{color:var(--up)}.d-down{color:var(--down)}.d-flat{color:var(--muted)}
.kpi .spark{height:38px;margin-top:4px}
.kpi .foot{font-size:.7rem;color:var(--muted)}

/* tables */
table{width:100%;border-collapse:collapse;font-size:.8rem}
th{padding:6px 8px;text-align:left;color:var(--muted);font-weight:600;font-size:.68rem;text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid var(--grid);white-space:nowrap}
td{padding:6px 8px;border-bottom:1px solid var(--grid);color:var(--ink2);vertical-align:top}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tr.hl td{color:var(--ink);font-weight:650;background:var(--surface-2)}
tr.sub td{font-size:.76rem}
td.k{color:var(--ink);font-weight:600}
.sw{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:.74rem;color:var(--ink2);margin:6px 0 2px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.legend i{display:inline-block;width:12px;height:12px;border-radius:3px}
.legend i.line{height:3px;border-radius:2px;width:16px}

/* pipeline composition bar */
.stack{display:flex;height:22px;border-radius:6px;overflow:hidden;gap:2px;background:var(--surface-2);margin:8px 0 6px}
.stack div{height:100%;min-width:2px}
.cov{font-size:1.5rem;font-weight:700;margin:6px 0 2px}
.cov small{font-size:.8rem;color:var(--ink2);font-weight:500}

/* notes */
.note{border-radius:10px;padding:10px 14px;font-size:.8rem;color:var(--ink2);line-height:1.55;margin-top:10px}
.note.warn{background:var(--warn-bg)}.note.info{background:var(--info-bg)}
.note b{color:var(--ink)}
.dq{display:flex;flex-direction:column;gap:2px}
.dq .v{font-size:1.4rem;font-weight:700}
.dq .l{font-size:.74rem;color:var(--ink2)}
.dq .s{font-size:.7rem;color:var(--muted)}
.ok{color:var(--up)}.bad{color:var(--down)}
.method p{margin:6px 0;font-size:.82rem;color:var(--ink2)}
.method b{color:var(--ink)}
.ftr{padding:26px 0 40px;font-size:.72rem;color:var(--muted);text-align:center}
.age{font-size:.7rem;color:var(--muted)}
.pl-tag{display:inline-block;font-size:.66rem;font-weight:700;padding:1px 6px;border-radius:5px;color:#fff;margin-right:6px}
.pl-TG1{background:var(--tg1)}.pl-TG2{background:var(--tg2)}.pl-S{background:var(--muted)}
.hidden{display:none!important}
@media print{.hdr{position:static}.card,.kpi{break-inside:avoid}}
</style>
</head>
<body>
<header class="hdr"><div class="wrap">
  <div class="brand"><h1>MEGBÍZÓ · Értékesítési áttekintés</h1><div class="asof" id="asof"></div></div>
  <div class="chips" id="year-chips" aria-label="Év"></div>
  <div class="chips" id="scope-chips" aria-label="Termékvonal">
    <button class="chip sc-all active" data-scope="all"><span class="dot" style="background:var(--all)"></span>Összes</button>
    <button class="chip sc-tg1" data-scope="tg1"><span class="dot" style="background:var(--tg1)"></span>TG1 · termékcsoport1</button>
    <button class="chip sc-tg2" data-scope="tg2"><span class="dot" style="background:var(--tg2)"></span>TG2 · termékcsoport2</button>
  </div>
  <button class="theme" id="theme-btn" title="Világos / sötét">◐</button>
</div></header>

<main class="wrap">

<!-- 1 ───────────────────────────────────────────── -->
<section id="s1">
  <div class="sec-h"><span class="n">01</span><h2>Hol tartunk</h2></div>
  <p class="lead" id="lead1"></p>
  <div class="grid g6" id="kpis"></div>
  <div class="insights" id="insights"></div>
</section>

<!-- 2 ───────────────────────────────────────────── -->
<section id="s2">
  <div class="sec-h"><span class="n">02</span><h2>Mi jön — megkeresések és pipeline</h2></div>
  <p class="lead">Van-e 2–3 havi előre látható munkánk? A havi beérkezés mutatja a keresletet, az élő pipeline a már kiajánlott, döntésre váró értéket.</p>
  <div class="grid g2">
    <div class="card" id="c-rfq"><h3>Beérkezett megkeresés havonta <span class="tools"><button class="tbtn tt">Táblázat</button></span></h3><div class="sub">db / hónap, az utolsó 24 hónap · a beérkezés dátuma szerint</div><div class="plot"><canvas></canvas></div><div class="tbl-view"></div></div>
    <div class="card" id="c-kiadott"><h3>Kiadott ajánlatok értéke havonta <span class="tools"><button class="tbtn tt">Táblázat</button></span></h3><div class="sub">ezer EUR / hónap, az utolsó 24 hónap · a megkeresés hónapjához rendelve</div><div class="plot"><canvas></canvas></div><div class="tbl-view"></div></div>
  </div>
  <div class="grid g12">
    <div class="card" id="c-pipe"><h3>Élő pipeline</h3><div class="sub" id="pipe-sub"></div><div id="pipe-body"></div></div>
    <div class="card" id="c-toplive"><h3>A legnagyobb élő ajánlatok</h3><div class="sub">kiajánlott, döntésre vár · a 10 legnagyobb érték</div><div id="toplive"></div></div>
  </div>
</section>

<!-- 3 ───────────────────────────────────────────── -->
<section id="s3">
  <div class="sec-h"><span class="n">03</span><h2>Mit hoztunk — ajánlati funnel és realizált rendelés</h2></div>
  <p class="lead">Évenként, a megkeresés évéhez rendelve: mennyit adtunk ki, mennyi dőlt el, és mi lett belőle. Mellette a rendelésnyilvántartó szerinti realizált érték — ez a szerződött, könyvelt szám.</p>
  <div class="grid g21">
    <div class="card" id="c-funnel"><h3>Ajánlati funnel évenként <span class="tools"><button class="tbtn tt">Táblázat</button></span></h3><div class="sub">kiadott ajánlatérték kimenet szerint, millió EUR · a megkeresés éve szerint</div><div class="plot tall"><canvas></canvas></div><div class="tbl-view"></div></div>
    <div class="card" id="c-conv"><h3>Win rate és konverzió</h3><div class="sub">win rate = nyert / (nyert + vesztett), db · konverzió = nyert érték / kiadott érték</div><div id="conv"></div></div>
  </div>
  <div class="card" id="c-ytable"><h3>Éves összesítő <span class="tools"><button class="tbtn" id="dom-toggle">Magyar / külföldi bontás</button></span></h3><div class="sub">a megkeresés éve szerint · érték millió EUR · a kiválasztott év kiemelve</div><div id="ytable"></div></div>
  <div class="grid g21">
    <div class="card" id="c-real"><h3>Realizált megrendelt érték (rendelésnyilvántartó) <span class="tools"><button class="tbtn tt">Táblázat</button></span></h3><div class="sub">millió EUR a nyilvántartási év szerint, időbeli elhatárolással · termékcsoport3 külön</div><div class="plot"><canvas></canvas></div><div class="tbl-view"></div></div>
    <div class="card" id="c-realcmp"><h3>Funnel-nyert vs. realizált</h3><div class="sub">a kettő más évhez rendel: a funnel a megkeresés, a regiszter a teljesítés évéhez</div><div id="realcmp"></div></div>
  </div>
  <div class="grid g2">
    <div class="card" id="c-quarter"><h3>Ajánlatadási teljesítmény negyedévente</h3><div class="sub">a kiküldés dátuma szerint · a friss negyedévek konverziója még nőhet (nyitott tételek)</div><div id="quarter"></div></div>
    <div class="card" id="c-loss"><h3>Miért nem lett belőle megrendelés <span class="tools"><button class="tbtn tt">Táblázat</button></span></h3><div class="sub">a kiválasztott év, státusz alapján (a forrásban nincs külön bukási-ok mező)</div><div class="plot short"><canvas></canvas></div><div class="tbl-view"></div></div>
  </div>
</section>

<!-- 4 ───────────────────────────────────────────── -->
<section id="s4">
  <div class="sec-h"><span class="n">04</span><h2>Kiknek dolgozunk — piac és ügyfélkör</h2></div>
  <p class="lead">Túlzottan egy piacra támaszkodunk? Bővül-e a vevői kör? Magyar / külföldi súly, a legnagyobb országok és az új vs. visszatérő partnerek.</p>
  <div class="grid g2">
    <div class="card" id="c-dom"><h3>Magyar / külföldi kiadott érték <span class="tools"><button class="tbtn tt">Táblázat</button></span></h3><div class="sub">millió EUR évenként · ország = akivel üzleti kapcsolatban állunk, nem a cégcsoport székhelye</div><div class="plot"><canvas></canvas></div><div class="tbl-view"></div></div>
    <div class="card" id="c-country"><h3>Legnagyobb piacok <span class="tools"><button class="tbtn tt">Táblázat</button></span></h3><div class="sub" id="country-sub"></div><div class="plot"><canvas></canvas></div><div class="tbl-view"></div></div>
  </div>
  <div class="grid g2">
    <div class="card" id="c-partners"><h3>Új és visszatérő partnerek <span class="tools"><button class="tbtn tt">Táblázat</button></span></h3><div class="sub">árajánlatkérő partnerek száma évenként · új = első megkeresés a vizsgált években</div><div class="plot"><canvas></canvas></div><div class="tbl-view"></div></div>
    <div class="card" id="c-ptable"><h3>Ügyfélkör számokban</h3><div class="sub">partnerek és országok évenként</div><div id="ptable"></div></div>
  </div>
</section>

<!-- 5 ───────────────────────────────────────────── -->
<section id="s5">
  <div class="sec-h"><span class="n">05</span><h2>Adat és módszertan</h2></div>
  <p class="lead">Mire lehet építeni és mire kell figyelni. Minden szám a forrás-Excelekből újraszámolva, nem kézzel beírva.</p>
  <div class="grid g6" id="dq"></div>
  <div class="grid g2">
    <div class="card method" id="method"></div>
    <div class="card" id="c-stale"><h3>Elavult nyitott ajánlatok</h3><div class="sub" id="stale-sub"></div><div id="stale"></div></div>
  </div>
</section>

</main>
<footer class="ftr">Generálva: __GENERATED__ · forrás: dashboard.db (ETL) · dashboard_data.json (v2 szerződés) · a diagramok táblázatként is olvashatók</footer>

<script>__CHARTJS__</script>
<script>
const DATA = __DATA__;
const META = DATA._meta;
const state = { year: META.default_year, scope: 'all' };
const charts = {};

// ── formatting (hu) ─────────────────────────────────────────────
const nf0 = new Intl.NumberFormat('hu-HU', { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat('hu-HU', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const nf2 = new Intl.NumberFormat('hu-HU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
function fmtEur(v, opts = {}) {
  if (v == null) return '—';
  const a = Math.abs(v);
  if (a >= 1e6) return nf1.format(v / 1e6) + ' M €';
  if (a >= 1e3) return nf0.format(v / 1e3) + ' k €';
  return nf0.format(v) + ' €';
}
function fmtM(v, nd = 1) { return v == null ? '—' : (nd === 2 ? nf2 : nf1).format(v / 1e6); }
function fmtN(v) { return v == null ? '—' : nf0.format(v); }
function fmtPct(v, nd = 0) { return v == null ? '—' : (nd ? nf1 : nf0).format(v) + ' %'; }
function pctChange(cur, prev) { if (!prev || cur == null) return null; return (cur - prev) / Math.abs(prev) * 100; }
function deltaHtml(cur, prev, { pp = false, upGood = true, ref = 'előző év azonos időszak' } = {}) {
  if (cur == null || prev == null || (!pp && !prev)) return `<span class="delta"><span class="d-flat">n/a</span> <span class="ref">${ref}</span></span>`;
  const d = pp ? cur - prev : pctChange(cur, prev);
  const sign = d > 0 ? '+' : '';
  const cls = Math.abs(d) < 0.5 ? 'd-flat' : ((d > 0) === upGood ? 'd-up' : 'd-down');
  const arrow = Math.abs(d) < 0.5 ? '→' : (d > 0 ? '▲' : '▼');
  const txt = pp ? `${sign}${nf1.format(d)} pp` : `${sign}${nf0.format(d)} %`;
  return `<span class="delta"><span class="${cls}">${arrow} ${txt}</span> <span class="ref">${ref}</span></span>`;
}
const HU_M = ['jan', 'feb', 'már', 'ápr', 'máj', 'jún', 'júl', 'aug', 'szep', 'okt', 'nov', 'dec'];
function mdLabel(md) { const [m, d] = md.split('-'); return `${HU_M[+m - 1]} ${+d}.`; }
function monthLabel(ym) { const [y, m] = ym.split('-'); return `${y.slice(2)} ${HU_M[+m - 1]}`; }
function esc(s) { return String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

// ── theme & tokens ──────────────────────────────────────────────
function cssVar(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
function tokens() {
  return { tg1: cssVar('--tg1'), tg1Soft: cssVar('--tg1-soft'), tg2: cssVar('--tg2'), tg2Soft: cssVar('--tg2-soft'), all: cssVar('--all'), allSoft: cssVar('--all-soft'),
    won: cssVar('--won'), lost: cssVar('--lost'), post: cssVar('--post'), open: cssVar('--open'), cnr: cssVar('--cnr'), prep: cssVar('--prep'),
    ink: cssVar('--ink'), ink2: cssVar('--ink2'), muted: cssVar('--muted'), grid: cssVar('--grid'), axis: cssVar('--axis'), surface: cssVar('--surface'), border: cssVar('--border') };
}
function scopeColor(t) { return state.scope === 'tg1' ? t.tg1 : state.scope === 'tg2' ? t.tg2 : t.all; }
function scopeSoft(t) { return state.scope === 'tg1' ? t.tg1Soft : state.scope === 'tg2' ? t.tg2Soft : t.allSoft; }
function applyTheme(mode) {
  if (mode) document.documentElement.setAttribute('data-theme', mode); else document.documentElement.removeAttribute('data-theme');
  try { mode ? localStorage.setItem('pm-theme', mode) : localStorage.removeItem('pm-theme'); } catch (e) {}
}
try { const t = localStorage.getItem('pm-theme'); if (t) applyTheme(t); } catch (e) {}
document.getElementById('theme-btn').onclick = () => {
  const dark = matchMedia('(prefers-color-scheme: dark)').matches;
  const cur = document.documentElement.getAttribute('data-theme') || (dark ? 'dark' : 'light');
  applyTheme(cur === 'dark' ? 'light' : 'dark'); render();
};

// ── data access ─────────────────────────────────────────────────
const S = () => DATA.scopes[state.scope];
const Y = (y = state.year) => S().years[String(y)];
const YEARS = META.years.map(String);
const prevYear = () => String(+state.year - 1);
function realizedFor(y, pl) { const r = (S().realized[String(y)] || {})[pl]; return r ? r.eur : 0; }
function realizedScope(y) { // TG1+TG2 (no S) for 'all', else the scope's line
  if (state.scope === 'tg1') return realizedFor(y, 'TG1');
  if (state.scope === 'tg2') return realizedFor(y, 'TG2');
  return realizedFor(y, 'TG1') + realizedFor(y, 'TG2');
}
const REG = META.register && META.register.loaded;
const scopeName = () => state.scope === 'tg1' ? 'TG1' : state.scope === 'tg2' ? 'TG2' : 'TG1+TG2';

// ── Chart.js defaults ───────────────────────────────────────────
function chartDefaults(t) {
  Chart.defaults.font.family = 'system-ui,-apple-system,"Segoe UI",sans-serif';
  Chart.defaults.font.size = 11;
  Chart.defaults.color = t.muted;
  Chart.defaults.borderColor = t.grid;
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.plugins.tooltip.backgroundColor = t.surface;
  Chart.defaults.plugins.tooltip.titleColor = t.ink;
  Chart.defaults.plugins.tooltip.bodyColor = t.ink2;
  Chart.defaults.plugins.tooltip.borderColor = t.axis;
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.boxPadding = 4;
  Chart.defaults.plugins.tooltip.usePointStyle = true;
  Chart.defaults.elements.bar.borderRadius = { topLeft: 4, topRight: 4, bottomLeft: 0, bottomRight: 0 };
  Chart.defaults.elements.bar.borderSkipped = false;
  Chart.defaults.elements.line.borderWidth = 2;
  Chart.defaults.elements.point.radius = 3;
  Chart.defaults.elements.point.hoverRadius = 5;
  Chart.defaults.elements.point.borderWidth = 2;
  Chart.defaults.elements.point.borderColor = t.surface;
  Chart.defaults.interaction.mode = 'index';
  Chart.defaults.interaction.intersect = false;
}
function mk(id, cfg) {
  const card = document.getElementById(id); const canvas = card.querySelector('canvas');
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(canvas, cfg);
}
function axisY(t, fmt) { return { grid: { color: t.grid, drawBorder: false }, border: { display: false }, ticks: { callback: fmt, maxTicksLimit: 6 } }; }
function axisX(t, extra = {}) { return { grid: { display: false }, border: { color: t.axis }, ticks: { maxRotation: 0, autoSkip: true, ...extra } }; }
function stackedBar(color, data, label, t, extra = {}) {
  return { label, data, backgroundColor: color, borderColor: t.surface, borderWidth: { top: 2, left: 0, right: 0, bottom: 0 }, maxBarThickness: 28, ...extra };
}
function legendHtml(items) { return `<div class="legend">${items.map(([c, l, line]) => `<span><i class="${line ? 'line' : ''}" style="background:${c}"></i>${esc(l)}</span>`).join('')}</div>`; }
function tableHtml(head, rows, opts = {}) {
  const th = head.map((h, i) => `<th class="${i ? 'n' : ''}">${esc(h)}</th>`).join('');
  const tr = rows.map(r => `<tr class="${r.cls || ''}">${r.cells.map((c, i) => `<td class="${i ? 'n' : 'k'}">${c}</td>`).join('')}</tr>`).join('');
  return `<table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table>`;
}
function setTable(id, html) { document.querySelector(`#${id} .tbl-view`).innerHTML = html; }
document.querySelectorAll('.tbtn.tt').forEach(b => b.onclick = () => { const c = b.closest('.card'); c.classList.toggle('show-table'); b.classList.toggle('on'); });

// ── header ──────────────────────────────────────────────────────
function renderHeader() {
  const yc = document.getElementById('year-chips');
  yc.innerHTML = YEARS.map(y => `<button class="chip ${y === state.year ? 'active' : ''}" data-year="${y}">${y}${Y(y).is_partial ? '*' : ''}</button>`).join('');
  yc.querySelectorAll('.chip').forEach(b => b.onclick = () => { state.year = b.dataset.year; render(); });
  document.querySelectorAll('#scope-chips .chip').forEach(b => { b.classList.toggle('active', b.dataset.scope === state.scope); b.onclick = () => { state.scope = b.dataset.scope; render(); }; });
  const asof = new Date(META.as_of);
  document.getElementById('asof').textContent = `Adatállapot: ${asof.getFullYear()}. ${HU_M[asof.getMonth()]} ${asof.getDate()}. · ${S().label} · ${Y().is_partial ? `${state.year} részév (jan 1 – ${mdLabel(META.through_md)})` : state.year + ' teljes év'}`;
}

// ── 01 KPIs ─────────────────────────────────────────────────────
function sparkline(id, values, color, soft) {
  const el = document.getElementById(id); if (!el) return;
  if (charts[id]) charts[id].destroy();
  const n = values.length;
  charts[id] = new Chart(el, { type: 'bar', data: { labels: values.map((_, i) => i), datasets: [{ data: values, backgroundColor: values.map((_, i) => i === n - 1 ? color : soft), maxBarThickness: 10, borderRadius: 2 }] },
    options: { responsive: true, maintainAspectRatio: false, animation: false, plugins: { tooltip: { enabled: false } }, scales: { x: { display: false }, y: { display: false, beginAtZero: true } } } });
}
function renderKpis() {
  const t = tokens(); const y = Y(); const ytd = y.ytd; const cur = ytd.cur, prev = ytd.prev; const p = S().pipeline;
  const partial = y.is_partial;
  const window = partial ? `jan 1 – ${mdLabel(ytd.through_md)}` : 'teljes év';
  const ref = `vs. ${prevYear()} ${window}`;
  const monthly = S().monthly; const last12 = monthly.slice(-12);
  const regCur = REG ? realizedScope(state.year) : null;
  const tiles = [
    { id: 'k-rfq', lbl: `Beérkezett megkeresés · ${window}`, val: `${fmtN(cur.rfq_n)} <small>db</small>`, delta: deltaHtml(cur.rfq_n, prev.rfq_n, { ref }), spark: last12.map(m => m.rfq_n), foot: `ebből érdemi ajánlat: ${fmtN(cur.quoted_n)} db` },
    { id: 'k-kiadott', lbl: `Kiadott ajánlatok értéke · ${window}`, val: fmtEur(cur.kiadott_eur), delta: deltaHtml(cur.kiadott_eur, prev.kiadott_eur, { ref }), spark: last12.map(m => m.kiadott_eur), foot: `${prevYear()} azonos időszak: ${fmtEur(prev.kiadott_eur)}` },
    { id: 'k-won', lbl: `Megnyert érték (funnel) · ${window}`, val: fmtEur(cur.won_eur), delta: deltaHtml(cur.won_eur, prev.won_eur, { ref }), spark: last12.map(m => m.won_eur), foot: `${fmtN(cur.won_n)} nyert ajánlat · a megkeresés évéhez rendelve` },
    { id: 'k-wr', lbl: `Win rate · ${window}`, val: fmtPct(cur.win_rate), delta: deltaHtml(cur.win_rate, prev.win_rate, { pp: true, ref }), spark: null, foot: `${fmtN(cur.won_n)} nyert / ${fmtN(cur.lost_n)} vesztett · lezárt döntésekből` },
    { id: 'k-pipe', lbl: `Élő pipeline · ${META.pipeline_window_months} hónapon belüli`, val: fmtEur(p.live.eur), delta: `<span class="delta"><span class="d-flat">${fmtN(p.live.n)} db kiajánlott</span> <span class="ref">pillanatkép</span></span>`, spark: null, foot: `+ ${fmtN(p.prep.n)} db előkészítés alatt (${fmtEur(p.prep.eur)}) · ${fmtN(p.stale.n)} db elavult nyitott nincs benne` },
    { id: 'k-rt', lbl: `Ajánlatadási reakcióidő · ${state.year}`, val: y.reaction.median_days == null ? '—' : `${nf1.format(y.reaction.median_days)} <small>nap (medián)</small>`, delta: `<span class="delta"><span class="${y.reaction.within7_pct >= 70 ? 'd-up' : 'd-flat'}">${fmtPct(y.reaction.within7_pct)}</span> <span class="ref">7 napon belül · cél: &lt; 5–7 nap</span></span>`, spark: null, foot: `átlag ${y.reaction.avg_days == null ? '—' : nf1.format(y.reaction.avg_days)} nap · ${fmtN(y.reaction.n)} kiküldött ajánlat alapján` },
  ];
  if (REG) tiles[2] = { id: 'k-real', lbl: `Realizált megrendelés · ${state.year} (regiszter)`, val: fmtEur(regCur), delta: deltaHtml(regCur, realizedScope(prevYear()), { ref: `vs. ${prevYear()} teljes év` }), spark: null, foot: `funnel-nyert ugyanerre az évre: ${fmtEur(y.won_eur)} (${fmtN(y.won_n)} db) · szerződött, elhatárolt érték` };
  document.getElementById('kpis').innerHTML = tiles.map(k => `<div class="kpi"><div class="lbl">${k.lbl}</div><div class="val">${k.val}</div>${k.delta}${k.spark ? `<div class="spark"><canvas id="${k.id}"></canvas></div>` : ''}<div class="foot">${k.foot}</div></div>`).join('');
  tiles.forEach(k => { if (k.spark) sparkline(k.id, k.spark, scopeColor(t), scopeSoft(t)); });
  document.getElementById('lead1').textContent = partial
    ? `${state.year}: részév, ${mdLabel(ytd.through_md)}-ig. Az azonos naptári időszakkal (${prevYear()} ${window}) vetjük össze, nem a teljes előző évvel.`
    : `${state.year}: teljes év, az előző teljes évvel összevetve.`;
}

// ── insights (generated from the data) ──────────────────────────
function renderInsights() {
  const y = Y(); const ytd = y.ytd; const cur = ytd.cur, prev = ytd.prev; const out = []; const yr = state.year; const py = prevYear();
  const sc = state.scope === 'tg1' ? 'tg1' : state.scope === 'tg2' ? 'tg2' : '';
  const opens = YEARS.map(k => Y(k).open_eur); const maxOpen = Math.max(...opens);
  if (y.open_eur === maxOpen && y.open_eur > 0) out.push(`A ${yr}-os megkeresésekből <b>${fmtEur(y.open_eur)}</b> még nyitott — a vizsgált évek legnagyobb nyitott állománya (${fmtN(y.open_n)} ajánlat).`);
  const dk = pctChange(cur.kiadott_eur, prev.kiadott_eur);
  if (dk != null) out.push(`${mdLabel(ytd.through_md)}-ig <b>${fmtEur(cur.kiadott_eur)}</b> értékű ajánlatot adtunk ki, ${dk >= 0 ? '<b>+' : '<b>'}${nf0.format(dk)} %</b> a ${py} azonos időszakához képest (${fmtEur(prev.kiadott_eur)}).`);
  if (y.is_partial && Y(py) && y.kiadott_eur > Y(py).kiadott_eur) out.push(`A ${yr} részév kiadott értéke (<b>${fmtEur(y.kiadott_eur)}</b>) már most meghaladja a teljes ${py}-ös évet (${fmtEur(Y(py).kiadott_eur)}).`);
  if (cur.win_rate != null && prev.win_rate != null) { const d = cur.win_rate - prev.win_rate; out.push(`A win rate <b>${fmtPct(cur.win_rate)}</b> (${fmtN(cur.won_n)} nyert / ${fmtN(cur.lost_n)} vesztett), ${d >= 0 ? '+' : ''}${nf1.format(d)} pp az előző év azonos időszakához képest${y.open_n > cur.won_n + cur.lost_n ? ` — ${fmtN(y.open_n)} ajánlat még eldöntetlen, ez még mozgatja` : ''}.`); }
  if (REG) { const r = realizedScope(yr); if (r) out.push(`A rendelésnyilvántartó szerint ${yr}-ra <b>${fmtEur(r)}</b> realizált ${scopeName()} megrendelés van könyvelve${y.is_partial ? ' eddig' : ''}, a funnel ${fmtEur(y.won_eur)} nyert értéke mellett — a kettő más évhez rendel.`); }
  const kulf = y.dom.kulfoldi.kiadott_eur, tot = y.kiadott_eur; if (tot) out.push(`A kiadott érték <b>${fmtPct(kulf / tot * 100)}</b>-a külföldi partnerhez ment (${fmtN(y.dom.kulfoldi.partners_n)} külföldi, ${fmtN(y.dom.magyar.partners_n)} magyar árajánlatkérő, ${fmtN(y.countries.n)} ország).`);
  const rpY = YEARS.filter(k => Y(k).partners.returning_pct != null); const rp = rpY.map(k => Y(k).partners.returning_pct);
  if (rp.length >= 2 && rp[rp.length - 1] > rp[0]) out.push(`A visszatérő partnerek aránya ${rp[0]} % → <b>${rp[rp.length - 1]} %</b> (${rpY[0]}–${rpY[rpY.length - 1]}): erősödik a törzsvevői bázis.`);
  document.getElementById('insights').innerHTML = out.slice(0, 6).map(s => `<div class="ins ${sc}">${s}</div>`).join('');
}

// ── 02 pipeline ─────────────────────────────────────────────────
function renderPipeline() {
  const t = tokens(); const monthly = S().monthly; const last = monthly.slice(-24);
  const labels = last.map(m => monthLabel(m.month)); const c = scopeColor(t); const soft = scopeSoft(t);
  const curY = String(+state.year);
  const colorFor = m => m.month.startsWith(curY) ? c : soft;
  mk('c-rfq', { type: 'bar', data: { labels, datasets: [{ label: 'Beérkezett', data: last.map(m => m.rfq_n), backgroundColor: last.map(colorFor), maxBarThickness: 24 }] },
    options: { responsive: true, maintainAspectRatio: false, scales: { x: axisX(t), y: { ...axisY(t, v => v), beginAtZero: true } }, plugins: { tooltip: { callbacks: { label: i => ` ${fmtN(i.raw)} db megkeresés · érdemi: ${fmtN(last[i.dataIndex].quoted_n)}` } } } } });
  setTable('c-rfq', tableHtml(['Hónap', 'Beérkezett (db)', 'Érdemi ajánlat (db)', 'Nyert (db)'], last.map(m => ({ cells: [monthLabel(m.month), fmtN(m.rfq_n), fmtN(m.quoted_n), fmtN(m.won_n)] }))));
  mk('c-kiadott', { type: 'bar', data: { labels, datasets: [{ label: 'Kiadott', data: last.map(m => m.kiadott_eur / 1e3), backgroundColor: last.map(colorFor), maxBarThickness: 24 }] },
    options: { responsive: true, maintainAspectRatio: false, scales: { x: axisX(t), y: { ...axisY(t, v => v >= 1000 ? nf0.format(v / 1000) + ' M' : nf0.format(v) + ' k'), beginAtZero: true } }, plugins: { tooltip: { callbacks: { label: i => ` ${fmtEur(last[i.dataIndex].kiadott_eur)} kiadott · nyert: ${fmtEur(last[i.dataIndex].won_eur)}` } } } } });
  setTable('c-kiadott', tableHtml(['Hónap', 'Kiadott (€)', 'Nyert (€)'], last.map(m => ({ cells: [monthLabel(m.month), fmtN(m.kiadott_eur), fmtN(m.won_eur)] }))));

  // pipeline composition
  const p = S().pipeline; const tot = p.live.eur + p.prep.eur + p.stale.eur || 1;
  document.getElementById('pipe-sub').textContent = `pillanatkép ${META.as_of} · élő = QUOTED, a megkeresés ${META.pipeline_window_months} hónapon belüli`;
  let cov = '';
  if (REG) {
    const y = Y(); const months = y.is_partial ? Math.max(1, y.days_elapsed / 30.4) : 12;
    const monthlyReal = realizedScope(state.year) / months;
    const full = YEARS.filter(k => !Y(k).is_partial && Y(k).conversion_pct != null);
    const conv = full.length ? full.reduce((a, k) => a + Y(k).conversion_pct, 0) / full.length / 100 : null;
    const expected = conv != null ? p.live.eur * conv : null;
    if (monthlyReal > 0 && expected != null) cov = `<div class="cov">≈ ${fmtEur(expected)} <small>várható megrendelés az élő pipeline-ból</small></div><div class="sub">durva becslés: élő pipeline × a teljes évek átlagos értékkonverziója (${fmtPct(conv * 100, 1)}, nyert érték / kiadott érték). Ez ≈ <b>${nf1.format(expected / monthlyReal)} havi</b> realizált forgalom a ${state.year}-os ütem szerint (${fmtEur(monthlyReal)}/hó, regiszter).</div>`;
  }
  document.getElementById('pipe-body').innerHTML = `
    <div class="val" style="font-size:1.6rem;font-weight:700">${fmtEur(p.live.eur)} <small style="font-size:.85rem;color:var(--ink2);font-weight:500">${fmtN(p.live.n)} ajánlat</small></div>
    <div class="stack"><div style="width:${p.live.eur / tot * 100}%;background:${c}" title="élő"></div><div style="width:${p.prep.eur / tot * 100}%;background:${t.prep}" title="előkészítés"></div><div style="width:${p.stale.eur / tot * 100}%;background:${t.cnr}" title="elavult"></div></div>
    ${legendHtml([[c, `élő kiajánlott ${fmtEur(p.live.eur)} (${fmtN(p.live.n)} db)`], [t.prep, `előkészítés alatt ${fmtEur(p.prep.eur)} (${fmtN(p.prep.n)} db)`], [t.cnr, `elavult nyitott ${fmtEur(p.stale.eur)} (${fmtN(p.stale.n)} db)`]])}
    <div class="sub" style="margin-top:8px">ebből 90 napon belüli: <b>${fmtEur(p.live_90.eur)}</b> (${fmtN(p.live_90.n)} db)</div>
    ${cov}`;
  document.getElementById('toplive').innerHTML = tableHtml(['Partner', 'Tárgy', 'Érték', 'Kor'], p.top_live.map(q => ({ cells: [`<span class="pl-tag pl-${q.product_line}">${q.product_line}</span>${esc(q.partner)}<div class="age">${esc(q.country || '')}</div>`, `<span style="color:var(--ink2)">${esc((q.subject || '').slice(0, 60))}</span>`, fmtEur(q.eur), `${fmtN(q.age_days)} nap`] })));
}

// ── 03 funnel & realized ────────────────────────────────────────
function renderFunnel() {
  const t = tokens(); const ys = YEARS; const lab = ys.map(y => y + (Y(y).is_partial ? '*' : ''));
  const ds = [
    stackedBar(t.won, ys.map(y => Y(y).won_eur / 1e6), 'Nyert', t),
    stackedBar(t.lost, ys.map(y => Y(y).lost_eur / 1e6), 'Vesztett', t),
    stackedBar(t.post, ys.map(y => Y(y).postponed_eur / 1e6), 'Elhalasztva', t),
    stackedBar(t.open, ys.map(y => Y(y).open_eur / 1e6), 'Nyitott', t),
  ];
  if (state.scope !== 'tg1') ds.push(stackedBar(t.cnr, ys.map(y => Y(y).cnr_eur / 1e6), 'Nem válaszolt (TG2, auto-lezárt)', t));
  mk('c-funnel', { type: 'bar', data: { labels: lab, datasets: ds }, options: { responsive: true, maintainAspectRatio: false, scales: { x: { ...axisX(t), stacked: true }, y: { ...axisY(t, v => nf0.format(v) + ' M'), stacked: true, beginAtZero: true } },
    plugins: { tooltip: { callbacks: { label: i => ` ${i.dataset.label}: ${nf1.format(i.raw)} M €`, footer: it => `Kiadott összesen: ${fmtM(Y(ys[it[0].dataIndex]).kiadott_eur)} M €` } } } } });
  const lg = legendHtml(ds.map(d => [d.backgroundColor, d.label]));
  const card = document.getElementById('c-funnel'); let lgEl = card.querySelector('.legend'); if (lgEl) lgEl.remove(); card.querySelector('.plot').insertAdjacentHTML('beforebegin', lg);
  setTable('c-funnel', tableHtml(['Év', 'Kiadott', 'Nyert', 'Vesztett', 'Elhalasztva', 'Nyitott', 'Nem válaszolt'], ys.map(y => { const b = Y(y); return { cls: y === state.year ? 'hl' : '', cells: [lab[ys.indexOf(y)], fmtM(b.kiadott_eur), fmtM(b.won_eur), fmtM(b.lost_eur), fmtM(b.postponed_eur), fmtM(b.open_eur), fmtM(b.cnr_eur)] }; })) + '<div class="sub">millió EUR</div>');

  // win rate / conversion
  document.getElementById('conv').innerHTML = tableHtml(['Év', 'Érdemi ajánlat', 'Nyert', 'Vesztett', 'Win rate', 'Konverzió'], ys.map(y => { const b = Y(y); return { cls: y === state.year ? 'hl' : '', cells: [y + (b.is_partial ? '*' : ''), fmtN(b.quoted_n), fmtN(b.won_n), fmtN(b.lost_n), fmtPct(b.win_rate), fmtPct(b.conversion_pct, 1)] }; })) +
    `<div class="note info">A konverzió az évek előrehaladtával nő, mert a nyitott ajánlatok eldőlnek; a friss évek konverziója ezért alulbecsült. ${Y().open_n ? `${state.year}: még ${fmtN(Y().open_n)} ajánlat (${fmtEur(Y().open_eur)}) nyitott.` : ''}</div>`;
}
let domMode = false;
document.getElementById('dom-toggle').onclick = e => { domMode = !domMode; e.target.classList.toggle('on', domMode); renderYearTable(); };
function renderYearTable() {
  const ys = YEARS; const head = ['', ...ys.map(y => y + (Y(y).is_partial ? '*' : ''))];
  const row = (label, f, cls = '') => ({ cls, cells: [label, ...ys.map(y => f(Y(y)))] });
  const block = (title, get) => [
    { cls: 'sub', cells: [`<b>${title}</b>`, ...ys.map(() => '')] },
    row('Árajánlatkérők száma', b => fmtN(get(b).partners_n)),
    row('Kiadott ajánlatok értéke', b => fmtM(get(b).kiadott_eur)),
    row('Megrendelt (nyert) érték', b => fmtM(get(b).won_eur)),
    row('Elutasított (vesztett) érték', b => fmtM(get(b).lost_eur)),
    row('Elhalasztott', b => fmtM(get(b).postponed_eur)),
    row('Nyitott / el nem dőlt', b => fmtM(get(b).open_eur)),
    ...(state.scope !== 'tg1' ? [row('Nem válaszolt (auto-lezárt)', b => fmtM(get(b).cnr_eur))] : []),
  ];
  let rows;
  if (domMode) rows = [...block('MAGYAR', b => b.dom.magyar), ...block('KÜLFÖLDI', b => b.dom.kulfoldi), ...block('ÖSSZESEN', b => b)];
  else rows = [
    row('Beérkezett megkeresés (db)', b => fmtN(b.rfq_n)),
    ...(state.scope !== 'tg2' ? [row('ebből nem készült ajánlat (db)', b => fmtN(b.noquote_n), 'sub')] : []),
    row('Érdemi ajánlat (db)', b => fmtN(b.quoted_n)),
    ...block('ÉRTÉK (M EUR)', b => b).slice(1),
    row('Win rate (lezárt döntésekből)', b => fmtPct(b.win_rate)),
    ...(REG ? [row('Realizált megrendelés (regiszter, M EUR)', b => fmtM(realizedScope(ys.find(k => Y(k) === b))), 'hl')] : []),
  ];
  let html = tableHtml(head, rows);
  // highlight selected year column
  html = html.replace(/<\/thead>/, '</thead>');
  document.getElementById('ytable').innerHTML = html + `<div class="sub" style="margin-top:6px">* részév (${mdLabel(META.through_md)}-ig) · magyar/külföldi: a besorolatlan partnerek csak az összesenben</div>`;
  const colIdx = ys.indexOf(state.year) + 1;
  document.querySelectorAll('#ytable tr').forEach(tr => { const c = tr.children[colIdx]; if (c) { c.style.color = 'var(--ink)'; c.style.fontWeight = '650'; c.style.background = 'var(--surface-2)'; } });
}
function renderRealized() {
  const t = tokens(); const card = document.getElementById('c-real');
  if (!REG) { card.querySelector('.plot').innerHTML = '<div class="note warn">A rendelésnyilvántartó nincs betöltve (futtasd az ETL-t a rendelesi_regiszter fájlokkal).</div>'; document.getElementById('realcmp').innerHTML = ''; return; }
  const ys = Object.keys(S().realized).sort(); const lab = ys.map(y => y + (Y(y) && Y(y).is_partial ? '*' : ''));
  const ds = [];
  if (state.scope !== 'tg2') ds.push(stackedBar(t.tg1, ys.map(y => realizedFor(y, 'TG1') / 1e6), 'TG1 termékcsoport1', t));
  if (state.scope !== 'tg1') ds.push(stackedBar(t.tg2, ys.map(y => realizedFor(y, 'TG2') / 1e6), 'TG2 termékcsoport2', t));
  if (state.scope === 'all') ds.push(stackedBar(t.cnr, ys.map(y => realizedFor(y, 'S') / 1e6), 'Termékcsoport3', t));
  mk('c-real', { type: 'bar', data: { labels: lab, datasets: ds }, options: { responsive: true, maintainAspectRatio: false, scales: { x: { ...axisX(t), stacked: true }, y: { ...axisY(t, v => nf0.format(v) + ' M'), stacked: true, beginAtZero: true } },
    plugins: { tooltip: { callbacks: { label: i => ` ${i.dataset.label}: ${nf2.format(i.raw)} M €` } } } } });
  let lgEl = card.querySelector('.legend'); if (lgEl) lgEl.remove(); card.querySelector('.plot').insertAdjacentHTML('beforebegin', legendHtml(ds.map(d => [d.backgroundColor, d.label])));
  setTable('c-real', tableHtml(['Év', 'TG1', 'TG2', 'Termékcsoport3', 'Összesen', 'ebből magyar', 'külföldi', 'besorolatlan'], ys.map(y => { const r = S().realized[y]; const g = pl => r[pl] || { eur: 0, magyar: 0, kulfoldi: 0, na: 0 };
    const lines = state.scope === 'all' ? ['TG1', 'TG2'] : [state.scope.toUpperCase()]; const sum = k => lines.reduce((a, pl) => a + g(pl)[k], 0);
    return { cls: y === state.year ? 'hl' : '', cells: [y, fmtM(g('TG1').eur, 2), fmtM(g('TG2').eur, 2), fmtM(g('S').eur, 2), fmtM(sum('eur') + (state.scope === 'all' ? g('S').eur : 0), 2), fmtM(sum('magyar'), 2), fmtM(sum('kulfoldi'), 2), fmtM(sum('na'), 2)] }; })) + '<div class="sub">millió EUR · a magyar/külföldi bontás az TG1/TG2-re (termékcsoport3 nélkül)</div>');
  document.getElementById('realcmp').innerHTML = tableHtml(['Év', 'Funnel nyert', 'Realizált'], ys.map(y => ({ cls: y === state.year ? 'hl' : '', cells: [y, Y(y) ? fmtM(Y(y).won_eur) : '—', fmtM(realizedScope(y))] }))) +
    `<div class="note info"><b>Miért tér el:</b> a funnel a <b>megkeresés évéhez</b>, a regiszter a <b>teljesítés évéhez</b> könyvel, elhatárolással (egy többéves rendelés minden évben az arra eső összeggel). A bank felé a realizált a mérvadó; a funnel a kereskedelmi aktivitást mutatja.${META.register.hibalista_count ? ` A két oldal egyeztetéséből <b>${META.register.hibalista_count}</b> tételes hibalista készült (${esc(META.register.hibalista_xlsx || 'scripts/_out')}).` : ''}</div>`;
}
function renderQuarterly() {
  const q = S().quarterly.filter(r => r.year >= +state.year - 1);
  document.getElementById('quarter').innerHTML = tableHtml(['Negyedév', 'Kiküldött (db)', 'Kiküldött érték', 'Nyert (db)', 'Nyert érték', 'Win rate'], q.map(r => ({ cls: r.year === +state.year ? '' : 'sub', cells: [r.label, fmtN(r.sent_n), fmtEur(r.sent_eur), fmtN(r.won_n), fmtEur(r.won_eur), fmtPct(r.win_rate)] })));
}
function renderLoss() {
  const t = tokens(); const l = Y().loss; const col = { LOST_COMPETITOR: t.lost, LOST_CUSTOMER: t.post, POSTPONED: t.open, CLOSED_NO_RESPONSE: t.cnr };
  mk('c-loss', { type: 'bar', data: { labels: l.map(x => x.label), datasets: [{ data: l.map(x => x.n), backgroundColor: l.map(x => col[x.status] || t.open), maxBarThickness: 22, borderRadius: { topRight: 4, bottomRight: 4 } }] },
    options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, scales: { x: { ...axisY(t, v => v), beginAtZero: true }, y: { grid: { display: false }, border: { display: false }, ticks: { color: t.ink2 } } }, plugins: { tooltip: { callbacks: { label: i => ` ${fmtN(i.raw)} db · ${fmtEur(l[i.dataIndex].eur)}` } } } } });
  setTable('c-loss', tableHtml(['Státusz', 'db', 'Érték'], l.map(x => ({ cells: [esc(x.label), fmtN(x.n), fmtEur(x.eur)] }))));
}

// ── 04 market ───────────────────────────────────────────────────
function renderMarket() {
  const t = tokens(); const ys = YEARS; const lab = ys.map(y => y + (Y(y).is_partial ? '*' : '')); const c = scopeColor(t), soft = scopeSoft(t);
  const ds = [stackedBar(c, ys.map(y => Y(y).dom.magyar.kiadott_eur / 1e6), 'Magyar', t), stackedBar(soft, ys.map(y => Y(y).dom.kulfoldi.kiadott_eur / 1e6), 'Külföldi', t)];
  mk('c-dom', { type: 'bar', data: { labels: lab, datasets: ds }, options: { responsive: true, maintainAspectRatio: false, scales: { x: { ...axisX(t), stacked: true }, y: { ...axisY(t, v => nf0.format(v) + ' M'), stacked: true, beginAtZero: true } },
    plugins: { tooltip: { callbacks: { label: i => ` ${i.dataset.label}: ${nf1.format(i.raw)} M € (${fmtPct(i.raw / (Y(ys[i.dataIndex]).kiadott_eur / 1e6) * 100)})` } } } } });
  const card = document.getElementById('c-dom'); let lgEl = card.querySelector('.legend'); if (lgEl) lgEl.remove(); card.querySelector('.plot').insertAdjacentHTML('beforebegin', legendHtml(ds.map(d => [d.backgroundColor, d.label])));
  setTable('c-dom', tableHtml(['Év', 'Magyar kiadott', 'Külföldi kiadott', 'Külföldi arány', 'Magyar partner', 'Külföldi partner'], ys.map(y => { const b = Y(y); return { cls: y === state.year ? 'hl' : '', cells: [lab[ys.indexOf(y)], fmtM(b.dom.magyar.kiadott_eur), fmtM(b.dom.kulfoldi.kiadott_eur), fmtPct(b.dom.kulfoldi.kiadott_eur / (b.kiadott_eur || 1) * 100), fmtN(b.dom.magyar.partners_n), fmtN(b.dom.kulfoldi.partners_n)] }; })) + '<div class="sub">millió EUR</div>');

  const cs = Y().countries; const top = cs.top;
  document.getElementById('country-sub').textContent = `${state.year}: kiadott ajánlatérték országonként, a 8 legnagyobb · összesen ${fmtN(cs.n)} ország`;
  mk('c-country', { type: 'bar', data: { labels: top.map(x => x.country), datasets: [{ data: top.map(x => x.kiadott_eur / 1e6), backgroundColor: top.map(x => x.is_domestic === 1 ? c : soft), maxBarThickness: 22, borderRadius: { topRight: 4, bottomRight: 4 } }] },
    options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, scales: { x: { ...axisY(t, v => nf0.format(v) + ' M'), beginAtZero: true }, y: { grid: { display: false }, border: { display: false }, ticks: { color: t.ink2 } } }, plugins: { tooltip: { callbacks: { label: i => ` kiadott ${nf1.format(i.raw)} M € · nyert ${fmtEur(top[i.dataIndex].won_eur)} · ${fmtN(top[i.dataIndex].n)} megkeresés` } } } } });
  setTable('c-country', tableHtml(['Ország', 'Megkeresés', 'Kiadott', 'Nyert'], top.map(x => ({ cells: [esc(x.country), fmtN(x.n), fmtEur(x.kiadott_eur), fmtEur(x.won_eur)] }))));

  const ds2 = [stackedBar(c, ys.map(y => Y(y).partners.returning), 'Visszatérő', t), stackedBar(soft, ys.map(y => Y(y).partners.new), 'Új', t), stackedBar(t.cnr, ys.map(y => Y(y).partners.base_year ? Y(y).partners.total : null), 'Bázisév (nem bontható)', t)];
  mk('c-partners', { type: 'bar', data: { labels: lab, datasets: ds2 }, options: { responsive: true, maintainAspectRatio: false, scales: { x: { ...axisX(t), stacked: true }, y: { ...axisY(t, v => v), stacked: true, beginAtZero: true } },
    plugins: { tooltip: { callbacks: { label: i => ` ${i.dataset.label}: ${fmtN(i.raw)} partner`, footer: it => `visszatérő arány: ${fmtPct(Y(ys[it[0].dataIndex]).partners.returning_pct)}` } } } } });
  const card2 = document.getElementById('c-partners'); lgEl = card2.querySelector('.legend'); if (lgEl) lgEl.remove(); card2.querySelector('.plot').insertAdjacentHTML('beforebegin', legendHtml(ds2.map(d => [d.backgroundColor, d.label])));
  setTable('c-partners', tableHtml(['Év', 'Összes', 'Új', 'Visszatérő', 'Visszatérő arány'], ys.map(y => { const p = Y(y).partners; return { cells: [y + (p.base_year ? ' (bázisév)' : ''), fmtN(p.total), fmtN(p.new), fmtN(p.returning), fmtPct(p.returning_pct)] }; })));
  document.getElementById('ptable').innerHTML = tableHtml(['', ...lab], [
    { cells: ['Árajánlatkérő partner', ...ys.map(y => fmtN(Y(y).partners.total))] },
    { cells: ['ebből új', ...ys.map(y => fmtN(Y(y).partners.new))], cls: 'sub' },
    { cells: ['— új magyar', ...ys.map(y => fmtN(Y(y).partners.new_magyar))], cls: 'sub' },
    { cells: ['— új külföldi', ...ys.map(y => fmtN(Y(y).partners.new_kulfoldi))], cls: 'sub' },
    { cells: ['Visszatérő arány', ...ys.map(y => fmtPct(Y(y).partners.returning_pct))] },
    { cells: ['Országok száma', ...ys.map(y => fmtN(Y(y).countries.n))] },
    { cells: ['Külföldi árajánlatkérők aránya', ...ys.map(y => fmtPct(Y(y).dom.kulfoldi.partners_n / (Y(y).partners_n || 1) * 100))] },
  ]) + `<div class="note info">Új partner = az adott termékvonalon az első megkeresése a betöltött években. ${YEARS[0]} a bázisév (a korábbi évek nincsenek betöltve), ezért ott az új/visszatérő bontás nem értelmezhető — a banki riport ezt a 2020–2022-es bázissal számolja.</div>`;
}

// ── 05 data quality & method ────────────────────────────────────
function renderQuality() {
  const q = DATA.quality; const r = q.register || {};
  const tile = (v, l, s, cls = '') => `<div class="card dq"><div class="v ${cls}">${v}</div><div class="l">${l}</div><div class="s">${s}</div></div>`;
  document.getElementById('dq').innerHTML = [
    tile(fmtPct(q.tg1.country_cov_pct, 1), 'TG1 ország-lefedettség', `${fmtN(q.tg1.n)} megkeresés 2023-tól`, q.tg1.country_cov_pct >= 99 ? 'ok' : ''),
    tile(fmtPct(q.tg2.country_cov_pct, 1), 'TG2 ország-lefedettség', `${fmtN(q.tg2.n)} megkeresés 2023-tól`, q.tg2.country_cov_pct >= 99 ? 'ok' : ''),
    tile(fmtN(q.stale_open.n), 'elavult nyitott ajánlat', `${fmtEur(q.stale_open.eur)} · 12 hónapnál régebbi, lezárandó`, q.stale_open.n ? 'bad' : 'ok'),
    tile(fmtN(q.tg1.no_date + q.tg2.no_date), 'megkeresés dátum nélkül', 'nem szerepel az időszaki számokban', (q.tg1.no_date + q.tg2.no_date) ? '' : 'ok'),
    tile(r.loaded ? fmtN(r.hibalista_count) : '—', 'regiszter-hibalista tétel', r.loaded ? `egyeztetés a munkaszámon · betöltve ${(r.loaded_at || '').slice(0, 10)}` : 'regiszter nincs betöltve', r.loaded ? '' : 'bad'),
    tile(r.loaded ? fmtPct(r.country_cov_pct, 1) : '—', 'regiszter ország-lefedettség', 'a realizált érték magyar/külföldi bontásához', r.country_cov_pct >= 95 ? 'ok' : ''),
  ].join('');
  document.getElementById('method').innerHTML = `<h3>Módszertan</h3>
    <p><b>Évhez rendelés.</b> A funnel minden ajánlatot a <b>megkeresés évéhez</b> rendel (a banki riporttal azonos definíciók). Kiadott érték = minden ajánlat, amire ajánlat készült; nyitott = kiajánlott vagy előkészítés alatt.</p>
    <p><b>Élő pipeline.</b> Csak a ${META.pipeline_window_months} hónapon belüli, kiajánlott (QUOTED) tételek. A régebbi nyitottak „elavult nyitott” tételek: le kellene zárni őket, addig csak az adatminőség-részben látszanak.</p>
    <p><b>Realizált érték.</b> A rendelesi_regiszter nyilvántartásból, a vállalási ár (EUR) szerint, <b>időbeli elhatárolással</b>: egy többéves rendelés minden évben az arra eső összeggel. Saját gyártás (MEGBÍZÓ → MEGBÍZÓ) kizárva, termékcsoport3 külön soron.</p>
    <p><b>Ország.</b> Azt a partnert jelöli, akivel ténylegesen üzletelünk, nem a cégcsoport székhelyét (pl. egy hazai bejegyzésű cég, amely minden ügyét a külföldi csoporttagon keresztül intézi → külföldi; egy külföldi csoport hazai leánya → Magyarország). A besorolás az admin adatbázisban rögzített operátori döntés.</p>
    <p><b>Win rate.</b> Nyert / (nyert + vesztett), darabban, csak az eldöntött tételekből. Az TG2-nél a válasz nélkül automatikusan lezárt ajánlatok (90–120 nap) nem számítanak vesztettnek — ez tudatos döntés, a win rate-et érdemben mozgatná.</p>
    <p><b>Részév.</b> A ${META.years[META.years.length - 1]} év ${mdLabel(META.through_md)}-ig tart; az összevetés mindig az előző év azonos naptári szakaszával történik.</p>`;
  const st = S().pipeline.top_stale; document.getElementById('stale-sub').textContent = `${fmtN(S().pipeline.stale.n)} db, ${fmtEur(S().pipeline.stale.eur)} · ${META.pipeline_window_months} hónapnál régebbi, még nyitott státuszú · a 10 legnagyobb`;
  document.getElementById('stale').innerHTML = st.length ? tableHtml(['Partner', 'Ajánlat', 'Érték', 'Kor'], st.map(x => ({ cells: [`<span class="pl-tag pl-${x.product_line}">${x.product_line}</span>${esc(x.partner)}`, `${esc(x.quote_id || '')} <span class="age">${x.request_date || ''}</span>`, fmtEur(x.eur), `${fmtN(x.age_days)} nap`] }))) : '<div class="note info">Nincs elavult nyitott ajánlat.</div>';
}

// ── render all ──────────────────────────────────────────────────
function render() {
  const t = tokens(); chartDefaults(t);
  renderHeader(); renderKpis(); renderInsights(); renderPipeline(); renderFunnel(); renderYearTable(); renderRealized(); renderQuarterly(); renderLoss(); renderMarket(); renderQuality();
}
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => render());
render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    out = PROJECT_ROOT / "dashboard.html"
    out.write_text(generate(), encoding="utf-8")
    print(f"Dashboard written to {out} ({out.stat().st_size // 1024} KB)")
