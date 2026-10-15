"""READ-ONLY GA4 Data API (scope analytics.readonly). Returns None if not configured / no data, never raises."""
import os, json

# Platforms we track. Order here does not matter; matching is by name inside GA4 "sessionSource".
PLATFORMS = ("pinterest", "facebook", "instagram", "youtube")
ALIASES = {"fb": "facebook", "ig": "instagram", "yt": "youtube"}  # short utm_source names

def classify(src, med):
    """Map a GA4 (sessionSource, sessionMedium) pair to one of our platform names, or None."""
    s = (src or "").lower().strip()
    if s == "google" and (med or "").lower() == "organic":
        return "google"
    if s in ALIASES:
        return ALIASES[s]
    for p in PLATFORMS:  # also catches l.facebook.com, m.facebook.com, l.instagram.com, m.youtube.com ...
        if p in s:
            return p
    return None

def fetch(days=30):
    pid, sa = os.getenv("GA4_PROPERTY_ID"), os.getenv("GA4_SERVICE_ACCOUNT_JSON")
    if not (pid and sa): return None
    try:
        from google.oauth2 import service_account
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import RunReportRequest, Dimension, Metric, DateRange
        creds = service_account.Credentials.from_service_account_info(json.loads(sa), scopes=["https://www.googleapis.com/auth/analytics.readonly"])
        rep = BetaAnalyticsDataClient(credentials=creds).run_report(RunReportRequest(
            property=f"properties/{pid}", date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            dimensions=[Dimension(name="date"), Dimension(name="sessionSource"), Dimension(name="sessionMedium"), Dimension(name="landingPage")],
            metrics=[Metric(name="sessions")], limit=100000))
        rows = []
        for r in rep.rows:
            d, src, med, page = [x.value for x in r.dimension_values]
            s = classify(src, med)
            if s: rows.append((f"{d[:4]}-{d[4:6]}-{d[6:]}", s, page.split("/p/")[-1].replace(".html", "") if "/p/" in page else "(other)", int(r.metric_values[0].value)))
        return rows
    except Exception:
        return None
