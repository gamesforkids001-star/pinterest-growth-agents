"""Curator: follows + saves of OTHERS' pins. Follows = manual task list only (no verified official follow endpoint).
Saves of others = API attempt (GET /search/pins + POST /pins/{id}/save); if the API refuses at your access level -> manual task list. Off unless curator.enabled."""
import urllib.parse, re
from src.integrations.pinterest import PinterestError
from src.core import llm

BAD = re.compile(r"\b(nsfw|adult|porn|sexy|casino|bet|crypto giveaway|replica|cracked)\b", re.I)

def relevant(item, topics):
    text = " ".join(str(item.get(k, "")) for k in ("title", "description", "alt_text")).lower()
    if BAD.search(text) or not text.strip(): return False
    return any(t.lower().split()[0] in text for t in topics)

def llm_relevant(item, topics):
    try:
        out = llm.generate(f"Answer only YES or NO. Is this Pinterest pin high quality, family-safe, not spammy and relevant to {', '.join(topics)}?\nTitle: {item.get('title')}\nDescription: {item.get('description')}")
        return out.strip().upper().startswith("Y")
    except Exception:
        return True   # rule-based filter already passed

def tool_for(item, tools):
    text = " ".join(str(item.get(k, "")) for k in ("title", "description")).lower()
    best = max(tools, key=lambda t: sum(1 for k in t.get("keywords", [])[:10] if k in text), default=None)
    return best if best and any(k in text for k in best.get("keywords", [])[:10]) else None

def run_saves(db, client, settings, tools, n):
    """Returns (done, manual_reason or None)."""
    done = 0
    for topic in settings["curator"]["topics"]:
        if done >= n: break
        try: items = client.search_pins(topic, 10)
        except PinterestError as e: return done, f"search/save via API not available at your access level ({e})"
        for it in items:
            if done >= n: break
            if not relevant(it, settings["curator"]["topics"]) or not llm_relevant(it, settings["curator"]["topics"]): continue
            t = tool_for(it, tools); board = (settings["pinterest"]["boards"].get("tools") or {}).get(t["slug"]) if t else None
            if not board: continue
            try:
                client.save_pin(it["id"], board); db.log_action("save_other", True, "relevant", t["slug"], it["id"]); done += 1
            except PinterestError as e: return done, f"save via API refused ({e})"
    return done, None

def manual_tasks(db, settings, n_follow, n_save):
    for i, topic in enumerate(settings["curator"]["topics"][:max(n_follow, n_save, 1)]):
        q = urllib.parse.quote(topic)
        if i < n_save: db.add_task(f"Save 1 achhi, relevant pin (topic: {topic}). Link kholo: https://www.pinterest.com/search/pins/?q={q} . Sirf high-quality, safe pin; matching tool board mein save.")
        if i < n_follow: db.add_task(f"Follow 1 relevant creator (topic: {topic}). Link: https://www.pinterest.com/search/users/?q={q} . Sirf real, active, safe account.")
