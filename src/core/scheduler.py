"""Day planning: owner's post_times + jitter, min gap, active hours. Owner numbers are never raised, only (optionally) lowered by risk multiplier."""
import random, math, datetime as dt
from zoneinfo import ZoneInfo

def _hm(t): h, m = t.split(":"); return int(h) * 60 + int(m)

def apply_mult(n, mult):
    return 0 if n == 0 else max(1, math.floor(n * mult))

def plan_pin_slots(settings, n, rng):
    """Returns (minutes_of_day list, notes)."""
    p, notes = settings["pinterest"], []
    lo, hi = p["active_hours"][0] * 60, p["active_hours"][1] * 60
    if n <= 0: return [], notes
    base = sorted(_hm(t) for t in p["post_times"] if lo <= _hm(t) < hi)
    if len(base) > n:
        base = [base[round(i * (len(base) - 1) / max(n - 1, 1))] for i in range(n)]
    elif len(base) < n:
        notes.append(f"post_times has {len(base)} entries but {n} pins planned: extra slots spread across active_hours")
        extra = [int(lo + (i + .5) * (hi - lo) / n) for i in range(n)]
        base = sorted(set(base + [e for e in extra if all(abs(e - b) >= p["min_gap_minutes"] for b in base)]))[:n]
    j = p["random_jitter_minutes"]
    slots = sorted(min(hi - 1, max(lo, b + rng.randint(-j, j))) for b in base)
    out = []
    for s in slots:
        if out and s - out[-1] < p["min_gap_minutes"]: s = out[-1] + p["min_gap_minutes"]
        if s < hi: out.append(s)
        else: notes.append("a slot was dropped: min_gap_minutes does not fit inside active_hours")
    return out, notes

def plan_random(n, settings, rng, min_gap=45):
    """n actions spread across active hours (stratified random)."""
    lo, hi = settings["pinterest"]["active_hours"][0] * 60, settings["pinterest"]["active_hours"][1] * 60
    if n <= 0: return []
    seg = (hi - lo) / n
    out = []
    for i in range(n):
        s = int(lo + i * seg + rng.random() * seg)
        if out and s - out[-1] < min_gap: s = out[-1] + min_gap
        if s < hi: out.append(s)
    return out

def now_minute(tz):
    n = dt.datetime.now(ZoneInfo(tz)); return n.hour * 60 + n.minute

def is_due(slots, done_n, now_min):
    return done_n < len(slots) and slots[done_n] <= now_min

def fmt(m): return f"{m // 60:02d}:{m % 60:02d}"
