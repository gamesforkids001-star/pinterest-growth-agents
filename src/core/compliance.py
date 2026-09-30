"""Compliance Agent core: every pin/action passes here first. Blocks + returns reasons."""
import re, difflib
from urllib.parse import urlparse, parse_qs

HARD_FORBIDDEN = {"unfollow", "follow_back", "comment", "message", "create_board", "write_website"}  # hard-coded, not configurable

def _words(t): return re.findall(r"[a-z0-9']+", t.lower())

def check_pin(pin, pol, recent=()):
    errs = []
    cls = pin.get("cls")
    if cls not in ("L", "I"): return ["cls must be L or I"]
    for f in pol["required_fields"][cls]:
        if not pin.get(f): errs.append(f"missing field: {f}")
    t, d, a = pin.get("title", ""), pin.get("description", ""), pin.get("alt_text", "")
    if len(t) > pol["title_max"]: errs.append("title too long")
    if len(d) > pol["description_max"]: errs.append("description too long")
    if len(a) > pol["alt_text_max"]: errs.append("alt text too long")
    kws = pin.get("keywords") or []
    if kws and not pol["keywords_min"] <= len(kws) <= pol["keywords_max"]:
        errs.append(f"keywords must be {pol['keywords_min']}-{pol['keywords_max']}")
    blob = f"{t} {d} {a}".lower()
    for w in pol["banned_words"]:
        if w.lower() in blob: errs.append(f"banned word: {w}")
    words = _words(f"{t} {d}")
    if words:
        for k in kws:
            n = sum(1 for _ in re.finditer(re.escape(k.lower()), " ".join(words)))
            if n * max(len(k.split()), 1) / len(words) > pol["keyword_density_max"] and n > 2:
                errs.append(f"keyword stuffing: {k}")
    link = pin.get("link")
    if cls == "L" and link:
        u = urlparse(link)
        if u.scheme != "https" or u.netloc != pol["allowed_domain"]: errs.append("link must be https on own domain")
        if "m" in parse_qs(u.query): errs.append("link must be canonical (no ?m=1)")
    if cls == "I":
        if link: errs.append("Class I must not have a link")
        if re.search(r"https?://|www\.|\.com|\.blogspot", blob): errs.append("Class I must not contain a URL")
    for r in recent:
        s = difflib.SequenceMatcher(None, f"{t} {d}".lower(), f"{r.get('title','')} {r.get('description','')}".lower()).ratio()
        if s >= pol["similarity_limit"]: errs.append(f"near-duplicate of earlier pin (similarity {s:.2f})"); break
    return errs

def check_action(kind, settings, pol, done_today, done_kind_today, hour_now):
    """Guard for publish/save/follow. Returns list of reasons to block."""
    errs = []
    if kind in HARD_FORBIDDEN or kind in pol["forbidden_actions"]: return [f"action '{kind}' is forbidden"]
    ah = settings["pinterest"]["active_hours"]
    if not ah[0] <= hour_now < ah[1]: errs.append("outside active_hours")
    if done_today >= settings["limits"]["max_actions_per_day"]: errs.append("max_actions_per_day reached")
    cap = {"publish": settings["pinterest"]["daily_pins"], "save_own": settings["pinterest"]["daily_saves_own"],
           "follow": settings["curator"]["daily_follows"], "save_other": settings["curator"]["daily_saves_others"]}.get(kind)
    if cap is None: errs.append(f"unknown action '{kind}'")
    elif done_kind_today >= cap: errs.append(f"daily cap for {kind} reached")
    if kind in ("follow", "save_other") and not settings["curator"]["enabled"]: errs.append("curator is off")
    return errs
