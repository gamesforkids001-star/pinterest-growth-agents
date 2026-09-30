"""Encrypts rotated Pinterest tokens before they go into the (public) state branch. Key = your STATE_KEY secret."""
import os, base64, hashlib
def _f():
    k = os.getenv("STATE_KEY")
    if not k: return None
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(k.encode()).digest()))
def enc(text):
    f = _f(); return f.encrypt(text.encode()).decode() if f else None
def dec(token):
    try: f = _f(); return f.decrypt(token.encode()).decode() if f and token else None
    except Exception: return None
