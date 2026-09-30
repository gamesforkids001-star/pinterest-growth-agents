"""Reporter: daily (short), weekly (fuller). Plain Roman Urdu/English, phone-friendly."""
def _n(v): return "n/a" if v is None else v

def daily(d):
    L = [f"Daily report {d['day']}", f"Mode: {'DRY-RUN (kuch publish nahi hota)' if d['dry_run'] else 'LIVE'} | Pinterest mode {d['mode']}",
         f"Active settings: pins/day={d['pins_day']}, times={d['times']}, saves_own/day={d['saves_own']}, curator={'on' if d['curator'] else 'off'}",
         f"Spam risk: {d['risk']}",
         f"Aaj: link pins={d['link']}, idea pins={d['idea']}, own saves={d['saves_done']}, others saves={d['others']}",
         f"Kal ki Pinterest numbers: impressions={_n(d.get('imp'))}, saves={_n(d.get('sv'))}, outbound clicks={_n(d.get('clk'))}",
         f"Website traffic (GA4): {d['ga4']}"]
    if d.get("package"): L.append(d["package"])
    if d.get("warnings"): L.append("Warnings:\n- " + "\n- ".join(d["warnings"]))
    if d.get("tasks"): L.append("TUMHARE TASKS (2-3 min):\n" + "\n".join(f"{i}. {t}" for i, t in enumerate(d["tasks"], 1)))
    return "\n".join(L)

def weekly(d):
    L = [f"Weekly report {d['day']}", f"Tools verified on live site: {d['verified']}/{d['total']}"]
    if d.get("changed"): L.append("Site pages changed: " + ", ".join(d["changed"]))
    if d.get("problems"): L.append("Problems (tumhara kaam):\n- " + "\n- ".join(d["problems"]))
    if d.get("best"): L.append("Best tools (clicks, saves): " + ", ".join(d["best"]))
    if d.get("worst"): L.append("Weakest tools: " + ", ".join(d["worst"]))
    if d.get("classes"): L.append("Class results: " + d["classes"])
    if d.get("followers") is not None: L.append(f"Followers: {d['followers']} (last week: {d.get('followers_prev','n/a')})")
    L.append("Policy self-audit: " + d["audit"])
    L.append("Rules summary: " + d["rules"])
    L.append("Agle hafte ka suggestion (tum faisla karo): " + d["suggest"])
    if d.get("site_suggestions"): L.append("Site suggestions (SIRF info, kabhi apply nahi hote):\n- " + "\n- ".join(d["site_suggestions"]))
    return "\n".join(L)
