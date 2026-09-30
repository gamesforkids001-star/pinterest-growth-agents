"""Site Knowledge Agent (READ-ONLY). Builds data/tools.json from live public pages. Never invents features."""
import json, re
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

def build(root, base_url, reader=None, use_llm=True):
    root = Path(root)
    seed = json.loads((root / "data/tools_seed.json").read_text(encoding="utf-8"))["tools"]
    reader = reader or SiteReader(base_url)
    tools, problems = [], []
    for name, slug in seed:
        page = reader.fetch(f"/p/{slug}.html")
        e = {"name": name, "slug": slug, "url": page["url"], "verified": page["ok"]}
        if not page["ok"]:
            problems.append(f"{name}: {page['url']} -> {page['error']} (slug galat ho sakta hai, tools_seed.json mein theek karo)")
            e.update({"what_it_does": "", "keywords": derive_keywords(name, "")}); tools.append(e); continue
        if page["js_only"]:
            problems.append(f"{name}: page text JavaScript se load hota hai, sirf title/description use hoga")
        e.update({"page_title": page["title"], "what_it_does": page["description"], "headings": page["headings"], "page_text_excerpt": page["text"][:800]})
        kws = derive_keywords(name, page["description"] + " " + " ".join(page["headings"]))
        if use_llm:
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
