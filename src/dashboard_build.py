"""Static, mobile-first dashboard. Numbers, one chart, one table, timestamp. No claims about WHY traffic moved."""
import datetime as dt, html
from collections import defaultdict

# (key used in rows, label shown, css colour variable)
SOURCES = [("google", "Google", "--g"), ("pinterest", "Pinterest", "--p"), ("facebook", "Facebook", "--f"),
           ("instagram", "Instagram", "--i"), ("youtube", "YouTube", "--y")]
KEYS = [k for k, _, _ in SOURCES]

CSS = """:root{--bg:#f6f5f2;--ink:#1c2430;--mut:#66707d;--g:#2b6cb0;--p:#c8232c;--f:#5b4bd5;--i:#d6249f;--y:#d97706;--card:#fff;--line:#dcdad4}
@media(prefers-color-scheme:dark){:root{--bg:#12161c;--ink:#e8eaee;--mut:#98a1ad;--g:#63a4ff;--p:#ff6b73;--f:#9d93ff;--i:#ff7ac8;--y:#ffb347;--card:#1b2029;--line:#2c3440}}
*{box-sizing:border-box}body{margin:0;padding:max(16px,env(safe-area-inset-top)) 16px 32px;background:var(--bg);color:var(--ink);font:16px/1.5 Georgia,'Times New Roman',serif;max-width:640px;margin-inline:auto}
h1{font-size:1.4rem;margin:.2em 0}h2{font-size:1rem;margin:1.6em 0 .4em}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.c{background:var(--card);border:1px solid var(--line);padding:12px;border-radius:6px}.c b{display:block;font-size:1.9rem;line-height:1.1;color:var(--k)}.c span{color:var(--mut);font-size:.85rem}
svg{width:100%;height:auto;background:var(--card);border:1px solid var(--line);border-radius:6px}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%}td,th{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}th{color:var(--mut);font-weight:normal}
.w{background:#fff3cd;color:#5c4400;padding:10px;border-radius:6px}.n,.t{color:var(--mut);font-size:.85rem}.lg span{display:inline-block;margin-right:12px;white-space:nowrap}.lg i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px;background:var(--k)}"""

def _sum(rows, source, days, today):
    lo = (today - dt.timedelta(days=days)).isoformat()
    return sum(r["visits"] for r in rows if r["source"] == source and r["day"] >= lo)

def build(rows, ga4_on, ga4_has_data, now=None, pin_rows=None):
    now = now or dt.datetime.utcnow(); today = now.date()
    if not ga4_on: note = "Traffic ke liye GA4 setup chahiye (google.enabled = false)."
    elif not ga4_has_data: note = "GA4 se abhi koi data nahi aaya. Nayi property ko 24-48 ghante lag sakte hain, ya setup adhura hai."
    else: note = ""
    cards = "".join(
        f'<div class="c" style="--k:var({v})"><b>{_sum(rows, k, 7, today)}</b><span>{label}, last 7 days</span></div>'
        f'<div class="c" style="--k:var({v})"><b>{_sum(rows, k, 30, today)}</b><span>{label}, last 30 days</span></div>'
        for k, label, v in SOURCES)
    days = [(today - dt.timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    series = {k: [sum(r["visits"] for r in rows if r["source"] == k and r["day"] == d) for d in days] for k in KEYS}
    mx = max([1] + [x for k in KEYS for x in series[k]])
    def pts(v): return " ".join(f"{i * 300 / 29:.1f},{110 - v[i] * 100 / mx:.1f}" for i in range(30))
    lines = "".join(f'<polyline fill="none" stroke="var({v})" stroke-width="2" points="{pts(series[k])}"/>' for k, _, v in SOURCES)
    legend = "".join(f'<span style="--k:var({v})"><i></i>{label}</span>' for _, label, v in SOURCES)
    tools = defaultdict(lambda: {k: 0 for k in KEYS})
    lo = (today - dt.timedelta(days=30)).isoformat()
    for r in rows:
        if r["day"] >= lo and r["source"] in KEYS: tools[r["tool_slug"]][r["source"]] += r["visits"]
    trs = "".join(f"<tr><td>{html.escape(k)}</td>" + "".join(f"<td>{v[s]}</td>" for s in KEYS) + "</tr>"
                  for k, v in sorted(tools.items(), key=lambda x: -sum(x[1].values())))
    head = "<th>Tool page</th>" + "".join(f"<th>{label}</th>" for _, label, _ in SOURCES)
    table = f"<table><tr>{head}</tr>{trs}</table>" if trs else "<p class=n>Abhi koi tool-page data nahi.</p>"
    pin_html = ""
    if pin_rows:
        tot = lambda k: sum(r[k] for r in pin_rows)
        pin_html = (f'<h2>Pinterest itself (last {len(pin_rows)} days)</h2><div class="grid" style="--k:var(--p)">'
                    f'<div class="c"><b>{tot("impressions")}</b><span>Impressions</span></div>'
                    f'<div class="c"><b>{tot("saves")}</b><span>Saves</span></div>'
                    f'<div class="c"><b>{tot("clicks")}</b><span>Outbound clicks</span></div></div>')
    warn = f'<p class="w">{html.escape(note)}</p>' if note else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<title>Traffic by platform</title><style>{CSS}</style></head><body>'
            f'<h1>Website traffic by platform</h1><p class="t">Updated {now.strftime("%Y-%m-%d %H:%M")} UTC</p>{warn}'
            f'<div class="grid">{cards}</div>'
            f'<h2>Daily visits, last 30 days</h2><svg viewBox="-4 0 308 120" role="img" aria-label="Daily visits by platform">{lines}</svg>'
            f'<p class="n lg">{legend}</p><p class="n">Peak scale: {mx} visits/day.</p>'
            f'{pin_html}<h2>By tool page (30 days)</h2><div class="tw">{table}</div></body></html>')
