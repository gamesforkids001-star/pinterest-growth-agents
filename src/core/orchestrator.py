"""Orchestrator: tick (hourly), daily, weekly, monitor, rules-check. Applies guardrails, owner settings, kill switch. Honest about failures."""
import os, json, random, csv, shutil, datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
from src.core import config, risk, db as dbm, logger, compliance, scheduler, healing
from src.integrations.notify import chain
from src.integrations import ga4, pinterest
from src.integrations.pinterest import PinterestError
from src import dashboard_build
from src.agents import site_knowledge, strategist, creator, manager, curator, analytics, reporter

log = logger.get()

def open_db(root, tz="Asia/Karachi"):
    p = Path(os.getenv("STATE_DB", str(Path(root) / "state" / "agents.db"))); p.parent.mkdir(parents=True, exist_ok=True)
    return dbm.DB(str(p), tz)

def ctx(root):
    s, pol, notes = config.load(root); return s, pol, notes, open_db(root, s["pinterest"]["timezone"])

def load_tools(root):
    p = Path(root) / "data/tools.json"
    return json.loads(p.read_text(encoding="utf-8"))["tools"] if p.exists() else []

def local_now(s): return dt.datetime.now(ZoneInfo(s["pinterest"]["timezone"]))

def flush(db, s): return chain.flush(db, s["reports"]["channels"])

# ---------- guards ----------
def rules_ok(pol, db):
    r = db.kv_get("rules_checked")
    if not r: return False
    return (dt.date.today() - dt.date.fromisoformat(r["day"])).days <= pol["rules_max_age_days"]

def risk_gate(s, pol, db):
    """Runs before publishing/curator actions and daily. Returns (level, factors, multiplier)."""
    day = db.today(); snap = risk.snapshot(s); cur = db.kv_get("risk_snap")
    hist = db.kv_get("risk_hist") or {}
    if cur is None: db.kv_set("risk_snap", snap); db.kv_set("first_run_day", db.kv_get("first_run_day") or day)
    elif cur != snap: hist = {"prev": cur, "changed": day}; db.kv_set("risk_hist", hist); db.kv_set("risk_snap", snap)
    prev = hist.get("prev") if hist and (dt.date.fromisoformat(day) - dt.date.fromisoformat(hist["changed"])).days <= 3 else None
    age = (dt.date.fromisoformat(day) - dt.date.fromisoformat(db.kv_get("first_run_day") or day)).days
    times = [scheduler._hm(t) for t in s["pinterest"]["post_times"]]
    cluster = (max(times) - min(times)) / 60 if len(times) > 1 else None
    lvl, f, mult = risk.score(s, pol, prev, age, cluster)
    until = db.kv_get("cautious_until")
    if until and day <= until: mult = min(mult, .5)
    if lvl != "low" and db.kv_get("risk_alerted") != f"{day}:{lvl}":
        db.kv_set("risk_alerted", f"{day}:{lvl}")
        db.add_alert(f"Spam-risk {lvl.upper()} (warning nahi aayi, ehtiyat)", "\n".join(f"- {x['factor']}\n  Why: {x['why']}\n  Fix: {x['fix']}" for x in f) + ("\nAaj ka action count kam kiya gaya (sirf kam, tumhare number se zyada kabhi nahi)." if mult < 1 else ""))
    return lvl, f, mult

def gate(root, s, db):
    if config.kill_switch_on(s, root): return "paused"
    return None

# ---------- publishing ----------
def api_error(root, s, pol, db, e, what):
    key = f"api{e.status}"; limit = pol["auto_pause"]["error_spike_count"]
    db.log_action(what, False, str(e))
    if e.status == 401:
        healing.pause(root, db, "Pinterest login (token) fail", f"HTTP 401 while {what}", "token refresh", ["Pinterest developers > apna app > Generate token (ya refresh token dubara)", "GitHub > Settings > Secrets: PINTEREST_ACCESS_TOKEN / PINTEREST_REFRESH_TOKEN update karo"])
    elif healing.record_problem(db, key, limit):
        healing.pause(root, db, f"Pinterest API error {e.status} bar bar", f"{e}", "retry/backoff, ek run rok diya", ["Pinterest account mein warning/notification check karo (pinterest.com > bell icon)", "Ghante-do ghante ruko; agar restriction notice ho to mujhe batao", "Phir Actions > Agents > resume"])
    else:
        db.add_alert(f"Pinterest API error {e.status} ({what})", f"Cause: {e}\nAbhi is run mein action ruk gaya, agli run mein dobara koshish hogi. Agar {limit} baar hua to auto-pause.")

def publish_one(root, s, pol, db, tools, rng, board_id=None, tool=None, cls=None):
    """Creates + publishes one pin (Main Board by default). Returns True on success."""
    plan = strategist.plan_for(tool, cls, s, db, rng) if tool else strategist.pick(tools, s, db, rng)
    if not plan:
        db.add_alert("ACTION NEEDED: koi verified tool nahi", "data/tools.json mein koi tool 'verified' nahi. Weekly run chalao aur tools_seed.json ke slugs theek karo."); return False
    dry = s["dry_run"]
    out = Path(root) / ("previews" if dry else "tmp_pins") / db.today()
    pin, errs = creator.create(plan, s, pol, db, rng, str(out))
    if not pin:
        db.log_action("publish", False, "compliance/creator: " + "; ".join(errs), plan["tool"]["slug"]); return False
    meta = {"angle": pin["angle"], "ptype": pin["ptype"], "uid": pin["uid"], "image": pin["image"], "link": pin.get("link"), "board": board_id or "main"}
    if dry:
        db.add_pin(pin["cls"], pin["tool_slug"], pin["title"], pin["description"], "dry_run", "", meta)
        db.log_action("publish", True, "dry_run", pin["tool_slug"], pin["title"]); return True
    board = board_id or s["pinterest"]["boards"]["main"]
    if not board:
        db.add_alert("ACTION NEEDED: Main Board ID khali", "settings.yaml > pinterest.boards.main mein Main Board ka ID daalo. 'board-check' (Actions > Agents > board-check) ID dikhata hai."); return False
    try:
        client = pinterest.get_client(db, s["pinterest"]["use_sandbox"])
        res = healing.retry(lambda: client.create_pin(board, pin["title"], pin["description"], pin["alt_text"], pin["image"], pin.get("link")),
                            tries=2, retry_if=lambda e: not (isinstance(e, PinterestError) and e.status in (400, 401, 403, 429)))
    except PinterestError as e:
        api_error(root, s, pol, db, e, "publish"); return False
    healing.clear_problem(db, "api403"); healing.clear_problem(db, "api429")
    db.add_pin(pin["cls"], pin["tool_slug"], pin["title"], pin["description"], "published", str(res.get("id", "")), meta)
    db.log_action("publish", True, "published", pin["tool_slug"], str(res.get("id", ""))); return True

def build_plan(s, pol, db, mult):
    day = db.today(); rng = random.Random(f"{day}:{s['pinterest']['daily_pins']}")
    n = scheduler.apply_mult(s["pinterest"]["daily_pins"], mult)
    pins, notes = scheduler.plan_pin_slots(s, n, rng)
    plan = {"pins": pins, "saves": scheduler.plan_random(scheduler.apply_mult(s["pinterest"]["daily_saves_own"], mult), s, rng),
            "others": scheduler.plan_random(scheduler.apply_mult(s["curator"]["daily_saves_others"], mult) if s["curator"]["enabled"] else 0, s, rng),
            "sig": [s["pinterest"]["daily_pins"], s["pinterest"]["post_times"], s["pinterest"]["daily_saves_own"], s["curator"]["daily_saves_others"], s["curator"]["enabled"], mult], "notes": notes}
    db.kv_set(f"plan:{day}", plan); return plan

def tick(root, rng=None, now_min=None):
    s, pol, notes, db = ctx(root); rng = rng or random.Random(); res = []
    db.kv_set("last_tick", db.now())
    if gate(root, s, db): return "paused"
    lvl, _, mult = risk_gate(s, pol, db)
    if not s["dry_run"] and not rules_ok(pol, db):
        db.add_alert("ACTION NEEDED: Pinterest rules check baqi", "LIVE mode se pehle rules summary chahiye. Actions > Agents > Run workflow > command: rules-check. Tab tak koi pin publish nahi hoga.")
        flush(db, s); return "blocked: rules not checked"
    day = db.today(); plan = db.kv_get(f"plan:{day}")
    sig_now = [s["pinterest"]["daily_pins"], s["pinterest"]["post_times"], s["pinterest"]["daily_saves_own"], s["curator"]["daily_saves_others"], s["curator"]["enabled"], mult]
    if not plan or plan["sig"] != sig_now: plan = build_plan(s, pol, db, mult)
    nowm = scheduler.now_minute(s["pinterest"]["timezone"]) if now_min is None else now_min; hour = nowm // 60
    tools = load_tools(root)
    # 1) publish to Main Board (Mode A). Mode B builds a CSV package in daily().
    if s["pinterest"]["mode"] == "A":
        done = db.count_actions_today("publish")
        if scheduler.is_due(plan["pins"], done, nowm):
            last = db.last_action_ts("publish"); gap_ok = (not last) or (dt.datetime.fromisoformat(db.now()) - last).total_seconds() / 60 >= s["pinterest"]["min_gap_minutes"]
            errs = compliance.check_action("publish", s, pol, db.count_actions_today(), done, hour)
            if errs: db.log_action("publish", False, "; ".join(errs))
            elif not gap_ok: res.append("publish deferred (min gap)")
            else: res.append("published" if publish_one(root, s, pol, db, tools, rng) else "publish failed")
        # 2) save own pins into their tool board
        if not s["dry_run"] and not config.kill_switch_on(s, root):
            sdone = db.count_actions_today("save_own")
            if s["pinterest"]["daily_saves_own"] and scheduler.is_due(plan["saves"], sdone, nowm) and not compliance.check_action("save_own", s, pol, db.count_actions_today(), sdone, hour):
                res.append(do_own_save(root, s, pol, db, tools, rng))
            # 3) curator saves of others
            odone = db.count_actions_today("save_other")
            if s["curator"]["enabled"] and scheduler.is_due(plan["others"], odone, nowm) and db.kv_get("curator_api", True) and not compliance.check_action("save_other", s, pol, db.count_actions_today(), odone, hour):
                try: client = pinterest.get_client(db, s["pinterest"]["use_sandbox"]); n, why = curator.run_saves(db, client, s, tools, 1)
                except PinterestError as e: n, why = 0, f"API: {e}"
                if why: db.kv_set("curator_api", False); db.add_alert("Curator: API se saves nahi ho sake", f"{why}\nAb Curator roz ke manual task list mein aayega (2-3 min).")
    flush(db, s); return ",".join(res) or "idle"

def do_own_save(root, s, pol, db, tools, rng):
    pend = [p for p in db.pending_saves() if manager.board_for(s, p["tool_slug"])]
    if not pend:
        return "no pending saves"
    pin = pend[0]; method = db.kv_get("save_method", "save")
    try:
        if method == "save":
            client = pinterest.get_client(db, s["pinterest"]["use_sandbox"])
            ok, used, note = manager.do_save(db, client, s, pin, method)
            if ok: db.log_action("save_own", True, "save", pin["tool_slug"], str(pin["id"])); return "saved"
            db.kv_set("save_method", "fallback")
            db.add_alert("Save-endpoint is access level par kaam nahi kiya", f"{note}\nAb fallback: har pin ke liye tool board par alag nayi pin (naya image + naya text) banayi jayegi, daily cap ke andar.")
        tool = next((t for t in tools if t["slug"] == pin["tool_slug"]), None)
        if not tool: return "tool missing"
        board = manager.board_for(s, pin["tool_slug"])
        if publish_one(root, s, pol, db, tools, rng, board_id=board, tool=tool, cls=pin["cls"]):
            db.add_save(pin["id"], pin["tool_slug"], board, "fresh", True); db.log_action("save_own", True, "fresh pin", pin["tool_slug"], str(pin["id"])); return "fresh pin on tool board"
        return "save failed"
    except PinterestError as e:
        api_error(root, s, pol, db, e, "save_own"); return "save error"

# ---------- Mode B package ----------
def build_package(root, s, pol, db, tools, rng, target_day, mult):
    if db.kv_get(f"package:{target_day}"): return None
    n = scheduler.apply_mult(s["pinterest"]["daily_pins"], mult)
    slots, _ = scheduler.plan_pin_slots(s, n, rng)
    dry = s["dry_run"]; base = Path(root) / ("previews" if dry else "packages") / target_day; base.mkdir(parents=True, exist_ok=True)
    repo = os.getenv("GITHUB_REPOSITORY", "OWNER/REPO"); rows, made, saveplan = [], 0, []
    for i in range(n):
        plan = strategist.pick(tools, s, db, rng)
        if not plan: break
        pin, errs = creator.create(plan, s, pol, db, rng, str(base))
        if not pin: db.log_action("package", False, "; ".join(errs)); continue
        fn = Path(pin["image"]).name; when = f"{target_day}T{scheduler.fmt(slots[min(i, len(slots) - 1)])}" if slots else ""
        rows.append([pin["title"], pin["description"], pin.get("link", ""), f"https://raw.githubusercontent.com/{repo}/main/{'previews' if dry else 'packages'}/{target_day}/{fn}", s["pinterest"]["boards"].get("main_name", "Main Board"), when, ", ".join(pin["keywords"])])
        db.add_pin(pin["cls"], pin["tool_slug"], pin["title"], pin["description"], "dry_run" if dry else "package", "", {"angle": pin["angle"], "ptype": pin["ptype"], "uid": pin["uid"], "image": pin["image"], "link": pin.get("link")})
        db.log_action("package", True, "dry_run" if dry else "package", pin["tool_slug"], fn)
        saveplan.append(f"'{pin['title'][:45]}' -> board: {plan['tool']['name']}"); made += 1
    with open(base / "pins.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["Title", "Description", "Link", "Media URL", "Pinterest board", "Publish date", "Keywords"]); w.writerows(rows)
    (base / "save_plan.txt").write_text("\n".join(saveplan[:s["pinterest"]["daily_saves_own"]]), encoding="utf-8")
    db.kv_set(f"package:{target_day}", made)
    return {"dir": str(base.relative_to(root)), "n": made, "saves": saveplan[:s["pinterest"]["daily_saves_own"]], "dry": dry}

# ---------- daily ----------
def refresh_dashboard(root, s, db):
    has = False
    if s["google"]["enabled"]:
        got = ga4.fetch(30)
        if got: db.save_metrics(got); has = True
    m = db.metrics(30); has = has or bool(m)
    (Path(root) / "dashboard").mkdir(exist_ok=True)
    (Path(root) / "dashboard/analytics.html").write_text(dashboard_build.build(m, s["google"]["enabled"], has, pin_rows=db.acct_metrics(30)), encoding="utf-8")
    return has

def prune(root, days=30):
    for folder in ("previews", "packages"):
        for d in (Path(root) / folder).glob("*") if (Path(root) / folder).exists() else []:
            try:
                if (dt.date.today() - dt.date.fromisoformat(d.name)).days > days: shutil.rmtree(d)
            except ValueError: pass

def daily(root, rng=None):
    s, pol, notes, db = ctx(root); rng = rng or random.Random(); db.kv_set("last_daily", db.now())
    if notes: db.add_alert("Settings adjust hui", "\n".join(f"- {n}" for n in notes))
    warnings, tasks = [], []
    if config.kill_switch_on(s, root):
        db.add_alert("PAUSED", "Kill switch / PAUSE active hai. Resume: Actions > Agents > Run workflow > resume."); flush(db, s); return "paused"
    lvl, _, mult = risk_gate(s, pol, db); tools = load_tools(root); has = refresh_dashboard(root, s, db)
    imp = sv = clk = None
    if os.getenv("PINTEREST_ACCESS_TOKEN") or os.getenv("PINTEREST_REFRESH_TOKEN"):
        try:
            client = pinterest.get_client(db, s["pinterest"]["use_sandbox"])
            n, err = analytics.collect(db, client); e2 = analytics.collect_account(db, client)
            if err or e2: warnings.append(f"Pinterest analytics adhoori: {err or e2}")
            rows = db.acct_metrics(3)
            if rows: imp, sv, clk = rows[-1]["impressions"], rows[-1]["saves"], rows[-1]["clicks"]
            drop = analytics.detect_drop(db, pol)
            if drop:
                db.kv_set("cautious_until", (dt.date.today() + dt.timedelta(days=pol["analytics"]["cautious_days"])).isoformat())
                if drop >= pol["analytics"]["drop_pause_pct"]:
                    healing.pause(root, db, "Impressions achanak gir gaye", f"Impressions {drop}% neeche (pichle 14 din ke muqable)", "activity aage ke liye 50% kam", ["Pinterest par account/pin warnings check karo", "Kya haal mein numbers barhaye? Wapas kam karo", "Phir resume"])
                else: warnings.append(f"Impressions {drop}% gire. Agle {pol['analytics']['cautious_days']} din activity 50% kam. Recent settings/pins check karo.")
        except PinterestError as e: warnings.append(f"Pinterest analytics fail: {e}")
        except Exception as e: warnings.append(f"Pinterest analytics skip ({type(e).__name__})")
    # Mode B package for tomorrow
    pkg_msg = None
    if s["pinterest"]["mode"] == "B" and s["pinterest"]["daily_pins"] > 0:
        tomorrow = (dt.date.fromisoformat(db.today()) + dt.timedelta(days=1)).isoformat()
        pk = build_package(root, s, pol, db, tools, rng, tomorrow, mult)
        if pk:
            if pk["dry"]: pkg_msg = f"DRY-RUN preview: {pk['n']} pins banayi gayi (repo folder {pk['dir']}). Kuch publish nahi hua."
            else:
                pkg_msg = f"Kal ka package tayyar: {pk['n']} pins, folder {pk['dir']} (pins.csv + images)."
                tasks.append(f"Pinterest par bulk upload: phone browser > pinterest.com > Desktop site on > Create > Bulk create Pins > repo ki {pk['dir']}/pins.csv upload. Agar ye option na dikhe, images {pk['dir']}/ se download karke manually pin banao (title/description pins.csv mein).")
                if pk["saves"]: tasks.append("Upload ke baad in pins ko unke tool board mein save karo: " + " | ".join(pk["saves"]))
    if s["curator"]["enabled"]:
        api_saves = s["pinterest"]["mode"] == "A" and not s["dry_run"] and db.kv_get("curator_api", True)
        curator.manual_tasks(db, s, s["curator"]["daily_follows"], 0 if api_saves else s["curator"]["daily_saves_others"])   # follows: always manual
    tasks += [t["text"] for t in db.open_tasks()]; db.close_tasks_before(db.today())
    l = sum(1 for p in db.recent_pins(50) if p["ts"][:10] == db.today() and p["cls"] == "L"); i_ = sum(1 for p in db.recent_pins(50) if p["ts"][:10] == db.today() and p["cls"] == "I")
    data = {"day": db.today(), "dry_run": s["dry_run"], "mode": s["pinterest"]["mode"], "pins_day": s["pinterest"]["daily_pins"], "times": s["pinterest"]["post_times"], "saves_own": s["pinterest"]["daily_saves_own"],
            "curator": s["curator"]["enabled"], "risk": lvl, "link": l, "idea": i_, "saves_done": db.count_actions_today("save_own"), "others": db.count_actions_today("save_other"),
            "imp": imp, "sv": sv, "clk": clk, "ga4": "haan" if has else "abhi data nahi", "package": pkg_msg, "warnings": warnings, "tasks": tasks}
    body = reporter.daily(data)
    db.add_alert(("ACTION NEEDED: " if tasks or warnings else "") + f"Daily report {db.today()}", body)
    prune(root); flush(db, s); return "ok"

# ---------- weekly ----------
def rules_check(root, pol=None, db=None, use_llm=True):
    import requests
    from src.core import llm
    pol = pol or config.load(root)[1]; db = db or ctx(root)[3]; ok, failed, parts = [], [], []
    for u in pol["rules_urls"]:
        try:
            r = requests.get(u, headers={"User-Agent": "EasyFileToolsPinBot/1.0"}, timeout=30)
            if r.status_code != 200: failed.append(f"{u} (HTTP {r.status_code})"); continue
            import re; text = re.sub(r"\s+", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", " ", r.text, flags=re.S))[:6000]
            summ = None
            if use_llm:
                try: summ = llm.generate("Summarize ONLY rules that affect an automated Pinterest publishing/curation tool (spam, automation, follow limits, links, duplicate content, API terms) as short bullets. If the text has no such rules say NONE.\n\n" + text)
                except Exception: summ = None
            ok.append(u); parts.append(f"## {u}\n" + (summ or f"(not summarized - raw excerpt)\n{text[:1200]}"))
        except Exception as e: failed.append(f"{u} ({type(e).__name__})")
    doc = f"# Pinterest rules summary\nChecked: {dt.date.today()}\nRead OK: {len(ok)}, could not read: {len(failed)}\n" + ("Could NOT read (I did not guess their content):\n" + "\n".join(f"- {f}" for f in failed) + "\n" if failed else "") + "\n" + "\n\n".join(parts) + "\n"
    (Path(root) / "docs").mkdir(exist_ok=True); (Path(root) / "docs/pinterest_rules_summary.md").write_text(doc, encoding="utf-8")
    if ok: db.kv_set("rules_checked", {"day": dt.date.today().isoformat(), "ok": len(ok), "failed": len(failed)})
    return ok, failed

def weekly(root, reader=None, use_llm=True):
    s, pol, notes, db = ctx(root); day = db.today()
    tools, problems = site_knowledge.build(root, s["site"]["base_url"], reader, use_llm); changed = site_knowledge.save(root, tools)
    rc = db.kv_get("rules_checked"); rules_txt = "ok"
    if not rc or (dt.date.today() - dt.date.fromisoformat(rc["day"])).days >= 30:
        ok, failed = rules_check(root, pol, db, use_llm)
        rules_txt = f"read {len(ok)} pages" + (f", could NOT read: {len(failed)} (URLs policies.yaml mein theek karo)" if failed else "")
        if failed: problems.append("Rules pages padhe nahi ja sake: " + "; ".join(failed))
    sm = analytics.summary(db)
    tl = [r for r in sm["tools"] if r["n"]]
    best = [f"{r['k']} ({r['c'] or 0} clicks, {r['s'] or 0} saves)" for r in tl[:3] if (r["c"] or r["s"])]
    worst = [r["k"] for r in tl[-3:]] if len(tl) > 3 else []
    cls = " | ".join(f"{r['k']}: {r['n']} pins, {r['i'] or 0} imp, {r['s'] or 0} saves, {r['c'] or 0} clicks" for r in sm["classes"])
    followers = prev = None
    try:
        client = pinterest.get_client(db, s["pinterest"]["use_sandbox"]); followers = client.user().get("follower_count"); prev = db.kv_get("followers")
        if followers is not None: db.kv_set("followers", followers)
    except Exception: pass
    blocked = db.c.execute("SELECT COUNT(*) FROM actions WHERE ok=0 AND ts>=?", ((dt.date.today() - dt.timedelta(days=30)).isoformat(),)).fetchone()[0]
    lvl = risk_gate(s, pol, db)[0]
    suggest = ("risk low aur koi problem nahi: chaho to daily_pins +1 (5-7 din mein ek se zyada nahi)." if lvl == "low" and not problems else "abhi numbers na barhao; pehle problems/risk theek karo.")
    site_sug = [f"{t['name']}: page description khali ya JS-only, pin quality ke liye behtar ho sakti hai" for t in tools if t["verified"] and not t.get("what_it_does")][:5]
    data = {"day": day, "verified": sum(t["verified"] for t in tools), "total": len(tools), "changed": changed, "problems": problems, "best": best, "worst": worst, "classes": cls,
            "followers": followers, "followers_prev": prev, "audit": f"pichle 30 din mein {blocked} blocked/failed actions; forbidden actions hard-coded, koi bypass nahi.", "rules": rules_txt, "suggest": suggest, "site_suggestions": site_sug}
    db.add_alert(("ACTION NEEDED: " if problems else "") + f"Weekly report {day}", reporter.weekly(data)); flush(db, s); return problems

# ---------- monitor / utilities ----------
def monitor(root):
    s, pol, notes, db = ctx(root); now = dt.datetime.fromisoformat(db.now())
    if config.kill_switch_on(s, root):
        if db.kv_get("pause_reminder") != db.today(): db.kv_set("pause_reminder", db.today()); db.add_alert("System PAUSED hai", "Resume: Actions > Agents > Run workflow > resume")
    else:
        last = db.kv_get("last_daily")
        if last and (now - dt.datetime.fromisoformat(last)).total_seconds() > 36 * 3600:
            db.add_alert("ACTION NEEDED: Daily run 36 ghante se nahi chali", "Actions tab kholo, Agents workflow ke errors dekho. GitHub kabhi schedule delay/skip karta hai; agar 60 din repo mein activity na ho to schedule band ho jata hai.")
    flush(db, s); return "ok"

def test_notify(root):
    s, _, _, db = ctx(root)
    via, errs = chain.send("Test notification", "Agar ye dikh raha hai to channel kaam kar raha hai.", s["reports"]["channels"])
    print("delivered via:", via, "| errors:", errs)
    if not via: db.add_alert("Test notification", "undelivered test"); return 1
    return 0

def board_check(root):
    s, _, _, db = ctx(root); tools = load_tools(root)
    client = pinterest.get_client(db, s["pinterest"]["use_sandbox"])
    mapping, miss, extra, main = pinterest.map_boards(client.boards(), tools)
    print(json.dumps({"mapped": len(mapping), "tools_without_board": miss, "boards_not_mapped": extra, "main_candidates": [m["id"] + ": " + m["name"] for m in main]}, indent=1))
    print("\n--- settings.yaml mein paste karo (pinterest.boards.tools) ---")
    print("tools:"); [print(f'      {k}: "{v}"') for k, v in mapping.items()]
    db.add_alert("Board check" + (" (mismatch!)" if miss else " OK"), f"Mapped {len(mapping)}/{len(tools)}. Bina board wale tools: {', '.join(miss) or 'none'}. Unmapped boards: {', '.join(extra) or 'none'}. Details Actions log mein.")
    flush(db, s)
