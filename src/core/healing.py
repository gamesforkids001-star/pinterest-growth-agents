"""Self-Healing: silent retries; same problem 3x or serious -> PAUSE + alert with exact steps."""
import time
from pathlib import Path

def retry(fn, tries=3, base=2, sleep=time.sleep, retry_if=lambda e: True):
    last = None
    for i in range(tries):
        try: return fn()
        except Exception as e:
            last = e
            if not retry_if(e): raise
            sleep(base ** i)
    raise last

def pause(root, db, title, cause, tried, steps):
    """Write PAUSE (committed by workflow) + queue alert. Resume: Actions > Agents > Run workflow > resume."""
    Path(root, "PAUSE").write_text(f"{db.now()} {title}\n")
    db.add_alert(f"ACTION NEEDED: {title}", alert_body(cause, tried, steps + ["Theek hone ke baad: Actions > Agents > Run workflow > command: resume"]))

def alert_body(cause, tried, steps):
    return f"Cause: {cause}\nAlready tried: {tried}\n\nTumhare steps:\n" + "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))

def record_problem(db, key, limit=3):
    """Counts consecutive occurrences per day-window. Returns True when limit reached."""
    n = (db.kv_get(f"problem:{key}", 0) or 0) + 1; db.kv_set(f"problem:{key}", n); return n >= limit

def clear_problem(db, key): db.kv_set(f"problem:{key}", 0)
