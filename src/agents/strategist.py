"""Pin Strategist: rotates all tools, weights by past performance, picks class/type/angle. Never touches the site."""
import datetime as dt, random
ANGLES = ["problem-solution", "quick how-to", "checklist", "before/after", "format comparison", "cheat sheet", "did you know", "common mistakes", "beginner tips", "time saver"]
SEASONAL = {1: "new-year fresh start", 6: "summer break", 8: "back to school", 9: "back to school", 10: "exam season", 11: "year-end office", 12: "year-end office", 4: "exam season", 5: "exam season"}
TYPES_L = {"image": ["before_after", "quick_how_to", "comparison"], "pdf": ["steps", "checklist", "quick_how_to"], "text": ["cheatsheet", "checklist", "did_you_know"],
           "dev": ["cheatsheet", "did_you_know", "checklist"], "calc": ["quick_facts", "did_you_know", "quick_how_to"]}
IDEA_FORMATS = {"tips": "steps", "cheatsheet": "cheatsheet", "steps": "steps", "checklist": "checklist"}

def category(tool):
    n = (tool["name"] + " " + tool["slug"]).lower()
    if "pdf" in n: return "pdf"
    if "image" in n or "color" in n or "photo" in n: return "image"
    if "json" in n: return "dev"
    if any(k in n for k in ("calculator", "converter", "age", "bmi", "unit", "random", "password", "qr")) and "case" not in n and "image" not in n: return "calc"
    return "text"

def _weeks_l(db, slug):
    since = dt.datetime.fromisoformat(db.now()) - dt.timedelta(days=7)
    return sum(1 for p in db.recent_pins(300) if p["tool_slug"] == slug and p["cls"] == "L" and dt.datetime.fromisoformat(p["ts"]) >= since)

def perf_weights(db):
    """tool -> multiplier 0.7..2.0 from saves+clicks per impression (stored pin_metrics)."""
    rows = db.c.execute("""SELECT p.tool_slug t, SUM(m.impressions) i, SUM(m.saves) s, SUM(m.clicks) c FROM pin_metrics m JOIN pins p ON p.id=m.pin_id GROUP BY p.tool_slug""").fetchall()
    rates = {r["t"]: (r["s"] + 3 * r["c"]) / r["i"] for r in rows if r["i"] and r["i"] >= 50}
    if not rates: return {}
    avg = sum(rates.values()) / len(rates)
    return {t: min(2.0, max(0.7, v / avg if avg else 1)) for t, v in rates.items()}

def pick(tools, settings, db, rng=None):
    rng = rng or random.Random()
    ok = [t for t in tools if t.get("verified") and t.get("url")]
    if not ok: return None
    recent = db.recent_pins(300); w = perf_weights(db)
    cnt = {t["slug"]: sum(1 for p in recent if p["tool_slug"] == t["slug"]) for t in ok}
    weights = [(3.0 if cnt[t["slug"]] == 0 else 1 / (1 + cnt[t["slug"]] ** .7)) * w.get(t["slug"], 1) for t in ok]
    want_l = rng.random() < settings["pins"]["link_share"]
    order = rng.choices(ok, weights=weights, k=len(ok))
    tool = order[0]
    if want_l and _weeks_l(db, tool["slug"]) >= settings["pins"]["max_link_pins_per_tool_per_week"]:
        alt = [t for t in ok if _weeks_l(db, t["slug"]) < settings["pins"]["max_link_pins_per_tool_per_week"]]
        if alt: tool = rng.choice(alt)
        else: want_l = False
    return plan_for(tool, "L" if want_l else "I", settings, db, rng, recent)

def plan_for(tool, cls, settings, db, rng, recent=None):
    recent = recent if recent is not None else db.recent_pins(300)
    cat = category(tool)
    used = [p["meta"].get("angle") for p in recent if p["tool_slug"] == tool["slug"]][:6]
    angles = [a for a in ANGLES if a not in used] or ANGLES
    angle = rng.choice(angles)
    month = dt.date.today().month
    if month in SEASONAL and rng.random() < .25: angle = f"{angle} ({SEASONAL[month]})"
    if cls == "L": ptype = rng.choice(TYPES_L[cat])
    else: ptype = IDEA_FORMATS.get(rng.choice(settings["pins"]["idea_formats"] or ["tips"]), "steps")
    kws = tool.get("keywords", [])[:]; rng.shuffle(kws)
    return {"tool": tool, "cls": cls, "ptype": ptype, "angle": angle, "category": cat, "keywords": (kws[:rng.randint(2, 4)] + [tool["name"].lower(), tool["slug"].replace("-", " ")])[:max(2, min(4, len(kws)))] if len(kws) < 2 else kws[:rng.randint(2, 4)]}
