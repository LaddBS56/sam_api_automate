import os, json, time, requests
from datetime import datetime, timedelta, timezone

API_KEY = os.environ.get("SAM_API_KEY")
if not API_KEY:
    raise RuntimeError("SAM_API_KEY not set in environment")

SEARCH_URL = "https://api.sam.gov/opportunities/v2/search"
DESC_URL_BASE = "https://api.sam.gov/prod/opportunities/v1/noticedesc"

headers = {"X-Api-Key": API_KEY, "Accept": "application/json"}

# ---------- Load previous run's descriptions (cache) ----------
prev_descs = {}
if os.path.exists("sam_data.json"):
    try:
        with open("sam_data.json") as f:
            prev = json.load(f)
            prev_descs = {
                r.get("noticeId"): r.get("fullDescription", "")
                for r in prev.get("opportunitiesData", [])
                if r.get("noticeId") and r.get("fullDescription")
            }
        print(f"Loaded {len(prev_descs)} cached descriptions")
    except Exception as e:
        print(f"Could not load cache: {e}")

# ---------- Fetch opportunities in 30-day chunks ----------
today = datetime.now(timezone.utc)
window_days = 90
chunk_days = 30
limit = 1000

all_rows = []
seen_ids = set()

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
        resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=60)
        print(f"  offset={offset} status={resp.status_code}")
        if resp.status_code >= 400:
            print(resp.text[:1000])
            resp.raise_for_status()

        payload = resp.json()
        page_rows = payload.get("opportunitiesData", []) or []
        if not page_rows:
            break

        # Dedupe across chunks (date boundaries can overlap)
        new_rows = [r for r in page_rows if r.get("noticeId") not in seen_ids]
        for r in new_rows:
            seen_ids.add(r.get("noticeId"))
        all_rows.extend(new_rows)

        if len(page_rows) < limit:
            break
        offset += limit
        time.sleep(0.25)

print(f"\nTotal unique opportunities: {len(all_rows)}")

# ---------- Hydrate descriptions (cache-aware) ----------
DAILY_DESC_BUDGET = 800   # leave headroom under 1000/day non-fed limit
new_fetches = 0
cache_hits = 0

for i, row in enumerate(all_rows):
    notice_id = row.get("noticeId")
    desc_url = row.get("description")

    # Cache hit
    if notice_id in prev_descs:
        row["fullDescription"] = prev_descs[notice_id]
        cache_hits += 1
        continue

    # No URL to call
    if not desc_url or not isinstance(desc_url, str) or not desc_url.startswith("http"):
        row["fullDescription"] = ""
        continue

    # Respect daily budget
    if new_fetches >= DAILY_DESC_BUDGET:
        row["fullDescription"] = ""
        continue

    try:
        r = requests.get(
            desc_url,
            headers=headers,
            params={"api_key": API_KEY},
            timeout=30,
        )
        if r.status_code == 200:
            row["fullDescription"] = r.json().get("description", "")
        else:
            row["fullDescription"] = ""
            print(f"  row {i} ({notice_id}): desc returned {r.status_code}")
    except Exception as e:
        row["fullDescription"] = ""
        print(f"  row {i} ({notice_id}): {e}")

    new_fetches += 1
    time.sleep(0.1)
    if new_fetches % 100 == 0:
        print(f"  hydrated {new_fetches} new descriptions")

print(f"\nCache hits: {cache_hits}  |  New fetches: {new_fetches}")

# ---------- Save ----------
out = {
    "generated_utc": today.isoformat(),
    "windowDays": window_days,
    "totalOpportunities": len(all_rows),
    "descriptionsHydrated": cache_hits + new_fetches,
    "opportunitiesData": all_rows,
}
with open("sam_data.json", "w") as f:
    json.dump(out, f, indent=2)

print(f"\n✅ Saved {len(all_rows)} opportunities to sam_data.json")
