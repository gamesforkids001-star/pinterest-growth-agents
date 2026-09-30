import logging, re, sys
_SECRET = re.compile(r"(ghp_|github_pat_|AIza|gsk_|pina_)[A-Za-z0-9_\-]{8,}")
class _Redact(logging.Filter):
    def filter(self, r):
        r.msg = _SECRET.sub("[REDACTED]", str(r.msg)); return True
def get(name="agents"):
    lg = logging.getLogger(name)
    if not lg.handlers:
        h = logging.StreamHandler(sys.stdout); h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        h.addFilter(_Redact()); lg.addHandler(h); lg.setLevel(logging.INFO)
    return lg
