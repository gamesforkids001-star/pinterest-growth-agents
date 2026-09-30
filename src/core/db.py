import sqlite3, json, datetime as dt
from zoneinfo import ZoneInfo
SCHEMA = """
CREATE TABLE IF NOT EXISTS actions(id INTEGER PRIMARY KEY, ts TEXT, kind TEXT, tool_slug TEXT, ok INTEGER, reason TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS pins(id INTEGER PRIMARY KEY, ts TEXT, cls TEXT, tool_slug TEXT, title TEXT, description TEXT, status TEXT, pinterest_id TEXT, meta TEXT);
CREATE TABLE IF NOT EXISTS metrics(day TEXT, source TEXT, tool_slug TEXT, visits INTEGER, PRIMARY KEY(day, source, tool_slug));
CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY, ts TEXT, title TEXT, body TEXT, delivered INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS saves(id INTEGER PRIMARY KEY, ts TEXT, pin_id INTEGER, tool_slug TEXT, board_id TEXT, method TEXT, ok INTEGER);
CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, day TEXT, text TEXT, done INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS pin_metrics(pin_id INTEGER PRIMARY KEY, day TEXT, impressions INTEGER, saves INTEGER, clicks INTEGER);
CREATE TABLE IF NOT EXISTS acct_metrics(day TEXT PRIMARY KEY, impressions INTEGER, saves INTEGER, clicks INTEGER);
"""
class DB:
    def __init__(self, path, tz="Asia/Karachi"):
        self.tz = tz; self.c = sqlite3.connect(path, timeout=30); self.c.row_factory = sqlite3.Row
        self.c.executescript(SCHEMA)
        try: self.c.execute("ALTER TABLE pins ADD COLUMN meta TEXT")
        except sqlite3.OperationalError: pass
        self.c.commit()
    def now(self): return dt.datetime.now(ZoneInfo(self.tz)).isoformat(timespec="seconds")
    def today(self): return dt.datetime.now(ZoneInfo(self.tz)).strftime("%Y-%m-%d")
    # actions
    def log_action(self, kind, ok, reason="", tool_slug="", detail=""):
        self.c.execute("INSERT INTO actions(ts,kind,tool_slug,ok,reason,detail) VALUES(?,?,?,?,?,?)", (self.now(), kind, tool_slug, int(ok), reason, detail)); self.c.commit()
    def count_actions_today(self, kind=None):
        q, a = "SELECT COUNT(*) FROM actions WHERE ts LIKE ? AND ok=1", [self.today() + "%"]
        if kind: q += " AND kind=?"; a.append(kind)
        return self.c.execute(q, a).fetchone()[0]
    def last_action_ts(self, kind):
        r = self.c.execute("SELECT ts FROM actions WHERE kind=? AND ok=1 ORDER BY id DESC LIMIT 1", (kind,)).fetchone()
        return dt.datetime.fromisoformat(r[0]) if r else None
    # pins
    def add_pin(self, cls, slug, title, desc, status="planned", pid="", meta=None):
        cur = self.c.execute("INSERT INTO pins(ts,cls,tool_slug,title,description,status,pinterest_id,meta) VALUES(?,?,?,?,?,?,?,?)",
                             (self.now(), cls, slug, title, desc, status, pid, json.dumps(meta or {}))); self.c.commit(); return cur.lastrowid
    def update_pin(self, pid, **f):
        if "meta" in f: f["meta"] = json.dumps(f["meta"])
        self.c.execute(f"UPDATE pins SET {','.join(k+'=?' for k in f)} WHERE id=?", (*f.values(), pid)); self.c.commit()
    def recent_pins(self, n=200):
        out = []
        for r in self.c.execute("SELECT * FROM pins ORDER BY id DESC LIMIT ?", (n,)):
            d = dict(r); d["meta"] = json.loads(d["meta"] or "{}"); out.append(d)
        return out
    def pending_saves(self, limit=20):
        rows = self.c.execute("""SELECT * FROM pins WHERE status='published' AND pinterest_id!='' AND id NOT IN (SELECT pin_id FROM saves WHERE ok=1)
                                 ORDER BY id LIMIT ?""", (limit,)).fetchall()
        return [dict(r) for r in rows]
    def add_save(self, pin_id, slug, board, method, ok):
        self.c.execute("INSERT INTO saves(ts,pin_id,tool_slug,board_id,method,ok) VALUES(?,?,?,?,?,?)", (self.now(), pin_id, slug, board, method, int(ok))); self.c.commit()
    # alerts / tasks
    def add_alert(self, title, body):
        self.c.execute("INSERT INTO alerts(ts,title,body) VALUES(?,?,?)", (self.now(), title, body)); self.c.commit()
    def undelivered_alerts(self):
        return [dict(r) for r in self.c.execute("SELECT * FROM alerts WHERE delivered=0 ORDER BY id")]
    def mark_delivered(self, i):
        self.c.execute("UPDATE alerts SET delivered=1 WHERE id=?", (i,)); self.c.commit()
    def add_task(self, text, day=None):
        self.c.execute("INSERT INTO tasks(day,text) VALUES(?,?)", (day or self.today(), text)); self.c.commit()
    def open_tasks(self):
        return [dict(r) for r in self.c.execute("SELECT * FROM tasks WHERE done=0 ORDER BY id")]
    def close_tasks_before(self, day):
        self.c.execute("UPDATE tasks SET done=1 WHERE day<?", (day,)); self.c.commit()
    # kv
    def kv_get(self, k, default=None):
        r = self.c.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone(); return json.loads(r[0]) if r else default
    def kv_set(self, k, v):
        self.c.execute("INSERT OR REPLACE INTO kv VALUES(?,?)", (k, json.dumps(v))); self.c.commit()
    # metrics
    def save_metrics(self, rows):
        self.c.executemany("INSERT OR REPLACE INTO metrics VALUES(?,?,?,?)", rows); self.c.commit()
    def metrics(self, days=30):
        since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        return [dict(r) for r in self.c.execute("SELECT * FROM metrics WHERE day>=? ORDER BY day", (since,))]
    def set_pin_metrics(self, pin_id, imp, sv, clk):
        self.c.execute("INSERT OR REPLACE INTO pin_metrics VALUES(?,?,?,?,?)", (pin_id, self.today(), imp, sv, clk)); self.c.commit()
    def set_acct_metrics(self, rows):
        self.c.executemany("INSERT OR REPLACE INTO acct_metrics VALUES(?,?,?,?)", rows); self.c.commit()
    def acct_metrics(self, days=30):
        since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        return [dict(r) for r in self.c.execute("SELECT * FROM acct_metrics WHERE day>=? ORDER BY day", (since,))]
