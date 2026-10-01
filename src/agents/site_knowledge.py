"""Site Knowledge Agent (READ-ONLY). Builds data/tools.json from live public pages. Never invents features."""
import json, re, time
from pathlib import Path
from src.integrations.site_reader import SiteReader
from src.core import llm

STOP = set("the a an and or to of in for on with your you is are it this that can free online tool tools easy file".split())

def derive_keywords(name, text, n=12):
    words = [w for w in re.findall(r"[a-z]{3,}", f"{name} {text}".lower()) if w not in STOP]
    freq = {}
    for w in words: freq[w] = freq.get(w, 0) + 1
    base = [name.lower()] + [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])]
    return list(dict.fromkeys(base))[:n]

def _slug(href):
    return re.sub(r"\.html$", "", href.split("?")[0].rstrip("/").rsplit("/", 1)[-1])

def _listed_slugs(reader):
    """ONE request lists every published page (sitemap first, Blogger feed as backup) -> no 429 rate limits. Empty dict if unavailable."""
    sess, base = getattr(reader, "s", None), getattr(reader, "base", None)
    if not sess or not base: return {}
    ua = {"User-Agent": "EasyFileToolsPinBot/1.0 (read-only; owner site)"}
    def get(path):
        url = base + path
        rp = getattr(reader, "rp", None)
        if rp is not None and not rp.can_fetch("EasyFileToolsPinBot/1.0", url): return None
        r = sess.get(url, headers=ua, timeout=30)
        return r if r.status_code == 200 else None
    out = {}
    try:
        r = get("/sitemap-pages.xml")
        if r:
            for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text):
                if "/p/" in loc: out[_slug(loc)] = {"url": loc.split("?")[0].replace("http://", "https://"), "title": ""}
    except Exception: pass
    if out: return out
    try:
        r = get("/feeds/pages/default?alt=json&max-results=500")
        for e in (r.json().get("feed", {}).get("entry", []) if r else []):
            href = next((l.get("href", "") for l in e.get("link", []) if l.get("rel") == "alternate"), "")
            if href: out[_slug(href)] = {"url": href.split("?")[0].replace("http://", "https://"), "title": (e.get("title") or {}).get("$t", "")}
    except Exception: pass
    return out

def build(root, base_url, reader=None, use_llm=True):
    root = Path(root)
    seed = json.loads((root / "data/tools_seed.json").read_text(encoding="utf-8"))["tools"]
    reader = reader or SiteReader(base_url)
    tools, problems = [], []
    feed, blocked, t0 = _listed_slugs(reader), 0, time.monotonic()
    for name, slug in seed:
        known = feed.get(slug)
        partial = {"url": (known or {}).get("url", ""), "ok": True, "title": (known or {}).get("title", ""), "description": "", "headings": [], "text": "", "js_only": False}
        if feed and not known:
            page = {"url": f"{base_url.rstrip('/')}/p/{slug}.html", "ok": False, "error": "HTTP 404 (ye slug site ki page-list mein nahi hai)"}
        elif known and (blocked >= 2 or time.monotonic() - t0 > 150):
            page = partial
        else:
            page = reader.fetch(f"/p/{slug}.html")
            if known and not page["ok"] and page.get("error") == "HTTP 429": blocked += 1; page = partial
            elif page["ok"]: blocked = 0
        e = {"name": name, "slug": slug, "url": page["url"], "verified": page["ok"]}
        if not page["ok"]:
            problems.append(f"{name}: {page['url']} -> {page['error']} (slug galat ho sakta hai, tools_seed.json mein theek karo)")
            e.update({"what_it_does": "", "keywords": derive_keywords(name, "")}); tools.append(e); continue
        if page["js_only"]:
            problems.append(f"{name}: page text JavaScript se load hota hai, sirf title/description use hoga")
        e.update({"page_title": page["title"], "what_it_does": page["description"], "headings": page["headings"], "page_text_excerpt": page["text"][:800]})
        kws = derive_keywords(name, page["description"] + " " + " ".join(page["headings"]))
        if use_llm and (page["description"] or page["headings"]):
            try:
                out = llm.generate(f"List 15 short Pinterest search keywords (comma separated, no numbering) for the web tool '{name}'. Use ONLY this page info: {page['description']} {' '.join(page['headings'])}")
                kws = list(dict.fromkeys([k.strip().lower() for k in out.split(",") if 2 < len(k.strip()) < 40] + kws))[:20]
            except Exception: pass
        e["keywords"] = kws
        tools.append(e)
    return tools, problems

def save(root, tools):
    p = Path(root) / "data/tools.json"; old = {}
    if p.exists():
        try: old = {t["slug"]: t for t in json.loads(p.read_text(encoding="utf-8"))["tools"]}
        except Exception: pass
    changed = [t["name"] for t in tools if t["slug"] in old and old[t["slug"]].get("what_it_does") != t.get("what_it_does")]
    p.write_text(json.dumps({"tools": tools}, indent=1, ensure_ascii=False), encoding="utf-8")
    return changed
