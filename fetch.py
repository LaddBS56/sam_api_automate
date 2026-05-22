import os, json, time, requests
from datetime import datetime, timedelta, timezone

API_KEY = os.environ.get("SAM_API_KEY")
if not API_KEY:
    raise RuntimeError("SAM_API_KEY not set in environment")

SEARCH_URL = "https://api.sam.gov/opportunities/v2/search"

headers = {"X-Api-Key": API_KEY, "Accept": "application/json"}

# ---------- Configuration ----------
today = datetime.now(timezone.utc)
window_days = 30          # Pull last 30 days of opportunities
chunk_days = 30           # Single chunk = single date range
limit = 1000              # Max page size allowed by SAM.gov

all_rows = []
seen_ids = set()

# ---------- Fetch opportunities ----------
for chunk_start in range(window_days, 0, -chunk_days):
    chunk_end = max(chunk_start - chunk_days, 0)
    posted_from = (today - timedelta(days=chunk_start)).strftime("%m/%d/%Y")
    posted_to   = (today - timedelta(days=chunk_end)).strftime("%m/%d/%Y")
    print(f"\nFetching {posted_from} → {posted_to}")

    offset = 0
    while True:
        params = {
            "limit": limit,
            "offset": offset,
            "postedFrom": posted_from,
            "postedTo": posted_to,
        }

        try:
            resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=60)
        except requests.exceptions.RequestException as e:
            print(f"  Network error at offset={offset}: {e}")
            raise

        print(f"  offset={offset} status={resp.status_code}")

        # Graceful 429 handling — log and exit cleanly
        if resp.status_code == 429:
            try:
                body = resp.json()
                next_access = body.get("nextAccessTime", "unknown")
                print(f"\n⚠️  Rate limit hit. Next access: {next_access}")
                print("Exiting cleanly — existing sam_data.json will remain unchanged.")
            except Exception:
                print(f"\n⚠️  Rate limit hit (could not parse response).")
            exit(0)  # Exit 0 so the workflow shows success, not failure

        if resp.status_code >= 400:
            print(resp.text[:1000])
            resp.raise_for_status()

        payload = resp.json()
        page_rows = payload.get("opportunitiesData", []) or []
        if not page_rows:
            break

        # Dedupe across pages (and against any prior chunks)
        new_rows = [r for r in page_rows if r.get("noticeId") not in seen_ids]
        for r in new_rows:
            seen_ids.add(r.get("noticeId"))
        all_rows.extend(new_rows)

        if len(page_rows) < limit:
            break
        offset += limit
        time.sleep(0.25)

print(f"\nTotal unique opportunities: {len(all_rows)}")

# ---------- Save ----------
out = {
    "generated_utc": today.isoformat(),
    "windowDays": window_days,
    "totalOpportunities": len(all_rows),
    "opportunitiesData": all_rows,
