"""OVRIQ browser-dashboard på / og /dashboard."""
from __future__ import annotations

from fastapi.responses import HTMLResponse

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="da"><head><meta charset="utf-8"><title>OVRIQ LIVE GRID</title>
<style>
:root{--bg:#07090f;--panel:#0d1220;--neon:#39ff8e;--mag:#ff3df0;--cyan:#3de0ff;--dim:#5b7a68;--warn:#ff4d4d}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--neon);font-family:Consolas,'Courier New',monospace;padding:24px;
background-image:radial-gradient(circle at 20% 0%,#131a2e 0%,var(--bg) 60%)}
h1{color:var(--mag);font-size:22px;letter-spacing:4px}h1 span{color:var(--neon)}
.sub{color:var(--dim);font-size:12px;margin:4px 0 20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid #1d2a44;border-radius:10px;padding:14px}
.card .lbl{color:var(--dim);font-size:11px;letter-spacing:2px;text-transform:uppercase}
.card .val{font-size:26px;margin-top:6px;color:var(--neon);text-shadow:0 0 12px rgba(57,255,142,.5)}
.card .val.mag{color:var(--mag)}.card .val.cyan{color:var(--cyan)}
.ok{color:var(--neon)}.bad{color:var(--warn)}
section{margin-top:24px}h2{color:var(--mag);font-size:13px;letter-spacing:3px;margin-bottom:10px}
table{width:100%;border-collapse:collapse;background:var(--panel);border-radius:10px;overflow:hidden;font-size:12px}
th{color:var(--cyan);text-align:left;padding:8px 12px;border-bottom:1px solid #1d2a44;font-size:11px}
td{padding:7px 12px;border-bottom:1px solid #131b2e;color:#9fdcb8}tr:last-child td{border-bottom:none}
.hash{color:#5b7a9a}footer{margin-top:28px;color:var(--dim);font-size:11px}#status{float:right;font-size:12px}
</style></head><body>
<h1>OVRIQ <span>// MARKET GRID</span> <span id="status"></span></h1>
<div class="sub">Markedspladsen for maskiner · OQ credits · journal-sikret · opdaterer hvert sekund</div>
<div class="grid" id="cards"></div>
<section><h2>&#10216; SENESTE HANDLER &#10217;</h2>
<table><thead><tr><th>#</th><th>Ressource</th><th>Pris</th><th>Antal</th><th>K&oslash;ber</th><th>S&aelig;lger</th><th>Kontrakt</th></tr></thead>
<tbody id="trades"></tbody></table></section>
<section><h2>&#10216; AKTIVE UDBUD &#10217;</h2>
<table><thead><tr><th>Ordre</th><th>Ressource</th><th>Pris</th><th>Antal</th><th>S&aelig;lger</th></tr></thead>
<tbody id="listings"></tbody></table></section>
<section><h2>&#10216; JOURNAL / BLOCK CHAIN &#10217;</h2>
<table><thead><tr><th>H&oslash;jde</th><th>Hash</th><th>Forrige</th><th>Txs</th></tr></thead>
<tbody id="blocks"></tbody></table></section>
<footer>ovriq.xyz · API: /docs · health: /health</footer>
<script>
const fmt=n=>typeof n==="number"?n.toLocaleString("da-DK",{maximumFractionDigits:2}):(n??"—");
const short=s=>(s||"").slice(0,12);
const card=(l,v,c="")=>`<div class="card"><div class="lbl">${l}</div><div class="val ${c}">${v}</div></div>`;
async function tick(){try{
const [m,b,l]=await Promise.all([fetch("/metrics").then(r=>r.json()),
fetch("/ledger/blocks?limit=6").then(r=>r.json()),fetch("/market/listings").then(r=>r.json())]);
document.getElementById("status").innerHTML='<span class="ok">&#9679; ONLINE</span>';
const c=m.contracts||{};
document.getElementById("cards").innerHTML=
card("Noder",fmt(m.nodes))+card("Handler",fmt(m.trades_total),"mag")+
card("Volumen (OQ)",m.volume_oq,"mag")+card("Journal-seq",fmt(m.journal_seq),"cyan")+
card("Blokke",fmt(m.blocks),"cyan")+card("Treasury (OQ)",m.treasury_oq)+
card("Afregnet",fmt(c.SETTLED||0))+card("Latency &Oslash;",(m.latency_ms_avg??"—")+" ms")+
card("Ledger",m.ledger_invariant_ok?"&#10004; OK":"&#10008; BRUD",m.ledger_invariant_ok?"":"bad")+
card("K&aelig;de",m.chain_valid?"&#10004; VALID":"&#10008; BRUDT",m.chain_valid?"":"bad");
document.getElementById("trades").innerHTML=(m.last_trades||[]).slice().reverse().map(t=>
`<tr><td>${t.trade_id}</td><td>${t.resource_type}</td><td>${t.price}</td><td>${t.qty}</td>
<td class="hash">${short(t.buyer)}…</td><td class="hash">${short(t.seller)}…</td><td>#${t.contract_id}</td></tr>`).join("")
||'<tr><td colspan="7">Ingen handler endnu…</td></tr>';
document.getElementById("listings").innerHTML=(l.listings||[]).slice(0,8).map(o=>
`<tr><td>${o.order_id}</td><td>${o.resource_type}</td><td>${o.price}</td><td>${o.open_qty}</td>
<td class="hash">${short(o.node_id)}…</td></tr>`).join("")||'<tr><td colspan="5">Ingen udbud…</td></tr>';
document.getElementById("blocks").innerHTML=(b.blocks||[]).slice().reverse().map(x=>
`<tr><td>${x.height}</td><td class="hash">${x.hash.slice(0,22)}…</td><td class="hash">${x.prev.slice(0,22)}…</td><td>${x.txs}</td></tr>`).join("")
||'<tr><td colspan="4">Ingen blokke endnu…</td></tr>';
}catch(e){document.getElementById("status").innerHTML='<span class="bad">&#9679; OFFLINE</span>'}}
tick();setInterval(tick,1000);
</script></body></html>"""


def attach(app) -> None:
    @app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    async def dashboard():
        return DASHBOARD_HTML

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def root():
        return DASHBOARD_HTML
