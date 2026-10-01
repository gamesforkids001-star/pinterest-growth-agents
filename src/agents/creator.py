"""Pinterest Creator: text (LLM, facts-only) + image. Deterministic fallback when LLM is unavailable. Every pin passes Compliance."""
import json, re, uuid, os
from src.core import llm, compliance
from src.images import generator

def _facts(tool):
    return f"Tool: {tool['name']}\nWhat the page says it does: {tool.get('what_it_does','')}\nHeadings: {'; '.join(tool.get('headings', []))}\nPage excerpt: {tool.get('page_text_excerpt','')[:600]}"

def _prompt(plan, errs=None):
    t, cls = plan["tool"], plan["cls"]
    rule = ("Class L (link pin): promote this exact tool honestly. Do NOT claim any feature that is not in the facts." if cls == "L" else
            "Class I (idea pin): a genuinely useful standalone tip list on the tool's TOPIC. Do NOT include any URL, website name, or call to visit. Tips must be accurate general knowledge.")
    return f"""You write Pinterest pins. {rule}
{_facts(t)}
Pin type: {plan['ptype']}. Angle: {plan['angle']}. Keywords to weave in naturally (2-4, no stuffing): {', '.join(plan['keywords'])}
Return ONLY JSON: {{"title": "<=90 chars", "description": "<=400 chars natural sentences", "alt_text": "<=200 chars describes the image", "benefit_line": "<=70 chars honest benefit", "bullets": ["3-5 short lines, <=60 chars each"]}}
Never use: guaranteed, viral, get rich, click here now. English only.{(' Fix these problems from last try: ' + '; '.join(errs)) if errs else ''}"""

def _parse(txt):
    i = txt.find("{")
    if i < 0: return None
    try: obj, _ = json.JSONDecoder().raw_decode(txt[i:])
    except Exception:
        m = re.search(r"\{.*\}", txt, re.S)
        obj = json.loads(m.group(0)) if m else None
    return obj if isinstance(obj, dict) else None

def _fallback(plan):
    t = plan["tool"]; name = t["name"]; d = (t.get("what_it_does") or "").strip()
    if not d: return None
    d = d[:300]
    heads = [h for h in t.get("headings", []) if 3 < len(h) < 60 and h.lower() != name.lower()][:4]
    lead = {"steps": f"How to use {name}", "checklist": f"{name} checklist", "cheatsheet": f"{name} quick reference", "before_after": f"{name}: before and after",
            "quick_how_to": f"Quick how-to: {name}", "did_you_know": f"Did you know? {name}", "comparison": f"Why use {name}", "quick_facts": f"{name} quick facts"}.get(plan["ptype"], f"{name} guide")
    return {"title": lead[:95], "description": d, "alt_text": f"Pin about {name}: {d[:120]}", "benefit_line": d[:70], "bullets": heads[:4]}

def create(plan, settings, pol, db, rng, out_dir, base_url=None):
    pin, errs = _create(plan, settings, pol, db, rng, out_dir, base_url)
    if not pin: print(f"[CREATOR] pin failed for {plan['tool']['slug']}: {errs}")
    return pin, errs

def _create(plan, settings, pol, db, rng, out_dir, base_url=None):
    t, cls = plan["tool"], plan["cls"]
    recent = db.recent_pins(200)
    data, errs_last = None, None
    have_llm = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY"))
    for attempt in range(3):
        cand = None
        if have_llm:
            try:
                raw = llm.generate(_prompt(plan, errs_last)); cand = _parse(raw)
                if cand is None: print(f"[CREATOR] AI reply was not JSON: {str(raw)[:150]!r}")
            except Exception as e:
                print(f"[CREATOR] AI call/parse failed: {type(e).__name__} {str(e)[:150]}"); cand = None
        if cand is None:
            cand = _fallback(plan)
            if cand is None: return None, ["no LLM output and no page facts for fallback"]
            if cls == "I" and len(cand["bullets"]) < 3: plan["cls"] = cls = "L"
        pin = {"cls": cls, "tool_slug": t["slug"], "title": str(cand.get("title", ""))[:100], "description": str(cand.get("description", ""))[:500],
               "alt_text": str(cand.get("alt_text", ""))[:500], "keywords": plan["keywords"][:5], "image": "pending"}
        uid = uuid.uuid4().hex[:10]
        if cls == "L": pin["link"] = f"{t['url']}?utm_source=pinterest&utm_medium=social&utm_campaign={t['slug']}&utm_content={uid}"
        errs = compliance.check_pin(pin, pol, recent)
        if not errs:
            data = (cand, pin, uid); break
        errs_last = errs
    if not data: return None, errs_last or ["creator failed"]
    cand, pin, uid = data
    path = os.path.join(out_dir, f"{t['slug']}-{uid}.jpg")
    layout = {"steps": "steps", "checklist": "checklist", "cheatsheet": "cheatsheet"}.get(plan["ptype"], rng.choice(generator.LAYOUTS))
    bullets = [b for b in cand.get("bullets", []) if isinstance(b, str)][:5]
    if cls == "I" and re.search(r"https?://|www\.|\.com", " ".join(bullets) + cand.get("benefit_line", "")):
        return None, ["Class I image text contained a URL"]
    generator.render({"layout": layout, "title": pin["title"], "benefit": str(cand.get("benefit_line", pin["title"]))[:90], "bullets": bullets, "tool_name": t["name"],
                      "category": plan["category"], "seed": uid}, path, settings["brand"]["name"], settings["brand"]["colors"])
    pin["image"] = path; pin["uid"] = uid; pin["ptype"] = plan["ptype"]; pin["angle"] = plan["angle"]
    return pin, []
