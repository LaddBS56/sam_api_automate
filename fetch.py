import os
import json
import time
import requests
from datetime import datetime, timedelta

# ---------- API KEY ----------
API_KEY = os.environ.get("SAM_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing SAM_API_KEY environment variable")

BASE_URL = "https://api.sam.gov/opportunities/v2/search"

# ---------- DATE RANGE ----------
today = datetime.utcnow()
start_date = today - timedelta(days=90)

posted_from = start_date.strftime("%m/%d/%Y")
posted_to = today.strftime("%m/%d/%Y")

headers = {
    "X-Api-Key": API_KEY,
    "Accept": "application/json"
}

# ---------- PAGINATION ----------
limit = 1000          # page size (use a conservative value; API is paginated) [1](https://open.gsa.gov/api/get-opportunities-public-api/)[2](https://open.gsa.gov/api/get-opportunities-public-api/v1/get-opportunities-v2.yml)
offset = 0
all_rows = []
last_payload_meta = {}

while True:
    params = {
        "limit": limit,
        "offset": offset,          # offset-based pagination [2](https://open.gsa.gov/api/get-opportunities-public-api/v1/get-opportunities-v2.yml)
        "postedFrom": posted_from,
        "postedTo": posted_to
    }

    
    resp = requests.get(BASE_URL, headers=headers, params=params, timeout=60)
    print(f"Request offset={offset} status={resp.status_code} url={resp.url}")

    if resp.status_code >= 400:
        # Print a snippet of the body to see the real API error message
        print("Error body (first 1000 chars):")
        print(resp.text[:1000])
        resp.raise_for_status()

    payload = resp.json()

    # opportunitiesData is the main array in the response (what Power BI expands)
    page_rows = payload.get("opportunitiesData", []) or []

    # Keep any metadata (like links, totalRecords, etc.) from the last response
    last_payload_meta = {k: v for k, v in payload.items() if k != "opportunitiesData"}

    # Stop when the API returns no more rows
    if not page_rows:
        break

    all_rows.extend(page_rows)
    offset += limit

    # Be nice to the API (avoid hammering)
    time.sleep(0.25)

# ---------- SAVE FILE ----------
out = {
    "generated_utc": today.isoformat(),
    "postedFrom": posted_from,
    "postedTo": posted_to,
    "opportunitiesData": all_rows,
    "meta": last_payload_meta
}

with open("sam_data.json", "w") as f:
    json.dump(out, f, indent=2)

print(f"✅ Saved {len(all_rows)} opportunities to sam_data.json")
``
