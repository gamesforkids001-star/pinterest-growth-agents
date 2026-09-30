"""Pinterest API v5 client.
VERIFIED in official docs/changelog: POST /pins (create), POST /pins/{pin_id}/save, GET /search/pins, GET /boards, sandbox host.
Used but NOT verified against a docs page (any failure is handled, never faked): pin analytics path/params, image_base64 media_source, link-less pins,
user_account analytics. Follow-user: no official v5 endpoint found -> never called (manual task list instead)."""
import os, re, base64, requests
PROD, SANDBOX = "https://api.pinterest.com/v5", "https://api-sandbox.pinterest.com/v5"

class PinterestError(Exception):
    def __init__(self, status, msg="", retry_after=None):
        super().__init__(f"HTTP {status}: {msg[:200]}"); self.status, self.retry_after = status, retry_after

def refresh_token(app_id, secret, refresh):
    r = requests.post(f"{PROD}/oauth/token", auth=(app_id, secret), data={"grant_type": "refresh_token", "refresh_token": refresh}, timeout=30)
    if r.status_code != 200: raise PinterestError(r.status_code, r.text)
    return r.json()

class Client:
    def __init__(self, token, sandbox=False, session=None):
        self.token, self.base, self.s = token, SANDBOX if sandbox else PROD, session or requests.Session()
        self.rate_remaining = None
    def _req(self, method, path, **kw):
        r = self.s.request(method, self.base + path, headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}, timeout=45, **kw)
        self.rate_remaining = r.headers.get("X-RateLimit-Remaining", self.rate_remaining)
        if r.status_code >= 400:
            raise PinterestError(r.status_code, r.text, r.headers.get("Retry-After"))
        return r.json() if r.text else {}
    def boards(self):
        out, bm = [], None
        while True:
            j = self._req("GET", "/boards", params={"page_size": 100, **({"bookmark": bm} if bm else {})})
            out += j.get("items", []); bm = j.get("bookmark")
            if not bm: return out
    def create_pin(self, board_id, title, description, alt_text, image_path, link=None):
        b64 = base64.b64encode(open(image_path, "rb").read()).decode()
        body = {"board_id": board_id, "title": title, "description": description, "alt_text": alt_text,
                "media_source": {"source_type": "image_base64", "content_type": "image/jpeg", "data": b64}}
        if link: body["link"] = link
        return self._req("POST", "/pins", json=body)
    def save_pin(self, pin_id, board_id):
        return self._req("POST", f"/pins/{pin_id}/save", json={"board_id": board_id})
    def search_pins(self, term, limit=10):
        return self._req("GET", "/search/pins", params={"term": term, "page_size": limit}).get("items", [])
    def pin_analytics(self, pin_id, start, end):
        j = self._req("GET", f"/pins/{pin_id}/analytics", params={"start_date": start, "end_date": end, "metric_types": "IMPRESSION,SAVE,OUTBOUND_CLICK"})
        return find_key(j, "summary_metrics") or {}
    def account_analytics(self, start, end):
        j = self._req("GET", "/user_account/analytics", params={"start_date": start, "end_date": end, "metric_types": "IMPRESSION,SAVE,OUTBOUND_CLICK"})
        return find_key(j, "daily_metrics") or []
    def user(self): return self._req("GET", "/user_account")

def find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj: return obj[key]
        for v in obj.values():
            r = find_key(v, key)
            if r is not None: return r
    elif isinstance(obj, list):
        for v in obj:
            r = find_key(v, key)
            if r is not None: return r

def get_client(db=None, sandbox=False):
    """Access token: refresh token flow if app creds exist (rotated refresh token stored encrypted), else PINTEREST_ACCESS_TOKEN."""
    from src.core import secrets_store
    app, sec = os.getenv("PINTEREST_APP_ID"), os.getenv("PINTEREST_APP_SECRET")
    rt = (secrets_store.dec(db.kv_get("enc_refresh_token")) if db else None) or os.getenv("PINTEREST_REFRESH_TOKEN")
    if app and sec and rt:
        j = refresh_token(app, sec, rt)
        if j.get("refresh_token") and j["refresh_token"] != rt and db:
            e = secrets_store.enc(j["refresh_token"])
            if e: db.kv_set("enc_refresh_token", e)
            else: db.add_alert("ACTION NEEDED: Pinterest refresh token rotated", "Pinterest ne naya refresh token diya lekin STATE_KEY secret nahi hai to save nahi ho saka. Secret 'STATE_KEY' (koi lamba random phrase) add karo.")
        return Client(j["access_token"], sandbox)
    tok = os.getenv("PINTEREST_ACCESS_TOKEN")
    if not tok: raise PinterestError(401, "no Pinterest token configured")
    return Client(tok, sandbox)

def _norm(s): return re.sub(r"[^a-z0-9]", "", s.lower())

def map_boards(boards, tools):
    by = {_norm(b["name"]): b for b in boards}
    mapping, miss = {}, []
    for t in tools:
        b = by.get(_norm(t["name"])) or by.get(_norm(t["slug"]))
        if b: mapping[t["slug"]] = b["id"]
        else: miss.append(t["name"])
    used = set(mapping.values()); rest = [b for b in boards if b["id"] not in used]
    return mapping, miss, [b["name"] for b in rest], [b for b in rest if "main" in b["name"].lower()]
