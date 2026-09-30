import json, os, random, shutil, datetime as dt
from pathlib import Path
from src.core import orchestrator as o, config, scheduler, healing, db as dbm
from src.agents import strategist, creator, curator, analytics, manager
from src.integrations import pinterest
from src.integrations.pinterest import PinterestError

ROOT = Path(__file__).resolve().parents[1]
TOOLS = [{"name": n, "slug": s, "url": f"https://easyfileonlinetools.blogspot.com/p/{s}.html", "verified": True,
          "what_it_does": f"{n} works in your browser and lets you finish the job quickly without installing anything.",
          "headings": ["Add your file", "Choose options", "Download the result", "Check the output"], "keywords": [n.lower(), s.replace("-", " "), "online tool", "free tool"]}
         for n, s in [("Merge PDF", "merge-pdf"), ("Age Calculator", "age-calculator"), ("Image Compressor", "image-compressor")]]

def _setup(tmp, monkeypatch, **over):
    shutil.copytree(ROOT / "config", tmp / "config"); (tmp / "data").mkdir()
    json.dump({"tools": TOOLS}, open(tmp / "data/tools.json", "w"))
    if over:
        import yaml; s = yaml.safe_load(open(tmp / "config/settings.yaml")); 
        for k, v in over.items():
            cur = s
            for part in k.split(".")[:-1]: cur = cur[part]
            cur[k.split(".")[-1]] = v
        yaml.safe_dump(s, open(tmp / "config/settings.yaml", "w"))
    monkeypatch.setenv("STATE_DB", str(tmp / "s.db"))
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "GITHUB_TOKEN", "PINTEREST_ACCESS_TOKEN", "PINTEREST_REFRESH_TOKEN"): monkeypatch.delenv(k, raising=False)

class FakeClient:
    def __init__(self, fail=None): self.created, self.saved, self.fail = [], [], fail
    def create_pin(self, board, title, desc, alt, image, link=None):
        if self.fail: raise PinterestError(self.fail, "boom")
        self.created.append((board, link)); return {"id": f"pin{len(self.created)}"}
    def save_pin(self, pid, board):
        if self.fail == "save": raise PinterestError(403, "no save")
        self.saved.append((pid, board)); return {}

def test_plan_slots_respect_gap_and_hours():
    s, pol, _ = config.load(ROOT); s["pinterest"]["daily_pins"] = 3
    slots, _ = scheduler.plan_pin_slots(s, 3, random.Random(3))
    assert len(slots) == 3 and all(9 * 60 <= x < 22 * 60 for x in slots) and all(b - a >= 120 for a, b in zip(slots, slots[1:]))
def test_mult_only_lowers(): assert scheduler.apply_mult(3, .5) == 1 and scheduler.apply_mult(0, .5) == 0 and scheduler.apply_mult(1, .5) == 1

def test_strategist_rotation_and_limits(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch); s, pol, _, db = o.ctx(tmp_path); rng = random.Random(5); seen = set()
    for _ in range(12):
        p = strategist.pick(TOOLS, s, db, rng); seen.add(p["tool"]["slug"]); assert len(p["keywords"]) >= 2
        db.add_pin(p["cls"], p["tool"]["slug"], f"t{_}", "d", "published", meta={"angle": p["angle"]})
    assert len(seen) == 3
    s["pins"]["link_share"] = 1.0; s["pins"]["max_link_pins_per_tool_per_week"] = 0
    assert strategist.pick(TOOLS, s, db, rng)["cls"] == "I"

def test_creator_fallback_and_compliance(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch); s, pol, _, db = o.ctx(tmp_path); rng = random.Random(2)
    plan = strategist.plan_for(TOOLS[0], "L", s, db, rng); pin, errs = creator.create(plan, s, pol, db, rng, str(tmp_path / "img"))
    assert pin and not errs and "utm_campaign=merge-pdf" in pin["link"] and "?m=1" not in pin["link"] and Path(pin["image"]).exists()
    from PIL import Image; assert Image.open(pin["image"]).size == (1000, 1500)
    plan = strategist.plan_for(TOOLS[0], "I", s, db, rng); pin, errs = creator.create(plan, s, pol, db, rng, str(tmp_path / "img"))
    assert pin and pin["cls"] == "I" and "link" not in pin

def test_duplicate_blocked(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch); s, pol, _, db = o.ctx(tmp_path); rng = random.Random(2)
    plan = strategist.plan_for(TOOLS[0], "L", s, db, rng); pin, _ = creator.create(plan, s, pol, db, rng, str(tmp_path / "i"))
    db.add_pin("L", "merge-pdf", pin["title"], pin["description"], "published")
    pin2, errs = creator.create(strategist.plan_for(TOOLS[0], "L", s, db, rng), s, pol, db, rng, str(tmp_path / "i"))
    assert pin2 is None and any("duplicate" in e for e in errs)

def test_tick_dry_run_mode_a(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, **{"pinterest.mode": "A"})
    assert o.tick(tmp_path, random.Random(1), now_min=23 * 60 - 1).startswith(("idle", "publish"))  # outside hours -> blocked by guard
    r = o.tick(tmp_path, random.Random(1), now_min=21 * 60 + 30)
    db = o.open_db(tmp_path); pins = db.recent_pins()
    assert len(pins) == 1 and pins[0]["status"] == "dry_run" and list((tmp_path / "previews").rglob("*.jpg"))

def test_tick_live_publishes_main_only_and_caps(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, **{"pinterest.mode": "A", "dry_run": False, "pinterest.boards.main": "MAIN1"})
    fc = FakeClient(); monkeypatch.setattr(pinterest, "get_client", lambda db=None, sandbox=False: fc)
    db = o.open_db(tmp_path); db.kv_set("rules_checked", {"day": dt.date.today().isoformat()}); db.c.close()
    o.tick(tmp_path, random.Random(1), now_min=21 * 60 + 30); o.tick(tmp_path, random.Random(1), now_min=21 * 60 + 40)
    assert [b for b, _ in fc.created] == ["MAIN1"]           # daily_pins=1 -> exactly one, on Main Board

def test_live_blocked_without_rules_check(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, **{"pinterest.mode": "A", "dry_run": False, "pinterest.boards.main": "M"})
    fc = FakeClient(); monkeypatch.setattr(pinterest, "get_client", lambda db=None, sandbox=False: fc)
    assert "rules" in o.tick(tmp_path, random.Random(1), now_min=21 * 60 + 30) and not fc.created

def test_api_403_alerts_then_pauses_on_third(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, **{"pinterest.mode": "A", "dry_run": False, "pinterest.boards.main": "M", "pinterest.daily_pins": 3, "pinterest.min_gap_minutes": 60})
    monkeypatch.setattr(pinterest, "get_client", lambda db=None, sandbox=False: FakeClient(fail=403))
    db = o.open_db(tmp_path); db.kv_set("rules_checked", {"day": dt.date.today().isoformat()}); db.c.close()
    for _ in range(3): o.tick(tmp_path, random.Random(1), now_min=21 * 60 + 50)
    assert (tmp_path / "PAUSE").exists()
    assert o.tick(tmp_path) == "paused"

def test_own_save_then_fallback(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, **{"pinterest.mode": "A", "dry_run": False, "pinterest.boards.main": "M", "pinterest.daily_saves_own": 2, "pinterest.boards.tools": {"merge-pdf": "B1"}})
    s, pol, _, db = o.ctx(tmp_path); pid = db.add_pin("L", "merge-pdf", "t", "d", "published", "P1", {})
    fc = FakeClient(); monkeypatch.setattr(pinterest, "get_client", lambda db=None, sandbox=False: fc)
    assert o.do_own_save(tmp_path, s, pol, db, TOOLS, random.Random(1)) == "saved" and fc.saved == [("P1", "B1")]
    pid2 = db.add_pin("L", "merge-pdf", "t2", "d2", "published", "P2", {})
    fc2 = FakeClient(fail="save"); monkeypatch.setattr(pinterest, "get_client", lambda db=None, sandbox=False: fc2)
    fc2.create_pin = lambda *a, **k: {"id": "NEW"}
    r = o.do_own_save(tmp_path, s, pol, db, TOOLS, random.Random(1))
    assert "fresh" in r and db.kv_get("save_method") == "fallback"

def test_mode_b_package(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, **{"dry_run": False}); monkeypatch.setenv("GITHUB_REPOSITORY", "me/repo")
    s, pol, _, db = o.ctx(tmp_path)
    pk = o.build_package(tmp_path, s, pol, db, TOOLS, random.Random(4), "2026-10-01", 1.0)
    rows = open(Path(tmp_path) / pk["dir"] / "pins.csv").read().splitlines()
    assert pk["n"] == 1 and len(rows) == 2 and "raw.githubusercontent.com/me/repo/main/packages/2026-10-01/" in rows[1]
    assert o.build_package(tmp_path, s, pol, db, TOOLS, random.Random(4), "2026-10-01", 1.0) is None   # no duplicate package

def test_curator_off_and_manual_fallback(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch); s, pol, _, db = o.ctx(tmp_path)
    assert curator.relevant({"title": "10 pdf tips", "description": "office"}, ["pdf tips"]) and not curator.relevant({"title": "porn pdf"}, ["pdf tips"])
    class NoSearch:
        def search_pins(self, t, n): raise PinterestError(403, "no")
    n, why = curator.run_saves(db, NoSearch(), s, TOOLS, 1); assert n == 0 and "not available" in why
    curator.manual_tasks(db, s, 1, 1); assert len(db.open_tasks()) >= 2 and any("Follow" in t["text"] for t in db.open_tasks())

def test_drop_detection(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch); s, pol, _, db = o.ctx(tmp_path); today = dt.date.today()
    rows = [((today - dt.timedelta(days=i)).isoformat(), 100 if i > 3 else 20, 5, 1) for i in range(1, 19)]
    db.set_acct_metrics(rows); assert analytics.detect_drop(db, pol) >= 50

def test_healing_retry_and_counter(tmp_path, monkeypatch):
    calls = []
    def flaky():
        calls.append(1)
        if len(calls) < 3: raise RuntimeError("x")
        return "ok"
    assert healing.retry(flaky, tries=3, sleep=lambda s: None) == "ok"
    _setup(tmp_path, monkeypatch); db = o.open_db(tmp_path)
    assert not healing.record_problem(db, "k") and not healing.record_problem(db, "k") and healing.record_problem(db, "k")

def test_daily_shows_owner_settings_and_risk(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, **{"pinterest.daily_pins": 999}); o.daily(tmp_path, random.Random(1))
    db = o.open_db(tmp_path); body = "\n".join(a["body"] for a in db.undelivered_alerts())
    assert "above ceiling" in body and "Spam risk" in body

def test_weekly_with_fake_reader(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch); shutil.copy(ROOT / "data/tools_seed.json", tmp_path / "data/tools_seed.json")
    class R:
        def fetch(self, p): return {"url": "https://x" + p, "ok": False, "error": "HTTP 404"}
    monkeypatch.setattr("src.core.orchestrator.rules_check", lambda *a, **k: ([], ["u (HTTP 404)"]))
    probs = o.weekly(tmp_path, R(), use_llm=False); assert len(probs) == 22 + 1

def test_encrypt_roundtrip(monkeypatch):
    monkeypatch.setenv("STATE_KEY", "long random phrase"); from src.core import secrets_store as ss
    assert ss.dec(ss.enc("refresh123")) == "refresh123"
