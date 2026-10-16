"""Static, mobile-first dashboard. Numbers, one chart, one table, timestamp. No claims about WHY traffic moved.
Premium light UI. Data logic is unchanged: only real rows are shown, nothing is invented."""
import datetime as dt, html, json
from collections import defaultdict

# (key used in rows, label shown, css colour variable)
SOURCES = [("google", "Google", "--g"), ("pinterest", "Pinterest", "--p"), ("facebook", "Facebook", "--f"),
           ("instagram", "Instagram", "--i"), ("youtube", "YouTube", "--y")]
KEYS = [k for k, _, _ in SOURCES]

CSS = """:root{color-scheme:light;--bg:#f6f7f9;--card:#fff;--ink:#0f172a;--mut:#64748b;--line:#e5e7eb;--acc:#2563eb;
--g:#2563eb;--g-t:#dbeafe;--p:#dc2626;--p-t:#fee2e2;--f:#7c3aed;--f-t:#ede9fe;--i:#db2777;--i-t:#fce7f3;--y:#ea580c;--y-t:#ffedd5}
*{box-sizing:border-box}html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased}
.nav{position:sticky;top:0;z-index:10;background:rgba(246,247,249,.92);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);border-bottom:1px solid var(--line);padding-top:env(safe-area-inset-top)}
.nav div{max-width:1040px;margin:0 auto;padding:8px 16px;display:flex;gap:6px}
.nav a{flex:1 1 0;min-width:0;text-align:center;text-decoration:none;color:var(--mut);font-size:.82rem;font-weight:600;padding:8px 4px;border-radius:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.nav a.on{background:#fff;color:var(--acc);box-shadow:0 1px 2px rgba(15,23,42,.08),0 0 0 1px var(--line)}
main{max-width:1040px;margin:0 auto;padding:20px 16px 40px}
section{scroll-margin-top:64px;margin-top:28px}
header h1{font-size:1.45rem;line-height:1.25;margin:0;font-weight:700;letter-spacing:-.01em}
.sub{margin:4px 0 0;color:var(--mut);font-size:.9rem}.upd{margin:8px 0 0;color:#94a3b8;font-size:.78rem}
.bn{display:flex;gap:10px;align-items:flex-start;margin-top:16px;padding:10px 12px;border-radius:10px;font-size:.85rem;line-height:1.45;border:1px solid}
.bn svg{flex:none;width:18px;height:18px;margin-top:1px}
.bn.warn{background:#fffbeb;border-color:#fde68a;color:#92400e}.bn.ok{background:#f0fdf4;border-color:#bbf7d0;color:#166534}.bn.err{background:#fef2f2;border-color:#fecaca;color:#991b1b}
h2{font-size:1.02rem;margin:0 0 12px;font-weight:700}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.c{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;box-shadow:0 1px 2px rgba(15,23,42,.04);min-width:0;transition:box-shadow .15s,border-color .15s}
@media(hover:hover){.c:hover{box-shadow:0 4px 14px rgba(15,23,42,.08);border-color:#d5d9e0}}
.ch{display:flex;align-items:center;gap:8px;color:var(--ink);font-size:.82rem;font-weight:600}
.ic{width:24px;height:24px;border-radius:7px;background:var(--kt);color:var(--k);display:inline-flex;align-items:center;justify-content:center;font-size:.78rem;font-weight:700}
.v{display:block;font-size:1.7rem;line-height:1.15;font-weight:700;margin:10px 0 6px;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.v.z{color:#94a3b8}
.cf{display:flex;justify-content:space-between;align-items:center;gap:6px;color:var(--mut);font-size:.76rem;flex-wrap:wrap}
.d{font-style:normal;font-weight:600}.d.up{color:#15803d}.d.dn{color:#b91c1c}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;box-shadow:0 1px 2px rgba(15,23,42,.04)}
.lg{display:flex;flex-wrap:wrap;gap:6px 14px;margin:0 0 10px;font-size:.78rem;color:var(--mut)}
.lg span{white-space:nowrap}.lg i,#tip i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;background:var(--k)}
.cw{position:relative}#chart svg{display:block;width:100%;touch-action:pan-y}
#tip{position:absolute;pointer-events:none;background:#0f172a;color:#fff;font-size:.75rem;line-height:1.5;padding:8px 10px;border-radius:8px;box-shadow:0 6px 20px rgba(15,23,42,.25);z-index:5;white-space:nowrap}
#tip[hidden]{display:none}#tip b{display:block;margin-bottom:2px}
.nt{margin:10px 0 0;color:var(--mut);font-size:.78rem}
.empty{text-align:center;color:var(--mut);padding:36px 12px;font-size:.88rem}.empty strong{display:block;color:var(--ink);font-size:.95rem;margin-bottom:4px}
.g3{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px}.g3 .v{margin:0 0 4px}.g3 .l{color:var(--mut);font-size:.8rem}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;font-size:.85rem}
th,td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
th{color:var(--mut);font-weight:600;font-size:.74rem;text-transform:uppercase;letter-spacing:.03em;background:#f8fafc}
th:first-child,td:first-child{text-align:left;position:sticky;left:0;background:#fff}th:first-child{background:#f8fafc}
tr:last-child td{border-bottom:0}
.tcard{padding:0;overflow:hidden}
@media(min-width:860px){main{padding-top:28px}header h1{font-size:1.7rem}.grid{grid-template-columns:repeat(5,1fr);grid-template-rows:repeat(2,auto);grid-auto-flow:column}.nav a{flex:0 0 auto;padding:8px 16px}.nav div{justify-content:flex-start}}
@media(max-width:339px){.grid{grid-template-columns:1fr}}"""

JS_NAV = """(function(){var L=[].slice.call(document.querySelectorAll('.nav a'));function spy(){var y=window.scrollY+90,c=L[0];L.forEach(function(a){var s=document.querySelector(a.getAttribute('href'));if(s&&s.offsetTop<=y)c=a;});L.forEach(function(a){a.classList.toggle('on',a===c);});}
window.addEventListener('scroll',spy,{passive:true});spy();})();"""

JS_CHART = """(function(){var el=document.getElementById('d');if(!el)return;
var D=JSON.parse(el.textContent),box=document.getElementById('chart'),tip=document.getElementById('tip');
var M=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function fd(s){var p=s.split('-');return M[+p[1]-1]+' '+(+p[2]);}
var cs=getComputedStyle(document.documentElement);function col(v){return cs.getPropertyValue(v).trim();}
var NS='http://www.w3.org/2000/svg';
function mk(t,a){var e=document.createElementNS(NS,t);for(var k in a)e.setAttribute(k,a[k]);return e;}
function draw(){box.innerHTML='';var W=box.clientWidth;if(!W)return;
var H=Math.round(Math.max(210,Math.min(320,W*.5))),L=34,R=10,T=10,B=26,pw=W-L-R,ph=H-T-B,n=D.days.length;
var top=Math.max(4,Math.ceil(D.max/4)*4);
var svg=mk('svg',{width:W,height:H,viewBox:'0 0 '+W+' '+H,role:'img','aria-label':'Daily visits by platform'});
function X(i){return L+pw*i/(n-1);}function Y(v){return T+ph-ph*v/top;}
for(var t=0;t<=4;t++){var v=top/4*t,y=Y(v);
svg.appendChild(mk('line',{x1:L,x2:W-R,y1:y,y2:y,stroke:'#eef0f3','stroke-width':1}));
var tx=mk('text',{x:L-6,y:y+4,'text-anchor':'end','font-size':11,fill:'#94a3b8'});tx.textContent=v;svg.appendChild(tx);}
[0,10,20,n-1].forEach(function(i,j,a){var tx=mk('text',{x:X(i),y:H-6,'text-anchor':j==0?'start':(j==a.length-1?'end':'middle'),'font-size':11,fill:'#94a3b8'});tx.textContent=fd(D.days[i]);svg.appendChild(tx);});
D.s.forEach(function(s){var d=s.v.map(function(v,i){return(i?'L':'M')+X(i).toFixed(1)+' '+Y(v).toFixed(1);}).join(' ');
svg.appendChild(mk('path',{d:d,fill:'none',stroke:col(s.c),'stroke-width':2,'stroke-linejoin':'round','stroke-linecap':'round'}));});
var vl=mk('line',{y1:T,y2:T+ph,stroke:'#cbd5e1','stroke-width':1,visibility:'hidden'});svg.appendChild(vl);
var ov=mk('rect',{x:L,y:T,width:pw,height:ph,fill:'transparent'});svg.appendChild(ov);
function show(ev){var r=svg.getBoundingClientRect(),i=Math.round((ev.clientX-r.left-L)/pw*(n-1));i=Math.max(0,Math.min(n-1,i));
vl.setAttribute('x1',X(i));vl.setAttribute('x2',X(i));vl.setAttribute('visibility','visible');
var h='<b>'+fd(D.days[i])+'</b>';D.s.forEach(function(s){h+='<div><i style="background:'+col(s.c)+'"></i>'+s.n+': <strong>'+s.v[i]+'</strong></div>';});
tip.innerHTML=h;tip.hidden=false;var tw=tip.offsetWidth,left=X(i)+12;if(left+tw>W)left=X(i)-tw-12;if(left<0)left=0;tip.style.left=left+'px';tip.style.top=T+'px';}
function hide(){vl.setAttribute('visibility','hidden');tip.hidden=true;}
ov.addEventListener('pointermove',show);ov.addEventListener('pointerdown',show);ov.addEventListener('pointerleave',hide);
box.appendChild(svg);}
window.addEventListener('resize',draw);draw();})();"""

ICON_INFO = '<svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/></svg>'
ICON_OK = '<svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.7-9.3a1 1 0 00-1.4-1.4L9 10.6 7.7 9.3a1 1 0 00-1.4 1.4l2 2a1 1 0 001.4 0l4-4z" clip-rule="evenodd"/></svg>'

def _sum(rows, source, days, today):
    lo = (today - dt.timedelta(days=days)).isoformat()
    return sum(r["visits"] for r in rows if r["source"] == source and r["day"] >= lo)

def _prev(rows, source, days, today):
    """Visits in the window just before the current one (for a real trend %)."""
    lo = (today - dt.timedelta(days=2 * days)).isoformat()
    hi = (today - dt.timedelta(days=days)).isoformat()
    return sum(r["visits"] for r in rows if r["source"] == source and lo <= r["day"] < hi)

def _card(rows, k, label, v, days, today):
    cur, prev = _sum(rows, k, days, today), _prev(rows, k, days, today)
    delta = ""
    if prev > 0:
        pct = (cur - prev) * 100 / prev
        cls, arrow = ("up", "&#9650;") if pct >= 0 else ("dn", "&#9660;")
        delta = f'<em class="d {cls}">{arrow} {abs(pct):.0f}%</em>'
    z = " z" if cur == 0 else ""
    return (f'<div class="c" style="--k:var({v});--kt:var({v}-t)"><div class="ch"><span class="ic">{html.escape(label[0])}</span>{html.escape(label)}</div>'
            f'<b class="v{z}">{cur}</b><div class="cf"><span>Last {days} days</span>{delta}</div></div>')

def build(rows, ga4_on, ga4_has_data, now=None, pin_rows=None):
    now = now or dt.datetime.utcnow(); today = now.date()
    if not ga4_on:
        note, state = "Google Analytics 4 is turned off (google.enabled = false). Set it up to start seeing traffic data.", "warn"
    elif not ga4_has_data:
        note, state = ("No analytics data available yet. Your Google Analytics property may need 24\u201348 hours to start reporting data, "
                       "or the configuration may need verification."), "warn"
    else:
        note, state = "Showing live data from Google Analytics 4.", "ok"
    banner = f'<div class="bn {state}" role="status">{ICON_OK if state == "ok" else ICON_INFO}<span>{html.escape(note)}</span></div>'
    cards = "".join(_card(rows, k, label, v, 7, today) + _card(rows, k, label, v, 30, today) for k, label, v in SOURCES)
    days = [(today - dt.timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    series = {k: [sum(r["visits"] for r in rows if r["source"] == k and r["day"] == d) for d in days] for k in KEYS}
    mx = max([1] + [x for k in KEYS for x in series[k]])
    total = sum(x for k in KEYS for x in series[k])
    legend = "".join(f'<span style="--k:var({v})"><i></i>{label}</span>' for _, label, v in SOURCES)
    if total > 0:
        data = {"days": days, "max": mx, "s": [{"n": label, "c": v, "v": series[k]} for k, label, v in SOURCES]}
        data_json = json.dumps(data).replace("</", "<\\/")
        chart = (f'<p class="lg">{legend}</p><div class="cw"><div id="chart"></div><div id="tip" hidden></div></div>'
                 f'<p class="nt">Peak: {mx} visits/day.</p>'
                 f'<script type="application/json" id="d">{data_json}</script>')
    else:
        chart = '<div class="empty"><strong>No visits recorded yet</strong>The chart will appear as soon as real traffic data arrives.</div>'
    tools = defaultdict(lambda: {k: 0 for k in KEYS})
    lo = (today - dt.timedelta(days=30)).isoformat()
    for r in rows:
        if r["day"] >= lo and r["source"] in KEYS: tools[r["tool_slug"]][r["source"]] += r["visits"]
    trs = "".join(f"<tr><td>{html.escape(k)}</td>" + "".join(f"<td>{v[s]}</td>" for s in KEYS) + "</tr>"
                  for k, v in sorted(tools.items(), key=lambda x: -sum(x[1].values())))
    head = "<th>Tool page</th>" + "".join(f"<th>{label}</th>" for _, label, _ in SOURCES)
    table = (f'<div class="card tcard"><div class="tw"><table><tr>{head}</tr>{trs}</table></div></div>' if trs
             else '<div class="card empty"><strong>No tool-page data yet</strong>Pages will be listed here once visits are recorded.</div>')
    pin_html, pin_nav = "", ""
    if pin_rows:
        tot = lambda k: sum(r[k] for r in pin_rows)
        pin_nav = '<a href="#pinterest">Pinterest</a>'
        pin_html = (f'<section id="pinterest"><h2>Pinterest itself (last {len(pin_rows)} days)</h2><div class="g3" style="--k:var(--p);--kt:var(--p-t)">'
                    f'<div class="c"><b class="v">{tot("impressions")}</b><span class="l">Impressions</span></div>'
                    f'<div class="c"><b class="v">{tot("saves")}</b><span class="l">Saves</span></div>'
                    f'<div class="c"><b class="v">{tot("clicks")}</b><span class="l">Outbound clicks</span></div></div></section>')
    nav = f'<nav class="nav"><div><a href="#overview">Overview</a><a href="#daily">Daily</a>{pin_nav}<a href="#tools">Tools</a></div></nav>'
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta name="color-scheme" content="light"><title>Website Traffic Analytics</title><style>{CSS}</style></head><body>{nav}<main>'
            f'<header id="overview"><h1>Website Traffic Analytics</h1><p class="sub">Visits to your website, broken down by traffic platform.</p>'
            f'<p class="upd">Updated {now.strftime("%Y-%m-%d %H:%M")} UTC</p>{banner}</header>'
            f'<section><h2>Traffic by platform</h2><div class="grid">{cards}</div></section>'
            f'<section id="daily"><h2>Daily visits, last 30 days</h2><div class="card">{chart}</div></section>'
            f'{pin_html}<section id="tools"><h2>By tool page (30 days)</h2>{table}</section>'
            f'</main><script>{JS_NAV}</script><script>{JS_CHART}</script></body></html>')
