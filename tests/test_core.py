import json, datetime as dt
from pathlib import Path
from src.core import config, compliance as C, risk, db as dbm
from src.integrations.notify import chain
from src.integrations import pinterest
from src import dashboard_build
from src.agents import site_knowledge

ROOT = Path(__file__).resolve().parents[1]
S, POL, NOTES = config.load(ROOT)

def pin(**kw):
    p = dict(cls="L", title="Merge PDF files in 3 steps", description="Combine several PDF files into one document right in your browser.",
             alt_text="Steps to merge PDF files", image="x.png", link="https://easyfileonlinetools.blogspot.com/p/merge-pdf.html?utm_source=pinterest",
             tool_slug="merge-pdf", keywords=["merge pdf", "combine pdf"])
    p.update(kw); return p

def test_default_settings_valid(): assert NOTES == []
def test_ceiling_clamps():
    s, n = config.validate({**S, "pinterest": {**S["pinterest"], "daily_pins": 999, "min_gap_minutes": 5}}, POL)
    assert s["pinterest"]["daily_pins"] == POL["ceilings"]["daily_pins"] and s["pinterest"]["min_gap_minutes"] == 60 and len(n) == 2
def test_invalid_time_reported():
    s, n = config.validate({**S, "pinterest": {**S["pinterest"], "post_times": ["25:00", "10:00"]}}, POL)
    assert s["pinterest"]["post_times"] == ["10:00"] and n
def test_read_only_forced():
    s, n = config.validate({**S, "site": {"read_only": False, "base_url": "x"}}, POL); assert s["site"]["read_only"] is True and n

def test_good_pin(): assert C.check_pin(pin(), POL) == []
def test_wrong_domain(): assert any("own domain" in e for e in C.check_pin(pin(link="https://evil.com/x"), POL))
def test_mobile_link(): assert any("canonical" in e for e in C.check_pin(pin(link="https://easyfileonlinetools.blogspot.com/p/a.html?m=1"), POL))
def test_class_i_no_link():
    assert any("must not have a link" in e for e in C.check_pin(pin(cls="I"), POL))
    assert C.check_pin(pin(cls="I", link=None), POL) == []
def test_class_i_no_url_text():
    assert any("URL" in e for e in C.check_pin(pin(cls="I", link=None, description="visit example.com now"), POL))
def test_banned_word(): assert any("banned" in e for e in C.check_pin(pin(title="Guaranteed merge"), POL))
def test_duplicate(): assert any("near-duplicate" in e for e in C.check_pin(pin(), POL, [pin()]))
def test_stuffing():
    p = pin(description="merge pdf merge pdf merge pdf merge pdf merge pdf tool", keywords=["merge pdf", "combine pdf"])
    assert any("stuffing" in e for e in C.check_pin(p, POL))
def test_forbidden_actions():
    assert C.check_action("unfollow", S, POL, 0, 0, 12) == ["action 'unfollow' is forbidden"]
def test_active_hours_and_caps():
    assert "outside active_hours" in C.check_action("publish", S, POL, 0, 0, 3)
    assert any("daily cap" in e for e in C.check_action("publish", S, POL, 0, S["pinterest"]["daily_pins"], 12))
    assert "curator is off" in C.check_action("follow", S, POL, 0, 0, 12)

def test_risk_low_and_jump():
    assert risk.score(S, POL, None, 40)[0] == "low"
    s, _ = config.validate({**S, "pinterest": {**S["pinterest"], "daily_pins": 9}}, POL)
    lvl, f, mult = risk.score(s, POL, {"daily_pins": 3, "daily_saves_own": 0, "daily_follows": 0, "daily_saves_others": 0}, 2)
    assert lvl == "high" and mult == 0.5 and f

def test_chain_fallback_and_never_lose(tmp_path):
    def bad(t, b): raise RuntimeError("x")
    ok_calls = []
    via, errs = chain.send("t", "b", ["a", "b"], {"a": bad, "b": lambda t, b: ok_calls.append(1)})
    assert via == "b" and len(errs) == 1
    d = dbm.DB(str(tmp_path / "s.db")); d.add_alert("x", "y")
    assert chain.flush(d, ["a"], {"a": bad}) == 0 and len(d.undelivered_alerts()) == 1
    assert chain.flush(d, ["a", "b"], {"a": bad, "b": lambda t, b: None}) == 1 and not d.undelivered_alerts()

def test_board_mapping():
    tools = [{"name": "Merge PDF", "slug": "merge-pdf"}, {"name": "Age Calculator", "slug": "age-calculator"}]
    boards = [{"id": "1", "name": "merge pdf"}, {"id": "2", "name": "Main Board"}, {"id": "3", "name": "Random"}]
    m, miss, extra, main = pinterest.map_boards(boards, tools)
    assert m == {"merge-pdf": "1"} and miss == ["Age Calculator"] and main[0]["id"] == "2"

def test_dashboard_states():
    h = dashboard_build.build([], True, False); assert "24-48" in h
    assert "GA4 setup" in dashboard_build.build([], False, False)
    rows = [{"day": dt.date.today().isoformat(), "source": "pinterest", "tool_slug": "merge-pdf", "visits": 5}]
    h = dashboard_build.build(rows, True, True); assert "merge-pdf" in h and ">5<" in h

class FakeReader:
    def fetch(self, path):
        if "merge" in path: return {"url": "https://x/p/merge-pdf.html", "ok": True, "title": "Merge PDF", "description": "Combine PDF files online.", "headings": ["Merge PDF"], "text": "t" * 300, "js_only": False}
        return {"url": "https://x" + path, "ok": False, "error": "HTTP 404"}
def test_site_knowledge():
    tools, probs = site_knowledge.build(ROOT, "https://x", FakeReader(), use_llm=False)
    assert len(tools) == 22 and sum(t["verified"] for t in tools) == 1 and len(probs) == 21
    assert next(t for t in tools if t["slug"] == "merge-pdf")["what_it_does"] == "Combine PDF files online."

def test_daily_end_to_end(tmp_path, monkeypatch):
    import shutil; shutil.copytree(ROOT / "config", tmp_path / "config"); shutil.copytree(ROOT / "data", tmp_path / "data")
    monkeypatch.setenv("STATE_DB", str(tmp_path / "s.db")); monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    from src.core import orchestrator as o
    assert o.daily(tmp_path) == "ok" and (tmp_path / "dashboard/analytics.html").exists()
    assert len(o.open_db(tmp_path).undelivered_alerts()) == 1   # no channel configured -> stays queued, not lost
    (tmp_path / "PAUSE").write_text("")
    assert o.daily(tmp_path) == "paused"
