import os, json, time, requests
from datetime import datetime, timedelta

API_KEY = os.environ.get("SAM_API_KEY")
if not API_KEY:
    raise RuntimeError("SAM_API_KEY not set in environment")

BASE_URL = "https://api.sam.gov/opportunities/v2/search"

today = datetime.utcnow()
posted_from = (today - timedelta(days=90)).strftime("%m/%d/%Y")
posted_to   = today.strftime("%m/%d/%Y")

headers = {"X-Api-Key": API_KEY, "Accept": "application/json"}

limit = 1000   # safer page size [2](https://informationhandyman.com/2026/digital/software/search-box-a-power-bi-custom-visual)
offset = 0
all_rows = []
last_meta = {}

while True:
    params = {
        "limit": limit,
        "offset": offset,            # pagination parameter [2](https://informationhandyman.com/2026/digital/software/search-box-a-power-bi-custom-visual)
        "postedFrom": posted_from,
        "postedTo": posted_to
    }

    resp = requests.get(BASE_URL, headers=headers, params=params, timeout=60)
    print(f"offset={offset} status={resp.status_code}")

    if resp.status_code >= 400:
        print("Error body (first 1000 chars):")
        print(resp.text[:1000])
        resp.raise_for_status()

    payload = resp.json()
    page_rows = payload.get("opportunitiesData", []) or []
    last_meta = {k: v for k, v in payload.items() if k != "opportunitiesData"}

    if not page_rows:
        break

    all_rows.extend(page_rows)
    offset += limit
    time.sleep(0.25)

out = {
    "generated_utc": today.isoformat(),
    "postedFrom": posted_from,
    "postedTo": posted_to,
    "opportunitiesData": all_rows,
    "meta": last_meta
}

with open("sam_data.json", "w") as f:
    json.dump(out, f, indent=2)

print(f"✅ Saved {len(all_rows)} opportunities")
