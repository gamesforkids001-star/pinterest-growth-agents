"""Predictive spam-risk score. Reduces risk, does NOT guarantee safety."""
def score(settings, pol, prev=None, account_age_days=0, cluster_hours=None):
    """prev = previous settings snapshot {'daily_pins':..} or None. Returns (level, factors[{factor,why,fix}], multiplier)."""
    f, pts = [], 0
    p, c = settings["pinterest"], pol["ceilings"]
    cur = {"daily_pins": p["daily_pins"], "daily_saves_own": p["daily_saves_own"],
           "daily_follows": settings["curator"]["daily_follows"], "daily_saves_others": settings["curator"]["daily_saves_others"]}
    for k, v in cur.items():
        if v and v >= 0.8 * c[k]:
            pts += 2; f.append({"factor": f"{k}={v} is near ceiling {c[k]}", "why": "Near-max activity is commonly treated as automated.", "fix": f"Lower {k} and raise slowly (+1 every 5-7 days)."})
        if prev and prev.get(k, 0) and v > prev[k] * pol["risk"]["max_daily_increase_factor"]:
            pts += 3; f.append({"factor": f"{k} raised from {prev[k]} to {v} at once", "why": "Sudden jumps look bot-like.", "fix": f"Step {k} up by +1 every 5-7 days."})
        elif prev and prev.get(k, 0) == 0 and v > 3:
            pts += 3; f.append({"factor": f"{k} jumped from 0 to {v}", "why": "Sudden start at volume looks bot-like.", "fix": "Start at 1-2 and increase slowly."})
    if account_age_days < pol["risk"]["warmup_days"] and (cur["daily_pins"] > 3 or cur["daily_follows"] > 3):
        pts += 2; f.append({"factor": f"account age {account_age_days}d (warm-up {pol['risk']['warmup_days']}d) with high volume", "why": "New accounts are watched more closely.", "fix": "Keep pins <=3/day and follows <=3/day during warm-up."})
    if cluster_hours is not None and cur["daily_pins"] >= 3 and cluster_hours < 3:
        pts += 2; f.append({"factor": "actions bunched into a short window", "why": "Bursts are a spam signal.", "fix": "Spread post_times across active_hours."})
    level = "high" if pts >= 5 else "medium" if pts >= 2 else "low"
    return level, f, (0.5 if level == "high" else 1.0)

def snapshot(settings):
    return {"daily_pins": settings["pinterest"]["daily_pins"], "daily_saves_own": settings["pinterest"]["daily_saves_own"],
            "daily_follows": settings["curator"]["daily_follows"], "daily_saves_others": settings["curator"]["daily_saves_others"]}
