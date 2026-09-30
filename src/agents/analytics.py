"""Analytics/Growth Agent: pin + account metrics from Pinterest, drop detection, feeds Strategist weights. Errors never fake numbers."""
import datetime as dt
from src.integrations.pinterest import PinterestError

def collect(db, client, cap=50):
    """Refresh per-pin metrics for recent published pins (oldest-refreshed first). Returns (n_ok, error or None)."""
    since = (dt.date.today() - dt.timedelta(days=45)).isoformat()
    pins = [p for p in db.recent_pins(400) if p["status"] == "published" and p["pinterest_id"] and p["ts"][:10] >= since][:cap]
    ok, err = 0, None
    for p in pins:
        try:
            m = client.pin_analytics(p["pinterest_id"], since, dt.date.today().isoformat())
            db.set_pin_metrics(p["id"], int(m.get("IMPRESSION", 0)), int(m.get("SAVE", 0)), int(m.get("OUTBOUND_CLICK", 0))); ok += 1
        except PinterestError as e:
            err = str(e)
            if e.status in (401, 403, 429): break
    return ok, err

def collect_account(db, client):
    end, start = dt.date.today() - dt.timedelta(days=1), dt.date.today() - dt.timedelta(days=21)
    try: rows = client.account_analytics(start.isoformat(), end.isoformat())
    except PinterestError as e: return str(e)
    out = []
    for r in rows:
        m = r.get("metrics", {}) or {}
        if r.get("date"): out.append((r["date"], int(m.get("IMPRESSION", 0) or 0), int(m.get("SAVE", 0) or 0), int(m.get("OUTBOUND_CLICK", 0) or 0)))
    if out: db.set_acct_metrics(out)
    return None

def detect_drop(db, pol):
    """Compare last 3 days avg with the prior 14 days avg. Returns (drop_pct or None)."""
    rows = db.acct_metrics(21)
    if len(rows) < 10: return None
    rec, base = rows[-3:], rows[:-3][-14:]
    b = sum(r["impressions"] for r in base) / len(base); r = sum(x["impressions"] for x in rec) / len(rec)
    if b < pol["analytics"]["min_baseline_impressions_per_day"]: return None
    drop = (1 - r / b) * 100
    return round(drop) if drop >= pol["analytics"]["drop_alert_pct"] else None

def summary(db):
    def grp(col):
        q = f"SELECT {col} k, COUNT(*) n, SUM(m.impressions) i, SUM(m.saves) s, SUM(m.clicks) c FROM pins p LEFT JOIN pin_metrics m ON m.pin_id=p.id WHERE p.status='published' GROUP BY {col} ORDER BY COALESCE(SUM(m.clicks),0) DESC, COALESCE(SUM(m.saves),0) DESC"
        return [dict(r) for r in db.c.execute(q)]
    return {"tools": grp("p.tool_slug"), "classes": grp("p.cls")}
