"""Static, mobile-first dashboard. Numbers, one chart, one table, timestamp. No claims about WHY traffic moved."""
import datetime as dt, html
from collections import defaultdict

def _sum(rows, source, days, today):
    lo = (today - dt.timedelta(days=days)).isoformat()
    return sum(r["visits"] for r in rows if r["source"] == source and r["day"] >= lo)

def build(rows, ga4_on, ga4_has_data, now=None, pin_rows=None):
    now = now or dt.datetime.utcnow(); today = now.date()
    if not ga4_on: note = "Google traffic ke liye GA4 setup chahiye (google.enabled = false)."
    elif not ga4_has_data: note = "GA4 se abhi koi data nahi aaya. Nayi property ko 24-48 ghante lag sakte hain, ya setup adhura hai."
    else: note = ""
    g7, g30, p7, p30 = (_sum(rows, s, d, today) for s, d in (("google", 7), ("google", 30), ("pinterest", 7), ("pinterest", 30)))
    days = [(today - dt.timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    series = {s: [sum(r["visits"] for r in rows if r["source"] == s and r["day"] == d) for d in days] for s in ("google", "pinterest")}
    mx = max([1] + series["google"] + series["pinterest"])
    def pts(v): return " ".join(f"{i * 300 / 29:.1f},{110 - v[i] * 100 / mx:.1f}" for i in range(30))
    tools = defaultdict(lambda: {"google": 0, "pinterest": 0})
    lo = (today - dt.timedelta(days=30)).isoformat()
    for r in rows:
        if r["day"] >= lo: tools[r["tool_slug"]][r["source"]] += r["visits"]
    trs = "".join(f"<tr><td>{html.escape(k)}</td><td>{v['google']}</td><td>{v['pinterest']}</td></tr>" for k, v in sorted(tools.items(), key=lambda x: -(x[1]['google'] + x[1]['pinterest'])))
    table = f"<table><tr><th>Tool page</th><th>Google</th><th>Pinterest</th></tr>{trs}</table>" if trs else "<p class=n>Abhi koi tool-page data nahi.</p>"
    pin_html = ""
    if pin_rows:
        tot = lambda k: sum(r[k] for r in pin_rows)
        pin_html = f'<h2>Pinterest itself (last {len(pin_rows)} days)</h2><div class="grid"><div class="c p"><b>{tot("impressions")}</b><span>Impressions</span></div><div class="c p"><b>{tot("saves")}</b><span>Saves</span></div><div class="c p"><b>{tot("clicks")}</b><span>Outbound clicks</span></div></div>'
    warn = f'<p class="w">{html.escape(note)}</p>' if note else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>Traffic: Google vs Pinterest</title>
<style>:root{{--bg:#f6f5f2;--ink:#1c2430;--mut:#66707d;--g:#2b6cb0;--p:#c8232c;--card:#fff;--line:#dcdad4}}
@media(prefers-color-scheme:dark){{:root{{--bg:#12161c;--ink:#e8eaee;--mut:#98a1ad;--g:#63a4ff;--p:#ff6b73;--card:#1b2029;--line:#2c3440}}}}
*{{box-sizing:border-box}}body{{margin:0;padding:max(16px,env(safe-area-inset-top)) 16px 32px;background:var(--bg);color:var(--ink);font:16px/1.5 Georgia,'Times New Roman',serif;max-width:640px;margin-inline:auto}}
h1{{font-size:1.4rem;margin:.2em 0}}h2{{font-size:1rem;margin:1.6em 0 .4em}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.c{{background:var(--card);border:1px solid var(--line);padding:12px;border-radius:6px}}.c b{{display:block;font-size:1.9rem;line-height:1.1}}.c span{{color:var(--mut);font-size:.85rem}}
.g b{{color:var(--g)}}.p b{{color:var(--p)}}svg{{width:100%;height:auto;background:var(--card);border:1px solid var(--line);border-radius:6px}}
.tw{{overflow-x:auto}}table{{border-collapse:collapse;width:100%}}td,th{{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}}th{{color:var(--mut);font-weight:normal}}
.w{{background:#fff3cd;color:#5c4400;padding:10px;border-radius:6px}}.n,.t{{color:var(--mut);font-size:.85rem}}</style></head><body>
<h1>Website traffic: Google vs Pinterest</h1><p class="t">Updated {now.strftime('%Y-%m-%d %H:%M')} UTC</p>{warn}
<div class="grid"><div class="c g"><b>{g7}</b><span>Google, last 7 days</span></div><div class="c p"><b>{p7}</b><span>Pinterest, last 7 days</span></div>
<div class="c g"><b>{g30}</b><span>Google, last 30 days</span></div><div class="c p"><b>{p30}</b><span>Pinterest, last 30 days</span></div></div>
<h2>Daily visits, last 30 days</h2><svg viewBox="-4 0 308 120" role="img" aria-label="Daily visits from Google (blue) and Pinterest (red)"><polyline fill="none" stroke="var(--g)" stroke-width="2" points="{pts(series['google'])}"/><polyline fill="none" stroke="var(--p)" stroke-width="2" points="{pts(series['pinterest'])}"/></svg>
<p class="n">Blue = Google (organic). Red = Pinterest. Peak scale: {mx} visits/day.</p>
{pin_html}<h2>By tool page (30 days)</h2><div class="tw">{table}</div></body></html>"""
