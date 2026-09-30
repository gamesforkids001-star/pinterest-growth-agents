"""READ-ONLY public page reader. GET only, robots.txt respected, polite delay. No write path exists in this module."""
import time, re, urllib.robotparser
from html.parser import HTMLParser
from urllib.parse import urlparse, urlunparse
import requests

UA = "EasyFileToolsPinBot/1.0 (read-only; owner site)"

def canonical(url):
    u = urlparse(url); return urlunparse((u.scheme or "https", u.netloc, u.path, "", "", ""))

class _P(HTMLParser):
    def __init__(s): super().__init__(); s.title = ""; s.meta = {}; s.h = []; s._t = None; s.text = []; s.skip = 0; s.canon = ""
    def handle_starttag(s, tag, a):
        a = dict(a)
        if tag in ("script", "style", "noscript"): s.skip += 1
        if tag == "title": s._t = "title"
        if tag in ("h1", "h2", "h3"): s._t = "h"; s.h.append("")
        if tag == "meta" and a.get("name") in ("description",) or (tag == "meta" and a.get("property") == "og:description"): s.meta["description"] = a.get("content", "")
        if tag == "link" and a.get("rel") == "canonical": s.canon = a.get("href", "")
    def handle_endtag(s, tag):
        if tag in ("script", "style", "noscript"): s.skip = max(0, s.skip - 1)
        if tag in ("title", "h1", "h2", "h3"): s._t = None
    def handle_data(s, d):
        if s.skip: return
        d = d.strip()
        if not d: return
        if s._t == "title": s.title += d
        elif s._t == "h": s.h[-1] += d + " "
        s.text.append(d)

class SiteReader:
    def __init__(self, base, delay=2.0, session=None):
        self.base, self.delay, self.s = base.rstrip("/"), delay, session or requests.Session()
        self.rp = urllib.robotparser.RobotFileParser()
        try:
            r = self.s.get(self.base + "/robots.txt", headers={"User-Agent": UA}, timeout=20); self.rp.parse(r.text.splitlines())
        except Exception: self.rp.parse([])
    def fetch(self, path):
        url = canonical(path if path.startswith("http") else self.base + path)
        if not self.rp.can_fetch(UA, url): return {"url": url, "ok": False, "error": "blocked by robots.txt"}
        time.sleep(self.delay)
        try: r = self.s.get(url, headers={"User-Agent": UA}, timeout=30)
        except Exception as e: return {"url": url, "ok": False, "error": type(e).__name__}
        if r.status_code != 200: return {"url": url, "ok": False, "error": f"HTTP {r.status_code}"}
        p = _P(); p.feed(r.text)
        text = re.sub(r"\s+", " ", " ".join(p.text))
        return {"url": url, "ok": True, "title": p.title.strip(), "description": p.meta.get("description", ""), "headings": [h.strip() for h in p.h if h.strip()][:15],
                "text": text[:3000], "js_only": len(text) < 200}
