"""Gemini (primary) -> Groq (fallback), retries + backoff. Free tiers only. Model names are configurable via env."""
import os, time, requests
GEMINI_MODELS = os.getenv("GEMINI_MODELS", "gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite").split(",")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

class LLMUnavailable(Exception): pass

def _gemini(prompt, model, key):
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                      headers={"x-goog-api-key": key}, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=60)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

def _groq(prompt, key):
    r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {key}"},
                      json={"model": GROQ_MODEL, "messages": [{"role": "user", "content": prompt}]}, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def generate(prompt, retries=3, sleep=time.sleep):
    gk, qk = os.getenv("GEMINI_API_KEY"), os.getenv("GROQ_API_KEY")
    attempts = [(lambda m=m: _gemini(prompt, m, gk)) for m in GEMINI_MODELS] if gk else []
    if qk: attempts.append(lambda: _groq(prompt, qk))
    if not attempts: raise LLMUnavailable("No LLM key set")
    last = None
    for fn in attempts:
        for i in range(retries):
            try: return fn()
            except Exception as e:
                last = e
                if getattr(getattr(e, "response", None), "status_code", None) in (400, 401, 403, 404): break   # model gone / bad key: try next model, no retries
                sleep(2 ** i)
    raise LLMUnavailable(f"All LLM attempts failed: {type(last).__name__}")
