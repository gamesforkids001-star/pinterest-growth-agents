"""Notification fallback chain. Never lose an alert: failures leave it undelivered in DB for the next run."""
import os, smtplib, ssl, requests
from email.message import EmailMessage

def github_issues(title, body):
    tok, repo = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY")
    if not (tok and repo): raise RuntimeError("GITHUB_TOKEN/GITHUB_REPOSITORY missing")
    r = requests.post(f"https://api.github.com/repos/{repo}/issues", headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"},
                      json={"title": title[:200], "body": body[:60000], "labels": ["agent-report"]}, timeout=30)
    r.raise_for_status()

def email(title, body):
    u, pw, to = os.getenv("SMTP_USER"), os.getenv("SMTP_APP_PASSWORD"), os.getenv("NOTIFY_EMAIL_TO") or os.getenv("SMTP_USER")
    if not (u and pw): raise RuntimeError("SMTP not configured")
    m = EmailMessage(); m["Subject"], m["From"], m["To"] = title, u, to; m.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as s:
        s.login(u, pw); s.send_message(m)

def ntfy(title, body):
    t = os.getenv("NTFY_TOPIC")
    if not t: raise RuntimeError("NTFY_TOPIC missing")
    requests.post(f"https://ntfy.sh/{t}", data=body.encode("utf-8"), headers={"Title": title.encode("ascii", "ignore").decode()}, timeout=20).raise_for_status()

def telegram(title, body):
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (tok and chat): raise RuntimeError("Telegram not configured")
    requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", json={"chat_id": chat, "text": f"{title}\n\n{body}"[:4000]}, timeout=20).raise_for_status()

CHANNELS = {"github_issues": github_issues, "email": email, "ntfy": ntfy, "telegram": telegram}

def send(title, body, order, channels=None):
    """Try channels in order. Returns (delivered_via or None, errors)."""
    ch, errs = channels or CHANNELS, []
    for name in order:
        fn = ch.get(name)
        if not fn: errs.append(f"{name}: unknown"); continue
        try: fn(title, body); return name, errs
        except Exception as e: errs.append(f"{name}: {type(e).__name__}")
    return None, errs

def flush(db, order, channels=None):
    """Deliver stored alerts; if all channels fail they stay undelivered (retry next run)."""
    n = 0
    for a in db.undelivered_alerts():
        via, _ = send(a["title"], a["body"], order, channels)
        if via: db.mark_delivered(a["id"]); n += 1
    return n
