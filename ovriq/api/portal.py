"""OVRIQ selvbetjeningsportal: opret node, koeb credits, se saldo — i browseren.

Noeglen gemmes KUN i browserens localStorage (vises een gang). PoW loeses i
JavaScript med WebCrypto. PayPal-return lander paa /credits/return som
auto-capturer og viser resultatet — det lukker redirect-hullet fra sandbox-testen.
"""
from __future__ import annotations

from fastapi.responses import HTMLResponse

STYLE = """<style>
:root{--bg:#07090f;--panel:#0d1220;--neon:#39ff8e;--mag:#ff3df0;--cyan:#3de0ff;--dim:#7a9a88;--txt:#c9e8d6}
*{box-sizing:border-box;margin:0}body{background:var(--bg);color:var(--txt);
font-family:'Segoe UI',system-ui,sans-serif;padding:40px 20px;
background-image:radial-gradient(circle at 30% 0%,#131a2e 0%,var(--bg) 55%)}
.w{max-width:560px;margin:0 auto}.logo{font-family:Consolas,monospace;letter-spacing:5px;color:var(--mag);font-size:14px}
h1{color:#fff;font-size:26px;margin:14px 0 6px}.sub{color:var(--dim);font-size:14px;margin-bottom:24px}
.card{background:var(--panel);border:1px solid #1d2a44;border-radius:12px;padding:22px;margin-bottom:18px}
h2{color:var(--cyan);font-size:15px;margin-bottom:12px}
input,button{font-family:inherit;font-size:15px;border-radius:8px;padding:11px 14px;border:1px solid #2a3a5c}
input{background:#0a0e1a;color:var(--txt);width:100%;margin-bottom:10px}
button{background:transparent;color:var(--neon);border-color:var(--neon);cursor:pointer;width:100%}
button:hover{background:rgba(57,255,142,.08)}button:disabled{opacity:.4;cursor:wait}
.key{font-family:Consolas,monospace;font-size:12px;background:#0a0e1a;padding:10px;border-radius:8px;
word-break:break-all;margin:8px 0;border:1px dashed var(--mag)}
.big{font-size:30px;color:var(--neon);font-family:Consolas,monospace}
.msg{font-size:13px;color:var(--dim);margin-top:8px}.ok{color:var(--neon)}.err{color:#ff4d4d}
a{color:var(--cyan)}</style>"""

PORTAL_HTML = """<!DOCTYPE html><html lang="da"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>OVRIQ Portal</title>
""" + STYLE + """</head><body><div class="w">
<div class="logo">OVRIQ</div><h1>Portal</h1>
<div class="sub">Opret din node, koeb credits, se din saldo. Din noegle gemmes kun i DIN browser.</div>

<div class="card" id="regcard"><h2>1 · Din node</h2>
<div id="noNode"><input id="name" placeholder="Node-navn (fx mit-firma-bot)" maxlength="64">
<button onclick="registerNode()" id="regbtn">Opret node</button>
<div class="msg" id="regmsg"></div></div>
<div id="hasNode" style="display:none">
<div class="msg">Node-id:</div><div class="key" id="nid"></div>
<div class="msg">API-noegle (gem den — vises kun her):</div><div class="key" id="nkey"></div>
<div class="msg">Saldo: <span class="big" id="bal">…</span> <span class="msg">OQ</span></div>
<button onclick="logout()" style="margin-top:10px;border-color:#555;color:#999">Glem node i denne browser</button>
</div></div>

<div class="card"><h2>2 · Koeb credits (1 DKK = 1 OQ)</h2>
<input id="amt" type="number" min="25" max="1000" value="100">
<button onclick="buy()" id="buybtn">Koeb via PayPal</button>
<div class="msg" id="buymsg">Min 25 / max 1.000 DKK. Gavekort-model: credits kan bruges paa markedspladsen, ikke udbetales. <a href="/vilkaar">Vilkaar</a> · <a href="/privatliv">Privatliv</a></div></div>

<div class="card"><h2>3 · Markedet</h2>
<div class="msg">API-dokumentation: <a href="/docs">/docs</a> · Live grid: <a href="/dashboard">/dashboard</a> · SDK: <a href="https://github.com/BeMintalitet/GitHub-org-ovriq-">GitHub</a></div></div>
</div>
<script>
const S = window.localStorage;
async function sha256hex(t){const b=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(t));
return [...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join('')}
async function solvePow(name){let n=0;while(!(await sha256hex(name+':'+n)).startsWith('000'))n++;return n}
function hdrs(){return {'X-Node-Id':S.getItem('nid')||'','X-Api-Key':S.getItem('nkey')||'','Content-Type':'application/json'}}
async function refresh(){if(!S.getItem('nid')){return}
document.getElementById('noNode').style.display='none';
document.getElementById('hasNode').style.display='block';
document.getElementById('nid').textContent=S.getItem('nid');
document.getElementById('nkey').textContent=S.getItem('nkey');
try{const r=await fetch('/ledger/balance',{headers:hdrs()});
document.getElementById('bal').textContent=(await r.json()).balance_oq}catch(e){}}
async function registerNode(){const name=document.getElementById('name').value.trim();
const msg=document.getElementById('regmsg');const btn=document.getElementById('regbtn');
if(!name){msg.textContent='Skriv et navn';return}
btn.disabled=true;msg.textContent='Loeser proof-of-work…';
const nonce=await solvePow(name);msg.textContent='Registrerer…';
const r=await fetch('/nodes/register',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({name:name,pow_nonce:nonce})});const d=await r.json();btn.disabled=false;
if(!r.ok){msg.innerHTML='<span class="err">'+(d.detail||'fejl')+'</span>';return}
S.setItem('nid',d.node_id);S.setItem('nkey',d.api_key);refresh()}
async function buy(){const amt=parseInt(document.getElementById('amt').value);
const msg=document.getElementById('buymsg');const btn=document.getElementById('buybtn');
if(!S.getItem('nid')){msg.innerHTML='<span class="err">Opret en node foerst</span>';return}
btn.disabled=true;msg.textContent='Opretter PayPal-ordre…';
const r=await fetch('/credits/checkout',{method:'POST',headers:hdrs(),
body:JSON.stringify({amount_dkk:amt})});const d=await r.json();
if(!r.ok){btn.disabled=false;msg.innerHTML='<span class="err">'+(d.detail||'fejl')+'</span>';return}
window.location=d.approve_url}
function logout(){S.removeItem('nid');S.removeItem('nkey');location.reload()}
refresh();
</script></body></html>"""

RETURN_HTML = """<!DOCTYPE html><html lang="da"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>OVRIQ · Gennemfoerer koeb</title>
""" + STYLE + """</head><body><div class="w">
<div class="logo">OVRIQ</div><h1 id="h">Gennemfoerer koeb…</h1>
<div class="card"><div class="msg" id="m">Indloeser hos PayPal…</div>
<div class="big" id="res"></div></div>
<a href="/portal">← Tilbage til portalen</a></div>
<script>
const S=window.localStorage;
(async()=>{const p=new URLSearchParams(location.search);const order=p.get('token');
const h=document.getElementById('h');const m=document.getElementById('m');
if(!order){h.textContent='Mangler ordre-id';return}
if(!S.getItem('nid')){h.textContent='Ingen node i denne browser';
m.textContent='Koebet kan indloeses fra den browser hvor noden er oprettet, eller via API: POST /credits/capture/'+order;return}
const r=await fetch('/credits/capture/'+order,{method:'POST',
headers:{'X-Node-Id':S.getItem('nid'),'X-Api-Key':S.getItem('nkey')}});
const d=await r.json();
if(r.ok){h.textContent='Koeb gennemfoert ✔';
document.getElementById('res').textContent='+'+d.credited_oq+' OQ';
m.innerHTML='<span class="ok">Crediteret paa verificerede PayPal-fakta og journalfoert.</span>'}
else{h.textContent='Kunne ikke indloese';m.innerHTML='<span class="err">'+(d.detail||'fejl')+'</span>'}})();
</script></body></html>"""

CANCEL_HTML = """<!DOCTYPE html><html lang="da"><head><meta charset="utf-8">
""" + STYLE + """<title>OVRIQ · Annulleret</title></head><body><div class="w">
<div class="logo">OVRIQ</div><h1>Koeb annulleret</h1>
<div class="card"><div class="msg">Ingen penge er trukket. <a href="/portal">Tilbage til portalen</a></div></div>
</div></body></html>"""


def attach_portal(app) -> None:
    @app.get("/portal", response_class=HTMLResponse, include_in_schema=False)
    async def portal():
        return PORTAL_HTML

    @app.get("/credits/return", response_class=HTMLResponse, include_in_schema=False)
    async def credits_return():
        return RETURN_HTML

    @app.get("/credits/cancel", response_class=HTMLResponse, include_in_schema=False)
    async def credits_cancel():
        return CANCEL_HTML

    from pathlib import Path
    legal_dir = Path(__file__).resolve().parents[2] / "legal"

    def _legal_page(fname: str, title: str) -> str:
        try:
            body = (legal_dir / fname).read_text(encoding="utf-8")
        except OSError:
            body = "Dokumentet er ikke publiceret endnu."
        import html as _h
        return ("<!DOCTYPE html><html lang='da'><head><meta charset='utf-8'>"
                "<title>OVRIQ · " + title + "</title>" + STYLE + "</head><body>"
                "<div class='w'><div class='logo'>OVRIQ</div>"
                "<div class='card'><pre style='white-space:pre-wrap;font-family:inherit;font-size:14px;line-height:1.6'>"
                + _h.escape(body) + "</pre></div>"
                "<a href='/portal'>← Portal</a></div></body></html>")

    @app.get("/vilkaar", response_class=HTMLResponse, include_in_schema=False)
    async def vilkaar():
        return _legal_page("vilkaar.md", "Handelsbetingelser")

    @app.get("/privatliv", response_class=HTMLResponse, include_in_schema=False)
    async def privatliv():
        return _legal_page("privatliv.md", "Privatlivspolitik")
