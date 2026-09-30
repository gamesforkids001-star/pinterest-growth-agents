"""Load + validate owner settings against policy ceilings. Never silently ignores a setting."""
import copy, re
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]

def load_yaml(p):
    return yaml.safe_load(Path(p).read_text(encoding="utf-8")) or {}

def _clamp(name, val, lo, hi, safe, notes):
    if not isinstance(val, int) or isinstance(val, bool) or val < lo:
        notes.append(f"{name}={val!r} invalid, safe value {safe} used")
        return safe
    if val > hi:
        notes.append(f"{name}={val} is above ceiling {hi}, {hi} used")
        return hi
    return val

def validate(settings, policies):
    """Returns (effective_settings, notes). notes = explanations shown to the owner."""
    s, notes = copy.deepcopy(settings), []
    c, p = policies["ceilings"], s.setdefault("pinterest", {})
    p["daily_pins"] = _clamp("pinterest.daily_pins", p.get("daily_pins"), 0, c["daily_pins"], 1, notes)
    p["daily_saves_own"] = _clamp("pinterest.daily_saves_own", p.get("daily_saves_own"), 0, c["daily_saves_own"], 0, notes)
    floor = policies["min_gap_minutes_floor"]
    g = p.get("min_gap_minutes")
    if not isinstance(g, int) or g < floor:
        notes.append(f"pinterest.min_gap_minutes={g!r} below floor {floor}, {floor} used")
        p["min_gap_minutes"] = floor
    ah = p.get("active_hours")
    if not (isinstance(ah, list) and len(ah) == 2 and all(isinstance(x, int) for x in ah) and 0 <= ah[0] < ah[1] <= 24):
        notes.append(f"pinterest.active_hours={ah!r} invalid, [9, 22] used")
        p["active_hours"] = [9, 22]
    times = []
    for t in p.get("post_times", []) or []:
        if isinstance(t, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", t):
            times.append(t)
        else:
            notes.append(f"post_time {t!r} invalid, skipped")
    p["post_times"] = sorted(set(times))
    j = p.get("random_jitter_minutes", 15)
    p["random_jitter_minutes"] = j if isinstance(j, int) and 0 <= j <= 60 else 15
    if p.get("mode") not in ("A", "B"):
        notes.append(f"pinterest.mode={p.get('mode')!r} invalid, 'B' used"); p["mode"] = "B"
    s.setdefault("brand", {"name": "Easy File Online Tools", "colors": ["#0F172A", "#1D4ED8"]})
    cu = s.setdefault("curator", {})
    cu["daily_follows"] = _clamp("curator.daily_follows", cu.get("daily_follows", 0), 0, c["daily_follows"], 0, notes)
    cu["daily_saves_others"] = _clamp("curator.daily_saves_others", cu.get("daily_saves_others", 0), 0, c["daily_saves_others"], 0, notes)
    lim = s.setdefault("limits", {})
    lim["max_actions_per_day"] = _clamp("limits.max_actions_per_day", lim.get("max_actions_per_day"), 0, c["max_actions_per_day"], 10, notes)
    ls = s.setdefault("pins", {}).get("link_share", 0.7)
    if not isinstance(ls, (int, float)) or not 0 <= ls <= 1:
        notes.append(f"pins.link_share={ls!r} invalid, 0.7 used"); ls = 0.7
    s["pins"]["link_share"] = ls
    if s.get("site", {}).get("read_only") is not True:
        notes.append("site.read_only must be true, forced to true")
    s.setdefault("site", {})["read_only"] = True
    if not isinstance(s.get("dry_run"), bool):
        notes.append("dry_run invalid, true used"); s["dry_run"] = True
    return s, notes

def load(root=ROOT):
    pol = load_yaml(Path(root) / "config/policies.yaml")
    s, notes = validate(load_yaml(Path(root) / "config/settings.yaml"), pol)
    return s, pol, notes

def kill_switch_on(settings, root=ROOT):
    return bool(settings.get("limits", {}).get("kill_switch")) or (Path(root) / "PAUSE").exists()
